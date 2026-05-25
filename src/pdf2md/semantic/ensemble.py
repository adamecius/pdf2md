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


def _weight(weights: dict[str, float] | None, backend: str) -> float:
    if weights is None:
        return 1.0
    return float(weights.get(backend, 1.0))


def _merge_markers(
    graphs: list[CrossReferenceGraph],
    weights: dict[str, float] | None = None,
) -> list[RefMarker]:
    best: dict[tuple[str, str, int, int], tuple[float, RefMarker]] = {}
    for graph in graphs:
        for marker in graph.markers:
            key = _marker_key(marker)
            weighted = marker.confidence * _weight(weights, marker.backend)
            current = best.get(key)
            if current is None or weighted > current[0]:
                best[key] = (weighted, marker)
    return [marker for _, marker in best.values()]


def _merge_entities(
    graphs: list[CrossReferenceGraph],
    weights: dict[str, float] | None = None,
) -> list[SemanticEntity]:
    best: dict[tuple[str, str], tuple[float, SemanticEntity]] = {}
    for graph in graphs:
        for entity in graph.entities:
            key = _entity_key(entity)
            weighted = entity.confidence * _weight(weights, entity.backend)
            current = best.get(key)
            if current is None or weighted > current[0]:
                best[key] = (weighted, entity)
    return [entity for _, entity in best.values()]


def _merge_versions(graphs: list[CrossReferenceGraph]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for graph in graphs:
        for name, version in graph.backend_versions.items():
            merged[name] = version
    return merged


def merge_graphs(
    graphs: list[CrossReferenceGraph],
    doc_hash: str,
    *,
    backend_weights: dict[str, float] | None = None,
) -> CrossReferenceGraph:
    """Merge multiple :class:`CrossReferenceGraph`s into one.

    Args:
        graphs: Per-backend graphs to merge. Must be non-empty.
        doc_hash: Document hash to stamp on the merged result. The caller
            supplies this because per-backend graphs may use slightly
            different hash inputs (PDF bytes vs. text) — the ensemble
            uses a single canonical value.
        backend_weights: Optional per-backend confidence multipliers.
            When supplied, each marker / entity's confidence is
            multiplied by ``backend_weights.get(backend, 1.0)`` before
            the best-wins tie-break. Used by the Plan 7 document-class
            mixer to down-weight backends that under-perform on a
            given document class (e.g. GROBID on ``book``-class
            inputs). The raw ``confidence`` fields on the surviving
            entities are NOT mutated — the weighting only affects
            which one wins the merge.

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
        markers=_merge_markers(graphs, backend_weights),
        edges=[],
        entities=_merge_entities(graphs, backend_weights),
        backend_versions=_merge_versions(graphs),
    )


#: GROBID is article-trained — it under-detects bibliography entries and
#: misses chapter / index structure on book-shaped inputs. The Plan 7
#: ensemble mixer multiplies GROBID's per-marker confidence by this
#: factor when the document classifies as ``book``, letting regex / VLM
#: win more tie-breaks. Other backends keep weight 1.0.
GROBID_BOOK_WEIGHT: float = 0.65


def weights_for_document_class(document_class: str | None) -> dict[str, float]:
    """Return the per-backend confidence multipliers for a doc-class.

    Args:
        document_class: One of ``"article"``, ``"book"``, ``"document"``,
            or ``None``. Anything other than ``"book"`` returns an empty
            map (i.e. uniform weights).

    Returns:
        A ``{backend_name: multiplier}`` dictionary, suitable for the
        :func:`merge_graphs` ``backend_weights`` argument.
    """
    if document_class == "book":
        return {"grobid": GROBID_BOOK_WEIGHT}
    return {}


def run_ensemble(
    backends: list[SemanticBackend],
    pdf_path: Path | None,
    text: str | None,
    output_dir: Path,
    doc_hash: str | None = None,
    *,
    document_class: str | None = None,
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
        document_class: Optional Plan 7 classification (``"article"``,
            ``"book"``, ``"document"``). When supplied, per-backend
            confidence weights from :func:`weights_for_document_class`
            are applied to the merge tie-break. The default behaviour
            (no document_class) keeps uniform weights — backwards
            compatible.

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
        try:
            graph = backend.extract(pdf_path=pdf_path, text=text, output_dir=sub_dir)
        except ValueError:
            # Skip backends whose required input is missing for this
            # invocation (e.g. VLM with no image, regex with no text).
            # These are *input-shape* mismatches, not real failures —
            # the ensemble's job is to opportunistically run whatever
            # backends can act on the given inputs.
            continue
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

    return merge_graphs(
        per_backend,
        doc_hash=doc_hash or per_backend[0].doc_hash,
        backend_weights=weights_for_document_class(document_class) or None,
    )
