"""Backend smoke-readiness wrapper around the existing pdf2md backend runner.

Plan 9 layer. This module reuses the repository's existing backend execution
path (`pdf2md.config.load_backend_config`, `pdf2md.config.get_enabled_backends`
and `pdf2md.backends.runner.run_configured_backends`) to attempt configured
backends on a real PDF, classify each backend into a smoke-readiness status,
and produce a deterministic report.

It does not implement a parallel backend runner, does not install environments
or models, and does not normalise backend output to PageExtractionIR. Plan 10
decides whether smoke outputs are sufficient for connector normalisation.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pdf2md.backends.runner import derive_run_name, run_configured_backends
from pdf2md.config import get_enabled_backends, load_backend_config

BACKEND_SMOKE_SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "backend_smoke"
DEFAULT_CORPUS_ROOT = Path("groundtruth/corpus/latex")
DEFAULT_GATE_MINIMUM = 2
DEFAULT_TIMEOUT_SECONDS = 300
SNIPPET_LIMIT = 2000

# Output artefacts requested from every backend by ``plan_backend_command``.
EXPECTED_OUTPUT_PATTERNS: tuple[str, ...] = ("output.md", "manifest.json")

_CONFIG_CANDIDATES: tuple[str, ...] = ("pdf2md.backends.toml", "config/backends.toml")

_ENV_MARKERS: tuple[str, ...] = (
    "could not find conda environment",
    "environmentlocationnotfound",
    "environmentnamenotfound",
    "conda: error",
    "is not a valid conda environment",
    "command not found",
    "executable not found",
    "no such file or directory: 'python'",
    "no such file or directory: 'conda'",
)
_MODEL_MARKERS: tuple[str, ...] = (
    "checkpoint",
    "model weights",
    "weights not found",
    "model not found",
    "no model found",
    ".safetensors",
    ".pth",
    "huggingface",
    "hf cache",
)
_DEPENDENCY_MARKERS: tuple[str, ...] = (
    "modulenotfounderror",
    "no module named",
    "importerror",
    "cannot open shared object",
    "libcuda",
    "libcudnn",
    "undefined symbol",
    "shared library",
)


class BackendSmokeStatus(str, Enum):
    SUCCESS = "success"
    ENV_NOT_READY = "env_not_ready"
    MODEL_MISSING = "model_missing"
    DEPENDENCY_MISSING = "dependency_missing"
    BACKEND_CRASH = "backend_crash"
    OUTPUT_MISSING = "output_missing"
    TIMEOUT = "timeout"
    NOT_CONFIGURED = "not_configured"


_FAILED_STATUSES = {
    BackendSmokeStatus.BACKEND_CRASH,
    BackendSmokeStatus.OUTPUT_MISSING,
    BackendSmokeStatus.TIMEOUT,
}
_DEFERRED_STATUSES = {
    BackendSmokeStatus.ENV_NOT_READY,
    BackendSmokeStatus.MODEL_MISSING,
    BackendSmokeStatus.DEPENDENCY_MISSING,
    BackendSmokeStatus.NOT_CONFIGURED,
}

_NEXT_ACTIONS: dict[BackendSmokeStatus, str] = {
    BackendSmokeStatus.SUCCESS: (
        "Backend produced output artefacts; Plan 10 will decide whether they are "
        "sufficient for PageExtractionIR normalisation."
    ),
    BackendSmokeStatus.ENV_NOT_READY: (
        "Create or repair the backend conda environment and command, then re-run the smoke check."
    ),
    BackendSmokeStatus.MODEL_MISSING: (
        "Install or configure the required model weights or checkpoints, then re-run the smoke check."
    ),
    BackendSmokeStatus.DEPENDENCY_MISSING: (
        "Install the missing Python or system dependencies in the backend environment, then re-run."
    ),
    BackendSmokeStatus.BACKEND_CRASH: (
        "Inspect the backend stderr log and fix the backend runtime failure before re-running."
    ),
    BackendSmokeStatus.OUTPUT_MISSING: (
        "Backend exited 0 but produced no expected artefact; inspect the backend output handling."
    ),
    BackendSmokeStatus.TIMEOUT: (
        "Increase --timeout-seconds or speed up the backend environment, then re-run the smoke check."
    ),
    BackendSmokeStatus.NOT_CONFIGURED: (
        "Add and enable this backend in the backend configuration to include it in the smoke run."
    ),
}

_FAILURE_REASONS: dict[BackendSmokeStatus, str] = {
    BackendSmokeStatus.ENV_NOT_READY: "Backend environment, command, interpreter or path is unavailable.",
    BackendSmokeStatus.MODEL_MISSING: "Required model weights, checkpoints or cached assets are missing.",
    BackendSmokeStatus.DEPENDENCY_MISSING: "A required Python module, shared library or system dependency is missing.",
    BackendSmokeStatus.BACKEND_CRASH: "Backend command exited non-zero without a more specific cause.",
    BackendSmokeStatus.OUTPUT_MISSING: "Backend exited 0 but no expected output artefact was found.",
    BackendSmokeStatus.TIMEOUT: "Backend run exceeded the configured timeout.",
    BackendSmokeStatus.NOT_CONFIGURED: "Backend is absent from configuration or not enabled for execution.",
}


class _SmokeBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BackendSmokeResult(_SmokeBaseModel):
    backend_name: str
    configured: bool
    enabled: bool
    environment_name: str | None = None
    command: list[str] | str | None = None
    input_pdf: str | None = None
    output_dir: str | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    status: BackendSmokeStatus
    expected_output_patterns: list[str] = Field(default_factory=list)
    output_files_found: list[str] = Field(default_factory=list)
    missing_output_patterns: list[str] = Field(default_factory=list)
    stdout_snippet: str = ""
    stderr_snippet: str = ""
    failure_reason: str | None = None
    next_action: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackendSmokeReport(_SmokeBaseModel):
    schema_name: Literal["pdf2md.BackendSmokeReport"] = "pdf2md.BackendSmokeReport"
    schema_version: Literal["1.0.0"] = BACKEND_SMOKE_SCHEMA_VERSION
    generated_at: str
    tool_name: Literal["backend_smoke"] = TOOL_NAME
    repo_root: str
    corpus_root: str | None = None
    input_pdf: str | None = None
    gate_minimum: int = DEFAULT_GATE_MINIMUM
    gate_passed: bool = False
    total_backends: int = 0
    backends_successful: int = 0
    backends_failed: int = 0
    backends_deferred: int = 0
    results: list[BackendSmokeResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _populate_counts(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        results = data.get("results") or []
        successful = _count_status(results, BackendSmokeStatus.SUCCESS)
        failed = sum(_count_status(results, status) for status in _FAILED_STATUSES)
        deferred = sum(_count_status(results, status) for status in _DEFERRED_STATUSES)
        gate_minimum = data.get("gate_minimum", DEFAULT_GATE_MINIMUM)
        data.setdefault("total_backends", len(results))
        data.setdefault("backends_successful", successful)
        data.setdefault("backends_failed", failed)
        data.setdefault("backends_deferred", deferred)
        data.setdefault("gate_passed", successful >= gate_minimum)
        return data

    @model_validator(mode="after")
    def _validate_report(self) -> BackendSmokeReport:
        names = [result.backend_name for result in self.results]
        if len(names) != len(set(names)):
            raise ValueError("backend names must be unique")
        successful = _count_status(self.results, BackendSmokeStatus.SUCCESS)
        failed = sum(_count_status(self.results, status) for status in _FAILED_STATUSES)
        deferred = sum(_count_status(self.results, status) for status in _DEFERRED_STATUSES)
        if self.total_backends != len(self.results):
            raise ValueError("total_backends must match the number of results")
        if self.backends_successful != successful:
            raise ValueError("backends_successful must match success results")
        if self.backends_failed != failed:
            raise ValueError("backends_failed must match failed results")
        if self.backends_deferred != deferred:
            raise ValueError("backends_deferred must match deferred results")
        if successful + failed + deferred != self.total_backends:
            raise ValueError("successful, failed and deferred counts must cover every backend")
        if self.gate_passed != (successful >= self.gate_minimum):
            raise ValueError("gate_passed must be true only when backends_successful >= gate_minimum")
        return self


def _status_value(result: Any) -> str:
    if isinstance(result, dict):
        status = result.get("status")
    else:
        status = getattr(result, "status", None)
    if isinstance(status, BackendSmokeStatus):
        return status.value
    return str(status)


def _count_status(results: list[Any], status: BackendSmokeStatus) -> int:
    return sum(1 for result in results if _status_value(result) == status.value)


def _snippet(text: str | None) -> str:
    if not text:
        return ""
    if len(text) <= SNIPPET_LIMIT:
        return text
    return "...(truncated)...\n" + text[-SNIPPET_LIMIT:]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_backend_status(
    *,
    configured: bool,
    enabled: bool,
    returncode: int | None,
    timed_out: bool,
    stdout: str,
    stderr: str,
    output_files_found: list[str],
) -> BackendSmokeStatus:
    """Classify a single backend run into a smoke-readiness status."""

    if not configured or not enabled:
        return BackendSmokeStatus.NOT_CONFIGURED
    if timed_out:
        return BackendSmokeStatus.TIMEOUT
    if returncode == 0:
        return BackendSmokeStatus.SUCCESS if output_files_found else BackendSmokeStatus.OUTPUT_MISSING
    text = f"{stdout}\n{stderr}".lower()
    if any(marker in text for marker in _ENV_MARKERS):
        return BackendSmokeStatus.ENV_NOT_READY
    if any(marker in text for marker in _MODEL_MARKERS):
        return BackendSmokeStatus.MODEL_MISSING
    if any(marker in text for marker in _DEPENDENCY_MARKERS):
        return BackendSmokeStatus.DEPENDENCY_MISSING
    return BackendSmokeStatus.BACKEND_CRASH


def next_action_for(status: BackendSmokeStatus) -> str:
    """Return the recommended next action for a smoke status."""

    return _NEXT_ACTIONS[status]


def build_backend_result(
    *,
    backend_name: str,
    configured: bool,
    enabled: bool,
    environment_name: str | None = None,
    command: list[str] | str | None = None,
    input_pdf: str | None = None,
    output_dir: str | None = None,
    exit_code: int | None = None,
    duration_seconds: float | None = None,
    timed_out: bool = False,
    stdout: str = "",
    stderr: str = "",
    output_files_found: list[str] | None = None,
    expected_patterns: tuple[str, ...] = EXPECTED_OUTPUT_PATTERNS,
    status_override: BackendSmokeStatus | None = None,
    failure_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BackendSmokeResult:
    """Build a fully classified per-backend smoke result."""

    found = sorted(output_files_found or [])
    status = status_override or classify_backend_status(
        configured=configured,
        enabled=enabled,
        returncode=exit_code,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
        output_files_found=found,
    )
    missing = sorted(pattern for pattern in expected_patterns if pattern not in found)
    reason = failure_reason
    if reason is None and status != BackendSmokeStatus.SUCCESS:
        reason = _FAILURE_REASONS.get(status)
    return BackendSmokeResult(
        backend_name=backend_name,
        configured=configured,
        enabled=enabled,
        environment_name=environment_name,
        command=command,
        input_pdf=input_pdf,
        output_dir=output_dir,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        status=status,
        expected_output_patterns=list(expected_patterns),
        output_files_found=found,
        missing_output_patterns=missing,
        stdout_snippet=_snippet(stdout),
        stderr_snippet=_snippet(stderr),
        failure_reason=reason,
        next_action=next_action_for(status),
        metadata=metadata or {},
    )


def assemble_smoke_report(
    *,
    results: list[BackendSmokeResult],
    gate_minimum: int,
    repo_root: str,
    corpus_root: str | None,
    input_pdf: str | None,
    generated_at: str | None = None,
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> BackendSmokeReport:
    """Assemble a backend smoke report from per-backend results."""

    ordered = sorted(results, key=lambda result: result.backend_name)
    return BackendSmokeReport(
        generated_at=generated_at or _utc_now(),
        repo_root=repo_root,
        corpus_root=corpus_root,
        input_pdf=input_pdf,
        gate_minimum=gate_minimum,
        results=ordered,
        warnings=warnings or [],
        metadata=metadata or {},
    )


def _resolve_config_path(repo_root: Path, config_path: Path | None) -> Path | None:
    if config_path is not None:
        return config_path if config_path.is_file() else None
    for candidate in _CONFIG_CANDIDATES:
        path = repo_root / candidate
        if path.is_file():
            return path
    return None


def _discover_backend_dirs(repo_root: Path) -> list[str]:
    backend_root = repo_root / "backend"
    if not backend_root.is_dir():
        return []
    return sorted(
        child.name
        for child in backend_root.iterdir()
        if child.is_dir() and not child.name.startswith((".", "_"))
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _collect_run_artifacts(work_dir: Path, input_pdf: Path, enabled: dict) -> dict[str, dict]:
    """Read the per-backend artefacts written by ``run_configured_backends``."""

    try:
        run_name = derive_run_name(input_pdf=input_pdf, override=None)
    except ValueError:
        return {}
    raw_root = work_dir / run_name / "raw"
    artifacts: dict[str, dict] = {}
    for backend_name in enabled:
        backend_dir = raw_root / backend_name
        if not backend_dir.is_dir():
            continue
        returncode: int | None = None
        duration: float | None = None
        status_path = backend_dir / "status.json"
        if status_path.is_file():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
                returncode = status.get("returncode")
                duration = status.get("duration_seconds")
            except (OSError, json.JSONDecodeError):
                pass
        command: list[str] | str | None = None
        command_path = backend_dir / "command.json"
        if command_path.is_file():
            try:
                command = json.loads(command_path.read_text(encoding="utf-8")).get("command")
            except (OSError, json.JSONDecodeError):
                pass
        found = [
            pattern
            for pattern in EXPECTED_OUTPUT_PATTERNS
            if (backend_dir / pattern).is_file() and (backend_dir / pattern).stat().st_size > 0
        ]
        artifacts[backend_name] = {
            "returncode": returncode,
            "duration_seconds": duration,
            "stdout": _read_text(backend_dir / "stdout.log"),
            "stderr": _read_text(backend_dir / "stderr.log"),
            "command": command,
            "output_dir": str(backend_dir),
            "output_files_found": found,
        }
    return artifacts


def build_backend_smoke_report(
    *,
    repo_root: Path,
    input_pdf: Path | None,
    work_dir: Path,
    gate_minimum: int = DEFAULT_GATE_MINIMUM,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    corpus_root: Path | None = None,
    config_path: Path | None = None,
    runner: Any = run_configured_backends,
    generated_at: str | None = None,
) -> BackendSmokeReport:
    """Run configured backends through the existing runner and classify each one.

    The real backend runner is only invoked when there is at least one enabled
    backend and a readable input PDF. Automated tests mock ``runner`` or this
    whole function; real backend execution is a human verification step.
    """

    repo_root = repo_root.resolve()
    warnings: list[str] = []
    metadata: dict[str, Any] = {
        "expected_output_patterns": list(EXPECTED_OUTPUT_PATTERNS),
        "status_groups": {
            "successful": ["success"],
            "failed": sorted(status.value for status in _FAILED_STATUSES),
            "deferred": sorted(status.value for status in _DEFERRED_STATUSES),
        },
    }

    resolved_config = _resolve_config_path(repo_root, config_path)
    config: dict | None = None
    if resolved_config is None:
        metadata["config_status"] = "missing"
        warnings.append(
            "no backend configuration found (looked for pdf2md.backends.toml and config/backends.toml); "
            "all backends classified as not_configured"
        )
    else:
        metadata["config_path"] = str(resolved_config)
        try:
            config = load_backend_config(resolved_config)
            metadata["config_status"] = "loaded"
        except Exception as exc:  # noqa: BLE001 - any load error degrades to not_configured
            config = None
            metadata["config_status"] = "invalid"
            warnings.append(f"backend configuration could not be loaded: {exc}")

    configured_backends: dict = (config or {}).get("backends", {}) if isinstance(config, dict) else {}
    enabled = get_enabled_backends(config) if isinstance(config, dict) else {}
    discovered = _discover_backend_dirs(repo_root)
    all_names = sorted(set(configured_backends) | set(discovered))

    run_artifacts: dict[str, dict] = {}
    run_timed_out = False
    if enabled and input_pdf is not None and input_pdf.is_file():
        try:
            runner(
                input_pdf=input_pdf,
                config=config,
                repo_root=repo_root,
                work_dir_override=work_dir,
                force=True,
                keep_going=True,
                timeout_override=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            run_timed_out = True
            warnings.append(f"backend run timed out after {timeout_seconds}s: {exc}")
        except Exception as exc:  # noqa: BLE001 - runner failure must not abort the report
            warnings.append(f"backend runner raised an error: {exc}")
        run_artifacts = _collect_run_artifacts(work_dir, input_pdf, enabled)
    elif enabled:
        warnings.append(
            "enabled backends are configured but no readable input PDF was provided; "
            "smoke execution was skipped"
        )

    input_pdf_str = str(input_pdf) if input_pdf is not None else None
    results: list[BackendSmokeResult] = []
    for name in all_names:
        cfg = configured_backends.get(name)
        is_configured = name in configured_backends
        is_enabled = name in enabled
        env_name = cfg.get("env_name") if isinstance(cfg, dict) else None

        if is_enabled and name in run_artifacts:
            artifact = run_artifacts[name]
            results.append(
                build_backend_result(
                    backend_name=name,
                    configured=True,
                    enabled=True,
                    environment_name=env_name,
                    command=artifact["command"],
                    input_pdf=input_pdf_str,
                    output_dir=artifact["output_dir"],
                    exit_code=artifact["returncode"],
                    duration_seconds=artifact["duration_seconds"],
                    stdout=artifact["stdout"],
                    stderr=artifact["stderr"],
                    output_files_found=artifact["output_files_found"],
                )
            )
        elif is_enabled:
            status = BackendSmokeStatus.TIMEOUT if run_timed_out else BackendSmokeStatus.ENV_NOT_READY
            reason = (
                "Backend run timed out before producing artefacts."
                if run_timed_out
                else "Backend is enabled but smoke execution did not run (no readable input PDF or runner error)."
            )
            results.append(
                build_backend_result(
                    backend_name=name,
                    configured=True,
                    enabled=True,
                    environment_name=env_name,
                    input_pdf=input_pdf_str,
                    status_override=status,
                    failure_reason=reason,
                )
            )
        else:
            results.append(
                build_backend_result(
                    backend_name=name,
                    configured=is_configured,
                    enabled=False,
                    environment_name=env_name,
                    status_override=BackendSmokeStatus.NOT_CONFIGURED,
                    metadata={"present_in_backend_dir": name in discovered},
                )
            )

    return assemble_smoke_report(
        results=results,
        gate_minimum=gate_minimum,
        repo_root=str(repo_root),
        corpus_root=str(corpus_root) if corpus_root is not None else None,
        input_pdf=input_pdf_str,
        generated_at=generated_at,
        warnings=warnings,
        metadata=metadata,
    )


def build_backend_smoke_summary(report: BackendSmokeReport) -> str:
    """Render a human-readable backend smoke summary.

    Successful backends are listed first, then failed and deferred backends with
    their next action. The summary states that Plan 10 owns the connector
    sufficiency decision.
    """

    gate_state = "PASSED" if report.gate_passed else "FAILED"
    lines = [
        "pdf2md backend smoke readiness",
        f"schema: {report.schema_name} {report.schema_version}",
        f"tool: {report.tool_name}",
        f"generated_at: {report.generated_at}",
        f"repo_root: {report.repo_root}",
        f"input_pdf: {report.input_pdf}",
        (
            f"gate: {report.backends_successful} successful / {report.gate_minimum} required "
            f"-> {gate_state}"
        ),
        (
            f"backends: {report.total_backends} total, {report.backends_successful} successful, "
            f"{report.backends_failed} failed, {report.backends_deferred} deferred"
        ),
        "",
        "successful backends:",
    ]
    successful = [r for r in report.results if r.status == BackendSmokeStatus.SUCCESS]
    if not successful:
        lines.append("- (none)")
    for result in successful:
        lines.append(f"- {result.backend_name}: output_files_found={result.output_files_found}")
        lines.append(f"    next_action: {result.next_action}")

    lines.extend(["", "failed / deferred backends:"])
    others = [r for r in report.results if r.status != BackendSmokeStatus.SUCCESS]
    if not others:
        lines.append("- (none)")
    for result in others:
        reason = result.failure_reason or ""
        lines.append(f"- {result.backend_name} [{result.status.value}]: {reason}")
        lines.append(f"    next_action: {result.next_action}")

    if report.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(
        [
            "",
            "note: Plan 9 only reports backend smoke readiness. Plan 10 will decide whether "
            "these backend outputs are sufficient for PageExtractionIR normalisation.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_backend_smoke_report(*, report: BackendSmokeReport, out_dir: Path) -> Path:
    """Write the machine-readable JSON report and the human-readable summary."""

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "backend_smoke_report.json"
    summary_path = out_dir / "backend_smoke_summary.txt"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    summary_path.write_text(build_backend_smoke_summary(report), encoding="utf-8")
    return report_path


__all__ = [
    "BACKEND_SMOKE_SCHEMA_VERSION",
    "TOOL_NAME",
    "DEFAULT_CORPUS_ROOT",
    "DEFAULT_GATE_MINIMUM",
    "DEFAULT_TIMEOUT_SECONDS",
    "EXPECTED_OUTPUT_PATTERNS",
    "BackendSmokeStatus",
    "BackendSmokeResult",
    "BackendSmokeReport",
    "classify_backend_status",
    "next_action_for",
    "build_backend_result",
    "assemble_smoke_report",
    "build_backend_smoke_report",
    "build_backend_smoke_summary",
    "write_backend_smoke_report",
]
