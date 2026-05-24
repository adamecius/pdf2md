"""Plan 18 — single-document pipeline orchestrator.

Chains the six existing pipeline stages (backend execution → connector →
calibration → consensus → linked structure → export) using the existing
module-level Python APIs. Backend execution remains a subprocess
(``run_configured_backends``) because backends live in separate conda
environments; every other stage is an in-process Python call.

Stage failures are isolated: when ``keep_going`` is set the orchestrator
records the error, marks downstream stages as ``not_started``, and emits
``pipeline_manifest.json`` + ``pipeline_summary.txt`` describing what
happened.
"""

from __future__ import annotations

import importlib
import json
import logging
import shutil
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pdf2md.backends.runner import run_configured_backends
from pdf2md.config import get_enabled_backends
from pdf2md.connectors.common import BackendConnectorConfig, connect_raw_dir
from pdf2md.consensus.factory import ConsensusFactorySettings, build_consensus_ir
from pdf2md.consensus.io import load_consensus_inputs, write_consensus_outputs
from pdf2md.export.docling import DoclingExportSettings
from pdf2md.export.io import build_export_run, load_export_inputs, write_export_outputs
from pdf2md.export.markdown import MarkdownExportSettings
from pdf2md.export.rag import RagExportSettings
from pdf2md.linking.builder import build_linked_structure
from pdf2md.linking.io import load_linker_inputs, write_linker_outputs
from pdf2md.pipeline.artifacts import RunLayout
from pdf2md.pipeline.reporting import build_orchestrator_pipeline_summary

logger = logging.getLogger(__name__)

PIPELINE_MANIFEST_SCHEMA_NAME = "pdf2md.PipelineManifest"
PIPELINE_MANIFEST_SCHEMA_VERSION = 1

STAGE_BACKEND_EXECUTION = "backend_execution"
STAGE_CONNECTOR = "connector"
STAGE_CALIBRATION = "calibration"
STAGE_CONSENSUS = "consensus"
STAGE_LINKING = "linking"
STAGE_EXPORT = "export"

ALL_STAGE_NAMES: tuple[str, ...] = (
    STAGE_BACKEND_EXECUTION,
    STAGE_CONNECTOR,
    STAGE_CALIBRATION,
    STAGE_CONSENSUS,
    STAGE_LINKING,
    STAGE_EXPORT,
)


@dataclass
class PipelineSettings:
    """Configuration for a single ``run_pipeline`` invocation.

    Attributes:
        config: Backend configuration dictionary used by the runner.
        priors_dir: Optional directory containing calibration prior JSON
            files to copy into the run's ``priors/`` subtree.
        force: When true, delete an existing ``out_dir`` before running.
        dry_run: When true, print the plan and return without writing.
        timeout: Per-backend subprocess timeout in seconds.
        keep_going: When true, continue downstream stages even after
            individual stage failures.
        skip_calibration: Skip the calibration copy stage.
        skip_export: Skip the export stage.
        verbose: Enable verbose stage logging.
    """

    config: dict
    priors_dir: Path | None = None
    force: bool = False
    dry_run: bool = False
    timeout: int | None = None
    keep_going: bool = True
    skip_calibration: bool = False
    skip_export: bool = False
    verbose: bool = False


