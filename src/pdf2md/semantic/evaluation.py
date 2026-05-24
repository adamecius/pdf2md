"""Semantic-layer evaluation harness.

Aligns an extracted :class:`CrossReferenceGraph` to a ground-truth
graph and reports precision/recall/F1 for marker detection, plus
resolution accuracy and per-type breakdowns.

Alignment is content-based: two markers match iff they share the same
``marker_type`` AND have an equivalent ``marker_text`` after
case-insensitive whitespace-collapsed normalisation. Char offsets are
not used (extracted and ground-truth graphs come from different text
coordinate spaces — the regex backend works on extracted text, the
ground-truth comes from LaTeXML).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from pdf2md.models.cross_ref import CrossReferenceGraph, RefEdge, RefMarker, SemanticEntity


@dataclass(frozen=True)
class SemanticEvalResult:
    """One per (document, backend) pair.

    Attributes:
        document_id: Stable identifier for the document under evaluation.
        backend: Backend identifier (``"regex"``, ``"grobid"``, ...).
        marker_precision: ``tp / (tp + fp)`` over detected markers.
        marker_recall: ``tp / (tp + fn)`` over GT markers.
        marker_f1: Harmonic mean of precision and recall.
        marker_f1_by_type: Per-RefType F1 score (key is the RefType value).
        resolution_accuracy: For matched markers, fraction where the
            ``target_ref`` agrees between extracted and GT graphs.
        resolution_accuracy_by_type: Per-RefType breakdown.
        entity_precision: Precision over :class:`SemanticEntity` pairs.
        entity_recall: Recall over :class:`SemanticEntity` pairs.
        entity_f1: Harmonic mean of entity precision and recall.
        n_markers_extracted: Total markers in the extracted graph.
        n_markers_truth: Total markers in the GT graph.
        n_markers_matched: Number of aligned (true-positive) pairs.
    """

    document_id: str
    backend: str
    marker_precision: float
    marker_recall: float
    marker_f1: float
    marker_f1_by_type: dict[str, float] = field(default_factory=dict)
    resolution_accuracy: float = 0.0
    resolution_accuracy_by_type: dict[str, float] = field(default_factory=dict)
    entity_precision: float = 0.0
    entity_recall: float = 0.0
    entity_f1: float = 0.0
    n_markers_extracted: int = 0
    n_markers_truth: int = 0
    n_markers_matched: int = 0


def _normalise_text(text: str) -> str:
    return " ".join(text.lower().split())


def _marker_key(marker: RefMarker) -> tuple[str, str]:
    return (str(marker.marker_type), _normalise_text(marker.marker_text))


def _entity_key(entity: SemanticEntity) -> tuple[str, str]:
    return (str(entity.entity_type), entity.item_ref)


def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def _f1(p: float, r: float) -> float:
    return _safe_div(2 * p * r, p + r)


def _edge_for_marker(edges: Iterable[RefEdge], marker: RefMarker) -> RefEdge | None:
    target_key = _marker_key(marker)
    for edge in edges:
        if _marker_key(edge.marker) == target_key:
            return edge
    return None


def _normalise_target(target: str | None) -> str | None:
    if target is None:
        return None
    return target.lstrip("#") or None


def _evaluate_markers(
    extracted: CrossReferenceGraph,
    truth: CrossReferenceGraph,
) -> tuple[float, float, float, int, int, int, dict[str, tuple[int, int, int]]]:
    """Return marker (P, R, F1, n_extracted, n_truth, n_matched, per_type_counts)."""
    extracted_counts: dict[tuple[str, str], int] = {}
    truth_counts: dict[tuple[str, str], int] = {}
    for m in extracted.markers:
        extracted_counts[_marker_key(m)] = extracted_counts.get(_marker_key(m), 0) + 1
    for m in truth.markers:
        truth_counts[_marker_key(m)] = truth_counts.get(_marker_key(m), 0) + 1

    tp = 0
    for key, count in extracted_counts.items():
        truth_n = truth_counts.get(key, 0)
        tp += min(count, truth_n)

    fp = sum(extracted_counts.values()) - tp
    fn = sum(truth_counts.values()) - tp

    p = _safe_div(tp, tp + fp)
    r = _safe_div(tp, tp + fn)
    f1 = _f1(p, r)

    # Per-type counts: {marker_type_value: (tp, fp, fn)}
    per_type: dict[str, tuple[int, int, int]] = {}
    types = {key[0] for key in extracted_counts} | {key[0] for key in truth_counts}
    for marker_type in types:
        ext_n = sum(c for k, c in extracted_counts.items() if k[0] == marker_type)
        tru_n = sum(c for k, c in truth_counts.items() if k[0] == marker_type)
        tp_t = sum(
            min(c, truth_counts.get(k, 0))
            for k, c in extracted_counts.items()
            if k[0] == marker_type
        )
        per_type[marker_type] = (tp_t, ext_n - tp_t, tru_n - tp_t)

    return p, r, f1, sum(extracted_counts.values()), sum(truth_counts.values()), tp, per_type


def _evaluate_resolution(
    extracted: CrossReferenceGraph,
    truth: CrossReferenceGraph,
) -> tuple[float, dict[str, float]]:
    extracted_edges_by_key: dict[tuple[str, str], list[RefEdge]] = {}
    for edge in extracted.edges:
        extracted_edges_by_key.setdefault(_marker_key(edge.marker), []).append(edge)
    truth_edges_by_key: dict[tuple[str, str], list[RefEdge]] = {}
    for edge in truth.edges:
        truth_edges_by_key.setdefault(_marker_key(edge.marker), []).append(edge)

    total = 0
    correct = 0
    per_type_totals: dict[str, int] = {}
    per_type_correct: dict[str, int] = {}

    for key, ext_edges in extracted_edges_by_key.items():
        truth_edges = truth_edges_by_key.get(key)
        if not truth_edges:
            continue
        marker_type = key[0]
        ext = ext_edges[0]
        tru = truth_edges[0]
        total += 1
        per_type_totals[marker_type] = per_type_totals.get(marker_type, 0) + 1
        ext_t = _normalise_target(ext.target_ref)
        tru_t = _normalise_target(tru.target_ref)
        if ext.resolved and tru.resolved and ext_t == tru_t:
            correct += 1
            per_type_correct[marker_type] = per_type_correct.get(marker_type, 0) + 1
        elif not ext.resolved and not tru.resolved:
            correct += 1
            per_type_correct[marker_type] = per_type_correct.get(marker_type, 0) + 1

    accuracy = _safe_div(correct, total)
    per_type_accuracy = {
        mt: _safe_div(per_type_correct.get(mt, 0), per_type_totals[mt])
        for mt in per_type_totals
    }
    return accuracy, per_type_accuracy


def _evaluate_entities(
    extracted: CrossReferenceGraph,
    truth: CrossReferenceGraph,
) -> tuple[float, float, float]:
    extracted_set = {_entity_key(e) for e in extracted.entities}
    truth_set = {_entity_key(e) for e in truth.entities}
    if not extracted_set and not truth_set:
        return 0.0, 0.0, 0.0
    tp = len(extracted_set & truth_set)
    fp = len(extracted_set - truth_set)
    fn = len(truth_set - extracted_set)
    p = _safe_div(tp, tp + fp)
    r = _safe_div(tp, tp + fn)
    return p, r, _f1(p, r)


def evaluate_semantic(
    extracted: CrossReferenceGraph,
    ground_truth: CrossReferenceGraph,
    *,
    document_id: str,
    backend: str,
) -> SemanticEvalResult:
    """Evaluate one extracted graph against ground truth.

    Args:
        extracted: The :class:`CrossReferenceGraph` produced by a backend.
        ground_truth: The :class:`CrossReferenceGraph` produced by
            :func:`pdf2md.semantic.groundtruth.generate_ground_truth`.
        document_id: Stable identifier (e.g. the relative .tex path).
        backend: Backend identifier (``"regex"``, ``"grobid"``, ...).

    Returns:
        A :class:`SemanticEvalResult` with all metrics populated.
    """
    p, r, f1, n_ext, n_tru, tp, per_type_counts = _evaluate_markers(extracted, ground_truth)
    per_type_f1: dict[str, float] = {}
    for marker_type, (tp_t, fp_t, fn_t) in per_type_counts.items():
        pt = _safe_div(tp_t, tp_t + fp_t)
        rt = _safe_div(tp_t, tp_t + fn_t)
        per_type_f1[marker_type] = _f1(pt, rt)

    resolution_accuracy, resolution_per_type = _evaluate_resolution(extracted, ground_truth)
    ent_p, ent_r, ent_f1 = _evaluate_entities(extracted, ground_truth)

    return SemanticEvalResult(
        document_id=document_id,
        backend=backend,
        marker_precision=p,
        marker_recall=r,
        marker_f1=f1,
        marker_f1_by_type=per_type_f1,
        resolution_accuracy=resolution_accuracy,
        resolution_accuracy_by_type=resolution_per_type,
        entity_precision=ent_p,
        entity_recall=ent_r,
        entity_f1=ent_f1,
        n_markers_extracted=n_ext,
        n_markers_truth=n_tru,
        n_markers_matched=tp,
    )


def result_to_csv_row(result: SemanticEvalResult) -> dict[str, str]:
    """Flatten a :class:`SemanticEvalResult` into a CSV-friendly row."""
    return {
        "document_id": result.document_id,
        "backend": result.backend,
        "marker_precision": f"{result.marker_precision:.4f}",
        "marker_recall": f"{result.marker_recall:.4f}",
        "marker_f1": f"{result.marker_f1:.4f}",
        "resolution_accuracy": f"{result.resolution_accuracy:.4f}",
        "entity_precision": f"{result.entity_precision:.4f}",
        "entity_recall": f"{result.entity_recall:.4f}",
        "entity_f1": f"{result.entity_f1:.4f}",
        "n_markers_extracted": str(result.n_markers_extracted),
        "n_markers_truth": str(result.n_markers_truth),
        "n_markers_matched": str(result.n_markers_matched),
    }


__all__ = [
    "SemanticEvalResult",
    "evaluate_semantic",
    "result_to_csv_row",
]
