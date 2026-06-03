"""Data-driven backend routing for the semantic ensemble.

The ensemble mixer (:func:`pdf2md.semantic.ensemble.merge_graphs`) accepts a
``{backend: multiplier}`` map that down-weights under-performing backends in
the best-wins tie-break. This module derives those multipliers from the Plan
007_2 calibration baseline instead of a hardcoded constant.

ROADMAP principle: *no hardcoded paper-vs-book routing — every semantic
backend is a candidate*. The derived weights only **down-weight** a backend;
they never drop it to zero, so no backend is ever excluded.

Derivation (per the 006_1 plan): for the ``book`` class, each semantic
backend's weight is its aggregate resolution rate on the book example
relative to the best backend (``rate / max_rate``), floored so it is never
zero. The ``article`` and ``document`` classes use uniform weights (an empty
map), because on article-shaped inputs the backends are competitive.

When no baseline file is available the loader returns empty maps, so the
ensemble falls back to uniform weights — behaviour identical to pre-007_2.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Default location of the Plan 007_2 calibration baseline.
DEFAULT_CALIBRATION_PATH = Path("docs/reports/semantic_calibration_baseline.json")

#: Floor applied to derived weights so a backend is never fully excluded.
MIN_WEIGHT: float = 0.1

#: Example ids in the baseline that are book-class. Everything else is
#: treated as article-class for aggregation.
_BOOK_EXAMPLES: frozenset[str] = frozenset({"example3"})

#: Map baseline semantic-backend names onto the runtime backend identifiers
#: returned by ``SemanticBackend.name()`` (the VLM adapter reports ``"vlm"``).
_BACKEND_ALIASES: dict[str, str] = {"vlm_v4": "vlm"}

#: Document classes that receive uniform (empty) weight maps.
_UNIFORM_CLASSES: tuple[str, ...] = ("article", "document")

# Lazy per-path cache so repeated calls do not re-read the baseline. Keyed by
# the resolved path string; ``None`` records a path that failed to load.
_WEIGHTS_CACHE: dict[str, dict[str, dict[str, float]]] = {}


def _normalize_backend(name: str) -> str:
    return _BACKEND_ALIASES.get(name, name)


def _book_weights_from_per_combo(per_combo: list[dict]) -> dict[str, float]:
    """Aggregate book-example resolution rates into relative weights."""

    resolved: dict[str, int] = {}
    total: dict[str, int] = {}
    for combo in per_combo:
        if combo.get("example") not in _BOOK_EXAMPLES:
            continue
        backend = _normalize_backend(str(combo.get("semantic_backend", "")))
        if not backend:
            continue
        resolved[backend] = resolved.get(backend, 0) + int(combo.get("resolved", 0))
        total[backend] = total.get(backend, 0) + int(combo.get("total", 0))

    rates = {backend: resolved[backend] / total[backend] for backend in total if total[backend] > 0}
    if not rates:
        return {}
    max_rate = max(rates.values())
    if max_rate <= 0:
        return {}
    return {backend: max(round(rate / max_rate, 6), MIN_WEIGHT) for backend, rate in rates.items()}


def load_calibration_weights(path: Path) -> dict[str, dict[str, float]]:
    """Load per-document-class backend weights from a baseline JSON file.

    Args:
        path: Path to a semantic calibration baseline JSON (the file written
            by ``tools/semantic_calibration_report.py``). Its ``per_combo``
            list provides per-example × per-semantic-backend resolution rates.

    Returns:
        ``{"book": {backend: weight, ...}, "article": {}, "document": {}}``.
        The ``book`` map carries derived down-weights relative to the best
        backend (never below :data:`MIN_WEIGHT`); the uniform classes carry
        empty maps. Returns all-empty maps when the file is absent or
        malformed (graceful degradation to uniform weights).
    """

    weights: dict[str, dict[str, float]] = {"book": {}, "article": {}, "document": {}}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return weights
    per_combo = payload.get("per_combo")
    if isinstance(per_combo, list):
        weights["book"] = _book_weights_from_per_combo(per_combo)
    return weights


def weights_for_document_class(
    document_class: str | None,
    calibration_path: Path | str | None = None,
) -> dict[str, float]:
    """Return the per-backend confidence multipliers for a document class.

    Args:
        document_class: One of ``"article"``, ``"book"``, ``"document"`` or
            ``None``. Anything that is not a calibrated, non-uniform class
            yields uniform weights (an empty map).
        calibration_path: Optional path to a calibration baseline JSON. When
            given (and not already cached), weights are loaded from it. When
            omitted, weights stay uniform — preserving the pre-007_2
            behaviour for callers that do not opt in.

    Returns:
        A ``{backend_name: multiplier}`` map for :func:`merge_graphs`'s
        ``backend_weights`` argument. Empty means uniform.
    """

    if document_class is None or calibration_path is None:
        return {}
    cache_key = str(Path(calibration_path))
    if cache_key not in _WEIGHTS_CACHE:
        _WEIGHTS_CACHE[cache_key] = load_calibration_weights(Path(calibration_path))
    return dict(_WEIGHTS_CACHE[cache_key].get(document_class, {}))


__all__ = [
    "DEFAULT_CALIBRATION_PATH",
    "MIN_WEIGHT",
    "load_calibration_weights",
    "weights_for_document_class",
]