@dataclass
class StageStatus:
    """Per-stage status entry written into ``pipeline_manifest.json``.

    Attributes:
        name: Stage identifier (one of ``ALL_STAGE_NAMES``).
        status: ``success``, ``failed``, ``skipped`` or ``not_started``.
        started_at: ISO-8601 UTC timestamp at stage start.
        finished_at: ISO-8601 UTC timestamp at stage finish.
        duration_seconds: Wall-clock stage duration.
        output_dir: Filesystem path of the stage's output directory.
        warnings: Stage-level warning messages.
        error: Failure message, when ``status == "failed"``.
    """

    name: str
    status: str = "not_started"  # success | failed | skipped | not_started
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    output_dir: str | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of this stage entry."""
        payload = {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "output_dir": self.output_dir,
            "warnings": list(self.warnings),
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass
class PipelineResult:
    """Result of a single ``run_pipeline`` invocation.

    Attributes:
        overall_status: ``success``, ``partial``, ``failed`` or
            ``not_started`` (dry run).
        stages: StageStatus entries in canonical stage order.
        manifest_path: Path of the written ``pipeline_manifest.json``.
        consensus_ir_path: Path of ``consensus_ir.json`` when consensus
            succeeded, otherwise None.
        docling_path: Path of the Docling JSON when export succeeded,
            otherwise None.
        markdown_path: Path of the markdown preview when export
            succeeded, otherwise None.
        warnings: Run-level warning messages.
    """

    overall_status: str  # "success" | "partial" | "failed"
    stages: list[StageStatus]
    manifest_path: Path
    consensus_ir_path: Path | None
    docling_path: Path | None
    markdown_path: Path | None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _empty_stages() -> dict[str, StageStatus]:
    return {name: StageStatus(name=name) for name in ALL_STAGE_NAMES}


def _resolve_connector_callable(backend: str) -> Callable[..., Any] | None:
    """Try to import ``backend.<name>.connector.connect``; return None if absent."""

    try:
        module = importlib.import_module(f"backend.{backend}.connector")
    except Exception:  # noqa: BLE001 — connector is optional
        return None
    connect = getattr(module, "connect", None)
    if callable(connect):
        return connect
    return None


def _backends_with_raw_success(layout: RunLayout, requested: list[str]) -> list[str]:
    """Return the backends whose ``raw/<name>/status.json`` reports success."""

    succeeded: list[str] = []
    for name in requested:
        status_path = layout.raw_backend_dir(name) / "status.json"
        if not status_path.exists():
            continue
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if data.get("success") is True:
            succeeded.append(name)
    return succeeded


def _mark_remaining_not_started(stages: dict[str, StageStatus], start_index: int) -> None:
    for name in ALL_STAGE_NAMES[start_index:]:
        stage = stages[name]
        if stage.status == "not_started":
            continue  # already touched (e.g. explicit skip)
        # Should not happen for genuinely not-yet-run stages; keep as-is.

    # Leave already-final statuses untouched. The default of new StageStatus is
    # "not_started" so nothing to do explicitly; this helper exists for clarity.


def _write_manifest(layout: RunLayout, manifest: dict) -> None:
    layout.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_summary(layout: RunLayout, manifest: dict) -> None:
    layout.summary_path.write_text(
        build_orchestrator_pipeline_summary(manifest), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Stage 1 — backend execution
# ---------------------------------------------------------------------------


def _run_stage_backends(
    *,
    input_pdf: Path,
    layout: RunLayout,
    settings: PipelineSettings,
    requested_backends: list[str],
    stage: StageStatus,
) -> list[str]:
    """Stage 1: run configured backends via subprocess. Returns succeeded list."""

    stage.started_at = _now_iso()
    started = datetime.now(UTC)
    stage.output_dir = str(layout.raw_dir)
    try:
        run_configured_backends(
            input_pdf=input_pdf,
            config=settings.config,
            repo_root=Path.cwd(),
            work_dir_override=layout.run_dir.parent,
            run_name_override=layout.run_dir.name,
            force=True,  # we already own out_dir; backend runner refuses pre-existing dirs
            dry_run=False,
            timeout_override=settings.timeout,
            keep_going=settings.keep_going,
        )
    except Exception as exc:  # noqa: BLE001
        stage.status = "failed"
        stage.error = f"{type(exc).__name__}: {exc}"
        stage.warnings.append("backend_runner_exception")
        logger.exception("backend execution failed")
        stage.finished_at = _now_iso()
        stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
        return []

    succeeded = _backends_with_raw_success(layout, requested_backends)
    stage.finished_at = _now_iso()
    stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()

    if not succeeded:
        stage.status = "failed"
        stage.error = "no backends produced successful raw output"
    elif len(succeeded) < len(requested_backends):
        stage.status = "success"
        failed = sorted(set(requested_backends) - set(succeeded))
        stage.warnings.append(f"backends_failed:{','.join(failed)}")
    else:
        stage.status = "success"
    return succeeded


# ---------------------------------------------------------------------------
# Stage 2 — connector
# ---------------------------------------------------------------------------


def _run_stage_connector(
    *,
    layout: RunLayout,
    document_id: str,
    succeeded_backends: list[str],
    stage: StageStatus,
) -> list[str]:
    """Stage 2: invoke each backend's connector. Returns backends with IR."""

    stage.started_at = _now_iso()
    started = datetime.now(UTC)
    stage.output_dir = str(layout.connector_dir)

    if not succeeded_backends:
        stage.status = "not_started"
        stage.finished_at = stage.started_at
        stage.duration_seconds = 0.0
        return []

    connected: list[str] = []
    errors: list[str] = []
    for backend in succeeded_backends:
        raw_dir = layout.raw_backend_dir(backend)
        connector_fn = _resolve_connector_callable(backend)
        try:
            if connector_fn is not None:
                result = connector_fn(raw_dir, document_id, layout.connector_dir)
            else:
                config = BackendConnectorConfig(
                    backend=backend, default_backend_version=None
                )
                result = connect_raw_dir(
                    raw_dir=raw_dir,
                    document_id=document_id,
                    config=config,
                    out_dir=layout.connector_dir,
                )
            stage.warnings.extend(
                f"{backend}:{w}" for w in getattr(result, "warnings", []) or []
            )
            connected.append(backend)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{backend}: {type(exc).__name__}: {exc}")
            logger.exception("connector failed for %s", backend)

    stage.finished_at = _now_iso()
    stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()

    if not connected:
        stage.status = "failed"
        stage.error = "; ".join(errors) if errors else "no backends produced IR"
    else:
        stage.status = "success"
        if errors:
            stage.warnings.extend(errors)
    return connected


