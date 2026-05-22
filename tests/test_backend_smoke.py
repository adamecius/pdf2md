from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from pdf2md.local.backend_smoke import (
    BackendSmokeStatus,
    assemble_smoke_report,
    build_backend_result,
    write_backend_smoke_report,
)

CLI = Path("tools/backend_smoke.py")
FIXED_TIMESTAMP = "2026-01-01T00:00:00Z"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("backend_smoke_cli_test", CLI)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(results, gate_minimum=2):
    return assemble_smoke_report(
        results=results,
        gate_minimum=gate_minimum,
        repo_root="/repo",
        corpus_root="/repo/groundtruth/corpus/latex",
        input_pdf="/repo/sample.pdf",
        generated_at=FIXED_TIMESTAMP,
    )


def test_success_requires_exit_zero_and_output_files() -> None:
    result = build_backend_result(
        backend_name="mineru",
        configured=True,
        enabled=True,
        exit_code=0,
        output_files_found=["output.md", "manifest.json"],
    )
    assert result.status == BackendSmokeStatus.SUCCESS
    assert result.missing_output_patterns == []


def test_exit_zero_without_outputs_is_output_missing() -> None:
    result = build_backend_result(
        backend_name="mineru",
        configured=True,
        enabled=True,
        exit_code=0,
        output_files_found=[],
    )
    assert result.status == BackendSmokeStatus.OUTPUT_MISSING
    assert "output.md" in result.missing_output_patterns


def test_env_not_ready_classification() -> None:
    result = build_backend_result(
        backend_name="mineru",
        configured=True,
        enabled=True,
        exit_code=1,
        stderr="CondaError: Could not find conda environment: pdf2md-mineru",
    )
    assert result.status == BackendSmokeStatus.ENV_NOT_READY


def test_model_missing_classification() -> None:
    result = build_backend_result(
        backend_name="deepseek",
        configured=True,
        enabled=True,
        exit_code=1,
        stderr="FileNotFoundError: model checkpoint missing at .local_models/deepseek/model.safetensors",
    )
    assert result.status == BackendSmokeStatus.MODEL_MISSING


def test_dependency_missing_classification() -> None:
    result = build_backend_result(
        backend_name="paddleocr",
        configured=True,
        enabled=True,
        exit_code=1,
        stderr="ModuleNotFoundError: No module named 'paddleocr'",
    )
    assert result.status == BackendSmokeStatus.DEPENDENCY_MISSING


def test_backend_crash_classification() -> None:
    result = build_backend_result(
        backend_name="mineru",
        configured=True,
        enabled=True,
        exit_code=1,
        stderr="RuntimeError: unexpected internal failure in the backend pipeline",
    )
    assert result.status == BackendSmokeStatus.BACKEND_CRASH


def test_timeout_classification() -> None:
    result = build_backend_result(
        backend_name="mineru",
        configured=True,
        enabled=True,
        exit_code=None,
        timed_out=True,
    )
    assert result.status == BackendSmokeStatus.TIMEOUT


def test_not_configured_classification() -> None:
    result = build_backend_result(
        backend_name="glm",
        configured=False,
        enabled=False,
    )
    assert result.status == BackendSmokeStatus.NOT_CONFIGURED


def test_gate_passes_with_two_successes() -> None:
    report = _report(
        [
            build_backend_result(backend_name="mineru", configured=True, enabled=True, exit_code=0,
                                  output_files_found=["output.md"]),
            build_backend_result(backend_name="paddleocr", configured=True, enabled=True, exit_code=0,
                                  output_files_found=["manifest.json"]),
            build_backend_result(backend_name="glm", configured=False, enabled=False),
        ]
    )
    assert report.backends_successful == 2
    assert report.gate_passed is True


def test_gate_fails_with_one_success() -> None:
    report = _report(
        [
            build_backend_result(backend_name="mineru", configured=True, enabled=True, exit_code=0,
                                  output_files_found=["output.md"]),
            build_backend_result(backend_name="deepseek", configured=True, enabled=True, exit_code=1,
                                  stderr="RuntimeError: crash"),
        ]
    )
    assert report.backends_successful == 1
    assert report.gate_passed is False


