"""Tests for the semantic ensemble runner (Plan 006_0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf2md.models import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefMarker,
    RefType,
    SemanticEntity,
)
from pdf2md.semantic.base import SemanticBackend
from pdf2md.semantic.ensemble import merge_graphs, run_ensemble


class _FakeBackend(SemanticBackend):
    """In-test backend that returns a pre-built graph."""

    def __init__(
        self,
        name: str,
        version: str,
        graph: CrossReferenceGraph,
        available: bool = True,
    ) -> None:
        self._name = name
        self._version = version
        self._graph = graph
        self._available = available
        self.calls = 0

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return self._version

    def is_available(self) -> bool:
        return self._available

    def extract(self, pdf_path, text, output_dir) -> CrossReferenceGraph:
        self.calls += 1
        return self._graph


def _make_marker(
    backend: str,
    confidence: float,
    text: str = "Figure 3",
    offset: tuple[int, int] = (0, 8),
    marker_type: RefType = RefType.FIGURE,
) -> RefMarker:
    return RefMarker(
        source_ref="#/texts/0",
        marker_text=text,
        marker_type=marker_type,
        char_offset=offset,
        confidence=confidence,
        backend=backend,
    )


def _make_graph(markers, entities=None, versions=None, doc_hash="sha256:fake") -> CrossReferenceGraph:
    return CrossReferenceGraph(
        schema_version=CROSS_REF_SCHEMA_VERSION,
        doc_hash=doc_hash,
        markers=markers,
        edges=[],
        entities=entities or [],
        backend_versions=versions or {},
    )


def test_merge_graphs_dedups_markers_by_content_and_keeps_highest_confidence() -> None:
    low = _make_marker("a", 0.6)
    high = _make_marker("b", 0.95)
    graphs = [
        _make_graph([low], versions={"a": "1.0"}),
        _make_graph([high], versions={"b": "1.0"}),
    ]
    merged = merge_graphs(graphs, doc_hash="sha256:merge")

    assert len(merged.markers) == 1
    assert merged.markers[0].backend == "b"
    assert merged.markers[0].confidence == 0.95
    assert sorted(merged.backend_versions) == ["a", "b"]
    assert merged.doc_hash == "sha256:merge"


def test_merge_graphs_does_not_dedup_distinct_markers() -> None:
    m1 = _make_marker("a", 0.9, text="Figure 3", offset=(0, 8))
    m2 = _make_marker("a", 0.9, text="Figure 4", offset=(20, 28))
    merged = merge_graphs([_make_graph([m1, m2])], doc_hash="sha256:x")
    assert len(merged.markers) == 2


def test_merge_graphs_dedups_entities_by_item_ref_and_type() -> None:
    e1 = SemanticEntity(
        item_ref="#/texts/5",
        entity_type=RefType.THEOREM,
        label="Theorem 3.2",
        confidence=0.7,
        backend="a",
    )
    e2 = SemanticEntity(
        item_ref="#/texts/5",
        entity_type=RefType.THEOREM,
        label="Theorem 3.2",
        confidence=0.95,
        backend="b",
    )
    merged = merge_graphs(
        [_make_graph([], entities=[e1]), _make_graph([], entities=[e2])],
        doc_hash="sha256:x",
    )
    assert len(merged.entities) == 1
    assert merged.entities[0].confidence == 0.95
    assert merged.entities[0].backend == "b"


def test_merge_graphs_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        merge_graphs([], doc_hash="sha256:x")


def test_run_ensemble_skips_unavailable_backends(tmp_path: Path) -> None:
    available = _FakeBackend(
        "regex",
        "0.1.0",
        _make_graph([_make_marker("regex", 1.0)], versions={"regex": "0.1.0"}),
        available=True,
    )
    missing = _FakeBackend(
        "grobid",
        "0.1.0",
        _make_graph([_make_marker("grobid", 1.0)], versions={"grobid": "0.1.0"}),
        available=False,
    )
    result = run_ensemble(
        backends=[available, missing],
        pdf_path=None,
        text="See Figure 3.",
        output_dir=tmp_path,
    )
    assert available.calls == 1
    assert missing.calls == 0
    assert "regex" in result.backend_versions
    assert "grobid" not in result.backend_versions
    assert len(result.markers) == 1


def test_run_ensemble_returns_empty_when_no_backend_available(tmp_path: Path) -> None:
    missing = _FakeBackend(
        "regex",
        "0.1.0",
        _make_graph([_make_marker("regex", 1.0)]),
        available=False,
    )
    result = run_ensemble(
        backends=[missing],
        pdf_path=None,
        text=None,
        output_dir=tmp_path,
        doc_hash="sha256:custom",
    )
    assert result.markers == []
    assert result.backend_versions == {}
    assert result.doc_hash == "sha256:custom"


def test_run_ensemble_rejects_empty_backend_list(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_ensemble(backends=[], pdf_path=None, text=None, output_dir=tmp_path)
