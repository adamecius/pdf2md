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
    # The CLI contract here is "no exit-2 bad-args case". Depending on
    # the host:
    #   exit 0 — GROBID env absent OR present but accepted the stub
    #            (rare; the stub is a 13-byte file, GROBID may bail
    #            out with HTTP 500),
    #   exit 1 — GROBID env present + GROBID rejected the stub
    #            (BAD_INPUT_DATA from the upstream service — realistic
    #            outcome on a host with the daemon running),
    #   exit 3 — GROBID env absent + the gating path caught it
    #            (realistic outcome on a clean CI host).
    # 2 from argparse would be a CLI regression.
    assert result.returncode in (0, 1, 3), result.stderr
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
    # The contract here is "no exit-2 bad-args case" — the args parse
    # cleanly, the backend dispatches, and we either:
    #   exit 0 — VLM env present + image was somehow valid (unlikely with the
    #            corrupt 16-byte stub PNG above, but harmless if it happens),
    #   exit 1 — VLM env present + the model load + inference crashes on the
    #            stub PNG (the realistic outcome on a host where the user
    #            has installed pdf2md-deepseek-vl2),
    #   exit 3 — VLM env absent + the gating path catches it (the realistic
    #            outcome on a clean host).
    # Anything other than 0/1/3 (in particular: 2 from argparse) would be a
    # CLI contract regression.
    assert result.returncode in (0, 1, 3), result.stderr
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


def test_cli_ocr_entities_flag_attaches_resolved_edges(tmp_path: Path) -> None:
    """End-to-end: regex backend produces markers, --ocr-entities feeds
    a hand-crafted EntityProposalDocument as the candidate pool, and the
    CLI writes a graph with resolved RefEdges attached."""
    if not SAMPLE_TEXT.is_file():
        pytest.skip(f"missing fixture: {SAMPLE_TEXT}")

    # Build a minimal EntityProposalDocument with a Figure 3 candidate
    # via the public Python API and serialise it next to the CLI input.
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT / "src"))
    from pdf2md.models.entities import (
        EntityProposalDocument,
        EntityProposal,
        EntityType,
        ConfidenceSource,
        EntityEvidence,
        EvidenceKind,
        entity_id,
    )
    from pdf2md.models.ir import extraction_id

    block_id = extraction_id("mineru", "doc", 1, 1)
    proposal = EntityProposal(
        id=entity_id("mineru", "doc", EntityType.CAPTION, 1),
        entity_type=EntityType.CAPTION,
        subtype=None,
        canonical_text="Figure 3. The bands.",
        page_no=1,
        block_ids=[block_id],
        confidence=0.8,
        confidence_source=ConfidenceSource.HEURISTIC,
        evidence=[
            EntityEvidence(
                kind=EvidenceKind.BLOCK_TEXT,
                page_no=1,
                source_block_id=block_id,
                raw_ref=None,
                text="Figure 3. The bands.",
                weight=1.0,
                reason="caption_detector",
                metadata={},
            )
        ],
        calibration_key="k",
        metadata={"caption_kind": "figure", "caption_number": "3"},
    )
    doc = EntityProposalDocument(
        document_id="doc",
        backend="mineru",
        backend_version=None,
        page_count=1,
        entities=[proposal],
        relations=[],
        warnings=[],
    )
    entities_path = tmp_path / "entities.json"
    entities_path.write_text(doc.model_dump_json(), encoding="utf-8")

    out_dir = tmp_path / "out"
    result = _run(
        [
            "--backend",
            "regex",
            "--text",
            str(SAMPLE_TEXT),
            "--out-dir",
            str(out_dir),
            "--ocr-entities",
            str(entities_path),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert "resolver:" in result.stderr  # the resolution-summary log line
    payload = json.loads((out_dir / "cross_references.json").read_text(encoding="utf-8"))
    # Regex detects "Figure 3" in the sample text; the OCR candidate
    # for "Figure 3" should produce at least one resolved edge with
    # target_ref pointing at the proposal's id.
    edges = payload["edges"]
    assert any(
        e["resolved"] and e["target_ref"] == proposal.id for e in edges
    ), f"expected a resolved edge to {proposal.id}, got: {edges}"


def test_cli_ocr_entities_missing_file_returns_exit_2(tmp_path: Path) -> None:
    if not SAMPLE_TEXT.is_file():
        pytest.skip(f"missing fixture: {SAMPLE_TEXT}")
    result = _run(
        [
            "--backend",
            "regex",
            "--text",
            str(SAMPLE_TEXT),
            "--out-dir",
            str(tmp_path / "out"),
            "--ocr-entities",
            str(tmp_path / "does_not_exist.json"),
        ]
    )
    assert result.returncode == 2
    assert "--ocr-entities not found" in result.stderr
