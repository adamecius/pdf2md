"""D3-compatible export for a :class:`CrossReferenceGraph`.

Converts the semantic-layer sidecar produced by the Plan 006 backends
into a node/edge JSON payload the Plan 008 static viewer can render.

The schema is intentionally narrow: each node carries an ``id``, a
``type`` (the originating ``RefType`` or one of the synthetic
``marker_source`` / ``unresolved`` types), and a display ``label``.
Each edge carries ``source``, ``target``, ``marker_type``, ``label``,
and ``resolved`` so the viewer can style unresolved edges differently
without reaching back into the original graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from pdf2md.models.cross_ref import (
    CrossReferenceGraph,
    RefEdge,
    RefMarker,
    SemanticEntity,
)


GRAPH_EXPORT_SCHEMA_VERSION = "1.0.0"
UNRESOLVED_NODE_ID = "_unresolved"
UNRESOLVED_NODE_TYPE = "unresolved"
MARKER_SOURCE_NODE_TYPE = "marker_source"


@dataclass(frozen=True)
class GraphExport:
    """A D3-ready payload for the cross-reference viewer.

    Attributes:
        schema_version: Schema version string.
        document_id: Caller-supplied identifier (or ``None`` if omitted).
        nodes: Ordered list of ``{id, type, label, ...}`` dictionaries.
        edges: Ordered list of ``{source, target, marker_type, label,
            resolved}`` dictionaries.
        metadata: Aggregate counts and the merged ``backend_versions``
            map from the source graph.
    """

    schema_version: str = GRAPH_EXPORT_SCHEMA_VERSION
    document_id: str | None = None
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable plain dict."""
        return {
            "schema_version": self.schema_version,
            "document_id": self.document_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "metadata": self.metadata,
        }


def _entity_label(entity: SemanticEntity) -> str:
    return entity.label or entity.item_ref


