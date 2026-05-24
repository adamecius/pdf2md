"""Tests for tools/run_semantic_benchmark.py (Plan 007_0)."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "tools" / "run_semantic_benchmark.py"
SAMPLE_GT_DIR = REPO_ROOT / "groundtruth" / "corpus" / "latex" / "linked_sections_figures"


def _have_latexml() -> bool:
    return shutil.which("latexml") is not None


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.skipif(not SAMPLE_GT_DIR.is_dir(), reason="missing sample corpus fixture")
@pytest.mark.skipif(not _have_latexml(), reason="latexml not on PATH")
def test_cli_runs_end_to_end_on_sample_corpus(tmp_path: Path) -> None:
    out_dir = tmp_path / "bench"
    result = _run(
        [
            "--gt-dir",
            str(SAMPLE_GT_DIR),
            "--backends",
            "regex",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert result.returncode == 0, result.stderr

    results_json = out_dir / "results.json"
    results_csv = out_dir / "results.csv"
    assert results_json.is_file()
    assert results_csv.is_file()

    payload = json.loads(results_json.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) >= 1

    with results_csv.open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) >= 1
    assert "document_id" in rows[0]
    assert rows[0]["backend"] == "regex"

    # GT artifacts are written per-document.
    doc_dirs = [p for p in out_dir.iterdir() if p.is_dir()]
    assert doc_dirs, "no per-document directories produced"
    gt_paths = [d / "gt_cross_references.json" for d in doc_dirs]
    assert any(p.is_file() for p in gt_paths)
    for gt_path in gt_paths:
        if not gt_path.is_file():
            continue
        gt_payload = json.loads(gt_path.read_text(encoding="utf-8"))
        assert "markers" in gt_payload
        assert "backend_versions" in gt_payload
        assert "ground_truth" in gt_payload["backend_versions"]


def test_cli_rejects_missing_gt_dir(tmp_path: Path) -> None:
    result = _run(
        [
            "--gt-dir",
            str(tmp_path / "nope"),
            "--backends",
            "regex",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    assert result.returncode == 2
    assert "--gt-dir not found" in result.stderr


def test_cli_rejects_unknown_backend(tmp_path: Path) -> None:
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    (gt_dir / "doc.tex").write_text(r"\documentclass{article}\begin{document}x\end{document}", encoding="utf-8")
    result = _run(
        [
            "--gt-dir",
            str(gt_dir),
            "--backends",
            "regex,unknown_backend",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    assert result.returncode == 2
    assert "unknown backend" in result.stderr


def test_cli_rejects_empty_corpus(tmp_path: Path) -> None:
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    result = _run(
        [
            "--gt-dir",
            str(gt_dir),
            "--backends",
            "regex",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    assert result.returncode == 2
    assert "no .tex files" in result.stderr


def test_cli_reports_env_not_ready_when_latexml_missing(tmp_path: Path) -> None:
    if not SAMPLE_GT_DIR.is_dir():
        pytest.skip("missing sample corpus fixture")
    out_dir = tmp_path / "out"
    # Run with an empty PATH so `latexml` is unreachable.
    env = {k: v for k, v in os.environ.items()}
    env["PATH"] = ""
    result = _run(
        [
            "--gt-dir",
            str(SAMPLE_GT_DIR),
            "--backends",
            "regex",
            "--out-dir",
            str(out_dir),
            "--latexml-bin",
            "latexml_not_here_xyz",
        ],
        env=env,
    )
    assert result.returncode == 3, result.stderr
    assert "env_not_ready" in result.stderr
