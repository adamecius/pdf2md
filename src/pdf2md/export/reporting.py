"""Reporting and manifest helpers for export runs (Plan 15 hardening)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from pdf2md.models.export import ExportArtefact, ExportArtefactType, ExportManifestDocument, ExportStatus, RagChunkDocument


INSPECTION_STATUSES: tuple[str, ...] = (
    "exported",
    "exported_with_warnings",
    "structural_mismatch",
    "ground_truth_unavailable",
    "ready_for_plan_16",
    "ready_with_warnings",
    "not_ready_for_plan_16",
    "diagnostic_only",
    "blocked",
)


def sha256_file(path: Path) -> str:
    """Compute the hex sha256 digest of ``path`` by streaming its bytes.

    Args:
        path: File to digest.

    Returns:
        The lowercase hexadecimal sha256 digest of the file contents.
    """

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plan16_readiness(
    *,
    document_id: str,
    docling: dict[str, Any],
    rag_chunks: RagChunkDocument,
    markdown: str,
    warnings: list[str],
    inspection_status: str,
    source_consensus_ir: str | None,
    source_pdf: str | None,
    ground_truth_ref: str | None,
    docling_core_available: bool,
) -> dict[str, Any]:
    docling_warnings = list(docling.get("metadata", {}).get("warnings", []))
    return {
        "document_id": document_id,
        "docling_text_count": len(docling.get("texts", [])),
        "docling_table_count": len(docling.get("tables", [])),
        "docling_picture_count": len(docling.get("pictures", [])),
        "docling_group_count": len(docling.get("groups", [])),
        "docling_page_count": len(docling.get("pages", {})),
        "docling_warning_count": len(docling_warnings),
        "rag_chunk_count": len(rag_chunks.chunks),
        "markdown_char_count": len(markdown),
        "consensus_report_used": source_consensus_ir is not None,
        "source_pdf_supplied": source_pdf is not None,
        "ground_truth_supplied": ground_truth_ref is not None,
        "docling_core_validation_available": docling_core_available,
        "warning_count": len(warnings),
        "inspection_status": inspection_status,
        "end_to_end_orchestration_handed_off_by": "plan_16",
    }


def build_export_report(
    *,
    document_id: str,
    docling: dict[str, Any],
    rag_chunks: RagChunkDocument,
    markdown: str,
    warnings: list[str],
    inspection_status: str | None = None,
    inspection_notes: Iterable[str] | None = None,
    source_consensus_ir: str | None = None,
    source_pdf: str | None = None,
    ground_truth_ref: str | None = None,
    docling_core_available: bool | None = None,
) -> dict[str, Any]:
    """Build the Plan 15 export audit report.

    Backwards compatible: pre-existing top-level fields (``schema_name``,
    ``schema_version``, ``document_id``, ``docling``, ``rag``, ``markdown``,
    ``warnings``) are preserved; new fields (``inspection_status``,
    ``inspection_notes``, ``ground_truth_ref``, ``plan16_readiness``) are
    added without renaming existing ones.
    """

    if inspection_status is not None and inspection_status not in INSPECTION_STATUSES:
        raise ValueError(
            f"inspection_status must be one of {INSPECTION_STATUSES}; got {inspection_status!r}"
        )
    effective_inspection = inspection_status or "diagnostic_only"

    confidences = [chunk.confidence for chunk in rag_chunks.chunks]

    docling_core_unavailable_warning = any(
        "docling_core_unavailable" in w for w in warnings
    )
    if docling_core_available is None:
        docling_core_available = not docling_core_unavailable_warning

    plan16 = _plan16_readiness(
        document_id=document_id,
        docling=docling,
        rag_chunks=rag_chunks,
        markdown=markdown,
        warnings=warnings,
        inspection_status=effective_inspection,
        source_consensus_ir=source_consensus_ir,
        source_pdf=source_pdf,
        ground_truth_ref=ground_truth_ref,
        docling_core_available=docling_core_available,
    )

    return {
        "schema_name": "pdf2md.ExportReport",
        "schema_version": "1.0.0",
        "document_id": document_id,
        "docling": {
            "text_count": len(docling.get("texts", [])),
            "table_count": len(docling.get("tables", [])),
            "picture_count": len(docling.get("pictures", [])),
            "group_count": len(docling.get("groups", [])),
            "page_count": len(docling.get("pages", {})),
            "warning_count": len(docling.get("metadata", {}).get("warnings", [])),
        },
        "rag": {"chunk_count": len(rag_chunks.chunks), "average_confidence": mean(confidences) if confidences else 0.0},
        "markdown": {"char_count": len(markdown), "warning_count": len([w for w in warnings if w.startswith("markdown_")])},
        "warnings": warnings,
        "inspection_status": effective_inspection,
        "inspection_notes": list(inspection_notes or []),
        "ground_truth_ref": ground_truth_ref,
        "plan16_readiness": plan16,
    }


def build_manifest(*, document_id: str, source_linked_structure: str, source_consensus_ir: str | None, source_pdf: str | None, artefacts: list[ExportArtefact], warnings: list[str]) -> ExportManifestDocument:
    """Assemble the ExportManifestDocument for a single export run.

    Args:
        document_id: Logical document identifier.
        source_linked_structure: Manifest reference for the input linked
            structure (typically a filesystem path).
        source_consensus_ir: Optional manifest reference for the input
            consensus IR.
        source_pdf: Optional manifest reference for the source PDF.
        artefacts: Artefact entries describing every produced file.
        warnings: Run-level warning list to record on the manifest.

    Returns:
        A populated ExportManifestDocument carrying the provided inputs
        and an ``exporter`` metadata tag.
    """

    return ExportManifestDocument(document_id=document_id, source_linked_structure=source_linked_structure, source_consensus_ir=source_consensus_ir, source_pdf=source_pdf, artefacts=artefacts, warnings=warnings, metadata={"exporter": "pdf2md"})


def artefact(path: str, artefact_type: ExportArtefactType, warnings: list[str] | None = None, sha256: str | None = None, skipped: bool = False) -> ExportArtefact:
    """Build an ExportArtefact entry with the correct status.

    Args:
        path: Relative path to the artefact under the export root.
        artefact_type: Artefact type enum value.
        warnings: Warnings associated with the artefact; presence of any
            warning promotes the status to ``WRITTEN_WITH_WARNINGS``.
        sha256: Pre-computed sha256 hex digest, when known.
        skipped: When true, mark the artefact ``SKIPPED`` regardless of
            warnings.

    Returns:
        A populated ExportArtefact ready to be added to a manifest.
    """

    return ExportArtefact(artefact_type=artefact_type, path=path, status=ExportStatus.SKIPPED if skipped else (ExportStatus.WRITTEN_WITH_WARNINGS if warnings else ExportStatus.WRITTEN), sha256=sha256, warnings=warnings or [], metadata={})


__all__ = [
    "INSPECTION_STATUSES",
    "sha256_file",
    "build_export_report",
    "build_manifest",
    "artefact",
]
