from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.backends.runner import derive_run_name, run_configured_backends, validate_safe_run_name
from pdf2md.config import get_enabled_backends, load_backend_config


def _config_text() -> str:
    return """
[settings]
work_dir = ".tmp"
default_timeout_seconds = 60
stop_on_failure = true

[backends.mineru]
enabled = true
runner = "conda"
env_name = "pdf2md-mineru"
script = "backend/mineru/pdf2md_mineru.py"

[backends.deepseek]
enabled = false
runner = "conda"
env_name = "pdf2md-deepseek"
script = "backend/deepseek/pdf2md_deepseek.py"
""".strip()


def test_safe_run_names() -> None:
    assert validate_safe_run_name("test") == "test"
    assert validate_safe_run_name("book_01") == "book_01"
    assert validate_safe_run_name("chapter-2") == "chapter-2"
    with pytest.raises(ValueError):
        validate_safe_run_name("my book")
    with pytest.raises(ValueError):
        validate_safe_run_name("../book")


def test_config_loading_and_enabled_selection(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    enabled = get_enabled_backends(config)
    assert "mineru" in enabled
    assert "deepseek" not in enabled


def test_dry_run_creates_manifest_and_does_not_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    called = {"run": False}

    def _fake_run(*args, **kwargs):
        called["run"] = True
        raise AssertionError("subprocess.run should not be called in dry-run")

    monkeypatch.setattr("pdf2md.backends.runner.subprocess.run", _fake_run)

    rc = run_configured_backends(
        input_pdf=pdf,
        config=config,
        repo_root=Path.cwd(),
        work_dir_override=tmp_path / ".tmp",
        dry_run=True,
    )
    assert rc == 0
    assert called["run"] is False

    run_dir = tmp_path / ".tmp" / derive_run_name(pdf, None)
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "raw" / "mineru" / "command.json").exists()
    assert (run_dir / "raw" / "mineru" / "status.json").exists()

    status = json.loads((run_dir / "raw" / "mineru" / "status.json").read_text(encoding="utf-8"))
    assert status["dry_run"] is True
    assert status["success"] is None


def test_missing_input_pdf_fails(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    with pytest.raises(ValueError):
        run_configured_backends(
            input_pdf=tmp_path / "missing.pdf",
            config=config,
            repo_root=Path.cwd(),
            work_dir_override=tmp_path / ".tmp",
            dry_run=True,
        )


def test_existing_run_dir_requires_force(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    run_dir = tmp_path / ".tmp" / "test"
    run_dir.mkdir(parents=True)

    with pytest.raises(ValueError):
        run_configured_backends(
            input_pdf=pdf,
            config=config,
            repo_root=Path.cwd(),
            work_dir_override=tmp_path / ".tmp",
            dry_run=True,
        )


def test_force_recreates_only_selected_run_dir(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    base = tmp_path / ".tmp"
    keep_dir = base / "keep"
    keep_dir.mkdir(parents=True)
    (keep_dir / "marker.txt").write_text("keep", encoding="utf-8")

    target = base / "test"
    target.mkdir(parents=True)
    (target / "old.txt").write_text("old", encoding="utf-8")

    rc = run_configured_backends(
        input_pdf=pdf,
        config=config,
        repo_root=Path.cwd(),
        work_dir_override=base,
        dry_run=True,
        force=True,
    )
    assert rc == 0
    assert (keep_dir / "marker.txt").exists()
    assert not (target / "old.txt").exists()
