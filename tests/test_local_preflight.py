from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from pdf2md.local import preflight
from pdf2md.local.preflight import (
    CheckSeverity,
    CheckStatus,
    PreflightCheck,
    PreflightReport,
    PreflightSettings,
    build_preflight_report,
    check_command_exists,
    check_conda_environment,
    check_latexml_executable,
    check_path_exists,
    check_python_import,
    check_writable_directory,
    parse_environment_list,
    run_help_check,
    write_preflight_report,
)

CLI = Path("tools/local_groundtruth_preflight.py")
FIXTURES = Path("tests/data/local_preflight_fixtures")


def _check(
    check_id: str = "check.pass",
    *,
    status: CheckStatus = CheckStatus.PASS,
    severity: CheckSeverity = CheckSeverity.REQUIRED,
) -> PreflightCheck:
    return PreflightCheck(
        id=check_id,
        label=check_id,
        status=status,
        severity=severity,
        command=None,
        returncode=0 if status == CheckStatus.PASS else 1,
        stdout_snippet=None,
        stderr_snippet=None,
        message=f"{check_id} message",
        metadata={},
    )


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("local_groundtruth_preflight_test", CLI)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_status_enum_values() -> None:
    assert [item.value for item in CheckStatus] == ["pass", "warn", "fail", "skip"]


def test_check_severity_enum_values() -> None:
    assert [item.value for item in CheckSeverity] == ["required", "optional"]


def test_preflight_check_minimal_construction() -> None:
    check = PreflightCheck(
        id="python.pdf2md.import",
        label="pdf2md import",
        status=CheckStatus.PASS,
        severity=CheckSeverity.REQUIRED,
        message="ok",
        metadata={},
    )
    assert check.command is None
    assert check.status == CheckStatus.PASS


def test_preflight_report_rejects_duplicate_check_ids() -> None:
    with pytest.raises(ValidationError, match="check ids must be unique"):
        PreflightReport(checks=[_check("dup"), _check("dup")])


def test_preflight_report_computes_counts() -> None:
    report = PreflightReport(
        checks=[
            _check("required.pass"),
            _check("required.fail", status=CheckStatus.FAIL),
            _check("optional.pass", severity=CheckSeverity.OPTIONAL),
            _check("optional.fail", status=CheckStatus.FAIL, severity=CheckSeverity.OPTIONAL),
        ]
    )
    assert report.required_passed == 1
    assert report.required_failed == 1
    assert report.optional_passed == 1
    assert report.optional_failed == 1


def test_preflight_report_rejects_bad_required_failed_count() -> None:
    with pytest.raises(ValidationError, match="required_failed must match"):
        PreflightReport(checks=[_check("required.fail", status=CheckStatus.FAIL)], required_failed=0)


def test_preflight_report_environment_ready_false_when_required_failures_exist() -> None:
    report = PreflightReport(checks=[_check("required.fail", status=CheckStatus.FAIL)])
    assert report.environment_ready is False
    with pytest.raises(ValidationError, match="environment_ready"):
        PreflightReport(
            checks=[_check("required.fail", status=CheckStatus.FAIL)],
            required_failed=1,
            environment_ready=True,
        )


def test_command_exists_check_passes_with_mocked_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: f"/usr/bin/{command}")
    check = check_command_exists("python")
    assert check.status == CheckStatus.PASS
    assert check.metadata["path"] == "/usr/bin/python"


def test_command_exists_check_fails_with_mocked_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: None)
    check = check_command_exists("latexml")
    assert check.status == CheckStatus.FAIL
    assert check.metadata["failure_class"] == "environment_missing"


def test_run_help_check_passes_when_subprocess_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(command, 0, stdout="usage\n", stderr="")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = run_help_check(
        check_id="cli.demo.help",
        label="demo CLI",
        command=["python", "demo.py", "--help"],
        severity=CheckSeverity.REQUIRED,
        timeout_seconds=3,
    )
    assert result.status == CheckStatus.PASS
    assert result.stdout_snippet == "usage\n"


