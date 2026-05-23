"""Pipeline artifact path helpers (Plan 16).

Defines the canonical disk layout for one-document and corpus/subset MVP
runs. Path helpers return ``Path`` objects without touching the filesystem
unless ``ensure=True`` is supplied — callers stay in control of when
directories are created.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTEFACT_PIPELINE_MANIFEST = "pipeline_manifest.json"
ARTEFACT_PIPELINE_SUMMARY = "pipeline_summary.txt"
ARTEFACT_STAGE_STATUS = "stage_status.json"
ARTEFACT_CORPUS_EVAL = "mvp_corpus_evaluation.json"
ARTEFACT_CORPUS_SUMMARY = "mvp_corpus_summary.txt"

WORK_BACKEND_SMOKE = "backend_smoke"
WORK_CONNECTOR_CANONICAL = "connector_canonical"
WORK_CONNECTOR_VALIDATION = "connector_validation"
WORK_ENTITY_VALIDATION = "entity_proposal_validation"
WORK_CONSENSUS = "consensus"
WORK_LINKED = "linked_structure"

EXPORT_DOCLING = "docling"
EXPORT_RAG = "rag"
EXPORT_MARKDOWN = "markdown"
EXPORT_REPORTS = "reports"
EXPORT_REPORT = "reports/export_report.json"
EXPORT_MANIFEST = "export_manifest.json"


# ---------------------------------------------------------------------------
# Layout dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OneDocumentPaths:
    """Resolved paths for a single-document MVP run.

    Directories are not created by this dataclass; call
    ``OneDocumentPaths.ensure()`` to materialise them.
    """

    document_id: str
    out_dir: Path
    work_dir: Path

    # Top-level artefacts (one-document mode keeps the export tree flat)
    @property
    def pipeline_manifest(self) -> Path:
        return self.out_dir / ARTEFACT_PIPELINE_MANIFEST

    @property
    def pipeline_summary(self) -> Path:
        return self.out_dir / ARTEFACT_PIPELINE_SUMMARY

    @property
    def stage_status(self) -> Path:
        return self.out_dir / ARTEFACT_STAGE_STATUS

    # Work-dir sub-trees (each stage owns its own subdirectory)
    @property
    def backend_smoke_dir(self) -> Path:
        return self.work_dir / WORK_BACKEND_SMOKE

    @property
    def connector_canonical_dir(self) -> Path:
        return self.work_dir / WORK_CONNECTOR_CANONICAL

    @property
    def connector_validation_dir(self) -> Path:
        return self.work_dir / WORK_CONNECTOR_VALIDATION

    @property
    def entity_validation_dir(self) -> Path:
        return self.work_dir / WORK_ENTITY_VALIDATION

    @property
    def consensus_dir(self) -> Path:
        return self.work_dir / WORK_CONSENSUS

    @property
    def linked_dir(self) -> Path:
        return self.work_dir / WORK_LINKED

    # Final export artefacts (live under out_dir, flat)
    @property
    def docling_path(self) -> Path:
        return self.out_dir / EXPORT_DOCLING / f"{self.document_id}.docling.json"

    @property
    def rag_path(self) -> Path:
        return self.out_dir / EXPORT_RAG / f"{self.document_id}.rag_chunks.json"

    @property
    def markdown_path(self) -> Path:
        return self.out_dir / EXPORT_MARKDOWN / f"{self.document_id}.preview.md"

    @property
    def export_report(self) -> Path:
        return self.out_dir / EXPORT_REPORT

    @property
    def export_manifest(self) -> Path:
        return self.out_dir / EXPORT_MANIFEST

    def ensure(self) -> "OneDocumentPaths":
        for d in (self.out_dir, self.work_dir):
            Path(d).mkdir(parents=True, exist_ok=True)
        return self


@dataclass(frozen=True)
class CorpusDocumentPaths:
    """Resolved paths for one document inside a corpus/subset MVP run."""

    document_id: str
    document_root: Path  # <out_dir>/documents/<doc_id>
    work_dir: Path  # <work_dir>/<doc_id>

    @property
    def stage_status(self) -> Path:
        return self.document_root / ARTEFACT_STAGE_STATUS

    @property
    def backend_smoke_dir(self) -> Path:
        return self.work_dir / WORK_BACKEND_SMOKE

    @property
    def connector_canonical_dir(self) -> Path:
        return self.work_dir / WORK_CONNECTOR_CANONICAL

    @property
    def connector_validation_dir(self) -> Path:
        return self.work_dir / WORK_CONNECTOR_VALIDATION

    @property
    def entity_validation_dir(self) -> Path:
        return self.work_dir / WORK_ENTITY_VALIDATION

    @property
    def consensus_dir(self) -> Path:
        return self.work_dir / WORK_CONSENSUS

    @property
    def linked_dir(self) -> Path:
        return self.work_dir / WORK_LINKED

    @property
    def docling_path(self) -> Path:
        return self.document_root / EXPORT_DOCLING / f"{self.document_id}.docling.json"

    @property
    def rag_path(self) -> Path:
        return self.document_root / EXPORT_RAG / f"{self.document_id}.rag_chunks.json"

    @property
    def markdown_path(self) -> Path:
        return self.document_root / EXPORT_MARKDOWN / f"{self.document_id}.preview.md"

    @property
    def export_report(self) -> Path:
        return self.document_root / EXPORT_REPORT

    @property
    def export_manifest(self) -> Path:
        return self.document_root / EXPORT_MANIFEST

    def ensure(self) -> "CorpusDocumentPaths":
        for d in (self.document_root, self.work_dir):
            Path(d).mkdir(parents=True, exist_ok=True)
        return self


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def one_document_paths(*, document_id: str, out_dir: Path, work_dir: Path | None = None) -> OneDocumentPaths:
    """Build a ``OneDocumentPaths`` with conventional defaults.

    ``work_dir`` defaults to ``<out_dir>/work``.
    """

    out_dir = Path(out_dir)
    work_dir = Path(work_dir) if work_dir is not None else out_dir / "work"
    return OneDocumentPaths(document_id=document_id, out_dir=out_dir, work_dir=work_dir)


def corpus_document_paths(*, document_id: str, corpus_out_dir: Path, corpus_work_dir: Path) -> CorpusDocumentPaths:
    """Build a ``CorpusDocumentPaths`` for one document inside a corpus run."""

    corpus_out_dir = Path(corpus_out_dir)
    corpus_work_dir = Path(corpus_work_dir)
    return CorpusDocumentPaths(
        document_id=document_id,
        document_root=corpus_out_dir / "documents" / document_id,
        work_dir=corpus_work_dir / document_id,
    )


__all__ = [
    "ARTEFACT_PIPELINE_MANIFEST",
    "ARTEFACT_PIPELINE_SUMMARY",
    "ARTEFACT_STAGE_STATUS",
    "ARTEFACT_CORPUS_EVAL",
    "ARTEFACT_CORPUS_SUMMARY",
    "EXPORT_DOCLING",
    "EXPORT_RAG",
    "EXPORT_MARKDOWN",
    "EXPORT_REPORT",
    "EXPORT_MANIFEST",
    "OneDocumentPaths",
    "CorpusDocumentPaths",
    "one_document_paths",
    "corpus_document_paths",
]