def _ensure_node(
    nodes: dict[str, dict[str, Any]],
    node_id: str,
    node_type: str,
    label: str,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    """Add a node if absent. If present, upgrade ``type`` only when the
    incoming type is more specific (i.e. the existing entry is a marker
    source placeholder)."""
    if node_id not in nodes:
        node: dict[str, Any] = {"id": node_id, "type": node_type, "label": label}
        if extra:
            node.update(extra)
        nodes[node_id] = node
        return
    existing = nodes[node_id]
    if existing.get("type") == MARKER_SOURCE_NODE_TYPE and node_type != MARKER_SOURCE_NODE_TYPE:
        existing["type"] = node_type
        existing["label"] = label
        if extra:
            existing.update(extra)


def _iter_entity_nodes(
    entities: Iterable[SemanticEntity],
) -> Iterable[tuple[str, str, str]]:
    for entity in entities:
        yield (
            entity.item_ref,
            str(entity.entity_type),
            _entity_label(entity),
        )


def _edge_label(edge: RefEdge) -> str:
    return edge.marker.marker_text


def _edge_target(edge: RefEdge) -> str:
    if edge.resolved and edge.target_ref:
        return edge.target_ref
    return UNRESOLVED_NODE_ID


def _marker_node_id(marker: RefMarker, index: int) -> str:
    """Stable id for a marker shown as its own node.

    Includes the index because two markers can legitimately share text
    (e.g. ``"Figure 1"`` appears twice in body text); using only the
    text + source_ref would collapse them into a single node.
    """
    return f"marker:{index}:{marker.source_ref}:{marker.marker_text}"


def export_graph(
    xref: CrossReferenceGraph,
    *,
    document_id: str | None = None,
    extra_entities: list[SemanticEntity] | None = None,
) -> GraphExport:
    """Convert a :class:`CrossReferenceGraph` into a :class:`GraphExport`.

    Args:
        xref: The semantic sidecar to render.
        document_id: Optional stable identifier for the viewer.
        extra_entities: Additional structural entities to expose as nodes
            (typically from a `LinkedStructure`). Deduplicated against
            ``xref.entities`` on ``item_ref``.

    Returns:
        A populated :class:`GraphExport`.

    Edge synthesis: when the source graph has markers but no edges (the
    default state of a CrossReferenceGraph produced by Plan 006's
    standalone backends), synthetic unresolved edges are emitted from
    each marker node to the ``_unresolved`` sink so the viewer has
    something to render. A marker that is also referenced by a
    :class:`RefEdge` in ``xref.edges`` skips its synthetic edge — the
    real edge wins.
    """
    nodes: dict[str, dict[str, Any]] = {}

    for triplet in _iter_entity_nodes(xref.entities):
        node_id, node_type, label = triplet
        _ensure_node(nodes, node_id, node_type, label)

    if extra_entities:
        for triplet in _iter_entity_nodes(extra_entities):
            node_id, node_type, label = triplet
            _ensure_node(nodes, node_id, node_type, label)

    marker_ids: dict[int, str] = {}
    for idx, marker in enumerate(xref.markers):
        node_id = _marker_node_id(marker, idx)
        marker_ids[idx] = node_id
        _ensure_node(
            nodes,
            node_id,
            str(marker.marker_type),
            marker.marker_text,
            extra={
                "source_ref": marker.source_ref,
                "char_offset": list(marker.char_offset),
                "backend": marker.backend,
            },
        )

    # Build a lookup from (source_ref, marker_text, char_offset) → marker index
    # so we can connect explicit edges back to their marker nodes.
    marker_lookup: dict[tuple[str, str, int, int], int] = {}
    for idx, marker in enumerate(xref.markers):
        key = (
            marker.source_ref,
            marker.marker_text,
            marker.char_offset[0],
            marker.char_offset[1],
        )
        marker_lookup[key] = idx

    resolved_count = 0
    unresolved_count = 0
    edges_out: list[dict[str, Any]] = []
    covered_marker_indices: set[int] = set()

    for edge in xref.edges:
        marker = edge.marker
        key = (
            marker.source_ref,
            marker.marker_text,
            marker.char_offset[0],
            marker.char_offset[1],
        )
        marker_idx = marker_lookup.get(key)
        if marker_idx is None:
            # The edge references a marker not present in xref.markers;
            # synthesise a marker node on the fly so the edge can still
            # render.
            marker_idx = len(xref.markers) + len(covered_marker_indices)
            synthetic_id = _marker_node_id(marker, marker_idx)
            marker_ids[marker_idx] = synthetic_id
            _ensure_node(
                nodes,
                synthetic_id,
                str(marker.marker_type),
                marker.marker_text,
                extra={
                    "source_ref": marker.source_ref,
                    "char_offset": list(marker.char_offset),
                    "backend": marker.backend,
                },
            )
        covered_marker_indices.add(marker_idx)

        if edge.resolved and edge.target_ref:
            _ensure_node(
                nodes,
                edge.target_ref,
                str(marker.marker_type),
                edge.target_ref,
            )
            resolved_count += 1
            target_id = edge.target_ref
        else:
            _ensure_node(
                nodes,
                UNRESOLVED_NODE_ID,
                UNRESOLVED_NODE_TYPE,
                "(unresolved)",
            )
            unresolved_count += 1
            target_id = UNRESOLVED_NODE_ID

        edges_out.append(
            {
                "source": marker_ids[marker_idx],
                "target": target_id,
                "marker_type": str(marker.marker_type),
                "label": _edge_label(edge),
                "resolved": bool(edge.resolved),
            }
        )

    # Synthesise unresolved edges for markers not covered by any RefEdge.
    if len(xref.markers) > len(covered_marker_indices):
        _ensure_node(
            nodes,
            UNRESOLVED_NODE_ID,
            UNRESOLVED_NODE_TYPE,
            "(unresolved)",
        )
        for idx, marker in enumerate(xref.markers):
            if idx in covered_marker_indices:
                continue
            edges_out.append(
                {
                    "source": marker_ids[idx],
                    "target": UNRESOLVED_NODE_ID,
                    "marker_type": str(marker.marker_type),
                    "label": marker.marker_text,
                    "resolved": False,
                }
            )
            unresolved_count += 1

    metadata: dict[str, Any] = {
        "doc_hash": xref.doc_hash,
        "total_markers": len(xref.markers),
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "backend_versions": dict(xref.backend_versions),
    }

    return GraphExport(
        schema_version=GRAPH_EXPORT_SCHEMA_VERSION,
        document_id=document_id,
        nodes=list(nodes.values()),
        edges=edges_out,
        metadata=metadata,
    )


__all__ = [
    "GRAPH_EXPORT_SCHEMA_VERSION",
    "MARKER_SOURCE_NODE_TYPE",
    "UNRESOLVED_NODE_ID",
    "UNRESOLVED_NODE_TYPE",
    "GraphExport",
    "export_graph",
]
