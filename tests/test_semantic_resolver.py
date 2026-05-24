"""Tests for the deterministic semantic resolver (Plan 006_0)."""

from __future__ import annotations

from pdf2md.models import RefMarker, RefType, SemanticEntity
from pdf2md.semantic.resolver import ResolverCandidate, resolve_markers


def _marker(text: str, marker_type: RefType, char_offset: tuple[int, int] = (0, 0)) -> RefMarker:
    return RefMarker(
        source_ref="#/texts/0",
        marker_text=text,
        marker_type=marker_type,
        char_offset=char_offset,
        confidence=1.0,
        backend="regex",
    )


def test_exact_figure_match_uses_exact_method() -> None:
    candidates = [
        ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3"),
        ResolverCandidate("#/pictures/2", RefType.FIGURE, "Figure 2"),
    ]
    edges = resolve_markers([_marker("Figure 3", RefType.FIGURE)], candidates)
    assert len(edges) == 1
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/pictures/3"
    assert edges[0].resolution_method == "exact"


def test_fuzzy_figure_match_normalises_prefix() -> None:
    candidates = [ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3")]
    edges = resolve_markers([_marker("Fig. 3", RefType.FIGURE)], candidates)
    assert edges[0].resolved is True
    assert edges[0].resolution_method == "fuzzy"
    assert edges[0].target_ref == "#/pictures/3"


def test_bibliography_match_by_number() -> None:
    candidates = [
        ResolverCandidate("#/refs/15", RefType.BIBLIOGRAPHY, "15"),
        ResolverCandidate("#/refs/12", RefType.BIBLIOGRAPHY, "12"),
    ]
    edges = resolve_markers([_marker("[15]", RefType.BIBLIOGRAPHY)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/refs/15"


def test_section_match_uses_fuzzy_path() -> None:
    candidates = [ResolverCandidate("#/sections/2.1", RefType.SECTION, "Section 2.1")]
    edges = resolve_markers([_marker("Sec. 2.1", RefType.SECTION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/sections/2.1"
    assert edges[0].resolution_method == "fuzzy"


def test_unresolved_marker_emits_unresolved_edge() -> None:
    candidates = [ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3")]
    edges = resolve_markers([_marker("Figure 99", RefType.FIGURE)], candidates)
    assert edges[0].resolved is False
    assert edges[0].target_ref is None
    assert edges[0].resolution_method == "unresolved"


def test_resolver_accepts_semantic_entity_candidates() -> None:
    entities = [
        SemanticEntity(
            item_ref="#/pictures/3",
            entity_type=RefType.FIGURE,
            label="Figure 3",
            confidence=1.0,
            backend="grobid",
        )
    ]
    edges = resolve_markers([_marker("Figure 3", RefType.FIGURE)], entities)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/pictures/3"
    assert edges[0].resolution_method == "exact"


def test_resolver_preserves_input_order() -> None:
    candidates = [
        ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3"),
        ResolverCandidate("#/refs/15", RefType.BIBLIOGRAPHY, "15"),
        ResolverCandidate("#/sections/2.1", RefType.SECTION, "Section 2.1"),
    ]
    markers = [
        _marker("Figure 3", RefType.FIGURE),
        _marker("[15]", RefType.BIBLIOGRAPHY),
        _marker("Section 2.1", RefType.SECTION),
        _marker("Figure 99", RefType.FIGURE),
    ]
    edges = resolve_markers(markers, candidates)
    assert [e.marker.marker_text for e in edges] == [
        "Figure 3",
        "[15]",
        "Section 2.1",
        "Figure 99",
    ]
    assert [e.resolved for e in edges] == [True, True, True, False]


def test_resolver_does_not_cross_entity_types() -> None:
    candidates = [ResolverCandidate("#/refs/3", RefType.BIBLIOGRAPHY, "3")]
    edges = resolve_markers([_marker("Figure 3", RefType.FIGURE)], candidates)
    assert edges[0].resolved is False
