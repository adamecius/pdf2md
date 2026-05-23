"""End-to-end MVP runner orchestration (Plan 16).

Chains the existing per-stage entry points at the module level (with
backend execution flowing through the existing backend runner). Every
stage records its own ``StageRecord``; the document-level outcome is
classified into a ``DocumentResult``; the run-level outcome is
classified into an ``MvpReadiness`` value.

The runner is callable as a pure Python function (``run_one_document``,
``run_corpus``) for testability and via the ``tools/run_mvp_pipeline.py``
CLI for command-line use. Tests inject mock stage callables via the
``stage_overrides`` parameter to avoid running real backends.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from pdf2md.pipeline.artifacts import (
    CorpusDocumentPaths,
    OneDocumentPaths,
    corpus_document_paths,
    one_document_paths,
)

PIPELINE_SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Typed enums
# ---------------------------------------------------------------------------


class StageName(str, Enum):
    BACKEND_SMOKE = "backend_smoke"
    CONNECTOR_CANONICAL = "connector_canonical"
    CONNECTOR_VALIDATION = "connector_validation"
    ENTITY_VALIDATION = "entity_proposal_validation"
    CONSENSUS = "consensus"
    LINKED_STRUCTURE = "linked_structure"
    EXPORT = "export"


STAGE_ORDER: tuple[StageName, ...] = (
    StageName.BACKEND_SMOKE,
    StageName.CONNECTOR_CANONICAL,
    StageName.CONNECTOR_VALIDATION,
    StageName.ENTITY_VALIDATION,
    StageName.CONSENSUS,
    StageName.LINKED_STRUCTURE,
    StageName.EXPORT,
)


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"


class DocumentResult(str, Enum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class MvpReadiness(str, Enum):
    MVP_READY = "MVP_ready"
    MVP_READY_WITH_WARNINGS = "MVP_ready_with_warnings"
    MVP_NOT_READY = "MVP_not_ready"
    DIAGNOSTIC_ONLY = "diagnostic_only"


# ---------------------------------------------------------------------------
# Report models
# ---------------------------------------------------------------------------


class _PipelineBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class StageRecord(_PipelineBaseModel):
    name: StageName
    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    skipped_reason: str | None = None
    failure_class: str | None = None
    failure_detail: str | None = None
    warnings: list[str] = Field(default_factory=list)
    artefacts: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRecord(_PipelineBaseModel):
    document_id: str
    input_pdf: str | None = None
    result: DocumentResult = DocumentResult.SKIPPED
    selected_backends: list[str] = Field(default_factory=list)
    eligible_backends: list[str] = Field(default_factory=list)
    final_artefacts: dict[str, str] = Field(default_factory=dict)
    stages: list[StageRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineManifest(_PipelineBaseModel):
    schema_name: Literal["pdf2md.MvpPipelineManifest"] = "pdf2md.MvpPipelineManifest"
    schema_version: Literal["1.0.0"] = PIPELINE_SCHEMA_VERSION
    generated_at: str
    mode: Literal["one_document", "corpus_subset"]
    input_pdf: str | None = None
    corpus_root: str | None = None
    out_dir: str
    work_dir: str
    selected_backends: list[str] = Field(default_factory=list)
    documents: list[DocumentRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    mvp_readiness: MvpReadiness = MvpReadiness.DIAGNOSTIC_ONLY
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorpusEvaluation(_PipelineBaseModel):
    schema_name: Literal["pdf2md.MvpCorpusEvaluation"] = "pdf2md.MvpCorpusEvaluation"
    schema_version: Literal["1.0.0"] = PIPELINE_SCHEMA_VERSION
    generated_at: str
    corpus_root: str
    out_dir: str
    selected_documents: list[str] = Field(default_factory=list)
    document_results: dict[str, str] = Field(default_factory=dict)  # doc_id -> DocumentResult value
    stage_bottlenecks: dict[str, int] = Field(default_factory=dict)  # stage -> failed count
    backend_eligibility: dict[str, int] = Field(default_factory=dict)
    final_export_availability: dict[str, bool] = Field(default_factory=dict)  # doc_id -> bool
    confidence_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    mvp_readiness: MvpReadiness = MvpReadiness.DIAGNOSTIC_ONLY
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage callable signatures (for tests to override)
# ---------------------------------------------------------------------------


StageCallable = Callable[..., dict[str, Any]]


# Each stage callable returns a dict with keys:
#   - status: StageStatus value
#   - warnings: list[str]
#   - artefacts: dict[str, str]      (relative or absolute paths)
#   - metadata: dict[str, Any]
#   - skipped_reason / failure_class / failure_detail (when applicable)
# Plus stage-specific context the next stage needs (e.g. backend_smoke
# returns ``raw_dirs_by_backend`` keyed by backend name).


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_monotonic() -> float:
    return datetime.now(timezone.utc).timestamp()


def _new_record(name: StageName) -> StageRecord:
    return StageRecord(name=name)


def _begin(rec: StageRecord) -> tuple[StageRecord, float]:
    return rec, _now_monotonic()


def _finalize(rec: StageRecord, started_at: float, payload: dict[str, Any]) -> StageRecord:
    finished_at = _now_monotonic()
    rec_dict = rec.model_dump()
    rec_dict.update(
        {
            "started_at": datetime.fromtimestamp(started_at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finished_at": datetime.fromtimestamp(finished_at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": round(finished_at - started_at, 3),
            "status": payload.get("status", StageStatus.SUCCEEDED.value),
            "skipped_reason": payload.get("skipped_reason"),
            "failure_class": payload.get("failure_class"),
            "failure_detail": payload.get("failure_detail"),
            "warnings": list(payload.get("warnings", []) or []),
            "artefacts": dict(payload.get("artefacts", {}) or {}),
            "metadata": dict(payload.get("metadata", {}) or {}),
        }
    )
    return StageRecord.model_validate(rec_dict)


def _document_result(stages: list[StageRecord]) -> DocumentResult:
    """Reduce a stage sequence into a per-document outcome."""

    statuses = [s.status if isinstance(s.status, str) else s.status.value for s in stages]
    if all(s == StageStatus.PENDING.value for s in statuses):
        return DocumentResult.SKIPPED
    if any(s == StageStatus.FAILED.value for s in statuses):
        return DocumentResult.FAILED
    if any(s == StageStatus.BLOCKED.value for s in statuses):
        return DocumentResult.BLOCKED

    export_status = next(
        (
            s.status if isinstance(s.status, str) else s.status.value
            for s in stages
            if (s.name if isinstance(s.name, str) else s.name.value) == StageName.EXPORT.value
        ),
        None,
    )
    if export_status != StageStatus.SUCCEEDED.value:
        # Export must succeed for a document to count as fully passed.
        return DocumentResult.FAILED

    any_warnings = any((s.warnings or []) for s in stages)
    any_skip = any(s == StageStatus.SKIPPED.value for s in statuses)
    if any_warnings or any_skip:
        return DocumentResult.PASSED_WITH_WARNINGS
    return DocumentResult.PASSED


def _mvp_readiness(documents: list[DocumentRecord]) -> MvpReadiness:
    if not documents:
        return MvpReadiness.DIAGNOSTIC_ONLY
    results = [d.result if isinstance(d.result, str) else d.result.value for d in documents]
    if all(r == DocumentResult.PASSED.value for r in results):
        return MvpReadiness.MVP_READY
    if any(r == DocumentResult.FAILED.value for r in results):
        return MvpReadiness.MVP_NOT_READY
    if all(
        r in (DocumentResult.PASSED.value, DocumentResult.PASSED_WITH_WARNINGS.value)
        for r in results
    ):
        return MvpReadiness.MVP_READY_WITH_WARNINGS
    return MvpReadiness.DIAGNOSTIC_ONLY


# ---------------------------------------------------------------------------
# Default stage implementations (call real Plan 9-15 modules)
# ---------------------------------------------------------------------------


def _default_backend_smoke_stage(
    *,
    repo_root: Path,
    input_pdf: Path,
    work_dir: Path,
    backends: list[str] | None,
    timeout_seconds: int,
    strict: bool,
) -> dict[str, Any]:
    from pdf2md.local.backend_smoke import build_backend_smoke_report, write_backend_smoke_report

    report = build_backend_smoke_report(
        repo_root=repo_root,
        input_pdf=input_pdf,
        work_dir=work_dir / "backend_runs",
        gate_minimum=1,
        timeout_seconds=timeout_seconds,
    )
    write_backend_smoke_report(report=report, out_dir=work_dir)

    raw_dirs: dict[str, Path] = {}
    successful: list[str] = []
    for r in report.results:
        if (r.status if isinstance(r.status, str) else r.status.value) == "success" and r.output_dir:
            raw_dirs[r.backend_name] = Path(r.output_dir)
            successful.append(r.backend_name)

    selected = [b for b in (backends or []) if not backends or b in {x.backend_name for x in report.results}] or [
        r.backend_name for r in report.results
    ]
    if backends:
        raw_dirs = {b: p for b, p in raw_dirs.items() if b in backends}
        successful = [b for b in successful if b in backends]

    if not successful:
        return {
            "status": StageStatus.BLOCKED.value,
            "warnings": list(report.warnings),
            "artefacts": {
                "backend_smoke_report": str((work_dir / "backend_smoke_report.json").resolve())
            },
            "metadata": {
                "backends_successful": int(report.backends_successful),
                "total_backends": int(report.total_backends),
            },
            "skipped_reason": "no_successful_backend",
            "failure_class": "plan9_artifact_missing",
            "raw_dirs_by_backend": {},
            "selected_backends": selected,
        }

    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": list(report.warnings),
        "artefacts": {
            "backend_smoke_report": str((work_dir / "backend_smoke_report.json").resolve())
        },
        "metadata": {
            "backends_successful": int(report.backends_successful),
            "total_backends": int(report.total_backends),
        },
        "raw_dirs_by_backend": raw_dirs,
        "selected_backends": successful,
    }


def _default_connector_canonical_stage(
    *,
    document_id: str,
    raw_dirs_by_backend: dict[str, Path],
    out_dir: Path,
) -> dict[str, Any]:
    """Convert each raw backend dir into the canonical connector layout."""

    from pdf2md.connectors.common import BackendConnectorConfig, connect_raw_dir

    artefacts: dict[str, str] = {}
    warnings: list[str] = []
    canonical_dirs: dict[str, Path] = {}
    out_dir.mkdir(parents=True, exist_ok=True)
    for backend, raw_dir in raw_dirs_by_backend.items():
        cfg = BackendConnectorConfig(backend=backend, default_backend_version=None)
        try:
            connect_raw_dir(
                raw_dir=raw_dir,
                document_id=document_id,
                config=cfg,
                out_dir=out_dir,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"connector_canonical_failed:{backend}:{type(exc).__name__}:{exc}")
            continue
        canonical_dir = out_dir / backend
        canonical_dirs[backend] = canonical_dir
        artefacts[f"{backend}_canonical_dir"] = str(canonical_dir.resolve())
    if not canonical_dirs:
        return {
            "status": StageStatus.FAILED.value,
            "warnings": warnings,
            "artefacts": artefacts,
            "failure_class": "connector_canonical_unavailable",
            "failure_detail": "no canonical connector output produced for any backend",
            "canonical_dirs_by_backend": {},
        }
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": warnings,
        "artefacts": artefacts,
        "canonical_dirs_by_backend": canonical_dirs,
    }


def _default_connector_validation_stage(
    *,
    backends_dirs: dict[str, Path],
    out_dir: Path,
) -> dict[str, Any]:
    from pdf2md.local.connector_validation import (
        build_connector_validation_report,
        write_connector_validation_report,
    )

    report = build_connector_validation_report(
        backend_outputs={b: d for b, d in backends_dirs.items()},
        preferred_gate_minimum=2,
        allow_reduced_gate=True,
        out_dir=out_dir,
    )
    write_connector_validation_report(report=report, out_dir=out_dir)
    validated = [r for r in report.results if (r.status if isinstance(r.status, str) else r.status.value) == "validated"]
    status = (
        StageStatus.SUCCEEDED.value
        if (report.preferred_gate_passed or (report.minimum_gate_passed and report.human_reduced_gate_required))
        else (StageStatus.FAILED.value if not validated else StageStatus.SUCCEEDED.value)
    )
    artefacts = {
        "connector_validation_report": str((out_dir / "connector_validation_report.json").resolve()),
        "connector_validation_summary": str((out_dir / "connector_validation_summary.txt").resolve()),
    }
    return {
        "status": status,
        "warnings": list(report.warnings),
        "artefacts": artefacts,
        "metadata": {
            "backends_validated": int(report.backends_validated),
            "preferred_gate_passed": bool(report.preferred_gate_passed),
            "minimum_gate_passed": bool(report.minimum_gate_passed),
        },
        "validated_backends": [r.backend_name for r in validated],
    }


def _default_entity_validation_stage(
    *,
    backends_dirs: dict[str, Path],
    out_dir: Path,
) -> dict[str, Any]:
    from pdf2md.local.entity_proposal_validation import (
        build_entity_proposal_validation_report,
        write_entity_proposal_validation_report,
    )

    # Each canonical dir already contains `entities.json` produced by connect_raw_dir.
    backend_entities = {b: (d / "entities.json") for b, d in backends_dirs.items()}
    report = build_entity_proposal_validation_report(
        backend_entities=backend_entities,
        preferred_gate_minimum=2,
        allow_reduced_gate=True,
        out_dir=out_dir,
    )
    write_entity_proposal_validation_report(report=report, out_dir=out_dir)

    artefacts = {
        "entity_proposal_validation_report": str(
            (out_dir / "entity_proposal_validation_report.json").resolve()
        ),
        "entity_proposal_validation_summary": str(
            (out_dir / "entity_proposal_validation_summary.txt").resolve()
        ),
    }
    warnings = list(report.warnings)
    no_entities_only = report.backends_validated == 0 and report.backends_no_entities >= 1
    if no_entities_only:
        return {
            "status": StageStatus.SUCCEEDED.value,
            "warnings": warnings + ["entity_validation_no_entities_only"],
            "artefacts": artefacts,
            "metadata": {
                "backends_validated": int(report.backends_validated),
                "backends_no_entities": int(report.backends_no_entities),
            },
        }
    return {
        "status": StageStatus.SUCCEEDED.value
        if report.backends_validated >= 1 or report.backends_no_entities >= 1
        else StageStatus.FAILED.value,
        "warnings": warnings,
        "artefacts": artefacts,
        "metadata": {
            "backends_validated": int(report.backends_validated),
            "backends_no_entities": int(report.backends_no_entities),
        },
    }


def _default_consensus_stage(
    *,
    document_id: str,
    connector_canonical_root: Path,
    backends: list[str],
    out_dir: Path,
) -> dict[str, Any]:
    from pdf2md.consensus.factory import ConsensusFactorySettings, build_consensus_ir
    from pdf2md.consensus.io import load_consensus_inputs, write_consensus_outputs
    from pdf2md.consensus.reporting import build_consensus_report

    loaded = load_consensus_inputs(
        connector_root=connector_canonical_root,
        document_id=document_id,
        backends=backends,
    )
    result = build_consensus_ir(
        document_id=document_id,
        pages_by_backend=loaded.pages_by_backend,
        entities_by_backend=loaded.entities_by_backend,
        priors_by_backend=loaded.priors_by_backend,
        settings=ConsensusFactorySettings(),
    )
    all_warnings = list(loaded.warnings) + list(result.warnings)
    rebuilt_report = build_consensus_report(
        consensus=result.consensus,
        warnings=all_warnings,
        backend_summary=result.report.get("backend_summary", {}),
        inspection_status="diagnostic_only",
    )
    merged = type(result)(
        consensus=result.consensus,
        report=rebuilt_report,
        warnings=all_warnings,
    )
    write_consensus_outputs(result=merged, out_dir=out_dir)
    artefacts = {
        "consensus_ir": str((out_dir / "consensus_ir.json").resolve()),
        "consensus_report": str((out_dir / "reports" / "consensus_report.json").resolve()),
        "consensus_summary": str((out_dir / "consensus_summary.txt").resolve()),
    }
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": all_warnings,
        "artefacts": artefacts,
        "metadata": {
            "page_count": int(merged.consensus.page_count),
            "block_count": int(rebuilt_report.get("block_count", 0)),
            "conflict_count": int(rebuilt_report.get("conflict_count", 0)),
        },
    }


def _default_linking_stage(
    *,
    consensus_ir_path: Path,
    consensus_report_path: Path,
    entities_root: Path,
    out_dir: Path,
) -> dict[str, Any]:
    from pdf2md.linking.builder import LinkerSettings, build_linked_structure
    from pdf2md.linking.io import load_linker_inputs, write_linker_outputs
    from pdf2md.linking.reporting import build_linking_report

    loaded = load_linker_inputs(
        consensus_ir_path=consensus_ir_path,
        consensus_report_path=consensus_report_path,
        entities_root=entities_root,
    )
    result = build_linked_structure(
        consensus=loaded.consensus,
        entities_by_backend=loaded.entities_by_backend,
        priors_by_backend=loaded.priors_by_backend,
        consensus_report=loaded.consensus_report,
        source_consensus_ir=str(consensus_ir_path),
        source_consensus_report=str(consensus_report_path),
        source_entity_documents=loaded.source_entity_documents,
        source_prior_documents=loaded.source_prior_documents,
        settings=LinkerSettings(),
    )
    linked = result.linked
    if loaded.warnings:
        linked = result.linked.model_copy(update={"warnings": result.linked.warnings + loaded.warnings})
    rebuilt_report = build_linking_report(linked, inspection_status="diagnostic_only")
    merged = type(result)(
        linked=linked,
        report=rebuilt_report,
        warnings=result.warnings + loaded.warnings,
    )
    write_linker_outputs(result=merged, out_dir=out_dir)
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": list(merged.warnings),
        "artefacts": {
            "linked_structure": str((out_dir / "linked_structure.json").resolve()),
            "linking_report": str((out_dir / "reports" / "linking_report.json").resolve()),
        },
        "metadata": {
            "node_count": int(rebuilt_report.get("node_count", 0)),
            "relation_count": int(rebuilt_report.get("relation_count", 0)),
            "conflict_count": int(rebuilt_report.get("conflict_count", 0)),
        },
    }


def _default_export_stage(
    *,
    linked_structure_path: Path,
    consensus_ir_path: Path,
    out_dir: Path,
    document_id: str,
    source_pdf: str | None,
) -> dict[str, Any]:
    from pdf2md.export.docling import DoclingExportSettings
    from pdf2md.export.io import build_export_run, load_export_inputs, write_export_outputs
    from pdf2md.export.markdown import MarkdownExportSettings
    from pdf2md.export.rag import RagExportSettings
    from pdf2md.export.reporting import build_export_report

    loaded = load_export_inputs(
        linked_structure_path=linked_structure_path,
        consensus_ir_path=consensus_ir_path,
    )
    result = build_export_run(
        linked=loaded.linked,
        consensus=loaded.consensus,
        source_linked_structure=str(linked_structure_path),
        source_consensus_ir=str(consensus_ir_path),
        source_pdf=source_pdf,
        docling_settings=DoclingExportSettings(),
        rag_settings=RagExportSettings(),
        markdown_settings=MarkdownExportSettings(),
    )
    all_warnings = result.warnings + loaded.warnings
    rebuilt_report = build_export_report(
        document_id=loaded.linked.document_id,
        docling=result.docling,
        rag_chunks=result.rag_chunks,
        markdown=result.markdown,
        warnings=all_warnings,
        inspection_status="diagnostic_only",
        source_consensus_ir=str(consensus_ir_path),
        source_pdf=source_pdf,
    )
    merged = type(result)(
        docling=result.docling,
        rag_chunks=result.rag_chunks,
        markdown=result.markdown,
        manifest=result.manifest.model_copy(
            update={"warnings": result.manifest.warnings + loaded.warnings}
        ) if loaded.warnings else result.manifest,
        report=rebuilt_report,
        warnings=all_warnings,
        write_rag=result.write_rag,
        write_markdown=result.write_markdown,
    )
    write_export_outputs(result=merged, out_dir=out_dir)
    docling_path = out_dir / "docling" / f"{document_id}.docling.json"
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": list(merged.warnings),
        "artefacts": {
            "docling": str(docling_path.resolve()),
            "rag": str((out_dir / "rag" / f"{document_id}.rag_chunks.json").resolve()),
            "markdown": str((out_dir / "markdown" / f"{document_id}.preview.md").resolve()),
            "export_report": str((out_dir / "reports" / "export_report.json").resolve()),
            "export_manifest": str((out_dir / "export_manifest.json").resolve()),
        },
        "metadata": {
            "docling_text_count": int(rebuilt_report["plan16_readiness"]["docling_text_count"]),
            "rag_chunk_count": int(rebuilt_report["plan16_readiness"]["rag_chunk_count"]),
            "markdown_char_count": int(rebuilt_report["plan16_readiness"]["markdown_char_count"]),
        },
    }


# ---------------------------------------------------------------------------
# One-document orchestration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StageOverrides:
    backend_smoke: StageCallable | None = None
    connector_canonical: StageCallable | None = None
    connector_validation: StageCallable | None = None
    entity_validation: StageCallable | None = None
    consensus: StageCallable | None = None
    linked_structure: StageCallable | None = None
    export: StageCallable | None = None


def _resolve_stage(name: StageName, overrides: _StageOverrides | None) -> StageCallable:
    if overrides is None:
        overrides = _StageOverrides()
    mapping = {
        StageName.BACKEND_SMOKE: overrides.backend_smoke or _default_backend_smoke_stage,
        StageName.CONNECTOR_CANONICAL: overrides.connector_canonical or _default_connector_canonical_stage,
        StageName.CONNECTOR_VALIDATION: overrides.connector_validation or _default_connector_validation_stage,
        StageName.ENTITY_VALIDATION: overrides.entity_validation or _default_entity_validation_stage,
        StageName.CONSENSUS: overrides.consensus or _default_consensus_stage,
        StageName.LINKED_STRUCTURE: overrides.linked_structure or _default_linking_stage,
        StageName.EXPORT: overrides.export or _default_export_stage,
    }
    return mapping[name]


def _run_stages_for_document(
    *,
    document_id: str,
    input_pdf: Path | None,
    paths: OneDocumentPaths | CorpusDocumentPaths,
    repo_root: Path,
    backends: list[str] | None,
    timeout_seconds: int,
    strict: bool,
    overrides: _StageOverrides | None = None,
) -> DocumentRecord:
    stages: list[StageRecord] = [StageRecord(name=s) for s in STAGE_ORDER]
    document = DocumentRecord(
        document_id=document_id,
        input_pdf=str(input_pdf) if input_pdf else None,
        stages=stages,
        selected_backends=list(backends or []),
    )

    raw_dirs_by_backend: dict[str, Path] = {}
    selected_after_smoke: list[str] = []
    canonical_dirs_by_backend: dict[str, Path] = {}
    consensus_ir_path: Path | None = None
    consensus_report_path: Path | None = None
    linked_path: Path | None = None
    final_artefacts: dict[str, str] = {}

    paths.ensure() if hasattr(paths, "ensure") else None

    # ---- Stage 1: backend smoke ----
    rec_idx = STAGE_ORDER.index(StageName.BACKEND_SMOKE)
    rec, t0 = _begin(stages[rec_idx])
    if input_pdf is None:
        payload = {
            "status": StageStatus.SKIPPED.value,
            "warnings": ["no_input_pdf"],
            "skipped_reason": "no_input_pdf",
        }
    else:
        try:
            payload = _resolve_stage(StageName.BACKEND_SMOKE, overrides)(
                repo_root=repo_root,
                input_pdf=Path(input_pdf),
                work_dir=paths.backend_smoke_dir,
                backends=backends,
                timeout_seconds=timeout_seconds,
                strict=strict,
            )
        except Exception as exc:  # noqa: BLE001
            payload = {
                "status": StageStatus.FAILED.value,
                "failure_class": "backend_smoke_crash",
                "failure_detail": f"{type(exc).__name__}: {exc}",
                "warnings": [],
            }
    stages[rec_idx] = _finalize(rec, t0, payload)
    raw_dirs_by_backend = payload.get("raw_dirs_by_backend", {})
    selected_after_smoke = payload.get("selected_backends", list(backends or []))
    document.eligible_backends = list(raw_dirs_by_backend.keys())

    if stages[rec_idx].status in (StageStatus.SKIPPED.value, StageStatus.FAILED.value, StageStatus.BLOCKED.value) or not raw_dirs_by_backend:
        for i in range(rec_idx + 1, len(stages)):
            stages[i] = StageRecord(
                name=STAGE_ORDER[i],
                status=StageStatus.SKIPPED,
                skipped_reason="upstream_blocked",
            )
        document.stages = stages
        document.result = _document_result(stages)
        return document

    # ---- Stage 2: connector canonical ----
    rec_idx = STAGE_ORDER.index(StageName.CONNECTOR_CANONICAL)
    rec, t0 = _begin(stages[rec_idx])
    try:
        payload = _resolve_stage(StageName.CONNECTOR_CANONICAL, overrides)(
            document_id=document_id,
            raw_dirs_by_backend=raw_dirs_by_backend,
            out_dir=paths.connector_canonical_dir,
        )
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": StageStatus.FAILED.value,
            "failure_class": "connector_canonical_crash",
            "failure_detail": f"{type(exc).__name__}: {exc}",
        }
    stages[rec_idx] = _finalize(rec, t0, payload)
    canonical_dirs_by_backend = payload.get("canonical_dirs_by_backend", {})

    if not canonical_dirs_by_backend or stages[rec_idx].status == StageStatus.FAILED.value:
        for i in range(rec_idx + 1, len(stages)):
            stages[i] = StageRecord(name=STAGE_ORDER[i], status=StageStatus.SKIPPED, skipped_reason="upstream_blocked")
        document.stages = stages
        document.result = _document_result(stages)
        return document

    # ---- Stage 3: connector validation ----
    rec_idx = STAGE_ORDER.index(StageName.CONNECTOR_VALIDATION)
    rec, t0 = _begin(stages[rec_idx])
    try:
        payload = _resolve_stage(StageName.CONNECTOR_VALIDATION, overrides)(
            backends_dirs=raw_dirs_by_backend,
            out_dir=paths.connector_validation_dir,
        )
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": StageStatus.FAILED.value,
            "failure_class": "connector_validation_crash",
            "failure_detail": f"{type(exc).__name__}: {exc}",
        }
    stages[rec_idx] = _finalize(rec, t0, payload)

    # ---- Stage 4: entity validation ----
    rec_idx = STAGE_ORDER.index(StageName.ENTITY_VALIDATION)
    rec, t0 = _begin(stages[rec_idx])
    try:
        payload = _resolve_stage(StageName.ENTITY_VALIDATION, overrides)(
            backends_dirs=canonical_dirs_by_backend,
            out_dir=paths.entity_validation_dir,
        )
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": StageStatus.FAILED.value,
            "failure_class": "entity_validation_crash",
            "failure_detail": f"{type(exc).__name__}: {exc}",
        }
    stages[rec_idx] = _finalize(rec, t0, payload)

    # ---- Stage 5: consensus ----
    rec_idx = STAGE_ORDER.index(StageName.CONSENSUS)
    rec, t0 = _begin(stages[rec_idx])
    try:
        payload = _resolve_stage(StageName.CONSENSUS, overrides)(
            document_id=document_id,
            connector_canonical_root=paths.connector_canonical_dir,
            backends=list(canonical_dirs_by_backend.keys()),
            out_dir=paths.consensus_dir,
        )
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": StageStatus.FAILED.value,
            "failure_class": "consensus_crash",
            "failure_detail": f"{type(exc).__name__}: {exc}",
        }
    stages[rec_idx] = _finalize(rec, t0, payload)
    if stages[rec_idx].status == StageStatus.SUCCEEDED.value:
        consensus_ir_path = paths.consensus_dir / "consensus_ir.json"
        consensus_report_path = paths.consensus_dir / "reports" / "consensus_report.json"

    if stages[rec_idx].status != StageStatus.SUCCEEDED.value:
        for i in range(rec_idx + 1, len(stages)):
            stages[i] = StageRecord(name=STAGE_ORDER[i], status=StageStatus.SKIPPED, skipped_reason="upstream_blocked")
        document.stages = stages
        document.result = _document_result(stages)
        return document

    # ---- Stage 6: linked structure ----
    rec_idx = STAGE_ORDER.index(StageName.LINKED_STRUCTURE)
    rec, t0 = _begin(stages[rec_idx])
    try:
        payload = _resolve_stage(StageName.LINKED_STRUCTURE, overrides)(
            consensus_ir_path=consensus_ir_path,
            consensus_report_path=consensus_report_path,
            entities_root=paths.connector_canonical_dir,
            out_dir=paths.linked_dir,
        )
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": StageStatus.FAILED.value,
            "failure_class": "linking_crash",
            "failure_detail": f"{type(exc).__name__}: {exc}",
        }
    stages[rec_idx] = _finalize(rec, t0, payload)
    if stages[rec_idx].status == StageStatus.SUCCEEDED.value:
        linked_path = paths.linked_dir / "linked_structure.json"

    if stages[rec_idx].status != StageStatus.SUCCEEDED.value:
        for i in range(rec_idx + 1, len(stages)):
            stages[i] = StageRecord(name=STAGE_ORDER[i], status=StageStatus.SKIPPED, skipped_reason="upstream_blocked")
        document.stages = stages
        document.result = _document_result(stages)
        return document

    # ---- Stage 7: export ----
    rec_idx = STAGE_ORDER.index(StageName.EXPORT)
    rec, t0 = _begin(stages[rec_idx])
    out_for_export = paths.out_dir if isinstance(paths, OneDocumentPaths) else paths.document_root
    try:
        payload = _resolve_stage(StageName.EXPORT, overrides)(
            linked_structure_path=linked_path,
            consensus_ir_path=consensus_ir_path,
            out_dir=out_for_export,
            document_id=document_id,
            source_pdf=str(input_pdf) if input_pdf else None,
        )
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": StageStatus.FAILED.value,
            "failure_class": "export_crash",
            "failure_detail": f"{type(exc).__name__}: {exc}",
        }
    stages[rec_idx] = _finalize(rec, t0, payload)
    if stages[rec_idx].status == StageStatus.SUCCEEDED.value:
        final_artefacts = stages[rec_idx].artefacts

    document.stages = stages
    document.final_artefacts = final_artefacts
    document.result = _document_result(stages)
    return document


def run_one_document(
    *,
    pdf_path: Path,
    out_dir: Path,
    work_dir: Path | None = None,
    backends: list[str] | None = None,
    repo_root: Path | None = None,
    timeout_seconds: int = 1500,
    strict: bool = False,
    stage_overrides: _StageOverrides | None = None,
    generated_at: str | None = None,
) -> PipelineManifest:
    """Run the MVP pipeline against a single PDF."""

    from pdf2md.pipeline.io import write_pipeline_manifest, write_stage_status

    repo_root = (repo_root or Path.cwd()).resolve()
    paths = one_document_paths(
        document_id=Path(pdf_path).stem,
        out_dir=Path(out_dir).resolve(),
        work_dir=Path(work_dir).resolve() if work_dir else None,
    ).ensure()
    document = _run_stages_for_document(
        document_id=paths.document_id,
        input_pdf=Path(pdf_path).resolve(),
        paths=paths,
        repo_root=repo_root,
        backends=backends,
        timeout_seconds=timeout_seconds,
        strict=strict,
        overrides=stage_overrides,
    )
    manifest = PipelineManifest(
        generated_at=generated_at or _utc_now(),
        mode="one_document",
        input_pdf=str(pdf_path),
        out_dir=str(paths.out_dir),
        work_dir=str(paths.work_dir),
        selected_backends=list(backends or document.eligible_backends),
        documents=[document],
        warnings=[],
        errors=[],
        mvp_readiness=_mvp_readiness([document]),
    )
    write_pipeline_manifest(manifest=manifest, target=paths.pipeline_manifest, summary_target=paths.pipeline_summary)
    write_stage_status(document=document, target=paths.stage_status)
    return manifest


# ---------------------------------------------------------------------------
# Corpus orchestration
# ---------------------------------------------------------------------------


def _discover_corpus_documents(*, corpus_root: Path, document_list: list[str] | None, max_documents: int | None) -> list[tuple[str, Path | None]]:
    """Find document ids and (optional) input PDFs under the corpus root.

    A document is one immediate sub-directory of ``corpus_root``. The first
    ``*.pdf`` file under that directory becomes the document's input PDF if
    present; otherwise the document is enqueued without a PDF (the runner
    will mark backend_smoke as ``skipped``/``blocked``).
    """

    corpus_root = Path(corpus_root)
    if not corpus_root.is_dir():
        return []
    candidates: list[tuple[str, Path | None]] = []
    for child in sorted(corpus_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if document_list and child.name not in document_list:
            continue
        pdf_files = sorted(child.glob("*.pdf"))
        pdf = pdf_files[0] if pdf_files else None
        candidates.append((child.name, pdf))
        if max_documents is not None and len(candidates) >= max_documents:
            break
    return candidates


def run_corpus(
    *,
    corpus_root: Path,
    out_dir: Path,
    work_dir: Path | None = None,
    backends: list[str] | None = None,
    max_documents: int | None = None,
    document_list: list[str] | None = None,
    repo_root: Path | None = None,
    timeout_seconds: int = 1500,
    strict: bool = False,
    stage_overrides: _StageOverrides | None = None,
    generated_at: str | None = None,
) -> tuple[PipelineManifest, CorpusEvaluation]:
    """Run the MVP pipeline against a corpus subset."""

    from pdf2md.pipeline.io import write_corpus_evaluation, write_pipeline_manifest, write_stage_status

    repo_root = (repo_root or Path.cwd()).resolve()
    out_dir = Path(out_dir).resolve()
    work_dir = Path(work_dir).resolve() if work_dir else out_dir / "work"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    selected = _discover_corpus_documents(
        corpus_root=Path(corpus_root),
        document_list=document_list,
        max_documents=max_documents,
    )

    documents: list[DocumentRecord] = []
    for doc_id, pdf in selected:
        paths = corpus_document_paths(
            document_id=doc_id,
            corpus_out_dir=out_dir,
            corpus_work_dir=work_dir,
        ).ensure()
        document = _run_stages_for_document(
            document_id=doc_id,
            input_pdf=pdf,
            paths=paths,
            repo_root=repo_root,
            backends=backends,
            timeout_seconds=timeout_seconds,
            strict=strict,
            overrides=stage_overrides,
        )
        documents.append(document)
        write_stage_status(document=document, target=paths.stage_status)

    manifest = PipelineManifest(
        generated_at=generated_at or _utc_now(),
        mode="corpus_subset",
        corpus_root=str(corpus_root),
        out_dir=str(out_dir),
        work_dir=str(work_dir),
        selected_backends=list(backends or []),
        documents=documents,
        warnings=[],
        errors=[],
        mvp_readiness=_mvp_readiness(documents),
    )
    write_pipeline_manifest(
        manifest=manifest,
        target=out_dir / "pipeline_manifest.json",
        summary_target=out_dir / "pipeline_summary.txt",
    )

    # Corpus evaluation aggregate
    stage_bottlenecks: dict[str, int] = {s.value: 0 for s in STAGE_ORDER}
    backend_eligibility: dict[str, int] = {}
    export_avail: dict[str, bool] = {}
    confidences: list[float] = []
    for d in documents:
        export_status = next(
            (
                s.status if isinstance(s.status, str) else s.status.value
                for s in d.stages
                if (s.name if isinstance(s.name, str) else s.name.value) == StageName.EXPORT.value
            ),
            None,
        )
        export_avail[d.document_id] = export_status == StageStatus.SUCCEEDED.value
        for backend in d.eligible_backends:
            backend_eligibility[backend] = backend_eligibility.get(backend, 0) + 1
        for s in d.stages:
            if (s.status if isinstance(s.status, str) else s.status.value) == StageStatus.FAILED.value:
                stage_bottlenecks[s.name if isinstance(s.name, str) else s.name.value] += 1

    evaluation = CorpusEvaluation(
        generated_at=generated_at or _utc_now(),
        corpus_root=str(corpus_root),
        out_dir=str(out_dir),
        selected_documents=[d.document_id for d in documents],
        document_results={
            d.document_id: (d.result if isinstance(d.result, str) else d.result.value) for d in documents
        },
        stage_bottlenecks=stage_bottlenecks,
        backend_eligibility=backend_eligibility,
        final_export_availability=export_avail,
        confidence_summary={
            "documents_with_export": int(sum(1 for v in export_avail.values() if v)),
            "documents_total": len(documents),
        },
        warnings=[],
        mvp_readiness=_mvp_readiness(documents),
    )
    write_corpus_evaluation(
        evaluation=evaluation,
        target=out_dir / "mvp_corpus_evaluation.json",
        summary_target=out_dir / "mvp_corpus_summary.txt",
    )
    if strict and any(
        (d.result if isinstance(d.result, str) else d.result.value) == DocumentResult.FAILED.value
        for d in documents
    ):
        raise SystemExit(1)
    return manifest, evaluation


__all__ = [
    "PIPELINE_SCHEMA_VERSION",
    "StageName",
    "STAGE_ORDER",
    "StageStatus",
    "DocumentResult",
    "MvpReadiness",
    "StageRecord",
    "DocumentRecord",
    "PipelineManifest",
    "CorpusEvaluation",
    "run_one_document",
    "run_corpus",
    "_StageOverrides",
]