def test_run_help_check_fails_when_subprocess_returns_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="ImportError: broken")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = run_help_check(
        check_id="cli.export_linked_docling.help",
        label="export CLI",
        command=["python", "tools/export_linked_docling.py", "--help"],
        severity=CheckSeverity.REQUIRED,
        timeout_seconds=3,
    )
    assert result.status == CheckStatus.FAIL
    assert result.metadata["failure_class"] == "repository_defect"


def test_run_help_check_records_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text, timeout, check):
        raise subprocess.TimeoutExpired(command, timeout, output="partial", stderr="late")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = run_help_check(
        check_id="latex.lualatex.version",
        label="lualatex",
        command=["lualatex", "--version"],
        severity=CheckSeverity.REQUIRED,
        timeout_seconds=3,
    )
    assert result.status == CheckStatus.FAIL
    assert result.metadata["failure_class"] == "command_timeout"


def test_latexml_probe_accepts_version_banner_from_stderr_when_returncode_is_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: "/usr/bin/latexml")

    def fake_run(command, capture_output, text, timeout, check):
        assert command == ["latexml", "--version"]
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="Unknown option: version\nlatexml (LaTeXML version 0.8.6)\nUsage:\n",
        )

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = check_latexml_executable(severity=CheckSeverity.REQUIRED, timeout_seconds=3)
    assert result.status == CheckStatus.PASS
    assert result.returncode == 1
    assert result.metadata["version"] == "0.8.6"
    assert result.metadata["probe_note"] == "unsupported_version_flag"


def test_latexml_probe_fails_when_executable_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: None)

    def fake_run(*args, **kwargs):
        raise AssertionError("latexml should not be invoked when it is missing")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = check_latexml_executable(severity=CheckSeverity.REQUIRED, timeout_seconds=3)
    assert result.status == CheckStatus.FAIL
    assert result.metadata["failure_class"] == "environment_missing"


def test_latexml_probe_warns_or_fails_cleanly_when_executable_exists_but_no_latexml_signal_is_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: "/usr/bin/latexml")
    commands: list[list[str]] = []

    def fake_run(command, capture_output, text, timeout, check):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="usage text", stderr="unrecognized option")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = check_latexml_executable(severity=CheckSeverity.REQUIRED, timeout_seconds=3)
    assert result.status == CheckStatus.FAIL
    assert result.metadata["failure_class"] == "command_failed"
    assert commands == [["latexml", "--version"], ["latexml", "--help"]]


def test_python_import_check_passes_with_mocked_import(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.importlib, "import_module", lambda module: object())
    result = check_python_import(module="pydantic", severity=CheckSeverity.REQUIRED)
    assert result.status == CheckStatus.PASS


def test_python_import_check_fails_with_mocked_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import(module):
        raise ImportError("missing")

    monkeypatch.setattr(preflight.importlib, "import_module", fake_import)
    result = check_python_import(module="docling_core", severity=CheckSeverity.OPTIONAL)
    assert result.status == CheckStatus.WARN
    assert result.metadata["failure_class"] == "optional_missing"


def test_path_exists_check_passes(tmp_path: Path) -> None:
    path = tmp_path / "connector.py"
    path.write_text("# ok\n", encoding="utf-8")
    assert check_path_exists(path=path, severity=CheckSeverity.REQUIRED).status == CheckStatus.PASS


def test_path_exists_check_fails(tmp_path: Path) -> None:
    result = check_path_exists(path=tmp_path / "missing.py", severity=CheckSeverity.REQUIRED)
    assert result.status == CheckStatus.FAIL
    assert result.metadata["failure_class"] == "path_missing"


def test_writable_directory_check_creates_directory(tmp_path: Path) -> None:
    path = tmp_path / "new" / "run"
    result = check_writable_directory(path=path, severity=CheckSeverity.REQUIRED)
    assert result.status == CheckStatus.PASS
    assert path.is_dir()
    assert not (path / ".write_test").exists()


