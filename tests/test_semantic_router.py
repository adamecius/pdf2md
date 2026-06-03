"""Tests for the data-driven semantic backend router (Plan 006_1)."""

from __future__ import annotations

from pathlib import Path

from pdf2md.semantic.router import (
    MIN_WEIGHT,
    load_calibration_weights,
    weights_for_document_class,
)

FIXTURE = Path("tests/data/semantic_fixtures/calibration_weights_fixture.json")


def test_load_derives_book_weights_relative_to_best_backend():
    weights = load_calibration_weights(FIXTURE)
    book = weights["book"]
    # Rates: consensus 0.80 (best), grobid 0.40, vlm 0.60, regex 0.00.
    assert book["consensus"] == 1.0
    assert book["grobid"] == 0.5
    assert book["vlm"] == 0.75


def test_load_normalizes_vlm_backend_alias():
    book = load_calibration_weights(FIXTURE)["book"]
    assert "vlm" in book
    assert "vlm_v4" not in book


def test_no_backend_weight_is_zero_floor_applied():
    book = load_calibration_weights(FIXTURE)["book"]
    # paddleocr resolved 0/100 -> rate 0 -> floored, never excluded.
    assert book["paddleocr"] == MIN_WEIGHT
    assert all(weight > 0.0 for weight in book.values())


def test_article_and_document_classes_are_uniform():
    weights = load_calibration_weights(FIXTURE)
    assert weights["article"] == {}
    assert weights["document"] == {}


def test_weights_for_book_returns_derived_map():
    weights = weights_for_document_class("book", FIXTURE)
    assert weights["grobid"] == 0.5
    assert weights["consensus"] == 1.0


def test_weights_for_article_is_uniform():
    assert weights_for_document_class("article", FIXTURE) == {}


def test_weights_without_calibration_path_is_uniform():
    # No path supplied -> pre-006_1 behaviour (uniform weights).
    assert weights_for_document_class("book", None) == {}


def test_weights_for_none_class_is_uniform():
    assert weights_for_document_class(None, FIXTURE) == {}


def test_missing_baseline_file_degrades_to_uniform(tmp_path: Path):
    missing = tmp_path / "does_not_exist.json"
    assert load_calibration_weights(missing) == {"book": {}, "article": {}, "document": {}}
    assert weights_for_document_class("book", missing) == {}


def test_malformed_baseline_file_degrades_to_uniform(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    assert load_calibration_weights(bad)["book"] == {}
