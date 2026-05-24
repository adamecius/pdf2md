"""Ensemble runner for semantic backends.

Runs a list of :class:`SemanticBackend` adapters on the same input and
merges their :class:`CrossReferenceGraph` outputs into one. Dedup is
confidence-based and content-keyed.
"""

from __future__ import annotations

from pathlib import Path

from pdf2md.models.cross_ref import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefMarker,
    SemanticEntity,
)
from pdf2md.semantic.base import SemanticBackend


def _marker_key(marker: RefMarker) -> tuple[str, str, int, int]:
    return (
        marker.source_ref,
        marker.marker_text,
        marker.char_offset[0],
        marker.char_offset[1],
    )


def _entity_key(entity: SemanticEntity) -> tuple[str, str]:
    # ``entity_type`` comes back as a string (Pydantic ``use_enum_values=True``).
    return (entity.item_ref, str(entity.entity_type))


def _merge_markers(graphs: list[CrossReferenceGraph]) -> list[RefMarker]:
    best: dict[tuple[str, str, int, int], RefMarker] = {}
    for graph in graphs:
        for marker in graph.markers:
            key = _marker_key(marker)
            current = best.get(key)
            if current is None or marker.confidence > current.confidence:
                best[key] = marker
    return list(best.values())


def _merge_entities(graphs: list[CrossReferenceGraph]) -> list[SemanticEntity]:
    best: dict[tuple[str, str], SemanticEntity] = {}
    for graph in graphs:
        for entity in graph.entities:
            key = _entity_key(entity)
            current = best.get(key)
            if current is None or entity.confidence > current.confidence:
                best[key] = entity
    return list(best.values())


def _merge_versions(graphs: list[CrossReferenceGraph]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for graph in graphs:
        for name, version in graph.backend_versions.items():
            merged[name] = version
    return merged


def merge_graphs(graphs: list[CrossReferenceGraph], doc_hash: str) -> CrossReferenceGraph:
    """Merge multiple :class:`CrossReferenceGraph`s into one.

    Args:
        graphs: Per-backend graphs to merge. Must be non-empty.
        doc_hash: Document hash to stamp on the merged result. The caller
            supplies this because per-backend graphs may use slightly
            different hash inputs (PDF bytes vs. text) — the ensemble
            uses a single canonical value.

    Returns:
        A new :class:`CrossReferenceGraph` with deduplicated markers and
        entities and a merged ``backend_versions`` map.

    Raises:
        ValueError: If ``graphs`` is empty.
    """
    if not graphs:
        raise ValueError("merge_graphs requires at least one input graph")

    return CrossReferenceGraph(
        schema_version=CROSS_REF_SCHEMA_VERSION,
        doc_hash=doc_hash,
        markers=_merge_markers(graphs),
        edges=[],
        entities=_merge_entities(graphs),
        backend_versions=_merge_versions(graphs),
    )


def run_ensemble(
    backends: list[SemanticBackend],
    pdf_path: Path | None,
    text: str | None,
    output_dir: Path,
    doc_hash: str | None = None,
) -> CrossReferenceGraph:
    """Run every backend in ``backends`` and merge the results.

    Backends whose :meth:`SemanticBackend.is_available` returns ``False``
    are skipped silently. If no backend is available, an empty graph is
    returned (with the supplied ``doc_hash`` or a placeholder).

    Args:
        backends: Adapters to run.
        pdf_path: Source PDF, or ``None`` for text-only backends.
        text: Pre-extracted text, or ``None``.
        output_dir: Directory for transient per-backend artefacts.
            Each backend writes into a ``<backend.name()>/`` subfolder.
        doc_hash: Optional canonical document hash to stamp on the merged
            graph. Defaults to the first available backend's hash, or
            ``"sha256:0"`` when no backend ran.

    Returns:
        Merged :class:`CrossReferenceGraph`.
    """
    if not backends:
        raise ValueError("run_ensemble requires at least one backend")

    output_dir.mkdir(parents=True, exist_ok=True)
    per_backend: list[CrossReferenceGraph] = []
    for backend in backends:
        if not backend.is_available():
            continue
        sub_dir = output_dir / backend.name()
        graph = backend.extract(pdf_path=pdf_path, text=text, output_dir=sub_dir)
        per_backend.append(graph)

    if not per_backend:
        return CrossReferenceGraph(
            schema_version=CROSS_REF_SCHEMA_VERSION,
            doc_hash=doc_hash or "sha256:0",
            markers=[],
            edges=[],
            entities=[],
            backend_versions={},
        )

    return merge_graphs(per_backend, doc_hash=doc_hash or per_backend[0].doc_hash)
