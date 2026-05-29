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


# ---------------------------------------------------------------------------
# Schema 1.1 — hierarchy export (document → page → entity backbone).
# ---------------------------------------------------------------------------
from pdf2md.models.entities import (
    ConfidenceSource,
    EntityEvidence,
    EntityProposal,
    EntityProposalDocument,
    EntityType,
    EvidenceKind,
    entity_id,
)


def _ent(backend: str, doc: str, et: EntityType, idx: int, *, page_no: int):
    return EntityProposal(
        id=entity_id(backend, doc, et, idx),
        entity_type=et,
        subtype=None,
        canonical_text="",
        page_no=page_no,
        block_ids=[],
        confidence=0.5,
        confidence_source=ConfidenceSource.HEURISTIC,
        evidence=[EntityEvidence(
            kind=EvidenceKind.BLOCK_TEXT, page_no=page_no, source_block_id=None,
            raw_ref="r", text="", bbox=None, weight=1.0, reason="d", metadata={},
        )],
        calibration_key=f"{backend}:{et.value}:detector",
        metadata={"detector": "detector"},
    )


def _proposals(entities) -> EntityProposalDocument:
    return EntityProposalDocument(
        document_id="d", backend="mineru", backend_version=None,
        page_count=10, entities=entities, relations=[], warnings=[], metadata={},
    )


def test_hierarchy_omitted_when_proposals_missing() -> None:
    """Schema 1.0 backwards-compat: no document/page nodes, no edge_kind."""
    graph = CrossReferenceGraph(doc_hash="sha256:noh")
    export = export_graph(graph)
    types = {n["type"] for n in export.nodes}
    assert "document" not in types
    assert "page" not in types
    assert export.metadata["has_hierarchy"] is False


def test_hierarchy_emits_document_and_page_nodes() -> None:
    entities = [
        _ent("mineru", "d", EntityType.FIGURE, 1, page_no=2),
        _ent("mineru", "d", EntityType.FIGURE, 2, page_no=5),
    ]
    proposals = _proposals(entities)
    sem_entities = [
        SemanticEntity(item_ref=entities[0].id, entity_type=RefType.FIGURE,
                       label="Figure 1", confidence=1.0, backend="grobid"),
        SemanticEntity(item_ref=entities[1].id, entity_type=RefType.FIGURE,
                       label="Figure 2", confidence=1.0, backend="grobid"),
    ]
    graph = CrossReferenceGraph(doc_hash="sha256:h", entities=sem_entities)
    export = export_graph(graph, document_id="d", proposals=proposals)

    types = {n["type"] for n in export.nodes}
    assert "document" in types
    assert "page" in types
    pages = sorted(int(n["page_no"]) for n in export.nodes if n["type"] == "page")
    assert pages == [2, 5]
    assert export.metadata["has_hierarchy"] is True


def test_hierarchy_emits_containment_edges_document_page_entity() -> None:
    entities = [_ent("mineru", "d", EntityType.FIGURE, 1, page_no=3)]
    graph = CrossReferenceGraph(
        doc_hash="sha256:c",
        entities=[SemanticEntity(
            item_ref=entities[0].id, entity_type=RefType.FIGURE,
            label="Figure 1", confidence=1.0, backend="grobid",
        )],
    )
    export = export_graph(graph, document_id="d", proposals=_proposals(entities))
    contains = [e for e in export.edges if e.get("edge_kind") == "contains"]
    sources = {e["source"] for e in contains}
    targets = {e["target"] for e in contains}
    assert "document:d" in sources
    # The figure entity's containment edge should target the entity id.
    assert entities[0].id in targets


def test_reference_items_attach_to_bibliography_section_not_page() -> None:
    """The user-visible 'bibliography looks orphan' fix — REFERENCE_ITEM
    entities cluster under a bibliography section, not their physical
    page."""
    ref1 = _ent("mineru", "d", EntityType.REFERENCE_ITEM, 1, page_no=8)
    ref2 = _ent("mineru", "d", EntityType.REFERENCE_ITEM, 2, page_no=8)
    proposals = _proposals([ref1, ref2])
    graph = CrossReferenceGraph(
        doc_hash="sha256:bib",
        entities=[
            SemanticEntity(item_ref=ref1.id, entity_type=RefType.BIBLIOGRAPHY,
                           label="[1]", confidence=1.0, backend="grobid"),
            SemanticEntity(item_ref=ref2.id, entity_type=RefType.BIBLIOGRAPHY,
                           label="[2]", confidence=1.0, backend="grobid"),
        ],
    )
    export = export_graph(graph, document_id="d", proposals=proposals)
    section_nodes = [n for n in export.nodes if n["type"] == "bibliography_section"]
    assert len(section_nodes) == 1
    section_id = section_nodes[0]["id"]
    # The contains edges from the section node should reach both refs.
    contains = [e for e in export.edges if e.get("edge_kind") == "contains" and e["source"] == section_id]
    assert {e["target"] for e in contains} == {ref1.id, ref2.id}


def test_cross_reference_edges_get_edge_kind_field() -> None:
    marker = _make_marker("Figure 1", RefType.FIGURE)
    graph = CrossReferenceGraph(
        doc_hash="sha256:e", markers=[marker],
        edges=[RefEdge(marker=marker, target_ref="ent:mineru:d:figure:1",
                       resolved=True, resolution_method="exact")],
    )
    export = export_graph(graph, document_id="d")
    xref_edges = [e for e in export.edges if e.get("edge_kind") == "cross_reference"]
    assert len(xref_edges) >= 1


