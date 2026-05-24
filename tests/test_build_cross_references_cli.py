"""Tests for tools/build_cross_references.py (Plan 006_0 CLI)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "tools" / "build_cross_references.py"
SAMPLE_TEXT = REPO_ROOT / "tests" / "data" / "semantic_fixtures" / "sample_text.txt"


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_runs_regex_backend_end_to_end(tmp_path: Path) -> None:
    if not SAMPLE_TEXT.is_file():
        pytest.skip(f"missing fixture: {SAMPLE_TEXT}")
    out_dir = tmp_path / "regex_out"
    result = _run(
        [
            "--backend",
            "regex",
            "--text",
            str(SAMPLE_TEXT),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert result.returncode == 0, result.stderr
    out_file = out_dir / "cross_references.json"
    assert out_file.is_file()

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    assert len(payload["markers"]) >= 1
    assert "regex" in payload["backend_versions"]


def test_cli_rejects_grobid_without_pdf(tmp_path: Path) -> None:
    result = _run(["--backend", "grobid", "--out-dir", str(tmp_path)])
    assert result.returncode == 2
    assert "--pdf is required" in result.stderr


def test_cli_grobid_returns_env_not_ready_when_unavailable(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "stub.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 stub")
    result = _run(
        [
            "--backend",
            "grobid",
            "--pdf",
            str(fake_pdf),
            "--out-dir",
            str(tmp_path),
        ]
    )
    # If a real GROBID is running on this host, the test environment is
    # not "no GROBID" and we just check the contract: either exit 0
    # (GROBID worked) or exit 3 (env not ready). Exit 1/2 are real bugs.
    assert result.returncode in (0, 3), result.stderr
    if result.returncode == 3:
        assert "env_not_ready" in result.stderr


def test_cli_vlm_returns_env_not_ready_without_conda_env(tmp_path: Path) -> None:
    fake_image = tmp_path / "page.png"
    fake_image.write_bytes(b"\x89PNG\r\n\x1a\n stub")
    result = _run(
        [
            "--backend",
            "vlm",
            "--pdf",
            str(fake_image),
            "--out-dir",
            str(tmp_path),
        ]
    )
    # Same logic as the GROBID test: in this sandbox the env is absent,
    # but a future sandbox with the VLM env installed should also pass.
    assert result.returncode in (0, 3), result.stderr
    if result.returncode == 3:
        assert "env_not_ready" in result.stderr


def test_cli_regex_requires_text_or_txt_pdf(tmp_path: Path) -> None:
    result = _run(
        [
            "--backend",
            "regex",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert result.returncode == 2
    assert "regex backend requires" in result.stderr


def test_cli_rejects_missing_text_file(tmp_path: Path) -> None:
    result = _run(
        [
            "--backend",
            "regex",
            "--text",
            str(tmp_path / "nope.txt"),
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_cli_ensemble_runs_available_backends_only(tmp_path: Path) -> None:
    if not SAMPLE_TEXT.is_file():
        pytest.skip(f"missing fixture: {SAMPLE_TEXT}")
    out_dir = tmp_path / "ensemble_out"
    result = _run(
        [
            "--backend",
            "ensemble",
            "--text",
            str(SAMPLE_TEXT),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads((out_dir / "cross_references.json").read_text(encoding="utf-8"))
    # The regex backend is the only one guaranteed available in CI.
    assert "regex" in payload["backend_versions"]
    assert len(payload["markers"]) >= 1