def test_writable_directory_check_reports_permission_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "write_text", denied)
    result = check_writable_directory(path=tmp_path / "locked", severity=CheckSeverity.REQUIRED)
    assert result.status == CheckStatus.FAIL
    assert result.metadata["failure_class"] == "permission_error"


def test_conda_env_parser_detects_expected_env() -> None:
    output = """
# conda environments:
base                     *  /opt/conda
pdf2md-mineru              /opt/conda/envs/pdf2md-mineru
"""
    assert "pdf2md-mineru" in parse_environment_list(output)


def test_mamba_env_parser_detects_expected_env() -> None:
    output = """
# mamba environments:
pdf2md-paddleocr           /mamba/envs/pdf2md-paddleocr
pdf2md-deepseek         *  /mamba/envs/pdf2md-deepseek
"""
    envs = parse_environment_list(output)
    assert {"pdf2md-paddleocr", "pdf2md-deepseek"} <= envs


def test_conda_environment_check_detects_expected_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: "/bin/conda" if command == "conda" else None)

    def fake_run(command, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(command, 0, stdout="pdf2md-mineru /envs/pdf2md-mineru\n", stderr="")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = check_conda_environment(
        env_name="pdf2md-mineru",
        severity=CheckSeverity.REQUIRED,
        timeout_seconds=3,
    )
    assert result.status == CheckStatus.PASS
    assert result.metadata["manager"] == "conda"


def test_mamba_environment_check_detects_expected_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: "/bin/mamba" if command == "mamba" else None)

    def fake_run(command, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(command, 0, stdout="pdf2md-aux /envs/pdf2md-aux\n", stderr="")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    result = check_conda_environment(
        env_name="pdf2md-aux",
        severity=CheckSeverity.OPTIONAL,
        timeout_seconds=3,
    )
    assert result.status == CheckStatus.PASS
    assert result.metadata["manager"] == "mamba"


def test_missing_conda_and_mamba_reports_required_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda command: None)
    result = check_conda_environment(
        env_name="pdf2md-mineru",
        severity=CheckSeverity.REQUIRED,
        timeout_seconds=3,
    )
    assert result.status == CheckStatus.FAIL
    assert result.metadata["failure_class"] == "conda_or_mamba_missing"


def test_build_preflight_report_includes_expected_check_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_command(command: str) -> PreflightCheck:
        return _check(f"command.{command}.exists")

    def fake_run_help(**kwargs) -> PreflightCheck:
        return _check(kwargs["check_id"], severity=kwargs["severity"])

    def fake_env(env_name: str, severity: CheckSeverity, timeout_seconds: int) -> PreflightCheck:
        return _check(f"env.{env_name}.exists", severity=severity)

    def fake_path(path: Path, severity: CheckSeverity) -> PreflightCheck:
        return _check(f"path.{path.parent.name}.{path.name}.exists", severity=severity)

    def fake_writable(path: Path, severity: CheckSeverity) -> PreflightCheck:
        return _check(f"path.{path.name}.writable", severity=severity)

    monkeypatch.setattr(preflight, "check_command_exists", fake_command)
    monkeypatch.setattr(preflight, "run_help_check", fake_run_help)
    monkeypatch.setattr(
        preflight,
        "check_latexml_executable",
        lambda severity, timeout_seconds: _check("latex.latexml.version", severity=severity),
    )
    monkeypatch.setattr(preflight, "check_conda_environment", fake_env)
    monkeypatch.setattr(preflight, "check_path_exists", fake_path)
    monkeypatch.setattr(preflight, "check_writable_directory", fake_writable)
    monkeypatch.setattr(preflight, "check_python_import", lambda module, severity: _check(f"python_import.{module}", severity=severity))

    report = build_preflight_report(settings=PreflightSettings(), repo_root=tmp_path)
    ids = {check.id for check in report.checks}
    assert "cli.calibrate_priors.help" in ids
    assert "cli.export_linked_docling.help" in ids
    assert "latex.lualatex.version" in ids
    assert "latex.latexml.version" in ids
    assert "backend_connector.mineru.help" in ids
    assert "env.pdf2md-mineru.exists" in ids


