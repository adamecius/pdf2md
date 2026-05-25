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

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from pdf2md.models.cross_ref import (
    CrossReferenceGraph,
    RefEdge,
    RefMarker,
    SemanticEntity,
)
from pdf2md.models.entities import EntityProposalDocument, EntityType

GRAPH_EXPORT_SCHEMA_VERSION = "1.1.0"
UNRESOLVED_NODE_ID = "_unresolved"
UNRESOLVED_NODE_TYPE = "unresolved"
MARKER_SOURCE_NODE_TYPE = "marker_source"

# Schema 1.1 hierarchy node types (semantic backbone — Document → Page →
# Entity). These nodes are added when ``export_graph`` is called with a
# ``proposals=…`` argument; the older flat-graph shape (no document /
# page nodes, schema 1.0.0 semantics) is preserved when ``proposals``
# is omitted so callers that don't have an EntityProposalDocument keep
# working.
DOCUMENT_NODE_TYPE = "document"
PAGE_NODE_TYPE = "page"
SECTION_NODE_ID_PREFIX = "section:"


def _section_node_id(kind: str, document_id: str) -> str:
    """Stable id for a synthetic section grouping node.

    ``kind`` ∈ {``bibliography``, ``index``, ``glossary``, ``markers``}.
    Format: ``section:<kind>:<document_id>``.
    """
    return f"{SECTION_NODE_ID_PREFIX}{kind}:{document_id}"

# Edge "kind" field added in schema 1.1: "cross_reference" (the
# marker → target edges already emitted by 1.0.0), "contains" (the
# hierarchy edges from document → page → entity), and "page_sequence"
# (next-page reading-order edges between adjacent page nodes).
EDGE_KIND_CROSS_REFERENCE = "cross_reference"
EDGE_KIND_CONTAINS = "contains"
EDGE_KIND_PAGE_SEQUENCE = "page_sequence"

# Markers whose source_ref doesn't encode a page (regex / grobid)
# cluster under this synthetic "markers" sibling of pages so they
# don't visually contaminate the page bodies.
MARKERS_SECTION_ID_PREFIX = "section:markers:"


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


# VLM marker source_refs encode page index as ``#/document/pages/N``.
# The standalone regex / grobid backends emit ``#/document`` (no page),
# so a ``None`` return means "page unknown — cluster under markers section".
_MARKER_PAGE_RE = re.compile(r"/pages/(\d+)\b")


def _marker_source_page(marker: RefMarker) -> int | None:
    """Return the marker's source page number, or ``None`` when unknown."""
    m = _MARKER_PAGE_RE.search(marker.source_ref or "")
    if m:
        return int(m.group(1))
    return None


def _marker_node_id(marker: RefMarker, index: int) -> str:
    """Stable id for a marker shown as its own node.

    Includes the index because two markers can legitimately share text
    (e.g. ``"Figure 1"`` appears twice in body text); using only the
    text + source_ref would collapse them into a single node.
    """
    return f"marker:{index}:{marker.source_ref}:{marker.marker_text}"


def _entity_type_value(et: Any) -> str:
    return et.value if hasattr(et, "value") else str(et)


_BACK_MATTER_TYPES: frozenset[str] = frozenset({
    EntityType.REFERENCE_ITEM.value,
    EntityType.REFERENCE_SECTION.value,
    EntityType.INDEX_ENTRY.value,
    EntityType.INDEX_SECTION.value,
    EntityType.GLOSSARY_ENTRY.value,
    EntityType.GLOSSARY_SECTION.value,
})


def _build_hierarchy_lookup(
    proposals: EntityProposalDocument,
) -> tuple[dict[str, int | None], dict[str, str | None]]:
    """From an EntityProposalDocument, build:

    * ``entity_id → page_no`` so a node can name its parent page.
    * ``entity_id → back_matter_section`` so REFERENCE_ITEM,
      INDEX_ENTRY, GLOSSARY_ENTRY entries can be re-parented under
      their logical section node instead of under whatever page the
      OCR happened to land them on (the user-visible "bibliography
      looks orphan" complaint).
    """
    page_by_id: dict[str, int | None] = {}
    section_by_id: dict[str, str | None] = {}
    for proposal in proposals.entities:
        page_by_id[proposal.id] = proposal.page_no
        et = _entity_type_value(proposal.entity_type)
        if et == EntityType.REFERENCE_ITEM.value:
            section_by_id[proposal.id] = "bibliography"
        elif et == EntityType.INDEX_ENTRY.value:
            section_by_id[proposal.id] = "index"
        elif et == EntityType.GLOSSARY_ENTRY.value:
            section_by_id[proposal.id] = "glossary"
        else:
            section_by_id[proposal.id] = None
    return page_by_id, section_by_id


