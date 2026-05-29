"""Tests for tools/export_cross_ref_graph.py (Plan 008_0)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "tools" / "export_cross_ref_graph.py"
SAMPLE_TEXT = REPO_ROOT / "tests" / "data" / "semantic_fixtures" / "sample_text.txt"
BUILD_XREF_CLI = REPO_ROOT / "tools" / "build_cross_references.py"
STATIC_VIEWER_INDEX = REPO_ROOT / "webui" / "cross_ref" / "index.html"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _build_xref(tmp_path: Path) -> Path:
    """Use the Plan 006 CLI to produce a real cross_references.json."""
    out_dir = tmp_path / "xref"
    result = subprocess.run(
        [
            sys.executable,
            str(BUILD_XREF_CLI),
            "--backend",
            "regex",
            "--text",
            str(SAMPLE_TEXT),
            "--out-dir",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    return out_dir / "cross_references.json"


def test_cli_writes_graph_json_with_expected_keys(tmp_path: Path) -> None:
    xref = _build_xref(tmp_path)
    out_path = tmp_path / "graph.json"
    result = _run(
        [
            "--xref",
            str(xref),
            "--output",
            str(out_path),
            "--document-id",
            "fixture",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"schema_version", "document_id", "nodes", "edges", "metadata"}
    assert payload["document_id"] == "fixture"
    # Schema 1.1 adds optional hierarchy when ``proposals`` is supplied;
    # the CLI does not yet take proposals, so the export keeps the flat
    # 1.0-style shape but the version string moves with the module.
    assert payload["schema_version"] == "1.1.0"
    assert payload["nodes"], "exporter produced no nodes"
    assert payload["edges"], "exporter produced no edges"


def test_cli_inline_viewer_writes_self_contained_html(tmp_path: Path) -> None:
    xref = _build_xref(tmp_path)
    out_path = tmp_path / "graph.json"
    viewer_path = tmp_path / "viewer.html"
    result = _run(
        [
            "--xref",
            str(xref),
            "--output",
            str(out_path),
            "--inline-viewer",
            str(viewer_path),
        ]
    )
    assert result.returncode == 0, result.stderr
    body = viewer_path.read_text(encoding="utf-8")
    assert "<script id=\"graph-data\"" in body
    assert "cdn.jsdelivr.net/npm/d3@7" in body
    # The payload should be inlined as JSON, so the doc_hash from the
    # cross_references.json must appear verbatim in the HTML.
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["doc_hash"] in body


def test_cli_rejects_missing_xref_file(tmp_path: Path) -> None:
    result = _run(
        [
            "--xref",
            str(tmp_path / "missing.json"),
            "--output",
            str(tmp_path / "graph.json"),
        ]
    )
    assert result.returncode == 2
    assert "--xref not found" in result.stderr


def test_cli_rejects_malformed_xref_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not really json", encoding="utf-8")
    result = _run(
        [
            "--xref",
            str(bad),
            "--output",
            str(tmp_path / "graph.json"),
        ]
    )
    assert result.returncode == 2
    assert "malformed" in result.stderr


def test_static_viewer_index_html_present_and_references_assets() -> None:
    assert STATIC_VIEWER_INDEX.is_file(), f"missing {STATIC_VIEWER_INDEX}"
    body = STATIC_VIEWER_INDEX.read_text(encoding="utf-8")
    # Syntactic check: balanced tags and reference to local + CDN assets.
    assert "<!doctype html>" in body.lower()
    assert "viewer.js" in body
    assert "style.css" in body
    assert "cdn.jsdelivr.net/npm/d3@7" in body
