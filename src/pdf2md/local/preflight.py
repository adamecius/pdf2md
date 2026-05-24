"""Local environment and toolchain preflight checks."""

from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LOCAL_PREFLIGHT_SCHEMA_VERSION = "1.0.0"
MAIN_CONDA_ENV = "pdf2md"
SNIPPET_LIMIT = 1000


class CheckStatus(str, Enum):
    """Outcome of a single preflight check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class CheckSeverity(str, Enum):
    """Whether a preflight check is required for environment readiness."""

    REQUIRED = "required"
    OPTIONAL = "optional"


class _PreflightBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflightCheck(_PreflightBaseModel):
    """One preflight check entry.

    Attributes:
        id: Stable identifier for the check.
        label: Human-readable label.
        status: Outcome of the check.
        severity: Whether the check is required or optional.
        command: Command line executed, when applicable.
        returncode: Process exit code, when a command ran.
        stdout_snippet: Truncated stdout for diagnostics.
        stderr_snippet: Truncated stderr for diagnostics.
        message: Short message describing the outcome.
        metadata: Free-form metadata, including ``failure_class``.
    """

    id: str
    label: str
    status: CheckStatus
    severity: CheckSeverity
    command: list[str] | None = None
    returncode: int | None = None
    stdout_snippet: str | None = None
    stderr_snippet: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PreflightReport(_PreflightBaseModel):
    """Aggregated local preflight report.

    Attributes:
        schema_name: Fixed schema marker.
        schema_version: Schema version string.
        environment_ready: True only when every required check passed.
        required_passed: Number of required checks with PASS status.
        required_failed: Number of required checks with FAIL status.
        optional_passed: Number of optional checks with PASS status.
        optional_failed: Number of optional checks with FAIL status.
        checks: Individual PreflightCheck entries.
        warnings: Run-level warnings (e.g. messages from WARN checks).
        metadata: Free-form metadata describing the run.
    """

    schema_name: Literal["pdf2md.LocalPreflightReport"] = "pdf2md.LocalPreflightReport"
    schema_version: Literal["1.0.0"] = LOCAL_PREFLIGHT_SCHEMA_VERSION
    environment_ready: bool = False
    required_passed: int = 0
    required_failed: int = 0
    optional_passed: int = 0
    optional_failed: int = 0
    checks: list[PreflightCheck]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _populate_counts(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        checks = data.get("checks") or []
        required_passed = _count_checks(checks, CheckSeverity.REQUIRED, CheckStatus.PASS)
        required_failed = _count_checks(checks, CheckSeverity.REQUIRED, CheckStatus.FAIL)
        optional_passed = _count_checks(checks, CheckSeverity.OPTIONAL, CheckStatus.PASS)
        optional_failed = _count_checks(checks, CheckSeverity.OPTIONAL, CheckStatus.FAIL)
        data.setdefault("required_passed", required_passed)
        data.setdefault("required_failed", required_failed)
        data.setdefault("optional_passed", optional_passed)
        data.setdefault("optional_failed", optional_failed)
        data.setdefault("environment_ready", required_failed == 0)
        return data

    @model_validator(mode="after")
    def _validate_report(self) -> PreflightReport:
        ids = [check.id for check in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("check ids must be unique")
        required_passed = _count_checks(self.checks, CheckSeverity.REQUIRED, CheckStatus.PASS)
        required_failed = _count_checks(self.checks, CheckSeverity.REQUIRED, CheckStatus.FAIL)
        optional_passed = _count_checks(self.checks, CheckSeverity.OPTIONAL, CheckStatus.PASS)
        optional_failed = _count_checks(self.checks, CheckSeverity.OPTIONAL, CheckStatus.FAIL)
        if self.required_passed != required_passed:
            raise ValueError("required_passed must match required pass checks")
        if self.required_failed != required_failed:
            raise ValueError("required_failed must match required failed checks")
        if self.optional_passed != optional_passed:
            raise ValueError("optional_passed must match optional pass checks")
        if self.optional_failed != optional_failed:
            raise ValueError("optional_failed must match optional failed checks")
        if self.environment_ready != (required_failed == 0):
            raise ValueError("environment_ready must be true only when required_failed == 0")
        return self


@dataclass(frozen=True)
class PreflightSettings:
    """Configuration for ``build_preflight_report``.

    Attributes:
        required_backends: Backends whose connector and environment are
            required for an environment to be considered ready.
        optional_backends: Backends checked but not required.
        backend_env_prefix: Prefix used to derive expected conda
            environment names from backend names.
        output_roots: Directories that must be writable.
        timeout_seconds: Per-subprocess timeout for help/version probes.
    """

    required_backends: tuple[str, ...] = ("mineru", "paddleocr", "deepseek")
    optional_backends: tuple[str, ...] = ()
    backend_env_prefix: str = "pdf2md-"
    output_roots: tuple[Path, ...] = (
        Path("groundtruth/runs/local_preflight"),
        Path("groundtruth/runs/local_e2e"),
    )
    timeout_seconds: int = 20


def _enum_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _raw_field(check: Any, field: str) -> Any:
    if isinstance(check, dict):
        return check.get(field)
    return getattr(check, field)


def _count_checks(checks: list[Any], severity: CheckSeverity, status: CheckStatus) -> int:
    return sum(
        1
        for check in checks
        if _enum_value(_raw_field(check, "severity")) == severity.value
        and _enum_value(_raw_field(check, "status")) == status.value
    )


def _failure_status(severity: CheckSeverity) -> CheckStatus:
    return CheckStatus.WARN if severity == CheckSeverity.OPTIONAL else CheckStatus.FAIL


def _missing_failure_class(severity: CheckSeverity) -> str:
    return "optional_missing" if severity == CheckSeverity.OPTIONAL else "environment_missing"


def _snippet(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    return text[:SNIPPET_LIMIT]


def _combined_output(stdout: Any, stderr: Any) -> str:
    return "\n".join(part for part in (_snippet(stdout), _snippet(stderr)) if part)


def _extract_latexml_version(output: str) -> str | None:
    match = re.search(r"\bLaTeXML(?:\s+version)?\s+([0-9]+(?:\.[0-9]+)+)\b", output, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _sanitize_id_fragment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower() or "root"


def _path_check_id(path: Path, suffix: str) -> str:
    parts = path.as_posix().split("/")
    if "backend" in parts:
        index = parts.index("backend")
        if index + 2 < len(parts) and parts[index + 2] == "connector.py":
            return f"backend_path.{parts[index + 1]}.connector.{suffix}"
    if "groundtruth" in parts:
        index = parts.index("groundtruth")
        return f"path.{'.'.join(_sanitize_id_fragment(part) for part in parts[index:])}.{suffix}"
    return f"path.{_sanitize_id_fragment(path.name or path.as_posix())}.{suffix}"


def _classify_command_failure(check_id: str, severity: CheckSeverity, stderr: str | None) -> str:
    if severity == CheckSeverity.OPTIONAL:
        return "optional_missing"
    lowered = (stderr or "").lower()
    if any(
        marker in lowered
        for marker in (
            "could not find conda environment",
            "environmentnamefound",
            "environmentlocationnotfound",
            "environment not found",
            "no such environment",
        )
    ):
        return "environment_missing"
    if "can't open file" in lowered or "no such file or directory" in lowered:
        return "path_missing"
    if check_id.startswith("cli.") or check_id.startswith("backend_connector."):
        return "repository_defect"
    return "command_failed"


def check_command_exists(command: str) -> PreflightCheck:
    """Check whether an executable is visible on PATH."""

    path = shutil.which(command)
    if path:
        return PreflightCheck(
            id=f"command.{_sanitize_id_fragment(command)}.exists",
            label=f"{command} executable",
            status=CheckStatus.PASS,
            severity=CheckSeverity.REQUIRED,
            command=[command],
            returncode=0,
            stdout_snippet=path,
            stderr_snippet=None,
            message=f"{command} is available on PATH",
            metadata={"path": path},
        )
    return PreflightCheck(
        id=f"command.{_sanitize_id_fragment(command)}.exists",
        label=f"{command} executable",
        status=CheckStatus.FAIL,
        severity=CheckSeverity.REQUIRED,
        command=[command],
        returncode=None,
        stdout_snippet=None,
        stderr_snippet=f"{command} not found",
        message=f"{command} is not available on PATH",
        metadata={"failure_class": "environment_missing"},
    )


def run_help_check(
    *,
    check_id: str,
    label: str,
    command: list[str],
    severity: CheckSeverity,
    timeout_seconds: int,
) -> PreflightCheck:
    """Run a lightweight command, normally a --help or --version check."""

    if not command:
        return PreflightCheck(
            id=check_id,
            label=label,
            status=_failure_status(severity),
            severity=severity,
            command=[],
            returncode=None,
            stdout_snippet=None,
            stderr_snippet="empty command",
            message=f"{label} command is empty",
            metadata={"failure_class": "command_failed"},
        )
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return PreflightCheck(
            id=check_id,
            label=label,
            status=_failure_status(severity),
            severity=severity,
            command=command,
            returncode=None,
            stdout_snippet=None,
            stderr_snippet=str(exc),
            message=f"{command[0]} is not available on PATH",
            metadata={"failure_class": _missing_failure_class(severity)},
        )
    except subprocess.TimeoutExpired as exc:
        return PreflightCheck(
            id=check_id,
            label=label,
            status=_failure_status(severity),
            severity=severity,
            command=command,
            returncode=None,
            stdout_snippet=_snippet(exc.stdout or exc.output),
            stderr_snippet=_snippet(exc.stderr),
            message=f"{label} timed out after {timeout_seconds} seconds",
            metadata={"failure_class": "command_timeout"},
        )

    if completed.returncode == 0:
        return PreflightCheck(
            id=check_id,
            label=label,
            status=CheckStatus.PASS,
            severity=severity,
            command=command,
            returncode=completed.returncode,
            stdout_snippet=_snippet(completed.stdout),
            stderr_snippet=_snippet(completed.stderr),
            message=f"{label} started successfully",
            metadata={},
        )

    failure_class = _classify_command_failure(check_id, severity, completed.stderr)
    return PreflightCheck(
        id=check_id,
        label=label,
        status=_failure_status(severity),
        severity=severity,
        command=command,
        returncode=completed.returncode,
        stdout_snippet=_snippet(completed.stdout),
        stderr_snippet=_snippet(completed.stderr),
        message=f"{label} did not start",
        metadata={"failure_class": failure_class},
    )


def check_latexml_executable(*, severity: CheckSeverity, timeout_seconds: int) -> PreflightCheck:
    """Check that LaTeXML is installed and emits a recognizable CLI signal."""

    check_id = "latex.latexml.version"
    label = "latexml executable"
    if shutil.which("latexml") is None:
        return PreflightCheck(
            id=check_id,
            label=label,
            status=_failure_status(severity),
            severity=severity,
            command=["latexml"],
            returncode=None,
            stdout_snippet=None,
            stderr_snippet="latexml not found",
            message="latexml is not available on PATH",
            metadata={"failure_class": _missing_failure_class(severity)},
        )

    last_completed: subprocess.CompletedProcess[str] | None = None
    for flag in ("--version", "--help"):
        command = ["latexml", flag]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            return PreflightCheck(
                id=check_id,
                label=label,
                status=_failure_status(severity),
                severity=severity,
                command=command,
                returncode=None,
                stdout_snippet=None,
                stderr_snippet=str(exc),
                message="latexml is not available on PATH",
                metadata={"failure_class": _missing_failure_class(severity)},
            )
        except subprocess.TimeoutExpired as exc:
            return PreflightCheck(
                id=check_id,
                label=label,
                status=_failure_status(severity),
                severity=severity,
                command=command,
                returncode=None,
                stdout_snippet=_snippet(exc.stdout or exc.output),
                stderr_snippet=_snippet(exc.stderr),
                message=f"{label} timed out after {timeout_seconds} seconds",
                metadata={"failure_class": "command_timeout"},
            )

        last_completed = completed
        output = _combined_output(completed.stdout, completed.stderr)
        version = _extract_latexml_version(output)
        if completed.returncode == 0 or version is not None:
            metadata: dict[str, Any] = {}
            if version is not None:
                metadata["version"] = version
            if completed.returncode != 0 and flag == "--version":
                metadata["probe_note"] = "unsupported_version_flag"
            elif flag == "--help":
                metadata["probe_note"] = "help_probe"
            return PreflightCheck(
                id=check_id,
                label=label,
                status=CheckStatus.PASS,
                severity=severity,
                command=command,
                returncode=completed.returncode,
                stdout_snippet=_snippet(completed.stdout),
                stderr_snippet=_snippet(completed.stderr),
                message="latexml emitted a recognizable CLI signal",
                metadata=metadata,
            )

    assert last_completed is not None
    return PreflightCheck(
        id=check_id,
        label=label,
        status=_failure_status(severity),
        severity=severity,
        command=["latexml", "--help"],
        returncode=last_completed.returncode,
        stdout_snippet=_snippet(last_completed.stdout),
        stderr_snippet=_snippet(last_completed.stderr),
        message="latexml started but did not emit a recognizable LaTeXML signal",
        metadata={"failure_class": "command_failed"},
    )


def check_python_import(*, module: str, severity: CheckSeverity) -> PreflightCheck:
    """Check whether a Python module imports in the current interpreter."""

    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 - importability is the signal
        return PreflightCheck(
            id=f"python_import.{_sanitize_id_fragment(module)}",
            label=f"{module} import",
            status=_failure_status(severity),
            severity=severity,
            command=None,
            returncode=None,
            stdout_snippet=None,
            stderr_snippet=str(exc),
            message=f"{module} could not be imported",
            metadata={"failure_class": _missing_failure_class(severity), "module": module},
        )
    return PreflightCheck(
        id=f"python_import.{_sanitize_id_fragment(module)}",
        label=f"{module} import",
        status=CheckStatus.PASS,
        severity=severity,
        command=None,
        returncode=0,
        stdout_snippet=f"{module} ok",
        stderr_snippet=None,
        message=f"{module} imports successfully",
        metadata={"module": module},
    )


def parse_environment_list(output: str) -> set[str]:
    """Parse names from `conda env list` or `mamba env list` text output."""

    envs: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        if name in {"Name", "*"}:
            continue
        if "/" in name or "\\" in name:
            continue
        envs.add(name)
    return envs


def check_conda_environment(
    *,
    env_name: str,
    severity: CheckSeverity,
    timeout_seconds: int,
) -> PreflightCheck:
    """Check whether a conda or mamba environment is listed locally."""

    attempted: list[str] = []
    last_failure: PreflightCheck | None = None
    for manager in ("conda", "mamba"):
        if shutil.which(manager) is None:
            continue
        command = [manager, "env", "list"]
        attempted.append(manager)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return PreflightCheck(
                id=f"env.{env_name}.exists",
                label=f"{env_name} backend environment",
                status=_failure_status(severity),
                severity=severity,
                command=command,
                returncode=None,
                stdout_snippet=_snippet(exc.stdout or exc.output),
                stderr_snippet=_snippet(exc.stderr),
                message=f"{manager} env list timed out after {timeout_seconds} seconds",
                metadata={"failure_class": "command_timeout", "manager": manager},
            )
        if completed.returncode != 0:
            last_failure = PreflightCheck(
                id=f"env.{env_name}.exists",
                label=f"{env_name} backend environment",
                status=_failure_status(severity),
                severity=severity,
                command=command,
                returncode=completed.returncode,
                stdout_snippet=_snippet(completed.stdout),
                stderr_snippet=_snippet(completed.stderr),
                message=f"{manager} env list failed",
                metadata={"failure_class": "command_failed", "manager": manager},
            )
            continue
        envs = parse_environment_list(completed.stdout)
        if env_name in envs:
            return PreflightCheck(
                id=f"env.{env_name}.exists",
                label=f"{env_name} backend environment",
                status=CheckStatus.PASS,
                severity=severity,
                command=command,
                returncode=completed.returncode,
                stdout_snippet=_snippet(completed.stdout),
                stderr_snippet=_snippet(completed.stderr),
                message=f"{env_name} is visible to {manager}",
                metadata={"manager": manager, "available_environments": sorted(envs)},
            )
        last_failure = PreflightCheck(
            id=f"env.{env_name}.exists",
            label=f"{env_name} backend environment",
            status=_failure_status(severity),
            severity=severity,
            command=command,
            returncode=completed.returncode,
            stdout_snippet=_snippet(completed.stdout),
            stderr_snippet=_snippet(completed.stderr),
            message=f"{env_name} is not listed by {manager}",
            metadata={
                "failure_class": _missing_failure_class(severity),
                "manager": manager,
                "available_environments": sorted(envs),
            },
        )

    if attempted:
        assert last_failure is not None
        return last_failure
    return PreflightCheck(
        id=f"env.{env_name}.exists",
        label=f"{env_name} backend environment",
        status=_failure_status(severity),
        severity=severity,
        command=None,
        returncode=None,
        stdout_snippet=None,
        stderr_snippet="conda and mamba not found",
        message="Neither conda nor mamba is available on PATH",
        metadata={"failure_class": "conda_or_mamba_missing"},
    )


def check_path_exists(*, path: Path, severity: CheckSeverity) -> PreflightCheck:
    """Check that a required local path exists."""

    if path.exists():
        return PreflightCheck(
            id=_path_check_id(path, "exists"),
            label=f"{path} exists",
            status=CheckStatus.PASS,
            severity=severity,
            command=None,
            returncode=0,
            stdout_snippet=str(path),
            stderr_snippet=None,
            message=f"{path} exists",
            metadata={"path": str(path)},
        )
    return PreflightCheck(
        id=_path_check_id(path, "exists"),
        label=f"{path} exists",
        status=_failure_status(severity),
        severity=severity,
        command=None,
        returncode=None,
        stdout_snippet=None,
        stderr_snippet=f"{path} does not exist",
        message=f"{path} does not exist",
        metadata={"failure_class": "path_missing", "path": str(path)},
    )


def check_writable_directory(*, path: Path, severity: CheckSeverity) -> PreflightCheck:
    """Check that a directory can be created and written to."""

    test_file = path / ".write_test"
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file.write_text("pdf2md local preflight\n", encoding="utf-8")
        test_file.unlink()
    except PermissionError as exc:
        return PreflightCheck(
            id=_path_check_id(path, "writable"),
            label=f"{path} writable",
            status=_failure_status(severity),
            severity=severity,
            command=None,
            returncode=None,
            stdout_snippet=None,
            stderr_snippet=str(exc),
            message=f"{path} is not writable",
            metadata={"failure_class": "permission_error", "path": str(path)},
        )
    except OSError as exc:
        return PreflightCheck(
            id=_path_check_id(path, "writable"),
            label=f"{path} writable",
            status=_failure_status(severity),
            severity=severity,
            command=None,
            returncode=None,
            stdout_snippet=None,
            stderr_snippet=str(exc),
            message=f"{path} could not be written",
            metadata={"failure_class": "permission_error", "path": str(path)},
        )
    return PreflightCheck(
        id=_path_check_id(path, "writable"),
        label=f"{path} writable",
        status=CheckStatus.PASS,
        severity=severity,
        command=None,
        returncode=0,
        stdout_snippet=str(path),
        stderr_snippet=None,
        message=f"{path} is writable",
        metadata={"path": str(path)},
    )


def build_preflight_report(*, settings: PreflightSettings, repo_root: Path) -> PreflightReport:
    """Run the Plan 7 local preflight check suite."""

    repo_root = repo_root.resolve()
    checks: list[PreflightCheck] = []
    timeout = settings.timeout_seconds

    checks.extend(
        [
            check_command_exists("python"),
            check_command_exists("pytest"),
            check_command_exists("sh"),
            check_conda_environment(
                env_name=MAIN_CONDA_ENV,
                severity=CheckSeverity.REQUIRED,
                timeout_seconds=timeout,
            ),
        ]
    )

    for module in ("pdf2md", "pydantic", "typer", "pytest"):
        checks.append(
            run_help_check(
                check_id=f"python.{_sanitize_id_fragment(module)}.import",
                label=f"{module} import in {MAIN_CONDA_ENV}",
                command=["conda", "run", "-n", MAIN_CONDA_ENV, "python", "-c", f"import {module}; print('{module} ok')"],
                severity=CheckSeverity.REQUIRED,
                timeout_seconds=timeout,
            )
        )
    checks.append(check_python_import(module="docling_core", severity=CheckSeverity.OPTIONAL))

    pipeline_clis = (
        ("calibrate_priors", "Plan 3 calibration CLI", repo_root / "tools/calibrate_priors.py"),
        ("build_consensus", "Plan 4 consensus CLI", repo_root / "tools/build_consensus.py"),
        ("build_linked_structure", "Plan 5 linked structure CLI", repo_root / "tools/build_linked_structure.py"),
        ("export_linked_docling", "Plan 6 export CLI", repo_root / "tools/export_linked_docling.py"),
    )
    for name, label, script in pipeline_clis:
        checks.append(
            run_help_check(
                check_id=f"cli.{name}.help",
                label=label,
                command=["conda", "run", "-n", MAIN_CONDA_ENV, "python", str(script), "--help"],
                severity=CheckSeverity.REQUIRED,
                timeout_seconds=timeout,
            )
        )

    for tool in ("latex", "lualatex"):
        checks.append(
            run_help_check(
                check_id=f"latex.{tool}.version",
                label=f"{tool} executable",
                command=[tool, "--version"],
                severity=CheckSeverity.REQUIRED,
                timeout_seconds=timeout,
            )
        )
    checks.append(check_latexml_executable(severity=CheckSeverity.REQUIRED, timeout_seconds=timeout))
    for tool in ("latexmk", "kpsewhich"):
        checks.append(
            run_help_check(
                check_id=f"latex.{tool}.version",
                label=f"{tool} executable",
                command=[tool, "--version"],
                severity=CheckSeverity.OPTIONAL,
                timeout_seconds=timeout,
            )
        )

    required_backends = _unique_nonempty(settings.required_backends)
    optional_backends = tuple(
        backend for backend in _unique_nonempty(settings.optional_backends) if backend not in required_backends
    )
    for backend, severity in (
        *((backend, CheckSeverity.REQUIRED) for backend in required_backends),
        *((backend, CheckSeverity.OPTIONAL) for backend in optional_backends),
    ):
        connector = repo_root / "backend" / backend / "connector.py"
        checks.append(check_path_exists(path=connector, severity=severity))
        checks.append(
            run_help_check(
                check_id=f"backend_connector.{backend}.help",
                label=f"{backend} connector CLI",
                command=["conda", "run", "-n", MAIN_CONDA_ENV, "python", str(connector), "--help"],
                severity=severity,
                timeout_seconds=timeout,
            )
        )
        checks.append(
            check_conda_environment(
                env_name=f"{settings.backend_env_prefix}{backend}",
                severity=severity,
                timeout_seconds=timeout,
            )
        )

    for output_root in settings.output_roots:
        path = output_root if output_root.is_absolute() else repo_root / output_root
        checks.append(check_writable_directory(path=path, severity=CheckSeverity.REQUIRED))

    warnings = [check.message for check in checks if check.status == CheckStatus.WARN]
    return PreflightReport(
        checks=checks,
        warnings=warnings,
        metadata={
            "repo_root": str(repo_root),
            "main_conda_env": MAIN_CONDA_ENV,
            "settings": {
                **asdict(settings),
                "output_roots": [str(path) for path in settings.output_roots],
            },
        },
    )


def _unique_nonempty(values: tuple[str, ...]) -> tuple[str, ...]:
    unique: list[str] = []
    for value in values:
        stripped = value.strip()
        if stripped and stripped not in unique:
            unique.append(stripped)
    return tuple(unique)


def write_preflight_report(*, report: PreflightReport, out_dir: Path) -> Path:
    """Write machine-readable JSON and a human-readable summary."""

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "preflight_report.json"
    summary_path = out_dir / "preflight_summary.txt"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    summary_path.write_text(_build_summary(report), encoding="utf-8")
    return report_path


def _build_summary(report: PreflightReport) -> str:
    lines = [
        "pdf2md local preflight",
        f"schema: {report.schema_name} {report.schema_version}",
        f"environment_ready: {str(report.environment_ready).lower()}",
        f"required: {report.required_passed} passed, {report.required_failed} failed",
        f"optional: {report.optional_passed} passed, {report.optional_failed} failed",
        "",
        "checks:",
    ]
    for check in report.checks:
        detail = f"- {check.status.value} [{check.severity.value}] {check.id}: {check.message}"
        failure_class = check.metadata.get("failure_class")
        if failure_class:
            detail = f"{detail} ({failure_class})"
        lines.append(detail)
    if report.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def report_to_json_dict(report: PreflightReport) -> dict[str, Any]:
    """Return a JSON-compatible report dictionary."""

    return json.loads(report.model_dump_json())


__all__ = [
    "LOCAL_PREFLIGHT_SCHEMA_VERSION",
    "MAIN_CONDA_ENV",
    "CheckStatus",
    "CheckSeverity",
    "PreflightCheck",
    "PreflightReport",
    "PreflightSettings",
    "build_preflight_report",
    "check_command_exists",
    "check_conda_environment",
    "check_latexml_executable",
    "check_path_exists",
    "check_python_import",
    "check_writable_directory",
    "parse_environment_list",
    "report_to_json_dict",
    "run_help_check",
    "write_preflight_report",
]