# ---------------------------------------------------------------------------
# Schema 1.1 — page-sequence edges + marker attribution.
# ---------------------------------------------------------------------------
def test_page_sequence_edges_chain_adjacent_pages() -> None:
    """Pages 1, 2, 3 should produce 2 page_sequence edges
    (1 → 2, 2 → 3) in addition to the contains edges."""
    entities = [
        _ent("mineru", "d", EntityType.FIGURE, 1, page_no=1),
        _ent("mineru", "d", EntityType.FIGURE, 2, page_no=2),
        _ent("mineru", "d", EntityType.FIGURE, 3, page_no=3),
    ]
    graph = CrossReferenceGraph(
        doc_hash="sha256:seq",
        entities=[
            SemanticEntity(item_ref=e.id, entity_type=RefType.FIGURE,
                           label=f"Figure {i+1}", confidence=1.0, backend="grobid")
            for i, e in enumerate(entities)
        ],
    )
    export = export_graph(graph, document_id="d", proposals=_proposals(entities))
    seq_edges = [e for e in export.edges if e.get("edge_kind") == "page_sequence"]
    assert len(seq_edges) == 2
    # Chain runs in ascending page order.
    sources = [e["source"] for e in seq_edges]
    targets = [e["target"] for e in seq_edges]
    assert sources[0].endswith(":1") and targets[0].endswith(":2")
    assert sources[1].endswith(":2") and targets[1].endswith(":3")


def test_page_sequence_skips_missing_pages_cleanly() -> None:
    """Pages 1, 3 (no page 2) still get a single edge 1 → 3 — the
    spine stays a single chain even with gaps in OCR page coverage."""
    entities = [
        _ent("mineru", "d", EntityType.FIGURE, 1, page_no=1),
        _ent("mineru", "d", EntityType.FIGURE, 2, page_no=3),
    ]
    graph = CrossReferenceGraph(
        doc_hash="sha256:skip",
        entities=[
            SemanticEntity(item_ref=e.id, entity_type=RefType.FIGURE,
                           label=f"Figure {i+1}", confidence=1.0, backend="grobid")
            for i, e in enumerate(entities)
        ],
    )
    export = export_graph(graph, document_id="d", proposals=_proposals(entities))
    seq_edges = [e for e in export.edges if e.get("edge_kind") == "page_sequence"]
    assert len(seq_edges) == 1


def test_vlm_marker_attached_to_source_page() -> None:
    """A marker with source_ref ``#/document/pages/N`` clusters
    under the matching page node, not under the markers section."""
    entities = [_ent("mineru", "d", EntityType.FIGURE, 1, page_no=7)]
    marker = _make_marker(
        "Figure 1", RefType.FIGURE,
        source_ref="#/document/pages/7", offset=(0, 8), backend="vlm",
    )
    graph = CrossReferenceGraph(
        doc_hash="sha256:vlm", markers=[marker],
        entities=[SemanticEntity(item_ref=entities[0].id, entity_type=RefType.FIGURE,
                                 label="Figure 1", confidence=1.0, backend="vlm")],
    )
    export = export_graph(graph, document_id="d", proposals=_proposals(entities))
    marker_nodes = [n for n in export.nodes if n.get("source_ref") == "#/document/pages/7"]
    assert len(marker_nodes) == 1
    assert marker_nodes[0]["page_no"] == 7
    assert "page:d:7" in marker_nodes[0]["parent_id"]


def test_regex_marker_falls_back_to_markers_section() -> None:
    """A marker with source_ref ``#/document`` (no page) clusters
    under the synthetic ``markers_section`` instead of floating
    unattached."""
    entities = [_ent("mineru", "d", EntityType.FIGURE, 1, page_no=1)]
    marker = _make_marker(
        "Figure 1", RefType.FIGURE,
        source_ref="#/document", offset=(0, 8), backend="regex",
    )
    graph = CrossReferenceGraph(
        doc_hash="sha256:reg", markers=[marker],
        entities=[SemanticEntity(item_ref=entities[0].id, entity_type=RefType.FIGURE,
                                 label="Figure 1", confidence=1.0, backend="regex")],
    )
    export = export_graph(graph, document_id="d", proposals=_proposals(entities))
    marker_node = next(n for n in export.nodes if n.get("source_ref") == "#/document")
    assert marker_node.get("page_no") is None
    section_node = next(n for n in export.nodes if n["type"] == "markers_section")
    assert marker_node["parent_id"] == section_node["id"]


def test_markers_section_not_minted_when_all_markers_have_pages() -> None:
    """All-VLM input → every marker attaches to a real page → the
    markers section is NOT emitted (avoid clutter on clean inputs)."""
    entities = [_ent("mineru", "d", EntityType.FIGURE, 1, page_no=5)]
    marker = _make_marker(
        "Figure 1", RefType.FIGURE,
        source_ref="#/document/pages/5", offset=(0, 8), backend="vlm",
    )
    graph = CrossReferenceGraph(
        doc_hash="sha256:nomks", markers=[marker],
        entities=[SemanticEntity(item_ref=entities[0].id, entity_type=RefType.FIGURE,
                                 label="Figure 1", confidence=1.0, backend="vlm")],
    )
    export = export_graph(graph, document_id="d", proposals=_proposals(entities))
    assert not any(n["type"] == "markers_section" for n in export.nodes)