def test_default_backend_scope_excludes_glm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_command(command: str) -> PreflightCheck:
        return _check(f"command.{command}.exists")

    def fake_run_help(**kwargs) -> PreflightCheck:
        return _check(kwargs["check_id"], severity=kwargs["severity"])

    def fake_env(env_name: str, severity: CheckSeverity, timeout_seconds: int) -> PreflightCheck:
        return _check(f"env.{env_name}.exists", severity=severity)

    def fake_path(path: Path, severity: CheckSeverity) -> PreflightCheck:
        return _check(f"path.{path.parent.name}.{path.name}.exists", severity=severity)

    def fake_writable(path: Path, severity: CheckSeverity) -> PreflightCheck:
        return _check(f"path.{path.name}.writable", severity=severity)

    monkeypatch.setattr(preflight, "check_command_exists", fake_command)
    monkeypatch.setattr(preflight, "run_help_check", fake_run_help)
    monkeypatch.setattr(
        preflight,
        "check_latexml_executable",
        lambda severity, timeout_seconds: _check("latex.latexml.version", severity=severity),
    )
    monkeypatch.setattr(preflight, "check_conda_environment", fake_env)
    monkeypatch.setattr(preflight, "check_path_exists", fake_path)
    monkeypatch.setattr(preflight, "check_writable_directory", fake_writable)
    monkeypatch.setattr(
        preflight,
        "check_python_import",
        lambda module, severity: _check(f"python_import.{module}", severity=severity),
    )

    report = build_preflight_report(settings=PreflightSettings(), repo_root=tmp_path)
    ids = {check.id for check in report.checks}
    assert PreflightSettings().optional_backends == ()
    assert "backend_connector.glm.help" not in ids
    assert "env.pdf2md-glm.exists" not in ids


def test_write_preflight_report_writes_json_and_summary(tmp_path: Path) -> None:
    report = PreflightReport(checks=[_check("required.pass")])
    path = write_preflight_report(report=report, out_dir=tmp_path)
    assert path == tmp_path / "preflight_report.json"
    assert json.loads(path.read_text(encoding="utf-8"))["schema_name"] == "pdf2md.LocalPreflightReport"
    assert "environment_ready: true" in (tmp_path / "preflight_summary.txt").read_text(encoding="utf-8")


def test_cli_help_exits_zero() -> None:
    completed = subprocess.run([sys.executable, str(CLI), "--help"], check=False, text=True, capture_output=True)
    assert completed.returncode == 0
    assert "--required-backends" in completed.stdout


def test_cli_writes_report_using_mocked_builder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cli = _load_cli_module()
    report = PreflightReport(checks=[_check("required.pass")])

    def fake_build(settings, repo_root):
        assert settings.required_backends == ("mineru", "deepseek")
        assert settings.optional_backends == ("aux",)
        return report

    monkeypatch.setattr(cli, "build_preflight_report", fake_build)
    rc = cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "out"),
            "--required-backends",
            "mineru,deepseek",
            "--optional-backends",
            "aux",
        ]
    )
    assert rc == 0
    assert (tmp_path / "out/preflight_report.json").exists()
    assert (tmp_path / "out/preflight_summary.txt").exists()


def test_expected_environment_fixtures_are_valid_json() -> None:
    minimal = json.loads((FIXTURES / "expected_environment.min.json").read_text(encoding="utf-8"))
    full = json.loads((FIXTURES / "expected_environment.full.json").read_text(encoding="utf-8"))
    assert minimal["required_backends"] == ["mineru", "paddleocr", "deepseek"]
    assert minimal["optional_backends"] == []
    assert full["optional_backends"] == []
    assert "tools/export_linked_docling.py" in full["required_project_clis"]
