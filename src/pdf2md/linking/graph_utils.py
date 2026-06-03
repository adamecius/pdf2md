"""networkx-backed traversal utilities for the document LinkedStructure.

The linker emits ``LinkedNode``/``LinkedRelation`` lists; this module turns
those into a :class:`networkx.MultiDiGraph` and exposes the traversal
primitives downstream consumers (RAG chunking, Docling export, visualisation)
would otherwise re-derive by hand.

A ``MultiDiGraph`` is used rather than a plain ``DiGraph`` because a single
ordered node pair can legitimately carry more than one relation (for example a
section both ``FOLLOWS`` and ``CONTAINS`` the next block). A simple graph would
silently collapse those into one edge, breaking the contract that the graph
has exactly one edge per ``LinkedStructure.relations`` entry.

The graph is a *derived view*. ``LinkedStructure`` still serialises as its
node/relation lists; :func:`linked_structure_to_graph` reconstructs the graph
on demand from any loaded structure.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import networkx as nx

from pdf2md.models.linked import LinkedRelationType, LinkedStructure

# ``LinkedStructure`` models use ``use_enum_values=True``, so ``relation_type``
# and ``status`` arrive as plain strings. ``_value`` normalises either form.
READING_ORDER_RELATION_TYPES: frozenset[str] = frozenset(
    {
        LinkedRelationType.FOLLOWS.value,
        LinkedRelationType.PAGE_NUMBER_SEQUENCE_NEXT.value,
    }
)
SECTION_CONTAINMENT_RELATION_TYPES: frozenset[str] = frozenset({LinkedRelationType.CONTAINS.value})


def _value(candidate: Any) -> Any:
    """Return the underlying value for an enum, or the value unchanged."""

    return candidate.value if isinstance(candidate, Enum) else candidate


def linked_structure_to_graph(linked: LinkedStructure) -> nx.MultiDiGraph:
    """Build a networkx graph view of a ``LinkedStructure``.

    Each ``LinkedNode`` becomes a graph node keyed by ``node.id`` with its
    structural attributes; each ``LinkedRelation`` becomes one directed edge
    carrying ``relation_type``, ``confidence``, and ``status``. The result has
    exactly ``len(linked.nodes)`` nodes and ``len(linked.relations)`` edges.

    Args:
        linked: The linked structure to project onto a graph.

    Returns:
        A :class:`networkx.MultiDiGraph` derived from the structure.
    """

    graph: nx.MultiDiGraph = nx.MultiDiGraph()
    for node in linked.nodes:
        graph.add_node(
            node.id,
            node_type=_value(node.node_type),
            text=node.text,
            page_no=node.page_no,
            order=node.order,
            confidence=node.confidence,
            status=_value(node.status),
        )
    for relation in linked.relations:
        graph.add_edge(
            relation.source_node_id,
            relation.target_node_id,
            relation_type=_value(relation.relation_type),
            confidence=relation.confidence,
            status=_value(relation.status),
        )
    return graph


def _reading_order_subgraph(graph: nx.MultiDiGraph | nx.DiGraph) -> nx.DiGraph:
    """Collapse reading-order/page-sequence edges into a simple DiGraph."""

    sub: nx.DiGraph = nx.DiGraph()
    for source, target, data in graph.edges(data=True):
        if data.get("relation_type") in READING_ORDER_RELATION_TYPES:
            sub.add_edge(source, target)
    return sub


def reading_order_sort(graph: nx.MultiDiGraph | nx.DiGraph) -> list[str]:
    """Topologically sort the reading-order / page-sequence subgraph.

    Considers only ``FOLLOWS`` and ``PAGE_NUMBER_SEQUENCE_NEXT`` edges.

    Args:
        graph: A LinkedStructure graph.

    Returns:
        Node ids in a valid reading order. Nodes not touched by any
        reading-order edge are omitted (they impose no ordering constraint).

    Raises:
        ValueError: If the reading-order subgraph contains a cycle.
    """

    sub = _reading_order_subgraph(graph)
    if not nx.is_directed_acyclic_graph(sub):
        raise ValueError("reading-order subgraph contains a cycle")
    return list(nx.topological_sort(sub))


def section_ancestors(graph: nx.MultiDiGraph | nx.DiGraph, node_id: str) -> list[str]:
    """Walk ``CONTAINS`` edges upward from ``node_id``.

    Args:
        graph: A LinkedStructure graph.
        node_id: The node whose ancestors are requested.

    Returns:
        Ancestor node ids ordered from the immediate parent to the root.
        Empty if the node has no containing parent (or is absent).
    """

    ancestors: list[str] = []
    current = node_id
    visited: set[str] = {node_id}
    if node_id not in graph:
        return ancestors
    while True:
        parents = [
            source
            for source, _target, data in graph.in_edges(current, data=True)
            if data.get("relation_type") in SECTION_CONTAINMENT_RELATION_TYPES
        ]
        next_parent = next((parent for parent in parents if parent not in visited), None)
        if next_parent is None:
            break
        ancestors.append(next_parent)
        visited.add(next_parent)
        current = next_parent
    return ancestors


def detect_cycles(graph: nx.MultiDiGraph | nx.DiGraph) -> list[list[str]]:
    """Return all simple directed cycles in the graph."""

    return [list(cycle) for cycle in nx.simple_cycles(graph)]


def orphan_nodes(graph: nx.MultiDiGraph | nx.DiGraph) -> list[str]:
    """Return node ids with no incident edges (total degree zero)."""

    return [node for node in graph.nodes if graph.degree(node) == 0]


__all__ = [
    "READING_ORDER_RELATION_TYPES",
    "SECTION_CONTAINMENT_RELATION_TYPES",
    "detect_cycles",
    "linked_structure_to_graph",
    "orphan_nodes",
    "reading_order_sort",
    "section_ancestors",
]
