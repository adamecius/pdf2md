"""Reporting and manifest helpers for export runs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from statistics import mean
from typing import Any

from pdf2md.models.export import ExportArtefact, ExportArtefactType, ExportManifestDocument, ExportStatus, RagChunkDocument


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_export_report(*, document_id: str, docling: dict[str, Any], rag_chunks: RagChunkDocument, markdown: str, warnings: list[str]) -> dict[str, Any]:
    confidences = [chunk.confidence for chunk in rag_chunks.chunks]
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
    }


def build_manifest(*, document_id: str, source_linked_structure: str, source_consensus_ir: str | None, source_pdf: str | None, artefacts: list[ExportArtefact], warnings: list[str]) -> ExportManifestDocument:
    return ExportManifestDocument(document_id=document_id, source_linked_structure=source_linked_structure, source_consensus_ir=source_consensus_ir, source_pdf=source_pdf, artefacts=artefacts, warnings=warnings, metadata={"exporter": "pdf2md"})


def artefact(path: str, artefact_type: ExportArtefactType, warnings: list[str] | None = None, sha256: str | None = None, skipped: bool = False) -> ExportArtefact:
    return ExportArtefact(artefact_type=artefact_type, path=path, status=ExportStatus.SKIPPED if skipped else (ExportStatus.WRITTEN_WITH_WARNINGS if warnings else ExportStatus.WRITTEN), sha256=sha256, warnings=warnings or [], metadata={})
