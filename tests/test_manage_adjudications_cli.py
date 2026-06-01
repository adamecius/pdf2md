"""Tests for tools/manage_adjudications.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "tools" / "manage_adjudications.py"
FIXTURE = REPO_ROOT / "tests" / "data" / "semantic_fixtures" / "sample_adjudications.json"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _write_payload(tmp_path: Path, name: str, updates: dict | None = None) -> Path:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if updates:
        payload.update(updates)
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_validate_happy_path() -> None:
    result = _run(["validate", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "valid:" in result.stdout
    assert "adjudications=4" in result.stdout


def test_validate_missing_file_returns_2(tmp_path: Path) -> None:
    result = _run(["validate", str(tmp_path / "missing.json")])
    assert result.returncode == 2
    assert "file not found" in result.stderr


def test_merge_happy_path_latest_wins(tmp_path: Path) -> None:
    left = _write_payload(tmp_path, "left.json")
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["adjudications"] = [
        payload["adjudications"][0]
        | {
            "decision": "noise",
            "target_entity_id": None,
            "corrected_type": None,
            "rule_hint": None,
            "decided_at": "2026-05-31T02:00:00Z",
        }
    ]
    right = tmp_path / "right.json"
    right.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "merged.json"

    result = _run(["merge", str(out), str(left), str(right)])
    assert result.returncode == 0, result.stderr
    merged = json.loads(out.read_text(encoding="utf-8"))
    winner = next(item for item in merged["adjudications"] if item["marker_id"] == payload["adjudications"][0]["marker_id"])
    assert winner["decision"] == "noise"
    assert merged["metadata"]["import_history"][-1]["overwritten"] == 1


def test_merge_document_id_mismatch_returns_2(tmp_path: Path) -> None:
    left = _write_payload(tmp_path, "left.json")
    right = _write_payload(tmp_path, "right.json", {"document_id": "different"})
    result = _run(["merge", str(tmp_path / "out.json"), str(left), str(right)])
    assert result.returncode == 2
    assert "document_id mismatch" in result.stderr


def test_summary_happy_path() -> None:
    result = _run(["summary", str(FIXTURE)])
    assert result.returncode == 0, result.stderr
    assert "marker_id count: 4" in result.stdout
    assert "resolve: 1" in result.stdout
    assert "duplicate-marker_id warnings: none" in result.stdout


def test_summary_malformed_json_returns_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    result = _run(["summary", str(bad)])
    assert result.returncode == 2
    assert "malformed JSON" in result.stderr
