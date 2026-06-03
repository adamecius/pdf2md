"""Tests for the networkx-backed LinkedStructure graph utilities."""

import networkx as nx
import pytest

from pdf2md.linking.graph_utils import (
    detect_cycles,
    linked_structure_to_graph,
    orphan_nodes,
    reading_order_sort,
    section_ancestors,
)
from pdf2md.models.linked import LinkedRelationType

FOLLOWS = LinkedRelationType.FOLLOWS.value
PAGE_SEQ = LinkedRelationType.PAGE_NUMBER_SEQUENCE_NEXT.value
CONTAINS = LinkedRelationType.CONTAINS.value


def _sample_graph():
    """5 nodes: a page-sequence/reading-order chain plus a section tree.

    Reading order: n0 -> n1 -> n2 (page sequence then follows).
    Section tree:  root contains n0; n0 contains n1; n1 contains n2.
    """

    g = nx.MultiDiGraph()
    for node_id in ("root", "n0", "n1", "n2"):
        g.add_node(node_id)
    g.add_edge("n0", "n1", relation_type=PAGE_SEQ)
    g.add_edge("n1", "n2", relation_type=FOLLOWS)
    g.add_edge("root", "n0", relation_type=CONTAINS)
    g.add_edge("n0", "n1", relation_type=CONTAINS)
    g.add_edge("n1", "n2", relation_type=CONTAINS)
    return g


def test_reading_order_sort_returns_correct_order():
    g = _sample_graph()
    order = reading_order_sort(g)
    assert order.index("n0") < order.index("n1") < order.index("n2")


def test_reading_order_sort_ignores_non_reading_edges():
    g = nx.MultiDiGraph()
    g.add_edge("a", "b", relation_type=CONTAINS)
    # Only a CONTAINS edge -> no reading-order edges -> empty order.
    assert reading_order_sort(g) == []


def test_section_ancestors_returns_chain_to_root():
    g = _sample_graph()
    assert section_ancestors(g, "n2") == ["n1", "n0", "root"]


def test_section_ancestors_empty_for_root():
    g = _sample_graph()
    assert section_ancestors(g, "root") == []


def test_section_ancestors_missing_node_is_empty():
    g = _sample_graph()
    assert section_ancestors(g, "does-not-exist") == []


def test_detect_cycles_finds_injected_cycle():
    g = _sample_graph()
    g.add_edge("n2", "n0", relation_type=FOLLOWS)
    cycles = detect_cycles(g)
    assert any(set(cycle) == {"n0", "n1", "n2"} for cycle in cycles)


def test_detect_cycles_empty_for_acyclic_graph():
    assert detect_cycles(_sample_graph()) == []


def test_orphan_nodes_returns_isolated_node():
    g = _sample_graph()
    g.add_node("island")
    assert orphan_nodes(g) == ["island"]


def test_reading_order_sort_raises_on_cyclic_subgraph():
    g = nx.MultiDiGraph()
    g.add_edge("a", "b", relation_type=FOLLOWS)
    g.add_edge("b", "a", relation_type=FOLLOWS)
    with pytest.raises(ValueError):
        reading_order_sort(g)


class _Node:
    def __init__(self, nid):
        self.id = nid
        self.node_type = "paragraph"
        self.text = None
        self.page_no = 1
        self.order = 0
        self.confidence = 1.0
        self.status = "resolved"


class _Rel:
    def __init__(self, source, target):
        self.source_node_id = source
        self.target_node_id = target
        self.relation_type = FOLLOWS
        self.confidence = 0.9
        self.status = "resolved"


class _Struct:
    def __init__(self):
        self.nodes = [_Node("node:doc:0"), _Node("node:doc:1")]
        self.relations = [_Rel("node:doc:0", "node:doc:1")]


def test_linked_structure_to_graph_round_trips_counts():
    # Projection over a minimal duck-typed structure; real LinkedStructure
    # projection counts are covered in test_linked_structure_builder.
    projected = linked_structure_to_graph(_Struct())
    assert isinstance(projected, nx.MultiDiGraph)
    assert projected.number_of_nodes() == 2
    assert projected.number_of_edges() == 1
    assert projected.has_edge("node:doc:0", "node:doc:1")
