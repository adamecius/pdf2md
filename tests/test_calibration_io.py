"""Plan 12 calibration I/O tests.

Covers the Docling-to-BlockKind mapping in the truth loading path, fixture
discovery, and the new ``load_calibration_truth_document`` helper.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.calibration.io import (
    discover_calibration_inputs,
    load_calibration_document,
    load_calibration_truth_document,
)
from pdf2md.models.priors import CalibrationTruthDocument

ROOT = Path(__file__).resolve().parents[1]
DOCLING_ROOT = ROOT / "tests" / "data" / "calibration_vocabulary_fixtures" / "docling_truth_root"
MISSING_MANDATORY_ROOT = (
    ROOT / "tests" / "data" / "calibration_vocabulary_fixtures" / "missing_mandatory_root"
)
PRIOR_ROOT = ROOT / "tests" / "data" / "calibration_prior_fixtures" / "canonical_truth"


def test_load_truth_normalises_text_to_paragraph(tmp_path: Path) -> None:
    truth = load_calibration_truth_document(DOCLING_ROOT / "docA" / "truth.json")
    assert truth is not None
    kinds = [b.block_kind for b in truth.blocks]
    # First block was "text" in the fixture; must surface as "paragraph"
    assert "paragraph" in kinds


def test_load_truth_normalises_section_header_and_title_to_heading() -> None:
    truth = load_calibration_truth_document(DOCLING_ROOT / "docA" / "truth.json")
    assert truth is not None
    kinds = [b.block_kind for b in truth.blocks]
    assert kinds.count("heading") == 2  # section_header + title


def test_load_truth_normalises_picture_to_figure() -> None:
    truth = load_calibration_truth_document(DOCLING_ROOT / "docA" / "truth.json")
    assert truth is not None
    kinds = [b.block_kind for b in truth.blocks]
    assert "figure" in kinds


def test_load_truth_preserves_already_canonical_labels() -> None:
    truth = load_calibration_truth_document(PRIOR_ROOT / "truth.json")
    assert truth is not None
    kinds = [b.block_kind for b in truth.blocks]
    assert set(kinds) <= {"paragraph", "heading", "figure"}


def test_load_truth_fails_when_unmapped_mandatory_label_present() -> None:
    """An unmapped label propagates to Pydantic validation which then rejects it."""

    warnings: list[str] = []
    truth = load_calibration_truth_document(
        MISSING_MANDATORY_ROOT / "truth.json",
        warnings=warnings,
    )
    assert truth is None
    assert any("invalid_truth" in w for w in warnings)


def test_load_truth_validates_against_calibration_truth_document_schema() -> None:
    truth = load_calibration_truth_document(DOCLING_ROOT / "docA" / "truth.json")
    assert isinstance(truth, CalibrationTruthDocument)


# ---------------------------------------------------------------------------
# discover_calibration_inputs + load_calibration_document
# ---------------------------------------------------------------------------


def test_discover_calibration_inputs_recognises_canonical_truth_layout() -> None:
    inputs = discover_calibration_inputs(root=PRIOR_ROOT)
    assert len(inputs) == 1
    item = inputs[0]
    assert item.document_id == "canonical_truth"
    assert set(item.prediction_roots.keys()) == {"mineru", "glm"}


def test_load_calibration_document_yields_canonical_truth_blocks() -> None:
    inputs = discover_calibration_inputs(root=PRIOR_ROOT)
    assert inputs, "expected one calibration input"
    result = load_calibration_document(item=inputs[0])
    assert result.truth is not None
    kinds = {b.block_kind for b in result.truth.blocks}
    assert kinds <= {"paragraph", "heading", "figure"}
    assert "mineru" in result.pages_by_backend
    assert "glm" in result.pages_by_backend


def test_load_calibration_document_loads_pages_for_each_backend() -> None:
    inputs = discover_calibration_inputs(root=PRIOR_ROOT)
    result = load_calibration_document(item=inputs[0])
    mineru_pages = result.pages_by_backend.get("mineru", [])
    glm_pages = result.pages_by_backend.get("glm", [])
    assert len(mineru_pages) == 2
    assert len(glm_pages) == 2


def test_load_calibration_document_strict_mode_raises_on_bad_truth(tmp_path: Path) -> None:
    # Construct a one-file truth with an invalid label that will not validate even after mapping.
    bad_truth = tmp_path / "doc" / "truth.json"
    bad_truth.parent.mkdir(parents=True)
    bad_truth.write_text(
        json.dumps(
            {
                "document_id": "doc",
                "blocks": [
                    {
                        "id": "tb1",
                        "block_kind": "weird_label",
                        "page_no": 1,
                        "metadata": {},
                    }
                ],
                "entities": [],
                "relations": [],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    inputs = discover_calibration_inputs(root=tmp_path)
    assert inputs
    with pytest.raises(Exception):
        load_calibration_document(item=inputs[0], strict=True)


def test_load_calibration_document_nonstrict_records_warning_on_bad_truth(tmp_path: Path) -> None:
    bad_truth = tmp_path / "doc" / "truth.json"
    bad_truth.parent.mkdir(parents=True)
    bad_truth.write_text(
        json.dumps(
            {
                "document_id": "doc",
                "blocks": [
                    {
                        "id": "tb1",
                        "block_kind": "weird_label",
                        "page_no": 1,
                        "metadata": {},
                    }
                ],
                "entities": [],
                "relations": [],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    inputs = discover_calibration_inputs(root=tmp_path)
    result = load_calibration_document(item=inputs[0], strict=False)
    assert result.truth is None
    assert any("invalid_truth" in w for w in result.warnings)
