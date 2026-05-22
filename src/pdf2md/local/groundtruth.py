"""Local LaTeX ground-truth corpus discovery and validation.

Plan 8 inspect-only layer. This module discovers the on-disk LaTeX-derived
ground-truth corpus, inspects each document for required and optional
artefacts, classifies document readiness, and produces a deterministic,
machine-readable report.

It deliberately does not compile LaTeX, run LuaLaTeX or LaTeXML, run the
ground-truth generator or validator scripts, or run any OCR backend. It only
inspects files that already exist on disk.
"""

from __future__ import annotations

import json
import tomllib
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LOCAL_GROUNDTRUTH_SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "local_groundtruth_validate"
DEFAULT_CORPUS_ROOT = Path("groundtruth/corpus/latex")

REQUIRED_ARTEFACTS: tuple[str, ...] = ("tex", "meta_toml", "docling_json")
OPTIONAL_ARTEFACTS: tuple[str, ...] = (
    "pdf",
    "tagged_pdf",
    "latexml_xml",
    "docling_groundtruth_meta",
)
_META_FIELDS: tuple[str, ...] = (
    "document_id",
    "documentclass",
    "expected_features",
    "expected_counts",
    "notes",
)


class DocumentStatus(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    MISSING_CRITICAL = "missing_critical"


class _GroundtruthBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtefactPresence(_GroundtruthBaseModel):
    kind: str
    required: bool
    present: bool
    paths: list[str] = Field(default_factory=list)
    detail: str | None = None


class DocumentValidationEntry(_GroundtruthBaseModel):
    document_id: str
    document_path: str
    status: DocumentStatus
    artefacts: dict[str, ArtefactPresence] = Field(default_factory=dict)
    required_present: list[str] = Field(default_factory=list)
    required_missing: list[str] = Field(default_factory=list)
    optional_present: list[str] = Field(default_factory=list)
    optional_missing: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GroundtruthValidationReport(_GroundtruthBaseModel):
    schema_name: Literal["pdf2md.LocalGroundtruthValidationReport"] = (
        "pdf2md.LocalGroundtruthValidationReport"
    )
    schema_version: Literal["1.0.0"] = LOCAL_GROUNDTRUTH_SCHEMA_VERSION
    generated_at: str
    tool_name: Literal["local_groundtruth_validate"] = TOOL_NAME
    corpus_root: str
    corpus_ready: bool = False
    total_documents: int = 0
    documents_ready: int = 0
    documents_partial: int = 0
    documents_missing_critical: int = 0
    documents: list[DocumentValidationEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _populate_counts(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        documents = data.get("documents") or []
        ready = _count_documents(documents, DocumentStatus.READY)
        partial = _count_documents(documents, DocumentStatus.PARTIAL)
        missing = _count_documents(documents, DocumentStatus.MISSING_CRITICAL)
        total = len(documents)
        data.setdefault("total_documents", total)
        data.setdefault("documents_ready", ready)
        data.setdefault("documents_partial", partial)
        data.setdefault("documents_missing_critical", missing)
        data.setdefault("corpus_ready", total > 0 and partial == 0 and missing == 0)
        return data

    @model_validator(mode="after")
    def _validate_report(self) -> GroundtruthValidationReport:
        ids = [document.document_id for document in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document ids must be unique")
        ready = _count_documents(self.documents, DocumentStatus.READY)
        partial = _count_documents(self.documents, DocumentStatus.PARTIAL)
        missing = _count_documents(self.documents, DocumentStatus.MISSING_CRITICAL)
        if self.total_documents != len(self.documents):
            raise ValueError("total_documents must match the number of documents")
        if self.documents_ready != ready:
            raise ValueError("documents_ready must match ready documents")
        if self.documents_partial != partial:
            raise ValueError("documents_partial must match partial documents")
        if self.documents_missing_critical != missing:
            raise ValueError("documents_missing_critical must match missing_critical documents")
        expected_ready = self.total_documents > 0 and partial == 0 and missing == 0
        if self.corpus_ready != expected_ready:
            raise ValueError("corpus_ready must be true only when every document is ready")
        return self


def _document_status_value(document: Any) -> str:
    if isinstance(document, dict):
        status = document.get("status")
    else:
        status = getattr(document, "status", None)
    if isinstance(status, DocumentStatus):
        return status.value
    return str(status)


def _count_documents(documents: list[Any], status: DocumentStatus) -> int:
    return sum(1 for document in documents if _document_status_value(document) == status.value)


def _glob_files(doc_dir: Path, pattern: str) -> list[Path]:
    return sorted((path for path in doc_dir.glob(pattern) if path.is_file()), key=lambda p: p.name)


def _artefact(kind: str, required: bool, files: list[Path], detail: str | None = None) -> ArtefactPresence:
    return ArtefactPresence(
        kind=kind,
        required=required,
        present=bool(files),
        paths=[path.name for path in files],
        detail=detail,
    )


def _detect_artefacts(doc_dir: Path) -> dict[str, ArtefactPresence]:
    """Detect every known required and optional artefact inside a document directory."""

    tex_files = _glob_files(doc_dir, "*.tex")
    meta_file = doc_dir / "meta.toml"
    meta_files = [meta_file] if meta_file.is_file() else []
    docling_files = _glob_files(doc_dir, "*.docling.json")
    pdf_files = sorted(
        {*_glob_files(doc_dir, "*.pdf"), *_glob_files(doc_dir, "*.pdf.placeholder")},
        key=lambda p: p.name,
    )
    tagged_files = [path for path in pdf_files if "tagged" in path.name.lower()]
    latexml_files = _glob_files(doc_dir, "*.xml")
    gt_meta_files = _glob_files(doc_dir, "*.docling_groundtruth_meta.json")

    placeholder_only = bool(pdf_files) and all(
        path.name.endswith(".placeholder") for path in pdf_files
    )
    return {
        "tex": _artefact("tex", True, tex_files),
        "meta_toml": _artefact("meta_toml", True, meta_files),
        "docling_json": _artefact("docling_json", True, docling_files),
        "pdf": _artefact(
            "pdf",
            False,
            pdf_files,
            detail="placeholder only" if placeholder_only else None,
        ),
        "tagged_pdf": _artefact(
            "tagged_pdf",
            False,
            tagged_files,
            detail="filename-heuristic detection" if tagged_files else None,
        ),
        "latexml_xml": _artefact("latexml_xml", False, latexml_files),
        "docling_groundtruth_meta": _artefact("docling_groundtruth_meta", False, gt_meta_files),
    }


def discover_corpus_documents(corpus_root: Path) -> list[Path]:
    """Return the document directories under ``corpus_root``, sorted by name."""

    if not corpus_root.is_dir():
        return []
    documents = [
        child
        for child in corpus_root.iterdir()
        if child.is_dir() and not child.name.startswith(".")
    ]
    return sorted(documents, key=lambda path: path.name)


def inspect_document(doc_dir: Path) -> DocumentValidationEntry:
    """Inspect a single document directory and classify its readiness."""

    document_id = doc_dir.name or str(doc_dir)
    if not doc_dir.is_dir():
        return DocumentValidationEntry(
            document_id=document_id,
            document_path=str(doc_dir),
            status=DocumentStatus.MISSING_CRITICAL,
            artefacts={},
            required_present=[],
            required_missing=list(REQUIRED_ARTEFACTS),
            optional_present=[],
            optional_missing=list(OPTIONAL_ARTEFACTS),
            warnings=["document directory does not exist or is not a directory"],
            metadata={"failure_class": "corpus_not_ready"},
        )

    artefacts = _detect_artefacts(doc_dir)
    required_present = [kind for kind in REQUIRED_ARTEFACTS if artefacts[kind].present]
    required_missing = [kind for kind in REQUIRED_ARTEFACTS if not artefacts[kind].present]
    optional_present = [kind for kind in OPTIONAL_ARTEFACTS if artefacts[kind].present]
    optional_missing = [kind for kind in OPTIONAL_ARTEFACTS if not artefacts[kind].present]

    warnings: list[str] = []
    metadata: dict[str, Any] = {}

    if not artefacts["tex"].present:
        status = DocumentStatus.MISSING_CRITICAL
        metadata["failure_class"] = "corpus_not_ready"
        warnings.append("no .tex source file found; document cannot be a ground-truth source")
    elif not required_missing:
        status = DocumentStatus.READY
    else:
        status = DocumentStatus.PARTIAL
        metadata["failure_class"] = "corpus_not_ready"
        warnings.append("missing required artefacts: " + ", ".join(required_missing))

    if artefacts["meta_toml"].present:
        _merge_meta(doc_dir / "meta.toml", metadata, warnings)

    return DocumentValidationEntry(
        document_id=document_id,
        document_path=str(doc_dir),
        status=status,
        artefacts=artefacts,
        required_present=required_present,
        required_missing=required_missing,
        optional_present=optional_present,
        optional_missing=optional_missing,
        warnings=warnings,
        metadata=metadata,
    )


def _merge_meta(meta_path: Path, metadata: dict[str, Any], warnings: list[str]) -> None:
    """Parse ``meta.toml`` and surface JSON-safe expectation fields into ``metadata``."""

    try:
        with meta_path.open("rb") as handle:
            meta = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warnings.append(f"meta.toml could not be parsed: {exc}")
        metadata.setdefault("failure_class", "corpus_not_ready")
        return
    metadata["meta_toml_keys"] = sorted(meta.keys())
    for field in _META_FIELDS:
        if field in meta:
            metadata[field] = meta[field]


def build_validation_report(
    corpus_root: Path,
    *,
    generated_at: str | None = None,
) -> GroundtruthValidationReport:
    """Inspect ``corpus_root`` and return a deterministic validation report.

    ``generated_at`` may be supplied for deterministic output; when omitted the
    current UTC time is used.
    """

    timestamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    corpus_root_str = str(corpus_root)
    warnings: list[str] = []
    metadata: dict[str, Any] = {
        "corpus_root": corpus_root_str,
        "artefact_contract": {
            "required": list(REQUIRED_ARTEFACTS),
            "optional": list(OPTIONAL_ARTEFACTS),
        },
    }

    if not corpus_root.exists():
        warnings.append(f"corpus root does not exist: {corpus_root}")
        metadata["failure_class"] = "corpus_missing"
        return GroundtruthValidationReport(
            generated_at=timestamp,
            corpus_root=corpus_root_str,
            documents=[],
            warnings=warnings,
            metadata=metadata,
        )
    if not corpus_root.is_dir():
        warnings.append(f"corpus root is not a directory: {corpus_root}")
        metadata["failure_class"] = "corpus_missing"
        return GroundtruthValidationReport(
            generated_at=timestamp,
            corpus_root=corpus_root_str,
            documents=[],
            warnings=warnings,
            metadata=metadata,
        )

    documents = [inspect_document(doc_dir) for doc_dir in discover_corpus_documents(corpus_root)]
    documents.sort(key=lambda entry: entry.document_id)

    if not documents:
        warnings.append("no documents found under the corpus root")
        metadata["failure_class"] = "corpus_not_ready"

    for entry in documents:
        for message in entry.warnings:
            warnings.append(f"{entry.document_id}: {message}")

    return GroundtruthValidationReport(
        generated_at=timestamp,
        corpus_root=corpus_root_str,
        documents=documents,
        warnings=warnings,
        metadata=metadata,
    )


def build_validation_summary(report: GroundtruthValidationReport) -> str:
    """Render a human-readable summary of a validation report."""

    lines = [
        "pdf2md local ground-truth corpus validation",
        f"schema: {report.schema_name} {report.schema_version}",
        f"tool: {report.tool_name}",
        f"generated_at: {report.generated_at}",
        f"corpus_root: {report.corpus_root}",
        f"corpus_ready: {str(report.corpus_ready).lower()}",
        (
            f"documents: {report.total_documents} total, "
            f"{report.documents_ready} ready, "
            f"{report.documents_partial} partial, "
            f"{report.documents_missing_critical} missing_critical"
        ),
        "",
        "documents:",
    ]
    if not report.documents:
        lines.append("- (none)")
    for entry in report.documents:
        lines.append(f"- {entry.status.value} {entry.document_id}")
        if entry.required_missing:
            lines.append(f"    required_missing: {', '.join(entry.required_missing)}")
        if entry.optional_missing:
            lines.append(f"    optional_missing: {', '.join(entry.optional_missing)}")
    if report.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def write_validation_report(*, report: GroundtruthValidationReport, out_dir: Path) -> Path:
    """Write the machine-readable JSON report and the human-readable summary."""

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "groundtruth_validation_report.json"
    summary_path = out_dir / "groundtruth_validation_summary.txt"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    summary_path.write_text(build_validation_summary(report), encoding="utf-8")
    return report_path


def report_to_json_dict(report: GroundtruthValidationReport) -> dict[str, Any]:
    """Return a JSON-compatible report dictionary."""

    return json.loads(report.model_dump_json())


__all__ = [
    "LOCAL_GROUNDTRUTH_SCHEMA_VERSION",
    "TOOL_NAME",
    "DEFAULT_CORPUS_ROOT",
    "REQUIRED_ARTEFACTS",
    "OPTIONAL_ARTEFACTS",
    "DocumentStatus",
    "ArtefactPresence",
    "DocumentValidationEntry",
    "GroundtruthValidationReport",
    "discover_corpus_documents",
    "inspect_document",
    "build_validation_report",
    "build_validation_summary",
    "write_validation_report",
    "report_to_json_dict",
]
