"""Filesystem loading, orchestration, and writing for export artefacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.export.docling import (
    DoclingExportSettings,
    build_docling_document,
    try_validate_with_docling_core,
    validate_docling_like_document,
)
from pdf2md.export.markdown import MarkdownExportSettings, build_markdown_preview
from pdf2md.export.rag import RagExportSettings, build_rag_chunks
from pdf2md.export.reporting import artefact, build_export_report, build_manifest, sha256_file
from pdf2md.models.export import ExportArtefactType, ExportManifestDocument, RagChunkDocument
from pdf2md.models.ir import ConsensusIR
from pdf2md.models.linked import LinkedStructure


@dataclass(frozen=True)
class ExportLoadResult:
    """Inputs loaded from disk for an export run.

    Attributes:
        linked: Parsed LinkedStructure document.
        consensus: Parsed ConsensusIR, if provided and valid.
        warnings: Warnings raised while loading inputs.
    """

    linked: LinkedStructure
    consensus: ConsensusIR | None
    warnings: list[str]


@dataclass(frozen=True)
class ExportRunResult:
    """Aggregated outputs of a single export run.

    Attributes:
        docling: Projected Docling document dictionary.
        rag_chunks: RAG chunk document with per-chunk metadata.
        markdown: Markdown preview text.
        manifest: Export manifest describing produced artefacts.
        report: Export audit report dictionary.
        warnings: Combined warnings across all sub-builders.
        write_rag: Whether RAG output should be written to disk.
        write_markdown: Whether markdown output should be written to disk.
    """

    docling: dict[str, Any]
    rag_chunks: RagChunkDocument
    markdown: str
    manifest: ExportManifestDocument
    report: dict[str, Any]
    warnings: list[str]
    write_rag: bool = True
    write_markdown: bool = True


def load_export_inputs(*, linked_structure_path: Path, consensus_ir_path: Path | None = None, strict: bool = False) -> ExportLoadResult:
    """Load LinkedStructure and optional ConsensusIR documents from disk.

    Args:
        linked_structure_path: Path to ``linked_structure.json``.
        consensus_ir_path: Optional path to ``consensus_ir.json``; when
            absent a ``consensus_ir_missing`` warning is recorded.
        strict: When true, re-raise consensus parsing errors instead of
            downgrading to a warning.

    Returns:
        An ExportLoadResult with the parsed documents and warnings.

    Raises:
        ValidationError: When ``strict`` is set and the consensus IR file
            cannot be parsed.
    """

    linked = LinkedStructure.model_validate_json(linked_structure_path.read_text())
    warnings: list[str] = []
    consensus: ConsensusIR | None = None
    if consensus_ir_path is None:
        warnings.append("consensus_ir_missing")
    else:
        try:
            consensus = ConsensusIR.model_validate_json(consensus_ir_path.read_text())
        except Exception:
            if strict:
                raise
            warnings.append("invalid_consensus_ir")
    return ExportLoadResult(linked=linked, consensus=consensus, warnings=warnings)


def build_export_run(
    *,
    linked: LinkedStructure,
    consensus: ConsensusIR | None,
    source_linked_structure: str,
    source_consensus_ir: str | None,
    source_pdf: str | None,
    docling_settings: DoclingExportSettings,
    rag_settings: RagExportSettings,
    markdown_settings: MarkdownExportSettings,
    strict: bool = False,
    include_rag: bool = True,
    include_markdown: bool = True,
) -> ExportRunResult:
    """Build a complete export run from in-memory inputs.

    Projects the LinkedStructure into a Docling document, builds RAG
    chunks and the markdown preview, validates the Docling output (both
    structurally and through ``docling_core`` when available), and
    assembles the export manifest plus audit report.

    Args:
        linked: Linked structure to export.
        consensus: Optional consensus IR for provenance backfill.
        source_linked_structure: Filesystem reference recorded in the
            manifest for the linked structure input.
        source_consensus_ir: Optional manifest reference for the
            consensus IR.
        source_pdf: Optional manifest reference for the source PDF.
        docling_settings: Settings for the Docling projection.
        rag_settings: Settings for RAG chunk generation.
        markdown_settings: Settings for markdown preview rendering.
        strict: When true, raise ``ValueError`` on structural Docling
            validation failure.
        include_rag: When false, skip RAG chunk generation and mark the
            artefact as skipped in the manifest.
        include_markdown: When false, skip markdown preview generation.

    Returns:
        An ExportRunResult containing every produced artefact and the
        aggregated warning list.

    Raises:
        ValueError: When ``strict`` is set and structural Docling
            validation reports any issue.
    """

    docling_result = build_docling_document(linked=linked, consensus=consensus, settings=docling_settings, source_pdf=source_pdf)
    warnings = list(docling_result.warnings)
    structural = validate_docling_like_document(docling_result.document)
    warnings.extend(w for w in structural if w not in warnings)
    ok, reason = try_validate_with_docling_core(docling_result.document)
    if (not ok and reason) or reason:
        warnings.append(reason)
    if strict and structural:
        raise ValueError("Docling validation failed: " + ", ".join(structural))

    rag_chunks = build_rag_chunks(linked=linked, settings=rag_settings) if include_rag else RagChunkDocument(document_id=linked.document_id, chunks=[], warnings=[], metadata={"skipped": True})
    warnings.extend(rag_chunks.warnings)
    markdown, markdown_warnings = build_markdown_preview(linked=linked, settings=markdown_settings) if include_markdown else ("", [])
    warnings.extend(markdown_warnings)
    report = build_export_report(document_id=linked.document_id, docling=docling_result.document, rag_chunks=rag_chunks, markdown=markdown, warnings=warnings)
    artefacts = [
        artefact(f"docling/{linked.document_id}.docling.json", ExportArtefactType.DOCLING_JSON, docling_result.warnings),
        artefact("reports/export_report.json", ExportArtefactType.EXPORT_REPORT, warnings),
        artefact(f"rag/{linked.document_id}.rag_chunks.json", ExportArtefactType.RAG_CHUNKS, rag_chunks.warnings, skipped=not include_rag),
        artefact(f"markdown/{linked.document_id}.preview.md", ExportArtefactType.MARKDOWN_PREVIEW, markdown_warnings, skipped=not include_markdown),
    ]
    manifest = build_manifest(document_id=linked.document_id, source_linked_structure=source_linked_structure, source_consensus_ir=source_consensus_ir, source_pdf=source_pdf, artefacts=artefacts, warnings=warnings)
    return ExportRunResult(docling=docling_result.document, rag_chunks=rag_chunks, markdown=markdown, manifest=manifest, report=report, warnings=warnings, write_rag=include_rag, write_markdown=include_markdown)


def write_export_outputs(*, result: ExportRunResult, out_dir: Path) -> None:
    """Write every artefact in an export run to disk under ``out_dir``.

    Materialises the Docling JSON, audit report, RAG chunks, markdown
    preview, and export manifest. Computes sha256 digests for every
    written file and updates the manifest with those digests before
    writing ``export_manifest.json``.

    Args:
        result: The export run result to persist.
        out_dir: Destination directory; subdirectories are created as
            needed.
    """

    docling_path = out_dir / f"docling/{result.manifest.document_id}.docling.json"
    report_path = out_dir / "reports/export_report.json"
    rag_path = out_dir / f"rag/{result.manifest.document_id}.rag_chunks.json"
    markdown_path = out_dir / f"markdown/{result.manifest.document_id}.preview.md"
    for path in [docling_path, report_path, rag_path, markdown_path, out_dir / "export_manifest.json"]:
        path.parent.mkdir(parents=True, exist_ok=True)
    docling_path.write_text(json.dumps(result.docling, indent=2, sort_keys=True) + "\n")
    report_path.write_text(json.dumps(result.report, indent=2, sort_keys=True) + "\n")
    if result.write_rag:
        rag_path.write_text(result.rag_chunks.model_dump_json(indent=2) + "\n")
    if result.write_markdown:
        markdown_path.write_text(result.markdown)

    sha_by_path = {
        f"docling/{result.manifest.document_id}.docling.json": sha256_file(docling_path),
        "reports/export_report.json": sha256_file(report_path),
    }
    if result.write_rag:
        sha_by_path[f"rag/{result.manifest.document_id}.rag_chunks.json"] = sha256_file(rag_path)
    if result.write_markdown:
        sha_by_path[f"markdown/{result.manifest.document_id}.preview.md"] = sha256_file(markdown_path)
    artefacts = [a.model_copy(update={"sha256": sha_by_path.get(a.path)}) for a in result.manifest.artefacts]
    manifest = result.manifest.model_copy(update={"artefacts": artefacts})
    (out_dir / "export_manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
