from __future__ import annotations

import json

import pytest

from pdf2md.calibration.semantic_report import (
    apply_adjudications,
    render_json,
    resolution_matrix,
)


def _edge(marker_type: str, resolved: bool) -> dict:
    return {
        "source": f"marker:{marker_type}",
        "target": f"target:{marker_type}" if resolved else "_unresolved",
        "marker_type": marker_type,
        "label": marker_type,
        "resolved": resolved,
        "edge_kind": "cross_reference",
    }


def _graph() -> dict:
    edges = [
        _edge("figure", True),
        _edge("figure", True),
        _edge("figure", True),
        _edge("figure", False),
        _edge("equation", True),
        _edge("equation", True),
        _edge("equation", False),
        _edge("equation", False),
        _edge("equation", False),
        _edge("equation", False),
        {"source": "document", "target": "page:1", "edge_kind": "contains"},
    ]
    return {
        "document_id": "example01/regex+mineru",
        "edges": edges,
        "_calibration": {
            "example": "example01",
            "semantic_backend": "regex",
            "ocr_backend": "mineru",
            "graph_path": "webui/cross_ref/data/example01/regex__resolved_with__mineru.json",
        },
    }


def test_resolution_matrix_counts_per_type_and_ignores_non_cross_reference_edges() -> None:
    report = resolution_matrix([_graph()])

    combo = report.per_combo[0]
    assert combo.total == 10
    assert combo.resolved == 5
    assert combo.resolution_rate == pytest.approx(0.5)
    assert combo.per_type["figure"].total == 4
    assert combo.per_type["figure"].resolved == 3
    assert combo.per_type["figure"].resolution_rate == pytest.approx(0.75)
    assert combo.per_type["equation"].total == 6
    assert combo.per_type["equation"].resolved == 2
    assert report.cross_backend_matrix["figure"]["mineru"] == pytest.approx(0.75)
    assert report.cross_backend_matrix["equation"]["mineru"] == pytest.approx(2 / 6)


def test_apply_adjudications_corrects_noise_and_resolve_counts() -> None:
    report = resolution_matrix([_graph()])
    adjudications = {
        "document_id": "example01",
        "adjudications": [
            {"decision": "noise", "marker_type": "figure"},
            {"decision": "resolve", "marker_type": "equation"},
            {"decision": "rule_hint", "marker_type": "equation"},
        ],
    }

    corrected = apply_adjudications(report, adjudications)

    combo = corrected.per_combo[0]
    assert corrected.adjudication_count == 2
    assert combo.total == 9
    assert combo.resolved == 6
    assert combo.per_type["figure"].total == 3
    assert combo.per_type["figure"].resolved == 3
    assert combo.per_type["figure"].resolution_rate == pytest.approx(1.0)
    assert combo.per_type["equation"].total == 6
    assert combo.per_type["equation"].resolved == 3
    assert report.per_combo[0].total == 10


def test_render_json_is_deterministic() -> None:
    report = resolution_matrix([_graph()])

    first = render_json(report)
    second = render_json(report)

    assert first == second
    payload = json.loads(first)
    assert payload["schema_name"] == "pdf2md.semantic_calibration_report"
    assert payload["calibration_weights"] == payload["cross_backend_matrix"]