# ---------------------------------------------------------------------------
# Stage 3 — calibration (copy-only)
# ---------------------------------------------------------------------------


def _run_stage_calibration(
    *,
    layout: RunLayout,
    settings: PipelineSettings,
    backends: list[str],
    stage: StageStatus,
) -> bool:
    """Stage 3: copy ``<priors_dir>/<backend>.json`` files. Returns True if any copied."""

    stage.started_at = _now_iso()
    started = datetime.now(UTC)
    stage.output_dir = str(layout.priors_dir)

    if settings.skip_calibration or settings.priors_dir is None:
        stage.status = "skipped"
        stage.finished_at = _now_iso()
        stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
        if settings.priors_dir is None:
            stage.warnings.append("no_priors_dir_provided")
        else:
            stage.warnings.append("skip_calibration_flag")
        return False

    priors_src = Path(settings.priors_dir)
    if not priors_src.exists() or not priors_src.is_dir():
        stage.status = "skipped"
        stage.warnings.append(f"priors_dir_missing:{priors_src}")
        stage.finished_at = _now_iso()
        stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
        return False

    layout.priors_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for backend in backends:
        source = priors_src / f"{backend}.json"
        if not source.exists():
            stage.warnings.append(f"prior_missing:{backend}")
            continue
        target = layout.priors_dir / f"{backend}.json"
        shutil.copy2(source, target)
        copied.append(backend)

    stage.finished_at = _now_iso()
    stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
    if not copied:
        stage.status = "skipped"
        stage.warnings.append("no_priors_copied")
        return False
    stage.status = "success"
    return True


# ---------------------------------------------------------------------------
# Stage 4 — consensus
# ---------------------------------------------------------------------------


def _run_stage_consensus(
    *,
    layout: RunLayout,
    document_id: str,
    priors_loaded: bool,
    stage: StageStatus,
) -> Path | None:
    stage.started_at = _now_iso()
    started = datetime.now(UTC)
    stage.output_dir = str(layout.consensus_dir)
    try:
        layout.consensus_dir.mkdir(parents=True, exist_ok=True)
        loaded = load_consensus_inputs(
            connector_root=layout.connector_dir,
            document_id=document_id,
            priors_root=layout.priors_dir if priors_loaded else None,
        )
        stage.warnings.extend(loaded.warnings)
        if not loaded.pages_by_backend:
            stage.status = "failed"
            stage.error = "no pages loaded for any backend"
            stage.finished_at = _now_iso()
            stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
            return None
        result = build_consensus_ir(
            document_id=document_id,
            pages_by_backend=loaded.pages_by_backend,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            settings=ConsensusFactorySettings(),
        )
        stage.warnings.extend(result.warnings)
        write_consensus_outputs(result=result, out_dir=layout.consensus_dir)
    except Exception as exc:  # noqa: BLE001
        stage.status = "failed"
        stage.error = f"{type(exc).__name__}: {exc}"
        logger.exception("consensus failed")
        stage.finished_at = _now_iso()
        stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
        return None
    stage.status = "success"
    stage.finished_at = _now_iso()
    stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
    return layout.consensus_dir / "consensus_ir.json"


