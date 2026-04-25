"""Groundtruth contract checks for deterministic/visual fixture parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

GROUNDTRUTH_DIR = Path(__file__).resolve().parents[1] / "groundtruth" / "test"


def _md_stems() -> list[str]:
    return sorted(path.stem for path in GROUNDTRUTH_DIR.glob("*.md"))


def _derive_markdown_from_docir(payload: dict) -> str:
    blocks = sorted(payload["blocks"], key=lambda item: item.get("order", 0))
    markdown_parts = [block.get("markdown", "") for block in blocks if block.get("markdown")]
    return "\n\n".join(markdown_parts).strip() + "\n"


def test_groundtruth_pairing_contract_pending() -> None:
    """Report the pending contract: deterministic+visual PDFs plus JSON per markdown fixture."""

    missing: list[str] = []
    for stem in _md_stems():
        expected = [
            GROUNDTRUTH_DIR / f"{stem}_deterministic.pdf",
            GROUNDTRUTH_DIR / f"{stem}_visual.pdf",
            GROUNDTRUTH_DIR / f"{stem}.json",
        ]
        for candidate in expected:
            if not candidate.exists():
                missing.append(candidate.name)

    if missing:
        pytest.xfail(
            "Groundtruth deterministic/visual pairing not completed yet: "
            + ", ".join(sorted(missing))
        )

    assert not missing


def test_markdown_is_derived_from_proposed_docir_schema() -> None:
    """Validate proposed DocIR-like fixture and derive markdown from JSON, not the inverse."""

    md_path = GROUNDTRUTH_DIR / "test1.md"
    json_path = GROUNDTRUTH_DIR / "test1.json"

    payload = json.loads(json_path.read_text(encoding="utf-8"))

    required_top_level = {
        "schema_version",
        "document_id",
        "source",
        "metadata",
        "pages",
        "body",
        "furniture",
        "blocks",
        "groups",
        "relations",
        "media",
        "backend_runs",
        "created_at",
        "warnings",
    }
    assert required_top_level.issubset(payload.keys())
    assert payload["schema_version"] == "docir.v0-proposed"

    block = payload["blocks"][0]
    required_block_fields = {
        "block_id",
        "type",
        "role",
        "text",
        "markdown",
        "order",
        "page_refs",
        "provenance",
        "confidence",
        "normalised",
        "attributes",
        "include_in_rag",
        "include_in_benchmark",
    }
    assert required_block_fields.issubset(block.keys())

    provenance = block["provenance"]
    required_provenance_fields = {
        "backend",
        "backend_version",
        "strategy",
        "page_index",
        "extraction_time_ms",
        "confidence",
        "warnings",
    }
    assert required_provenance_fields.issubset(provenance.keys())

    derived_md = _derive_markdown_from_docir(payload)
    expected_md = md_path.read_text(encoding="utf-8")
    assert derived_md == expected_md
