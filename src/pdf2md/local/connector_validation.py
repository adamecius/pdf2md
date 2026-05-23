"""Connector PageExtractionIR validation wrapper (Plan 10).

This module reuses the repository's existing connector entrypoint
``pdf2md.connectors.common.connect_raw_dir`` to convert real raw backend
outputs (typically successful Plan 9 smoke results) into ``PageExtractionIR``
and classify the outcome per backend. It does not implement a parallel
connector architecture, does not execute backends, and does not validate
``EntityProposalDocument`` for Plan 10 pass/fail.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from pdf2md.connectors.common import BackendConnectorConfig, ConnectorResult, connect_raw_dir
from pdf2md.models.ir import BlockKind, PageExtractionIR

CONNECTOR_VALIDATION_SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "validate_connectors_page_ir"
DEFAULT_PREFERRED_GATE_MINIMUM = 2
DEFAULT_DOCUMENT_ID = "plan10_doc"
PLAN9_SUCCESS_STATUS = "success"


class ConnectorValidationStatus(str, Enum):
    """The five Plan 10 connector validation statuses."""

    VALIDATED = "validated"
    CONNECTOR_CRASH = "connector_crash"
    SCHEMA_FAILED = "schema_failed"
    MISSING_REQUIRED_OUTPUT = "missing_required_output"
    DEFERRED_FROM_PLAN_9 = "deferred_from_plan_9"


_NEXT_ACTIONS: dict[ConnectorValidationStatus, str] = {
    ConnectorValidationStatus.VALIDATED: (
        "Backend PageExtractionIR validated; downstream Plan 11 may consume it for "
        "EntityProposalDocument validation."
    ),
    ConnectorValidationStatus.CONNECTOR_CRASH: (
        "Connector raised an exception; inspect the error and fix the connector defect "
        "or supply corrected raw backend output."
    ),
    ConnectorValidationStatus.SCHEMA_FAILED: (
        "Connector produced PageExtractionIR-like data that failed schema validation; "
        "inspect validation_error_summary and fix the connector output."
    ),
    ConnectorValidationStatus.MISSING_REQUIRED_OUTPUT: (
        "Backend raw output directory is missing files required by the connector; "
        "re-run the backend or supply corrected raw artefacts."
    ),
    ConnectorValidationStatus.DEFERRED_FROM_PLAN_9: (
        "Backend did not produce a successful Plan 9 output; rerun Plan 9 for this "
        "backend or supply an approved raw output."
    ),
}


class _ConnectorBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ConnectorValidationResult(_ConnectorBaseModel):
    """Per-backend connector validation entry."""

    backend_name: str
    plan9_status: str | None = None
    raw_output_dir: str | None = None
    connector_entrypoint: str
    status: ConnectorValidationStatus
    page_count: int = 0
    block_count: int = 0
    block_kind_counts: dict[str, int] = Field(default_factory=dict)
    has_text: bool = False
    has_bboxes: bool = False
    has_provenance: bool = False
    raw_artefact_references: list[str] = Field(default_factory=list)
    semantic_quality_passed: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    validation_error_summary: str | None = None
    page_extraction_ir_path: str | None = None
    next_action: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorValidationReport(_ConnectorBaseModel):
    """Plan 10 connector validation report."""

    schema_name: Literal["pdf2md.ConnectorPageExtractionIRValidationReport"] = (
        "pdf2md.ConnectorPageExtractionIRValidationReport"
    )
    schema_version: Literal["1.0.0"] = CONNECTOR_VALIDATION_SCHEMA_VERSION
    generated_at: str
    tool_name: Literal["validate_connectors_page_ir"] = TOOL_NAME
    plan9_report_path: str | None = None
    gate_mode: Literal["preferred", "reduced"] = "preferred"
    preferred_gate_minimum: int = DEFAULT_PREFERRED_GATE_MINIMUM
    preferred_gate_passed: bool = False
    minimum_gate_passed: bool = False
    human_reduced_gate_required: bool = False
    total_backends_considered: int = 0
    backends_validated: int = 0
    backends_failed: int = 0
    backends_deferred: int = 0
    results: list[ConnectorValidationResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_counts(self) -> ConnectorValidationReport:
        names = [r.backend_name for r in self.results]
        if len(names) != len(set(names)):
            raise ValueError("backend names must be unique")
        validated = _count_status(self.results, ConnectorValidationStatus.VALIDATED)
        deferred = _count_status(self.results, ConnectorValidationStatus.DEFERRED_FROM_PLAN_9)
        failed = sum(
            _count_status(self.results, s)
            for s in (
                ConnectorValidationStatus.CONNECTOR_CRASH,
                ConnectorValidationStatus.SCHEMA_FAILED,
                ConnectorValidationStatus.MISSING_REQUIRED_OUTPUT,
            )
        )
        if self.total_backends_considered != len(self.results):
            raise ValueError("total_backends_considered must match results length")
        if self.backends_validated != validated:
            raise ValueError("backends_validated must match validated results")
        if self.backends_failed != failed:
            raise ValueError("backends_failed must match failed results")
        if self.backends_deferred != deferred:
            raise ValueError("backends_deferred must match deferred results")
        if validated + failed + deferred != self.total_backends_considered:
            raise ValueError(
                "validated, failed and deferred counts must cover every backend"
            )
        return self


def _status_value(result: Any) -> str:
    status = result.status if hasattr(result, "status") else None
    if isinstance(status, ConnectorValidationStatus):
        return status.value
    return str(status)


def _count_status(results: list[Any], status: ConnectorValidationStatus) -> int:
    return sum(1 for r in results if _status_value(r) == status.value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_noise_text(text: str) -> bool:
    """Detect parser noise, log lines, or file paths that are not document content."""

    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) < 3:
        return True
    # Log-line markers like "INFO: ...", "ERROR ...", "[DEBUG] ..."
    if re.match(r"^(\[)?(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|TRACE)(\])?[\s:]", stripped, re.I):
        return True
    # Absolute-path-only blocks
    if re.fullmatch(r"/(?:[A-Za-z0-9_.\-]+/?)+", stripped):
        return True
    # Pure pythonic traceback or stack-frame markers
    if stripped.startswith("Traceback (most recent call last)"):
        return True
    if re.match(r'^\s*File "[^"]+", line \d+', stripped):
        return True
    return False


def _semantic_quality_passed(pages: list[PageExtractionIR]) -> tuple[bool, list[str]]:
    """Return (passed, semantic_warnings)."""

    warnings: list[str] = []
    if not pages:
        warnings.append("semantic_no_pages")
        return False, warnings
    total_blocks = sum(len(p.blocks) for p in pages)
    if total_blocks == 0:
        warnings.append("semantic_no_blocks")
        return False, warnings
    meaningful = 0
    noisy = 0
    for page in pages:
        for block in page.blocks:
            if _is_noise_text(block.text):
                noisy += 1
            else:
                meaningful += 1
    if meaningful == 0:
        warnings.append("semantic_all_blocks_noise_or_empty")
        return False, warnings
    if noisy > meaningful:
        warnings.append("semantic_mostly_noise")
    return True, warnings


def _aggregate_block_kind_counts(pages: list[PageExtractionIR]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for page in pages:
        for block in page.blocks:
            key = block.kind.value if isinstance(block.kind, BlockKind) else str(block.kind)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _collect_raw_artefact_references(pages: list[PageExtractionIR]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for page in pages:
        if page.raw_artifact_ref and page.raw_artifact_ref not in seen:
            seen.add(page.raw_artifact_ref)
            refs.append(page.raw_artifact_ref)
        for block in page.blocks:
            if block.raw_ref and block.raw_ref not in seen:
                seen.add(block.raw_ref)
                refs.append(block.raw_ref)
    return refs


def _has_provenance(pages: list[PageExtractionIR]) -> bool:
    if not pages:
        return False
    return all(bool(p.backend) for p in pages)


def _has_text(pages: list[PageExtractionIR]) -> bool:
    return any(bool(b.text.strip()) for p in pages for b in p.blocks)


def _has_bboxes(pages: list[PageExtractionIR]) -> bool:
    return any(b.bbox is not None for p in pages for b in p.blocks)


def _revalidate_pages(pages_dump: list[Mapping[str, Any]]) -> tuple[bool, str | None]:
    """Re-validate each page dict against PageExtractionIR. Return (ok, error_summary)."""

    for index, page_dump in enumerate(pages_dump):
        try:
            PageExtractionIR.model_validate(page_dump)
        except ValidationError as exc:
            return False, f"page {index}: {exc}"
        except Exception as exc:  # noqa: BLE001 - any failure here is a schema failure
            return False, f"page {index}: {exc}"
    return True, None


def _write_page_extraction_ir(
    *,
    backend_name: str,
    pages: list[PageExtractionIR],
    out_dir: Path,
) -> Path:
    """Write a single page_extraction_ir.json file aggregating all pages for a backend."""

    backend_dir = out_dir / backend_name
    backend_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "pdf2md.ConnectorPageExtractionIRBundle",
        "schema_version": CONNECTOR_VALIDATION_SCHEMA_VERSION,
        "backend": backend_name,
        "page_count": len(pages),
        "pages": [json.loads(p.model_dump_json()) for p in pages],
    }
    target = backend_dir / "page_extraction_ir.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def _result(
    *,
    backend_name: str,
    status: ConnectorValidationStatus,
    plan9_status: str | None = None,
    raw_output_dir: str | None = None,
    connector_entrypoint: str = "pdf2md.connectors.common.connect_raw_dir",
    page_count: int = 0,
    block_count: int = 0,
    block_kind_counts: dict[str, int] | None = None,
    has_text: bool = False,
    has_bboxes: bool = False,
    has_provenance: bool = False,
    raw_artefact_references: list[str] | None = None,
    semantic_quality_passed: bool = False,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    validation_error_summary: str | None = None,
    page_extraction_ir_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ConnectorValidationResult:
    return ConnectorValidationResult(
        backend_name=backend_name,
        plan9_status=plan9_status,
        raw_output_dir=raw_output_dir,
        connector_entrypoint=connector_entrypoint,
        status=status,
        page_count=page_count,
        block_count=block_count,
        block_kind_counts=block_kind_counts or {},
        has_text=has_text,
        has_bboxes=has_bboxes,
        has_provenance=has_provenance,
        raw_artefact_references=raw_artefact_references or [],
        semantic_quality_passed=semantic_quality_passed,
        warnings=warnings or [],
        errors=errors or [],
        validation_error_summary=validation_error_summary,
        page_extraction_ir_path=page_extraction_ir_path,
        next_action=_NEXT_ACTIONS[status],
        metadata=metadata or {},
    )


def validate_one_backend(
    *,
    backend_name: str,
    raw_dir: Path | None,
    plan9_status: str | None = None,
    document_id: str = DEFAULT_DOCUMENT_ID,
    connector: Callable[..., ConnectorResult] = connect_raw_dir,
    out_dir: Path | None = None,
) -> ConnectorValidationResult:
    """Validate one backend's raw output via the existing connector entrypoint."""

    connector_name = f"{connector.__module__}.{connector.__name__}" if hasattr(connector, "__module__") else "custom_connector"

    if plan9_status is not None and plan9_status != PLAN9_SUCCESS_STATUS:
        return _result(
            backend_name=backend_name,
            status=ConnectorValidationStatus.DEFERRED_FROM_PLAN_9,
            plan9_status=plan9_status,
            raw_output_dir=str(raw_dir) if raw_dir else None,
            connector_entrypoint=connector_name,
            warnings=[f"plan9_status_not_success:{plan9_status}"],
        )

    if raw_dir is None:
        return _result(
            backend_name=backend_name,
            status=ConnectorValidationStatus.DEFERRED_FROM_PLAN_9,
            plan9_status=plan9_status,
            raw_output_dir=None,
            connector_entrypoint=connector_name,
            warnings=["no_raw_output_dir"],
        )

    raw_dir = Path(raw_dir)
    if not raw_dir.exists() or not raw_dir.is_dir():
        return _result(
            backend_name=backend_name,
            status=ConnectorValidationStatus.MISSING_REQUIRED_OUTPUT,
            plan9_status=plan9_status,
            raw_output_dir=str(raw_dir),
            connector_entrypoint=connector_name,
            errors=[f"raw_dir_missing:{raw_dir}"],
        )

    config = BackendConnectorConfig(backend=backend_name, default_backend_version=None)

    try:
        connector_result = connector(
            raw_dir=raw_dir,
            document_id=document_id,
            config=config,
        )
    except Exception as exc:  # noqa: BLE001 - any connector exception is a crash
        return _result(
            backend_name=backend_name,
            status=ConnectorValidationStatus.CONNECTOR_CRASH,
            plan9_status=plan9_status,
            raw_output_dir=str(raw_dir),
            connector_entrypoint=connector_name,
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    pages = list(getattr(connector_result, "pages", []) or [])
    raw_warnings = list(getattr(connector_result, "warnings", []) or [])

    # Re-validate each page through PageExtractionIR.model_validate to detect
    # connectors that return PageExtractionIR-like data which fails schema validation.
    try:
        pages_dump = [p.model_dump() for p in pages]
    except Exception as exc:  # noqa: BLE001 - schema dump failure is schema_failed
        return _result(
            backend_name=backend_name,
            status=ConnectorValidationStatus.SCHEMA_FAILED,
            plan9_status=plan9_status,
            raw_output_dir=str(raw_dir),
            connector_entrypoint=connector_name,
            warnings=raw_warnings,
            errors=[f"{type(exc).__name__}: {exc}"],
            validation_error_summary=f"model_dump failed: {exc}",
        )

    ok, error_summary = _revalidate_pages(pages_dump)
    if not ok:
        return _result(
            backend_name=backend_name,
            status=ConnectorValidationStatus.SCHEMA_FAILED,
            plan9_status=plan9_status,
            raw_output_dir=str(raw_dir),
            connector_entrypoint=connector_name,
            warnings=raw_warnings,
            errors=["page_extraction_ir_model_validate_failed"],
            validation_error_summary=error_summary,
        )

    if not pages or "raw_text_missing" in raw_warnings:
        errors = ["raw_text_missing"] if "raw_text_missing" in raw_warnings else ["no_pages_produced"]
        return _result(
            backend_name=backend_name,
            status=ConnectorValidationStatus.MISSING_REQUIRED_OUTPUT,
            plan9_status=plan9_status,
            raw_output_dir=str(raw_dir),
            connector_entrypoint=connector_name,
            warnings=raw_warnings,
            errors=errors,
        )

    page_count = len(pages)
    block_count = sum(len(p.blocks) for p in pages)
    block_kind_counts = _aggregate_block_kind_counts(pages)
    has_text = _has_text(pages)
    has_bboxes = _has_bboxes(pages)
    has_provenance = _has_provenance(pages)
    raw_artefact_references = _collect_raw_artefact_references(pages)
    sem_ok, sem_warnings = _semantic_quality_passed(pages)

    page_extraction_ir_path: str | None = None
    if out_dir is not None:
        target = _write_page_extraction_ir(
            backend_name=backend_name,
            pages=pages,
            out_dir=out_dir,
        )
        page_extraction_ir_path = str(target)

    return _result(
        backend_name=backend_name,
        status=ConnectorValidationStatus.VALIDATED,
        plan9_status=plan9_status,
        raw_output_dir=str(raw_dir),
        connector_entrypoint=connector_name,
        page_count=page_count,
        block_count=block_count,
        block_kind_counts=block_kind_counts,
        has_text=has_text,
        has_bboxes=has_bboxes,
        has_provenance=has_provenance,
        raw_artefact_references=raw_artefact_references,
        semantic_quality_passed=sem_ok,
        warnings=raw_warnings + sem_warnings,
        page_extraction_ir_path=page_extraction_ir_path,
    )


def _load_plan9_report(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Best-effort load of the Plan 9 backend smoke report."""

    warnings: list[str] = []
    if not path.is_file():
        warnings.append(f"plan9_report_missing:{path}")
        return None, warnings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"plan9_report_unreadable:{exc}")
        return None, warnings
    if not isinstance(data, dict):
        warnings.append("plan9_report_not_object")
        return None, warnings
    return data, warnings


def _backends_from_plan9_report(report: dict[str, Any]) -> list[tuple[str, str | None, Path | None]]:
    """Return (backend_name, status, raw_output_dir) tuples from a Plan 9 report."""

    out: list[tuple[str, str | None, Path | None]] = []
    results = report.get("results")
    if not isinstance(results, list):
        return out
    for entry in results:
        if not isinstance(entry, dict):
            continue
        name = entry.get("backend_name")
        if not isinstance(name, str) or not name:
            continue
        status = entry.get("status")
        status_str = status if isinstance(status, str) else None
        output_dir = entry.get("output_dir")
        path = Path(output_dir) if isinstance(output_dir, str) and output_dir else None
        out.append((name, status_str, path))
    return out


def _gates(
    results: list[ConnectorValidationResult],
    preferred_minimum: int,
) -> tuple[bool, bool]:
    """Compute (preferred_gate_passed, minimum_gate_passed)."""

    semantically_useful = [
        r
        for r in results
        if _status_value(r) == ConnectorValidationStatus.VALIDATED.value
        and r.semantic_quality_passed
    ]
    preferred = len(semantically_useful) >= preferred_minimum
    minimum = len(semantically_useful) >= 1
    return preferred, minimum


def build_connector_validation_report(
    *,
    backend_outputs: Mapping[str, Path] | None = None,
    plan9_report_path: Path | None = None,
    preferred_gate_minimum: int = DEFAULT_PREFERRED_GATE_MINIMUM,
    allow_reduced_gate: bool = False,
    document_id: str = DEFAULT_DOCUMENT_ID,
    connector: Callable[..., ConnectorResult] = connect_raw_dir,
    out_dir: Path | None = None,
    generated_at: str | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> ConnectorValidationReport:
    """Validate connector outputs for backends and produce a Plan 10 report.

    Backends are selected from ``backend_outputs`` (explicit override) and/or
    from ``plan9_report_path`` (every backend in the Plan 9 report). Explicit
    overrides take precedence when both supply the same backend name.
    """

    warnings: list[str] = []
    metadata: dict[str, Any] = {
        "connector_entrypoint": f"{connector.__module__}.{connector.__name__}"
        if hasattr(connector, "__module__")
        else "custom_connector",
        "document_id": document_id,
        "entity_proposal_document_handled_by": "plan_11",
    }
    if extra_metadata:
        metadata.update(dict(extra_metadata))

    plan9_data: dict[str, Any] | None = None
    if plan9_report_path is not None:
        plan9_data, plan9_warnings = _load_plan9_report(Path(plan9_report_path))
        warnings.extend(plan9_warnings)

    selections: dict[str, dict[str, Any]] = {}
    if plan9_data is not None:
        for name, status, path in _backends_from_plan9_report(plan9_data):
            selections[name] = {
                "plan9_status": status,
                "raw_output_dir": path,
            }

    explicit_overrides: dict[str, Path] = {}
    if backend_outputs:
        for name, path in backend_outputs.items():
            explicit_overrides[name] = Path(path)
            current = selections.get(name, {})
            current["raw_output_dir"] = Path(path)
            # Treat explicit overrides as "promoted to plan9 success" so they are
            # validated rather than deferred.
            current["plan9_status"] = current.get("plan9_status") or PLAN9_SUCCESS_STATUS
            if "plan9_status" in current and current["plan9_status"] != PLAN9_SUCCESS_STATUS:
                current["plan9_status"] = PLAN9_SUCCESS_STATUS
            selections[name] = current

    if not selections:
        warnings.append(
            "no_backends_selected: provide --plan9-report and/or --backend-output entries"
        )

    results: list[ConnectorValidationResult] = []
    for name in sorted(selections):
        spec = selections[name]
        raw_dir = spec.get("raw_output_dir")
        plan9_status = spec.get("plan9_status")
        result = validate_one_backend(
            backend_name=name,
            raw_dir=raw_dir,
            plan9_status=plan9_status,
            document_id=document_id,
            connector=connector,
            out_dir=out_dir if name in explicit_overrides or plan9_status == PLAN9_SUCCESS_STATUS else None,
        )
        results.append(result)

    preferred_passed, minimum_passed = _gates(results, preferred_gate_minimum)
    gate_mode = "preferred"
    human_reduced_gate_required = False
    if not preferred_passed and minimum_passed and allow_reduced_gate:
        gate_mode = "reduced"
        human_reduced_gate_required = True

    validated_count = _count_status(results, ConnectorValidationStatus.VALIDATED)
    deferred_count = _count_status(results, ConnectorValidationStatus.DEFERRED_FROM_PLAN_9)
    failed_count = sum(
        _count_status(results, s)
        for s in (
            ConnectorValidationStatus.CONNECTOR_CRASH,
            ConnectorValidationStatus.SCHEMA_FAILED,
            ConnectorValidationStatus.MISSING_REQUIRED_OUTPUT,
        )
    )

    return ConnectorValidationReport(
        generated_at=generated_at or _utc_now(),
        plan9_report_path=str(plan9_report_path) if plan9_report_path else None,
        gate_mode=gate_mode,
        preferred_gate_minimum=preferred_gate_minimum,
        preferred_gate_passed=preferred_passed,
        minimum_gate_passed=minimum_passed,
        human_reduced_gate_required=human_reduced_gate_required,
        total_backends_considered=len(results),
        backends_validated=validated_count,
        backends_failed=failed_count,
        backends_deferred=deferred_count,
        results=results,
        warnings=warnings,
        metadata=metadata,
    )


def build_connector_validation_summary(report: ConnectorValidationReport) -> str:
    """Render a human-readable Plan 10 summary including the Plan 11 hand-off."""

    preferred_state = "PASSED" if report.preferred_gate_passed else "FAILED"
    minimum_state = "PASSED" if report.minimum_gate_passed else "FAILED"
    lines = [
        "pdf2md connector PageExtractionIR validation (Plan 10)",
        f"schema: {report.schema_name} {report.schema_version}",
        f"tool: {report.tool_name}",
        f"generated_at: {report.generated_at}",
        f"plan9_report_path: {report.plan9_report_path}",
        f"gate_mode: {report.gate_mode}",
        f"preferred_gate ({report.preferred_gate_minimum} required): {preferred_state}",
        f"minimum_gate (1 required): {minimum_state}",
        f"human_reduced_gate_required: {str(report.human_reduced_gate_required).lower()}",
        (
            f"backends: {report.total_backends_considered} considered, "
            f"{report.backends_validated} validated, "
            f"{report.backends_failed} failed, "
            f"{report.backends_deferred} deferred"
        ),
        "",
        "validated backends:",
    ]
    validated = [
        r for r in report.results if _status_value(r) == ConnectorValidationStatus.VALIDATED.value
    ]
    if not validated:
        lines.append("- (none)")
    for r in validated:
        sem = "yes" if r.semantic_quality_passed else "no"
        lines.append(
            f"- {r.backend_name}: pages={r.page_count} blocks={r.block_count} "
            f"semantic_quality_passed={sem} ir_path={r.page_extraction_ir_path}"
        )
        if r.block_kind_counts:
            lines.append(f"    block_kind_counts: {r.block_kind_counts}")
        if r.raw_artefact_references:
            lines.append(f"    raw_artefact_references: {r.raw_artefact_references}")
        lines.append(f"    next_action: {r.next_action}")

    lines.extend(["", "failed or deferred backends:"])
    others = [
        r for r in report.results if _status_value(r) != ConnectorValidationStatus.VALIDATED.value
    ]
    if not others:
        lines.append("- (none)")
    for r in others:
        detail = r.validation_error_summary or (r.errors[0] if r.errors else "")
        lines.append(f"- {r.backend_name} [{_status_value(r)}]: {detail}")
        lines.append(f"    next_action: {r.next_action}")

    if report.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in report.warnings)

    lines.extend(
        [
            "",
            "Plan 11 hand-off:",
            (
                "- Candidate backends for EntityProposalDocument validation in Plan 11: "
                + ", ".join(r.backend_name for r in validated if r.semantic_quality_passed)
                if any(r.semantic_quality_passed for r in validated)
                else "- No semantically useful PageExtractionIR available for Plan 11 hand-off."
            ),
        ]
    )
    for r in validated:
        if r.semantic_quality_passed and r.page_extraction_ir_path:
            lines.append(f"- {r.backend_name} page_extraction_ir: {r.page_extraction_ir_path}")
    if report.human_reduced_gate_required:
        lines.append(
            "- Reduced-gate progression requires explicit human approval recorded "
            "in the human verification report."
        )
    lines.append(
        "- EntityProposalDocument validation is deferred to Plan 11 and is not used "
        "for Plan 10 pass/fail."
    )

    return "\n".join(lines) + "\n"


def write_connector_validation_report(
    *,
    report: ConnectorValidationReport,
    out_dir: Path,
) -> Path:
    """Write the machine-readable JSON report and human-readable summary."""

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "connector_validation_report.json"
    summary_path = out_dir / "connector_validation_summary.txt"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    summary_path.write_text(build_connector_validation_summary(report), encoding="utf-8")
    return report_path


__all__ = [
    "CONNECTOR_VALIDATION_SCHEMA_VERSION",
    "TOOL_NAME",
    "DEFAULT_PREFERRED_GATE_MINIMUM",
    "DEFAULT_DOCUMENT_ID",
    "PLAN9_SUCCESS_STATUS",
    "ConnectorValidationStatus",
    "ConnectorValidationResult",
    "ConnectorValidationReport",
    "validate_one_backend",
    "build_connector_validation_report",
    "build_connector_validation_summary",
    "write_connector_validation_report",
]