def test_strict_gate_exit_one_when_gate_fails(tmp_path: Path) -> None:
    cli = _load_cli_module()
    report = _report(
        [build_backend_result(backend_name="mineru", configured=True, enabled=True, exit_code=0,
                              output_files_found=["output.md"])]
    )
    assert report.gate_passed is False

    def fake_build(**kwargs):
        return report

    cli.build_backend_smoke_report = fake_build
    rc = cli.main(["--out-dir", str(tmp_path / "out"), "--strict-gate"])
    assert rc == 1
    assert (tmp_path / "out/backend_smoke_report.json").exists()


def test_nonstrict_gate_exit_zero_when_gate_fails(tmp_path: Path) -> None:
    cli = _load_cli_module()
    report = _report(
        [build_backend_result(backend_name="mineru", configured=True, enabled=True, exit_code=0,
                              output_files_found=["output.md"])]
    )
    assert report.gate_passed is False

    def fake_build(**kwargs):
        return report

    cli.build_backend_smoke_report = fake_build
    rc = cli.main(["--out-dir", str(tmp_path / "out")])
    assert rc == 0
    assert (tmp_path / "out/backend_smoke_report.json").exists()


def test_report_json_contract() -> None:
    report = _report(
        [
            build_backend_result(backend_name="mineru", configured=True, enabled=True, exit_code=0,
                                  output_files_found=["output.md"]),
            build_backend_result(backend_name="glm", configured=False, enabled=False),
        ]
    )
    payload = json.loads(report.model_dump_json())
    for key in (
        "schema_name",
        "schema_version",
        "generated_at",
        "tool_name",
        "repo_root",
        "corpus_root",
        "input_pdf",
        "gate_minimum",
        "gate_passed",
        "total_backends",
        "backends_successful",
        "backends_failed",
        "backends_deferred",
        "results",
        "warnings",
        "metadata",
    ):
        assert key in payload
    assert payload["schema_name"] == "pdf2md.BackendSmokeReport"
    assert payload["tool_name"] == "backend_smoke"
    assert "ready_for_connector_validation" not in payload
    backend = payload["results"][0]
    for key in (
        "backend_name",
        "configured",
        "enabled",
        "environment_name",
        "command",
        "input_pdf",
        "output_dir",
        "exit_code",
        "duration_seconds",
        "status",
        "expected_output_patterns",
        "output_files_found",
        "missing_output_patterns",
        "stdout_snippet",
        "stderr_snippet",
        "failure_reason",
        "next_action",
        "metadata",
    ):
        assert key in backend


def test_summary_is_written(tmp_path: Path) -> None:
    report = _report(
        [
            build_backend_result(backend_name="mineru", configured=True, enabled=True, exit_code=0,
                                  output_files_found=["output.md"]),
            build_backend_result(backend_name="deepseek", configured=True, enabled=True, exit_code=1,
                                  stderr="RuntimeError: crash"),
        ]
    )
    report_path = write_backend_smoke_report(report=report, out_dir=tmp_path)
    summary_path = report_path.with_name("backend_smoke_summary.txt")
    assert report_path == tmp_path / "backend_smoke_report.json"
    assert summary_path.exists()
    summary = summary_path.read_text(encoding="utf-8")
    assert "backend smoke readiness" in summary
    assert "Plan 10" in summary


def test_next_action_is_present_for_every_backend() -> None:
    report = _report(
        [
            build_backend_result(backend_name="b_success", configured=True, enabled=True, exit_code=0,
                                  output_files_found=["output.md"]),
            build_backend_result(backend_name="b_output", configured=True, enabled=True, exit_code=0,
                                  output_files_found=[]),
            build_backend_result(backend_name="b_env", configured=True, enabled=True, exit_code=1,
                                  stderr="Could not find conda environment: pdf2md-x"),
            build_backend_result(backend_name="b_model", configured=True, enabled=True, exit_code=1,
                                  stderr="missing model checkpoint .safetensors"),
            build_backend_result(backend_name="b_dep", configured=True, enabled=True, exit_code=1,
                                  stderr="ModuleNotFoundError: No module named 'x'"),
            build_backend_result(backend_name="b_crash", configured=True, enabled=True, exit_code=1,
                                  stderr="RuntimeError: crash"),
            build_backend_result(backend_name="b_timeout", configured=True, enabled=True, timed_out=True),
            build_backend_result(backend_name="b_notcfg", configured=False, enabled=False),
        ]
    )
    assert report.total_backends == 8
    for result in report.results:
        assert isinstance(result.next_action, str)
        assert result.next_action.strip()
