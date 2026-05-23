"""Plan 18 — tests for the single-document pipeline orchestrator.

These tests never spawn real backend subprocesses: we monkeypatch
``run_configured_backends`` to write synthetic raw markdown into
``<out_dir>/raw/<backend>/`` and a matching ``status.json``. From there the
real connector, consensus, linking and export modules execute end-to-end.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pdf2md.pipeline import orchestrator as orch
from pdf2md.pipeline.orchestrator import (
    PIPELINE_MANIFEST_SCHEMA_NAME,
    PipelineResult,
    PipelineSettings,
    run_pipeline,
)


SAMPLE_MARKDOWN = """# Introduction

This is the first paragraph of a synthetic document.

<--- Page Split --->

# Methods

Another paragraph on page two.
"""


def _config(backends: list[str]) -> dict:
    return {
        "settings": {"work_dir": ".tmp", "default_timeout_seconds": 60, "stop_on_failure": False},
        "backends": {
            name: {
                "enabled": True,
                "env_name": f"pdf2md-{name}",
                "script": f"backend/{name}/run.py",
            }
            for name in backends
        },
    }


def _write_raw_success(layout_run_dir: Path, backend: str, markdown: str = SAMPLE_MARKDOWN) -> None:
    backend_dir = layout_run_dir / "raw" / backend
    backend_dir.mkdir(parents=True, exist_ok=True)
    (backend_dir / "output.md").write_text(markdown, encoding="utf-8")
    (backend_dir / "manifest.json").write_text(
        json.dumps({"backend_version": "test"}), encoding="utf-8"
    )
    now = datetime.now(UTC).isoformat()
    (backend_dir / "status.json").write_text(
        json.dumps(
            {
                "backend": backend,
                "returncode": 0,
                "success": True,
                "output_md": str(backend_dir / "output.md"),
                "manifest_json": str(backend_dir / "manifest.json"),
                "started_at": now,
                "finished_at": now,
                "duration_seconds": 0.1,
            }
        ),
        encoding="utf-8",
    )


def _write_raw_failure(layout_run_dir: Path, backend: str) -> None:
    backend_dir = layout_run_dir / "raw" / backend
    backend_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    (backend_dir / "status.json").write_text(
        json.dumps(
            {
                "backend": backend,
                "returncode": 1,
                "success": False,
                "output_md": str(backend_dir / "output.md"),
                "manifest_json": str(backend_dir / "manifest.json"),
                "started_at": now,
                "finished_at": now,
                "duration_seconds": 0.1,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def fake_input_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% fake")
    return pdf


def _install_backend_mock(monkeypatch: pytest.MonkeyPatch, succeed: list[str], fail: list[str] | None = None) -> list[dict]:
    """Replace ``run_configured_backends`` with a writer that simulates outputs.

    Returns a list that will collect the call kwargs for assertion.
    """

    fail = fail or []
    calls: list[dict] = []

    def fake_runner(**kwargs: object) -> int:
        calls.append(dict(kwargs))
        work_dir = Path(kwargs["work_dir_override"])  # type: ignore[arg-type]
        run_name = str(kwargs["run_name_override"])
        run_dir = work_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        for backend in succeed:
            _write_raw_success(run_dir, backend)
        for backend in fail:
            _write_raw_failure(run_dir, backend)
        return 0 if not fail else 1

    monkeypatch.setattr(orch, "run_configured_backends", fake_runner)
    # Make sure backend-specific connector imports fall back to the default
    # connector (avoid picking up backend/mineru/connector.py if present).
    monkeypatch.setattr(orch, "_resolve_connector_callable", lambda backend: None)
    return calls


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_single_backend_full_pipeline(tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_backend_mock(monkeypatch, succeed=["mineru"])

    out_dir = tmp_path / "out"
    settings = PipelineSettings(config=_config(["mineru"]))
    result = run_pipeline(fake_input_pdf, out_dir, settings)

    assert isinstance(result, PipelineResult)
    assert result.overall_status == "success", _stage_dump(result)
    assert result.consensus_ir_path is not None
    assert result.consensus_ir_path.exists()
    assert result.docling_path is not None and result.docling_path.exists()
    assert result.markdown_path is not None and result.markdown_path.exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_name"] == PIPELINE_MANIFEST_SCHEMA_NAME
    assert manifest["schema_version"] == 1
    assert manifest["document_id"] == "doc"
    assert manifest["backends_requested"] == ["mineru"]
    assert manifest["backends_succeeded"] == ["mineru"]
    assert manifest["overall_status"] == "success"

    stage_names = [s["name"] for s in manifest["stages"]]
    assert stage_names == [
        "backend_execution",
        "connector",
        "calibration",
        "consensus",
        "linking",
        "export",
    ]


def test_two_backends_full_pipeline(tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_backend_mock(monkeypatch, succeed=["mineru", "paddleocr"])

    settings = PipelineSettings(config=_config(["mineru", "paddleocr"]))
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)

    assert result.overall_status == "success", _stage_dump(result)
    consensus = json.loads(result.consensus_ir_path.read_text())
    backends = {b["backend"] for b in consensus["backends"]}
    assert backends == {"mineru", "paddleocr"}


# ---------------------------------------------------------------------------
# Partial / failure cases
# ---------------------------------------------------------------------------


def test_one_backend_fails_pipeline_partial(tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_backend_mock(monkeypatch, succeed=["mineru"], fail=["paddleocr"])

    settings = PipelineSettings(config=_config(["mineru", "paddleocr"]))
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)

    assert result.overall_status == "partial", _stage_dump(result)
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["backends_succeeded"] == ["mineru"]
    backend_stage = next(s for s in manifest["stages"] if s["name"] == "backend_execution")
    assert backend_stage["status"] == "success"
    assert any("backends_failed" in w for w in backend_stage.get("warnings", []))


def test_all_backends_fail_overall_failed_downstream_not_started(
    tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_backend_mock(monkeypatch, succeed=[], fail=["mineru", "paddleocr"])

    settings = PipelineSettings(config=_config(["mineru", "paddleocr"]))
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)

    assert result.overall_status == "failed", _stage_dump(result)
    manifest = json.loads(result.manifest_path.read_text())
    by_name = {s["name"]: s for s in manifest["stages"]}
    assert by_name["backend_execution"]["status"] == "failed"
    for downstream in ("connector", "consensus", "linking", "export"):
        assert by_name[downstream]["status"] == "not_started", downstream


def test_zero_enabled_backends_fails_cleanly(tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = PipelineSettings(config={"settings": {}, "backends": {}})
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)
    assert result.overall_status == "failed"
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["backends_requested"] == []


# ---------------------------------------------------------------------------
# Priors / calibration
# ---------------------------------------------------------------------------


def test_pre_existing_priors_get_copied(tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_backend_mock(monkeypatch, succeed=["mineru"])

    priors_src = tmp_path / "priors"
    priors_src.mkdir()
    prior = {
        "schema_name": "pdf2md.CalibrationPriorDocument",
        "schema_version": "1.0.0",
        "backend": "mineru",
        "backend_version": "test",
        "block_priors": [],
        "entity_priors": [],
        "metadata": {},
    }
    (priors_src / "mineru.json").write_text(json.dumps(prior))

    settings = PipelineSettings(config=_config(["mineru"]), priors_dir=priors_src)
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)

    # Even if the prior schema validation upstream emits warnings, calibration
    # stage itself must report "success" because the file was copied.
    manifest = json.loads(result.manifest_path.read_text())
    calib = next(s for s in manifest["stages"] if s["name"] == "calibration")
    copied = (tmp_path / "out" / "priors" / "mineru.json").exists()
    assert copied
    assert calib["status"] == "success"


def test_without_priors_calibration_skipped(tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_backend_mock(monkeypatch, succeed=["mineru"])

    settings = PipelineSettings(config=_config(["mineru"]))  # no priors
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)

    manifest = json.loads(result.manifest_path.read_text())
    calib = next(s for s in manifest["stages"] if s["name"] == "calibration")
    assert calib["status"] == "skipped"
    # Consensus still ran successfully without priors:
    consensus_stage = next(s for s in manifest["stages"] if s["name"] == "consensus")
    assert consensus_stage["status"] == "success"


# ---------------------------------------------------------------------------
# Dry run / manifest schema
# ---------------------------------------------------------------------------


def test_dry_run_creates_no_files(tmp_path: Path, fake_input_pdf: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_dir = tmp_path / "out"
    settings = PipelineSettings(config=_config(["mineru"]), dry_run=True)
    result = run_pipeline(fake_input_pdf, out_dir, settings)

    assert result.overall_status == "not_started"
    assert not out_dir.exists()
    assert all(s.status == "not_started" for s in result.stages)
    captured = capsys.readouterr()
    assert "dry-run" in captured.out.lower()


def test_manifest_has_required_schema_fields(
    tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_backend_mock(monkeypatch, succeed=["mineru"])

    settings = PipelineSettings(config=_config(["mineru"]))
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)

    manifest = json.loads(result.manifest_path.read_text())
    for key in (
        "schema_name",
        "schema_version",
        "document_id",
        "input_pdf",
        "backends_requested",
        "backends_succeeded",
        "stages",
        "overall_status",
    ):
        assert key in manifest, key
    for stage in manifest["stages"]:
        assert "name" in stage and "status" in stage


def test_summary_file_written(tmp_path: Path, fake_input_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_backend_mock(monkeypatch, succeed=["mineru"])
    settings = PipelineSettings(config=_config(["mineru"]))
    result = run_pipeline(fake_input_pdf, tmp_path / "out", settings)

    summary_path = result.manifest_path.with_name("pipeline_summary.txt")
    assert summary_path.exists()
    text = summary_path.read_text()
    assert "Pipeline Summary" in text
    assert "Document: doc" in text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stage_dump(result: PipelineResult) -> str:
    return "\n".join(f"{s.name}: {s.status} err={s.error}" for s in result.stages)
