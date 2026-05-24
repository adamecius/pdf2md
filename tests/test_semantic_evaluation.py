"""Tests for the semantic evaluation harness (Plan 007_0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf2md.models import CrossReferenceGraph
from pdf2md.semantic.evaluation import (
    SemanticEvalResult,
    evaluate_semantic,
    result_to_csv_row,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_TRUTH = REPO_ROOT / "tests" / "data" / "semantic_fixtures" / "eval_truth.json"
EVAL_EXTRACTED = REPO_ROOT / "tests" / "data" / "semantic_fixtures" / "eval_extracted.json"


@pytest.fixture(scope="module")
def truth_graph() -> CrossReferenceGraph:
    return CrossReferenceGraph.model_validate_json(
        EVAL_TRUTH.read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def extracted_graph() -> CrossReferenceGraph:
    return CrossReferenceGraph.model_validate_json(
        EVAL_EXTRACTED.read_text(encoding="utf-8")
    )


def test_evaluate_semantic_returns_result(
    extracted_graph: CrossReferenceGraph, truth_graph: CrossReferenceGraph
) -> None:
    result = evaluate_semantic(
        extracted=extracted_graph,
        ground_truth=truth_graph,
        document_id="fixture",
        backend="regex",
    )
    assert isinstance(result, SemanticEvalResult)
    assert result.document_id == "fixture"
    assert result.backend == "regex"


def test_marker_metrics_match_expected_fixture_values(
    extracted_graph: CrossReferenceGraph, truth_graph: CrossReferenceGraph
) -> None:
    # Fixture: truth has Figure 1, Figure 2, Section 2, [15] (4 markers).
    # Extracted has Figure 1, Figure 2, [15], Figure 99 (4 markers).
    # Matches: 3 (Figure 1, Figure 2, [15]). FP: 1 (Figure 99). FN: 1 (Section 2).
    result = evaluate_semantic(
        extracted=extracted_graph,
        ground_truth=truth_graph,
        document_id="fixture",
        backend="regex",
    )
    assert result.n_markers_extracted == 4
    assert result.n_markers_truth == 4
    assert result.n_markers_matched == 3
    assert result.marker_precision == pytest.approx(0.75)
    assert result.marker_recall == pytest.approx(0.75)
    assert result.marker_f1 == pytest.approx(0.75)


def test_marker_f1_by_type_breaks_down_correctly(
    extracted_graph: CrossReferenceGraph, truth_graph: CrossReferenceGraph
) -> None:
    result = evaluate_semantic(
        extracted=extracted_graph,
        ground_truth=truth_graph,
        document_id="fixture",
        backend="regex",
    )
    # Bibliography: 1 match / 1 ext / 1 truth → F1 = 1.0
    # Section: 0 match / 0 ext / 1 truth → F1 = 0.0
    # Figure: 2 match / 3 ext / 2 truth → P=2/3, R=2/2=1, F1=0.8
    assert result.marker_f1_by_type["bibliography"] == pytest.approx(1.0)
    assert result.marker_f1_by_type["section"] == pytest.approx(0.0)
    assert result.marker_f1_by_type["figure"] == pytest.approx(0.8)


def test_resolution_accuracy_counts_correct_targets(
    extracted_graph: CrossReferenceGraph, truth_graph: CrossReferenceGraph
) -> None:
    # Aligned markers (matched by content):
    #   Figure 1: extracted #fig:one == truth #fig:one → correct
    #   Figure 2: extracted #fig:wrong != truth #fig:two → incorrect
    #   [15]:    extracted #bib:fifteen == truth #bib:fifteen → correct
    # → 2 / 3 = 0.6666...
    result = evaluate_semantic(
        extracted=extracted_graph,
        ground_truth=truth_graph,
        document_id="fixture",
        backend="regex",
    )
    assert result.resolution_accuracy == pytest.approx(2 / 3)


def test_entity_metrics_match_fixture(
    extracted_graph: CrossReferenceGraph, truth_graph: CrossReferenceGraph
) -> None:
    # Both fixtures have exactly one entity, identical → P=R=F1=1
    result = evaluate_semantic(
        extracted=extracted_graph,
        ground_truth=truth_graph,
        document_id="fixture",
        backend="regex",
    )
    assert result.entity_precision == pytest.approx(1.0)
    assert result.entity_recall == pytest.approx(1.0)
    assert result.entity_f1 == pytest.approx(1.0)


def test_perfect_match_yields_unit_f1(truth_graph: CrossReferenceGraph) -> None:
    # Evaluating GT against itself should give P=R=F1=1.0 and
    # resolution_accuracy=1.0.
    result = evaluate_semantic(
        extracted=truth_graph,
        ground_truth=truth_graph,
        document_id="self",
        backend="ground_truth",
    )
    assert result.marker_precision == pytest.approx(1.0)
    assert result.marker_recall == pytest.approx(1.0)
    assert result.marker_f1 == pytest.approx(1.0)
    assert result.resolution_accuracy == pytest.approx(1.0)


def test_empty_extraction_yields_zero_recall(truth_graph: CrossReferenceGraph) -> None:
    empty = CrossReferenceGraph(doc_hash="sha256:empty")
    result = evaluate_semantic(
        extracted=empty,
        ground_truth=truth_graph,
        document_id="empty",
        backend="noop",
    )
    assert result.marker_precision == 0.0
    assert result.marker_recall == 0.0
    assert result.marker_f1 == 0.0
    assert result.n_markers_matched == 0


def test_result_to_csv_row_has_expected_columns(
    extracted_graph: CrossReferenceGraph, truth_graph: CrossReferenceGraph
) -> None:
    result = evaluate_semantic(
        extracted=extracted_graph,
        ground_truth=truth_graph,
        document_id="fixture",
        backend="regex",
    )
    row = result_to_csv_row(result)
    expected = {
        "document_id",
        "backend",
        "marker_precision",
        "marker_recall",
        "marker_f1",
        "resolution_accuracy",
        "entity_precision",
        "entity_recall",
        "entity_f1",
        "n_markers_extracted",
        "n_markers_truth",
        "n_markers_matched",
    }
    assert set(row.keys()) == expected
    assert row["document_id"] == "fixture"
    assert row["backend"] == "regex"