# ---------------------------------------------------------------------------
# Stage 5 — linked structure
# ---------------------------------------------------------------------------


def _run_stage_linking(
    *,
    layout: RunLayout,
    consensus_ir_path: Path,
    priors_loaded: bool,
    stage: StageStatus,
) -> Path | None:
    stage.started_at = _now_iso()
    started = datetime.now(UTC)
    stage.output_dir = str(layout.linked_dir)
    try:
        layout.linked_dir.mkdir(parents=True, exist_ok=True)
        consensus_report_path = layout.consensus_dir / "reports" / "consensus_report.json"
        loaded = load_linker_inputs(
            consensus_ir_path=consensus_ir_path,
            consensus_report_path=consensus_report_path if consensus_report_path.exists() else None,
            entities_root=layout.connector_dir,
            priors_root=layout.priors_dir if priors_loaded else None,
        )
        stage.warnings.extend(loaded.warnings)
        result = build_linked_structure(
            consensus=loaded.consensus,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            consensus_report=loaded.consensus_report,
            source_consensus_ir=str(consensus_ir_path),
            source_consensus_report=str(consensus_report_path) if consensus_report_path.exists() else None,
            source_entity_documents=loaded.source_entity_documents,
            source_prior_documents=loaded.source_prior_documents,
        )
        stage.warnings.extend(result.warnings)
        write_linker_outputs(result=result, out_dir=layout.linked_dir)
    except Exception as exc:  # noqa: BLE001
        stage.status = "failed"
        stage.error = f"{type(exc).__name__}: {exc}"
        logger.exception("linking failed")
        stage.finished_at = _now_iso()
        stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
        return None
    stage.status = "success"
    stage.finished_at = _now_iso()
    stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
    return layout.linked_dir / "linked_structure.json"


# ---------------------------------------------------------------------------
# Stage 6 — export
# ---------------------------------------------------------------------------


