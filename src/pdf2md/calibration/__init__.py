"""Calibration helpers for backend confidence priors."""

from .matching import MatchRecord, match_blocks, match_entities, match_relations, normalise_text, token_overlap
from .metrics import (
    CalibrationSettings,
    build_prior_document,
    compute_f1,
    compute_precision,
    compute_recall,
    metric_from_counts,
    smoothed_precision,
)

__all__ = [
    "CalibrationSettings",
    "MatchRecord",
    "build_prior_document",
    "compute_f1",
    "compute_precision",
    "compute_recall",
    "match_blocks",
    "match_entities",
    "match_relations",
    "metric_from_counts",
    "normalise_text",
    "smoothed_precision",
    "token_overlap",
]
