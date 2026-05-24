"""Tests for the CrossReferenceGraph pydantic schema (Plan 006_0)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pdf2md.models import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefEdge,
    RefMarker,
    RefType,
    SemanticEntity,
)


def _make_marker(**overrides) -> RefMarker:
    defaults = {
        "source_ref": "#/texts/0",
        "marker_text": "Figure 3",
        "marker_type": RefType.FIGURE,
        "char_offset": (0, 8),
        "confidence": 1.0,
        "backend": "regex",
    }
    defaults.update(overrides)
    return RefMarker(**defaults)


def test_schema_version_is_one_zero_zero() -> None:
    assert CROSS_REF_SCHEMA_VERSION == "1.0.0"


def test_ref_marker_round_trip() -> None:
    marker = _make_marker()
    payload = marker.model_dump_json()
    restored = RefMarker.model_validate_json(payload)
    assert restored.marker_text == "Figure 3"
    # ``use_enum_values=True`` means the deserialised value is a string.
    assert restored.marker_type == RefType.FIGURE.value


def test_ref_marker_rejects_negative_offset() -> None:
    with pytest.raises(ValidationError):
        _make_marker(char_offset=(-1, 5))


def test_ref_marker_rejects_inverted_offset() -> None:
    with pytest.raises(ValidationError):
        _make_marker(char_offset=(10, 5))


def test_ref_marker_rejects_confidence_outside_unit_interval() -> None:
    with pytest.raises(ValidationError):
        _make_marker(confidence=1.5)
    with pytest.raises(ValidationError):
        _make_marker(confidence=-0.1)


def test_ref_marker_rejects_empty_source_ref() -> None:
    with pytest.raises(ValidationError):
        _make_marker(source_ref="")


def test_ref_edge_resolved_requires_target() -> None:
    marker = _make_marker()
    with pytest.raises(ValidationError):
        RefEdge(
            marker=marker,
            target_ref=None,
            resolved=True,
            resolution_method="exact",
        )


def test_ref_edge_unresolved_requires_method_unresolved() -> None:
    marker = _make_marker()
    with pytest.raises(ValidationError):
        RefEdge(
            marker=marker,
            target_ref=None,
            resolved=False,
            resolution_method="exact",
        )


def test_ref_edge_rejects_unknown_resolution_method() -> None:
    marker = _make_marker()
    with pytest.raises(ValidationError):
        RefEdge(
            marker=marker,
            target_ref="#/pictures/0",
            resolved=True,
            resolution_method="hallucinated",
        )


def test_ref_edge_round_trip() -> None:
    marker = _make_marker()
    edge = RefEdge(
        marker=marker,
        target_ref="#/pictures/0",
        resolved=True,
        resolution_method="fuzzy",
    )
    restored = RefEdge.model_validate_json(edge.model_dump_json())
    assert restored.resolved is True
    assert restored.target_ref == "#/pictures/0"
    assert restored.resolution_method == "fuzzy"


def test_semantic_entity_accepts_no_label() -> None:
    entity = SemanticEntity(
        item_ref="#/texts/5",
        entity_type=RefType.THEOREM,
        label=None,
        confidence=0.9,
        backend="regex",
    )
    assert entity.label is None
    assert entity.entity_type == RefType.THEOREM.value


def test_cross_reference_graph_round_trip() -> None:
    marker = _make_marker()
    edge = RefEdge(
        marker=marker,
        target_ref="#/pictures/0",
        resolved=True,
        resolution_method="exact",
    )
    entity = SemanticEntity(
        item_ref="#/texts/5",
        entity_type=RefType.THEOREM,
        label="Theorem 3.2",
        confidence=0.9,
        backend="grobid",
    )
    graph = CrossReferenceGraph(
        doc_hash="sha256:abc",
        markers=[marker],
        edges=[edge],
        entities=[entity],
        backend_versions={"regex": "0.1.0", "grobid": "0.1.0"},
    )

    payload = json.loads(graph.model_dump_json())
    assert payload["schema_version"] == CROSS_REF_SCHEMA_VERSION
    assert payload["doc_hash"] == "sha256:abc"
    assert len(payload["markers"]) == 1
    assert len(payload["edges"]) == 1
    assert payload["entities"][0]["label"] == "Theorem 3.2"
    assert sorted(payload["backend_versions"]) == ["grobid", "regex"]

    restored = CrossReferenceGraph.model_validate_json(graph.model_dump_json())
    assert restored.markers[0].marker_text == "Figure 3"
    assert restored.edges[0].resolution_method == "exact"


def test_cross_reference_graph_rejects_empty_doc_hash() -> None:
    with pytest.raises(ValidationError):
        CrossReferenceGraph(doc_hash="")


def test_cross_reference_graph_defaults_are_empty_lists() -> None:
    graph = CrossReferenceGraph(doc_hash="sha256:zero")
    assert graph.markers == []
    assert graph.edges == []
    assert graph.entities == []
    assert graph.backend_versions == {}
