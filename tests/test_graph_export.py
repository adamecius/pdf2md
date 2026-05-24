"""Tests for the CrossReferenceGraph → D3 export (Plan 008_0)."""

from __future__ import annotations

from pdf2md.models import (
    CrossReferenceGraph,
    RefEdge,
    RefMarker,
    RefType,
    SemanticEntity,
)
from pdf2md.semantic.graph_export import (
    GRAPH_EXPORT_SCHEMA_VERSION,
    MARKER_SOURCE_NODE_TYPE,
    UNRESOLVED_NODE_ID,
    UNRESOLVED_NODE_TYPE,
    export_graph,
)


def _make_marker(
    text: str,
    marker_type: RefType,
    *,
    source_ref: str = "#/document",
    offset: tuple[int, int] = (0, 0),
    backend: str = "regex",
) -> RefMarker:
    return RefMarker(
        source_ref=source_ref,
        marker_text=text,
        marker_type=marker_type,
        char_offset=offset,
        confidence=1.0,
        backend=backend,
    )


def test_export_with_no_markers_or_edges_returns_empty_payload() -> None:
    graph = CrossReferenceGraph(doc_hash="sha256:empty")
    result = export_graph(graph)
    assert result.schema_version == GRAPH_EXPORT_SCHEMA_VERSION
    assert result.nodes == []
    assert result.edges == []
    assert result.metadata["total_markers"] == 0
    assert result.metadata["resolved_count"] == 0
    assert result.metadata["unresolved_count"] == 0


def test_export_synthesises_unresolved_edges_for_markerless_graph() -> None:
    """Markers without explicit edges still appear as nodes connected
    to the synthetic ``_unresolved`` sink (so the viewer has something
    to render against a Plan 006 marker-only graph)."""
    markers = [
        _make_marker("Figure 3", RefType.FIGURE, offset=(0, 8)),
        _make_marker("[15]", RefType.BIBLIOGRAPHY, offset=(20, 24)),
    ]
    graph = CrossReferenceGraph(doc_hash="sha256:m", markers=markers)
    result = export_graph(graph)
    # 2 marker nodes + the unresolved sink
    assert len(result.nodes) == 3
    types = {n["type"] for n in result.nodes}
    assert types == {RefType.FIGURE.value, RefType.BIBLIOGRAPHY.value, UNRESOLVED_NODE_TYPE}
    assert len(result.edges) == 2
    assert all(edge["target"] == UNRESOLVED_NODE_ID for edge in result.edges)
    assert all(edge["resolved"] is False for edge in result.edges)
    assert result.metadata["unresolved_count"] == 2


def test_export_resolved_edge_links_to_target_node() -> None:
    marker = _make_marker("Figure 3", RefType.FIGURE)
    edge = RefEdge(
        marker=marker,
        target_ref="#/pictures/3",
        resolved=True,
        resolution_method="exact",
    )
    graph = CrossReferenceGraph(
        doc_hash="sha256:r", markers=[marker], edges=[edge]
    )
    result = export_graph(graph)
    targets = {n["id"] for n in result.nodes if n["type"] == RefType.FIGURE.value}
    assert "#/pictures/3" in targets
    assert result.metadata["resolved_count"] == 1
    assert result.metadata["unresolved_count"] == 0
    assert result.edges[0]["target"] == "#/pictures/3"
    assert result.edges[0]["resolved"] is True


def test_export_includes_marker_extra_metadata_on_marker_nodes() -> None:
    marker = _make_marker(
        "Figure 3",
        RefType.FIGURE,
        source_ref="#/texts/42",
        offset=(10, 18),
        backend="regex",
    )
    graph = CrossReferenceGraph(doc_hash="sha256:m", markers=[marker])
    result = export_graph(graph)
    marker_nodes = [
        n for n in result.nodes if n["type"] == RefType.FIGURE.value and "marker:" in n["id"]
    ]
    assert len(marker_nodes) == 1
    n = marker_nodes[0]
    assert n["source_ref"] == "#/texts/42"
    assert n["char_offset"] == [10, 18]
    assert n["backend"] == "regex"


def test_export_with_extra_entities_includes_them_as_nodes() -> None:
    graph = CrossReferenceGraph(doc_hash="sha256:e")
    entity = SemanticEntity(
        item_ref="#/pictures/5",
        entity_type=RefType.FIGURE,
        label="Figure 5",
        confidence=1.0,
        backend="docling",
    )
    result = export_graph(graph, extra_entities=[entity])
    assert any(n["id"] == "#/pictures/5" for n in result.nodes)


def test_export_metadata_passes_through_backend_versions() -> None:
    graph = CrossReferenceGraph(
        doc_hash="sha256:bv",
        backend_versions={"regex": "0.1.0", "grobid": "0.2.1"},
    )
    result = export_graph(graph)
    assert result.metadata["backend_versions"] == {"regex": "0.1.0", "grobid": "0.2.1"}


def test_export_to_dict_has_expected_top_level_keys() -> None:
    graph = CrossReferenceGraph(doc_hash="sha256:tld")
    payload = export_graph(graph, document_id="d1").to_dict()
    assert set(payload.keys()) == {"schema_version", "document_id", "nodes", "edges", "metadata"}
    assert payload["document_id"] == "d1"


def test_export_unique_marker_nodes_for_repeated_text() -> None:
    """Two markers with the same text + source_ref but different offsets
    must yield two distinct nodes."""
    markers = [
        _make_marker("Figure 1", RefType.FIGURE, offset=(0, 8)),
        _make_marker("Figure 1", RefType.FIGURE, offset=(50, 58)),
    ]
    graph = CrossReferenceGraph(doc_hash="sha256:dup", markers=markers)
    result = export_graph(graph)
    figure_marker_nodes = [
        n for n in result.nodes if n.get("type") == RefType.FIGURE.value
    ]
    assert len(figure_marker_nodes) == 2
