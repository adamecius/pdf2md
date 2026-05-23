"""Plan 18 — tests for the ``pdf2md convert`` CLI command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pdf2md.cli import main as cli_main
from pdf2md.cli.main import app
from pdf2md.pipeline.orchestrator import PipelineResult


@dataclass
class _MockResult:
    overall_status: str
    manifest_path: Path
    stages: list = None
    consensus_ir_path: Path | None = None
    docling_path: Path | None = None
    markdown_path: Path | None = None
    warnings: list = None

    def __post_init__(self) -> None:
        if self.stages is None:
            self.stages = []
        if self.warnings is None:
            self.warnings = []


def _make_inputs(tmp_path: Path) -> tuple[Path, Path]:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    config = tmp_path / "config.toml"
    config.write_text(
        """[settings]
work_dir = ".tmp"

[backends.mineru]
enabled = true
runner = "conda"
env_name = "pdf2md-mineru"
script = "backend/mineru/pdf2md_mineru.py"
"""
    )
    return pdf, config


def test_convert_help_shows_all_options() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["convert", "--help"])
    assert result.exit_code == 0, result.stdout
    text = result.stdout
    for option in (
        "--config",
        "--out-dir",
        "--priors-dir",
        "--force",
        "--dry-run",
        "--timeout",
        "--keep-going",
        "--skip-export",
        "--verbose",
    ):
        assert option in text, option


def test_convert_dry_run_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf, config = _make_inputs(tmp_path)
    out_dir = tmp_path / "out"

    captured: dict = {}

    def fake_run_pipeline(input_pdf: Path, target_out_dir: Path, settings) -> PipelineResult:
        captured["dry_run"] = settings.dry_run
        captured["out_dir"] = target_out_dir
        return _MockResult(overall_status="not_started", manifest_path=target_out_dir / "pipeline_manifest.json")

    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["convert", str(pdf), "--config", str(config), "--out-dir", str(out_dir), "--dry-run"],
    )
    assert result.exit_code == 0, result.stdout
    assert captured["dry_run"] is True


def test_convert_success_exit_code_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf, config = _make_inputs(tmp_path)

    def fake_run_pipeline(input_pdf: Path, target_out_dir: Path, settings) -> PipelineResult:
        target_out_dir.mkdir(parents=True, exist_ok=True)
        manifest = target_out_dir / "pipeline_manifest.json"
        manifest.write_text("{}")
        (target_out_dir / "pipeline_summary.txt").write_text("ok summary\n")
        return _MockResult(overall_status="success", manifest_path=manifest)

    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        app, ["convert", str(pdf), "--config", str(config), "--out-dir", str(tmp_path / "out")]
    )
    assert result.exit_code == 0, result.stdout
    assert "ok summary" in result.stdout


def test_convert_failed_exit_code_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf, config = _make_inputs(tmp_path)

    def fake_run_pipeline(input_pdf: Path, target_out_dir: Path, settings) -> PipelineResult:
        target_out_dir.mkdir(parents=True, exist_ok=True)
        manifest = target_out_dir / "pipeline_manifest.json"
        manifest.write_text("{}")
        (target_out_dir / "pipeline_summary.txt").write_text("failed\n")
        return _MockResult(overall_status="failed", manifest_path=manifest)

    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        app, ["convert", str(pdf), "--config", str(config), "--out-dir", str(tmp_path / "out")]
    )
    assert result.exit_code == 1, result.stdout


def test_convert_partial_exit_code_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf, config = _make_inputs(tmp_path)

    def fake_run_pipeline(input_pdf: Path, target_out_dir: Path, settings) -> PipelineResult:
        target_out_dir.mkdir(parents=True, exist_ok=True)
        manifest = target_out_dir / "pipeline_manifest.json"
        manifest.write_text("{}")
        (target_out_dir / "pipeline_summary.txt").write_text("partial\n")
        return _MockResult(overall_status="partial", manifest_path=manifest)

    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        app, ["convert", str(pdf), "--config", str(config), "--out-dir", str(tmp_path / "out")]
    )
    assert result.exit_code == 2, result.stdout


def test_convert_default_out_dir_is_tmp_stem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf, config = _make_inputs(tmp_path)
    seen: dict = {}

    def fake_run_pipeline(input_pdf: Path, target_out_dir: Path, settings) -> PipelineResult:
        seen["out_dir"] = target_out_dir
        target_out_dir.mkdir(parents=True, exist_ok=True)
        manifest = target_out_dir / "pipeline_manifest.json"
        manifest.write_text("{}")
        (target_out_dir / "pipeline_summary.txt").write_text("\n")
        return _MockResult(overall_status="success", manifest_path=manifest)

    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["convert", str(pdf), "--config", str(config)])
        assert result.exit_code == 0, result.stdout
        assert seen["out_dir"] == Path(".tmp") / "doc"