def _run_stage_export(
    *,
    layout: RunLayout,
    linked_structure_path: Path,
    consensus_ir_path: Path,
    input_pdf: Path,
    document_id: str,
    stage: StageStatus,
) -> tuple[Path | None, Path | None]:
    stage.started_at = _now_iso()
    started = datetime.now(UTC)
    stage.output_dir = str(layout.export_dir)
    try:
        layout.export_dir.mkdir(parents=True, exist_ok=True)
        loaded = load_export_inputs(
            linked_structure_path=linked_structure_path,
            consensus_ir_path=consensus_ir_path,
        )
        stage.warnings.extend(loaded.warnings)
        result = build_export_run(
            linked=loaded.linked,
            consensus=loaded.consensus,
            source_linked_structure=str(linked_structure_path),
            source_consensus_ir=str(consensus_ir_path),
            source_pdf=str(input_pdf),
            docling_settings=DoclingExportSettings(),
            rag_settings=RagExportSettings(),
            markdown_settings=MarkdownExportSettings(),
        )
        stage.warnings.extend(result.warnings)
        write_export_outputs(result=result, out_dir=layout.export_dir)
    except Exception as exc:  # noqa: BLE001
        stage.status = "failed"
        stage.error = f"{type(exc).__name__}: {exc}"
        logger.exception("export failed")
        stage.finished_at = _now_iso()
        stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
        return None, None
    stage.status = "success"
    stage.finished_at = _now_iso()
    stage.duration_seconds = (datetime.now(UTC) - started).total_seconds()
    docling_path = layout.export_dir / f"docling/{document_id}.docling.json"
    markdown_path = layout.export_dir / f"markdown/{document_id}.preview.md"
    return (
        docling_path if docling_path.exists() else None,
        markdown_path if markdown_path.exists() else None,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _classify_overall(
    *,
    stages: dict[str, StageStatus],
    requested_backends: list[str],
    succeeded_backends: list[str],
    skip_export: bool,
) -> str:
    backend_stage = stages[STAGE_BACKEND_EXECUTION]
    consensus_stage = stages[STAGE_CONSENSUS]
    if not succeeded_backends or backend_stage.status == "failed":
        return "failed"
    if consensus_stage.status == "failed":
        return "failed"
    terminal_name = STAGE_CONSENSUS if skip_export else STAGE_EXPORT
    terminal_stage = stages[terminal_name]
    if terminal_stage.status != "success":
        return "failed"
    if len(succeeded_backends) < len(requested_backends):
        return "partial"
    # check none of the intermediate stages failed
    for stage in stages.values():
        if stage.status == "failed":
            return "partial"
    return "success"


def _build_manifest_dict(
    *,
    document_id: str,
    input_pdf: Path,
    requested_backends: list[str],
    succeeded_backends: list[str],
    stages: dict[str, StageStatus],
    overall_status: str,
) -> dict:
    return {
        "schema_name": PIPELINE_MANIFEST_SCHEMA_NAME,
        "schema_version": PIPELINE_MANIFEST_SCHEMA_VERSION,
        "document_id": document_id,
        "input_pdf": str(input_pdf),
        "backends_requested": list(requested_backends),
        "backends_succeeded": list(succeeded_backends),
        "stages": [stages[name].to_dict() for name in ALL_STAGE_NAMES],
        "overall_status": overall_status,
    }


def run_pipeline(
    input_pdf: Path,
    out_dir: Path,
    settings: PipelineSettings,
) -> PipelineResult:
    """Execute the six-stage pipeline for one PDF.

    See :class:`PipelineSettings` for available knobs. Returns a
    :class:`PipelineResult` summarising the run; the canonical manifest is
    always written to ``<out_dir>/pipeline_manifest.json`` (unless
    ``dry_run`` is set).
    """

    input_pdf = Path(input_pdf)
    out_dir = Path(out_dir)
    layout = RunLayout(run_dir=out_dir)
    document_id = input_pdf.stem
    requested = list(get_enabled_backends(settings.config).keys())

    stages = _empty_stages()

    if settings.dry_run:
        print("[dry-run] Planned pipeline:")
        print(f"  input_pdf: {input_pdf}")
        print(f"  out_dir:   {out_dir}")
        print(f"  backends:  {requested}")
        print("  stages:")
        for name in ALL_STAGE_NAMES:
            print(f"    - {name}")
        # Don't materialise files; return a not-started result.
        result = PipelineResult(
            overall_status="not_started",
            stages=[stages[name] for name in ALL_STAGE_NAMES],
            manifest_path=layout.manifest_path,
            consensus_ir_path=None,
            docling_path=None,
            markdown_path=None,
            warnings=["dry_run"],
        )
        return result

    if out_dir.exists() and settings.force:
        shutil.rmtree(out_dir)
    layout.create_dirs()

    if input_pdf.exists() and input_pdf.is_file():
        try:
            shutil.copy2(input_pdf, layout.input_dir / input_pdf.name)
        except Exception as exc:  # noqa: BLE001 — copy is best-effort
            logger.warning("failed to copy input PDF: %s", exc)

    warnings: list[str] = []

    if not requested:
        msg = "no enabled backends configured"
        stages[STAGE_BACKEND_EXECUTION].status = "failed"
        stages[STAGE_BACKEND_EXECUTION].error = msg
        stages[STAGE_BACKEND_EXECUTION].started_at = _now_iso()
        stages[STAGE_BACKEND_EXECUTION].finished_at = _now_iso()
        manifest = _build_manifest_dict(
            document_id=document_id,
            input_pdf=input_pdf,
            requested_backends=requested,
            succeeded_backends=[],
            stages=stages,
            overall_status="failed",
        )
        _write_manifest(layout, manifest)
        _write_summary(layout, manifest)
        return PipelineResult(
            overall_status="failed",
            stages=[stages[name] for name in ALL_STAGE_NAMES],
            manifest_path=layout.manifest_path,
            consensus_ir_path=None,
            docling_path=None,
            markdown_path=None,
            warnings=[msg],
        )

    succeeded = _run_stage_backends(
        input_pdf=input_pdf,
        layout=layout,
        settings=settings,
        requested_backends=requested,
        stage=stages[STAGE_BACKEND_EXECUTION],
    )

    consensus_ir_path: Path | None = None
    linked_structure_path: Path | None = None
    docling_path: Path | None = None
    markdown_path: Path | None = None
    priors_loaded = False

    can_proceed = bool(succeeded) and (
        settings.keep_going or stages[STAGE_BACKEND_EXECUTION].status == "success"
    )
    if not can_proceed:
        manifest = _build_manifest_dict(
            document_id=document_id,
            input_pdf=input_pdf,
            requested_backends=requested,
            succeeded_backends=succeeded,
            stages=stages,
            overall_status=_classify_overall(
                stages=stages,
                requested_backends=requested,
                succeeded_backends=succeeded,
                skip_export=settings.skip_export,
            ),
        )
        _write_manifest(layout, manifest)
        _write_summary(layout, manifest)
        return PipelineResult(
            overall_status=manifest["overall_status"],
            stages=[stages[name] for name in ALL_STAGE_NAMES],
            manifest_path=layout.manifest_path,
            consensus_ir_path=None,
            docling_path=None,
            markdown_path=None,
            warnings=warnings,
        )

    connected = _run_stage_connector(
        layout=layout,
        document_id=document_id,
        succeeded_backends=succeeded,
        stage=stages[STAGE_CONNECTOR],
    )

    if connected:
        priors_loaded = _run_stage_calibration(
            layout=layout,
            settings=settings,
            backends=connected,
            stage=stages[STAGE_CALIBRATION],
        )
    else:
        stages[STAGE_CALIBRATION].status = "not_started"

    if connected and stages[STAGE_CONNECTOR].status == "success":
        consensus_ir_path = _run_stage_consensus(
            layout=layout,
            document_id=document_id,
            priors_loaded=priors_loaded,
            stage=stages[STAGE_CONSENSUS],
        )
    else:
        stages[STAGE_CONSENSUS].status = "not_started"

    if consensus_ir_path is not None:
        linked_structure_path = _run_stage_linking(
            layout=layout,
            consensus_ir_path=consensus_ir_path,
            priors_loaded=priors_loaded,
            stage=stages[STAGE_LINKING],
        )
    else:
        stages[STAGE_LINKING].status = "not_started"

    if settings.skip_export:
        stages[STAGE_EXPORT].status = "skipped"
        stages[STAGE_EXPORT].warnings.append("skip_export_flag")
    elif linked_structure_path is not None and consensus_ir_path is not None:
        docling_path, markdown_path = _run_stage_export(
            layout=layout,
            linked_structure_path=linked_structure_path,
            consensus_ir_path=consensus_ir_path,
            input_pdf=input_pdf,
            document_id=document_id,
            stage=stages[STAGE_EXPORT],
        )
    else:
        stages[STAGE_EXPORT].status = "not_started"

    overall_status = _classify_overall(
        stages=stages,
        requested_backends=requested,
        succeeded_backends=succeeded,
        skip_export=settings.skip_export,
    )

    manifest = _build_manifest_dict(
        document_id=document_id,
        input_pdf=input_pdf,
        requested_backends=requested,
        succeeded_backends=succeeded,
        stages=stages,
        overall_status=overall_status,
    )
    _write_manifest(layout, manifest)
    _write_summary(layout, manifest)

    return PipelineResult(
        overall_status=overall_status,
        stages=[stages[name] for name in ALL_STAGE_NAMES],
        manifest_path=layout.manifest_path,
        consensus_ir_path=consensus_ir_path,
        docling_path=docling_path,
        markdown_path=markdown_path,
        warnings=warnings,
    )


__all__ = [
    "PipelineSettings",
    "StageStatus",
    "PipelineResult",
    "run_pipeline",
    "PIPELINE_MANIFEST_SCHEMA_NAME",
    "PIPELINE_MANIFEST_SCHEMA_VERSION",
    "ALL_STAGE_NAMES",
]