def export_graph(
    xref: CrossReferenceGraph,
    *,
    document_id: str | None = None,
    extra_entities: list[SemanticEntity] | None = None,
    proposals: EntityProposalDocument | None = None,
) -> GraphExport:
    """Convert a :class:`CrossReferenceGraph` into a :class:`GraphExport`.

    Args:
        xref: The semantic sidecar to render.
        document_id: Optional stable identifier for the viewer.
        extra_entities: Additional structural entities to expose as nodes
            (typically from a `LinkedStructure`). Deduplicated against
            ``xref.entities`` on ``item_ref``.
        proposals: Optional OCR-side entity proposals. When supplied,
            the export emits the schema 1.1 hierarchy: one
            :data:`DOCUMENT_NODE_TYPE` root, one
            :data:`PAGE_NODE_TYPE` per distinct page, plus
            ``contains`` edges from document → page → entity. Entities
            on the back-matter list (REFERENCE_ITEM, INDEX_ENTRY,
            GLOSSARY_ENTRY) are re-parented under synthetic
            ``section:<kind>`` nodes (children of the document) so the
            bibliography / index / glossary visually cluster together
            instead of dispersing across the pages where the OCR landed
            them.

            When ``proposals`` is omitted the export keeps the
            1.0.0-shaped flat graph (back-compat for callers that don't
            have an EntityProposalDocument).

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
    containment_edges: list[dict[str, Any]] = []

    # Hierarchy backbone (schema 1.1). Only emitted when proposals is
    # supplied — otherwise we keep the 1.0.0 flat shape.
    document_node_id: str | None = None
    page_by_id: dict[str, int | None] = {}
    section_by_id: dict[str, str | None] = {}
    if proposals is not None:
        document_node_id = f"document:{document_id or proposals.document_id}"
        _ensure_node(
            nodes,
            document_node_id,
            DOCUMENT_NODE_TYPE,
            document_id or proposals.document_id,
            extra={"page_count": proposals.page_count},
        )
        page_by_id, section_by_id = _build_hierarchy_lookup(proposals)
        # Mint one page node per distinct page_no the proposals know
        # about. Pages are ordered low → high.
        pages_seen: set[int] = {p for p in page_by_id.values() if p is not None}
        sorted_pages = sorted(pages_seen)
        prev_page_id: str | None = None
        for page_no in sorted_pages:
            page_id = f"page:{document_id or proposals.document_id}:{page_no}"
            _ensure_node(
                nodes,
                page_id,
                PAGE_NODE_TYPE,
                f"Page {page_no}",
                extra={"page_no": page_no, "parent_id": document_node_id},
            )
            containment_edges.append(
                {
                    "source": document_node_id,
                    "target": page_id,
                    "edge_kind": EDGE_KIND_CONTAINS,
                    "label": "",
                }
            )
            # Sequential reading-order edge (page_sequence) — page N
            # is followed by page N+1. Emitted between consecutive
            # pages in sorted order; non-consecutive page numbers
            # (e.g. a missing page 7) still get a single edge from
            # the previous numbered page to the next one we have, so
            # the spine stays a single chain.
            if prev_page_id is not None:
                containment_edges.append(
                    {
                        "source": prev_page_id,
                        "target": page_id,
                        "edge_kind": EDGE_KIND_PAGE_SEQUENCE,
                        "label": "",
                    }
                )
            prev_page_id = page_id
        # Markers section is minted lazily later (only when at least
        # one marker lacks page info), so we don't pre-compute its id
        # here. The minted-flag plus _section_node_id() handle creation
        # in the marker loop below.
        # Back-matter section nodes — children of the document, NOT of
        # any page. REFERENCE_ITEM / INDEX_ENTRY / GLOSSARY_ENTRY
        # entries are reparented under these.
        for section_kind in {s for s in section_by_id.values() if s is not None}:
            section_id = _section_node_id(section_kind, document_id or proposals.document_id)
            _ensure_node(
                nodes,
                section_id,
                f"{section_kind}_section",
                section_kind.capitalize(),
                extra={"parent_id": document_node_id, "back_matter_kind": section_kind},
            )
            containment_edges.append(
                {
                    "source": document_node_id,
                    "target": section_id,
                    "edge_kind": EDGE_KIND_CONTAINS,
                    "label": "",
                }
            )

    def _attach_to_hierarchy(node_id: str) -> None:
        """If ``node_id`` matches a known entity and ``proposals`` was
        supplied, set its ``parent_id`` field to the right container
        (page or back-matter section) and emit the containment edge."""
        if proposals is None or document_node_id is None:
            return
        if node_id not in nodes:
            return
        # Back-matter takes precedence over page (so REFERENCE_ITEM
        # clusters under "bibliography" rather than under whichever
        # page the OCR landed it on).
        section_kind = section_by_id.get(node_id)
        if section_kind is not None:
            parent_id = _section_node_id(section_kind, document_id or proposals.document_id)
        else:
            page_no = page_by_id.get(node_id)
            parent_id = (
                f"page:{document_id or proposals.document_id}:{page_no}"
                if page_no is not None
                else document_node_id
            )
        nodes[node_id]["parent_id"] = parent_id
        nodes[node_id]["page_no"] = page_by_id.get(node_id)
        containment_edges.append(
            {
                "source": parent_id,
                "target": node_id,
                "edge_kind": EDGE_KIND_CONTAINS,
                "label": "",
            }
        )

    for triplet in _iter_entity_nodes(xref.entities):
        node_id, node_type, label = triplet
        _ensure_node(nodes, node_id, node_type, label)
        _attach_to_hierarchy(node_id)

    if extra_entities:
        for triplet in _iter_entity_nodes(extra_entities):
            node_id, node_type, label = triplet
            _ensure_node(nodes, node_id, node_type, label)
            _attach_to_hierarchy(node_id)

    marker_ids: dict[int, str] = {}
    markers_section_minted = False
    for idx, marker in enumerate(xref.markers):
        node_id = _marker_node_id(marker, idx)
        marker_ids[idx] = node_id
        marker_page = _marker_source_page(marker)
        extra: dict[str, Any] = {
            "source_ref": marker.source_ref,
            "char_offset": list(marker.char_offset),
            "backend": marker.backend,
        }
        if marker_page is not None:
            extra["page_no"] = marker_page
        _ensure_node(
            nodes,
            node_id,
            str(marker.marker_type),
            marker.marker_text,
            extra=extra,
        )
        # Attribute the marker to its source page when known. Markers
        # whose source_ref doesn't encode a page (regex / grobid) get
        # parented under the synthetic markers section (minted lazily
        # on first hit so empty graphs stay clean).
        if proposals is not None and document_node_id is not None:
            if marker_page is not None and marker_page in pages_seen:
                page_id = f"page:{document_id or proposals.document_id}:{marker_page}"
                nodes[node_id]["parent_id"] = page_id
                containment_edges.append(
                    {
                        "source": page_id,
                        "target": node_id,
                        "edge_kind": EDGE_KIND_CONTAINS,
                        "label": "",
                    }
                )
            else:
                section_id = _section_node_id(
                    "markers", document_id or proposals.document_id
                )
                if not markers_section_minted:
                    _ensure_node(
                        nodes,
                        section_id,
                        "markers_section",
                        "Markers",
                        extra={
                            "parent_id": document_node_id,
                            "back_matter_kind": "markers",
                        },
                    )
                    containment_edges.append(
                        {
                            "source": document_node_id,
                            "target": section_id,
                            "edge_kind": EDGE_KIND_CONTAINS,
                            "label": "",
                        }
                    )
                    markers_section_minted = True
                nodes[node_id]["parent_id"] = section_id
                containment_edges.append(
                    {
                        "source": section_id,
                        "target": node_id,
                        "edge_kind": EDGE_KIND_CONTAINS,
                        "label": "",
                    }
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
            # Newly-introduced target node (from a resolver edge that
            # points at an OCR-side entity); attach it to the hierarchy
            # via its EntityProposal's page_no.
            _attach_to_hierarchy(edge.target_ref)
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
                "edge_kind": EDGE_KIND_CROSS_REFERENCE,
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
                    "edge_kind": EDGE_KIND_CROSS_REFERENCE,
                }
            )
            unresolved_count += 1

    metadata: dict[str, Any] = {
        "doc_hash": xref.doc_hash,
        "total_markers": len(xref.markers),
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "backend_versions": dict(xref.backend_versions),
        "has_hierarchy": proposals is not None,
    }

    # Containment edges are appended AFTER cross-reference edges so a
    # consumer can render the backbone first (in a static layer) and
    # overlay the cross-ref arcs on top.
    edges_out = edges_out + containment_edges

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
