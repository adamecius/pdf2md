"""Metric aggregation for calibration priors."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from pdf2md.calibration.matching import MatchRecord
from pdf2md.models.priors import (
    CalibrationCounts,
    CalibrationMetric,
    CalibrationPriorDocument,
    CalibrationStatus,
    CalibrationTarget,
    MatchOutcome,
)


@dataclass(frozen=True)
class CalibrationSettings:
    """Thresholds and smoothing parameters used to compute calibration priors.

    Attributes:
        min_samples: Minimum number of supporting matches (TP+FP+FN) required
            before a metric is considered ``CALIBRATED`` rather than
            ``UNDERPOWERED``.
        smoothing_alpha: Laplace alpha pseudo-count added to true positives in
            smoothed-precision computation.
        smoothing_beta: Laplace beta pseudo-count added to false positives in
            smoothed-precision computation.
        default_confidence: Confidence value to fall back to when a key has no
            calibration prior.

    Raises:
        ValueError: If any field is outside its admissible range.
    """

    min_samples: int = 5
    smoothing_alpha: float = 1.0
    smoothing_beta: float = 1.0
    default_confidence: float = 0.5

    def __post_init__(self) -> None:
        if self.min_samples < 1:
            raise ValueError("min_samples must be >= 1")
        if self.smoothing_alpha <= 0:
            raise ValueError("smoothing_alpha must be > 0")
        if self.smoothing_beta <= 0:
            raise ValueError("smoothing_beta must be > 0")
        if not 0.0 <= self.default_confidence <= 1.0:
            raise ValueError("default_confidence must be in [0.0, 1.0]")


def compute_precision(tp: int, fp: int) -> float:
    """Return ``tp / (tp + fp)``, or ``0.0`` when both counts are zero."""
    denominator = tp + fp
    return 0.0 if denominator == 0 else tp / denominator


def compute_recall(tp: int, fn: int) -> float:
    """Return ``tp / (tp + fn)``, or ``0.0`` when both counts are zero."""
    denominator = tp + fn
    return 0.0 if denominator == 0 else tp / denominator


def compute_f1(precision: float, recall: float) -> float:
    """Return the harmonic mean of precision and recall, or ``0.0`` when both are zero."""
    denominator = precision + recall
    return 0.0 if denominator == 0 else 2 * precision * recall / denominator


def smoothed_precision(tp: int, fp: int, alpha: float, beta: float) -> float:
    """Return Laplace-smoothed precision ``(tp + alpha) / (tp + fp + alpha + beta)``."""
    return (tp + alpha) / (tp + fp + alpha + beta)


def metric_from_counts(
    *,
    target: CalibrationTarget,
    key: str,
    counts: CalibrationCounts,
    settings: CalibrationSettings,
    metadata: dict[str, Any] | None = None,
) -> CalibrationMetric:
    """Build a calibration metric from raw TP/FP/FN counts.

    Computes precision, recall, F1, and smoothed precision (the calibrated
    confidence), and assigns a status of ``NO_SAMPLES``, ``UNDERPOWERED``, or
    ``CALIBRATED`` based on the support count and ``settings.min_samples``.

    Args:
        target: Calibration target this metric belongs to.
        key: Target-specific bucket key (block-kind value, entity type, ...).
        counts: TP/FP/FN counts for the bucket.
        settings: Thresholds and smoothing parameters.
        metadata: Optional free-form payload attached to the metric.

    Returns:
        A ``CalibrationMetric`` populated with the derived values.
    """
    tp = counts.true_positive
    fp = counts.false_positive
    fn = counts.false_negative
    precision = compute_precision(tp, fp)
    recall = compute_recall(tp, fn)
    support = tp + fp + fn
    if support == 0:
        status = CalibrationStatus.NO_SAMPLES
    elif support < settings.min_samples:
        status = CalibrationStatus.UNDERPOWERED
    else:
        status = CalibrationStatus.CALIBRATED
    return CalibrationMetric(
        target=target,
        key=key,
        counts=counts,
        precision=precision,
        recall=recall,
        f1=compute_f1(precision, recall),
        support=support,
        calibrated_confidence=smoothed_precision(tp, fp, settings.smoothing_alpha, settings.smoothing_beta),
        status=status,
        metadata=metadata or {},
    )


def _counts_from_records(records: list[MatchRecord]) -> dict[tuple[CalibrationTarget, str], CalibrationCounts]:
    raw: dict[tuple[CalibrationTarget, str], dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for record in records:
        bucket = raw[(CalibrationTarget(record.target), record.key)]
        if record.outcome == MatchOutcome.TRUE_POSITIVE:
            bucket["tp"] += 1
        elif record.outcome == MatchOutcome.FALSE_POSITIVE:
            bucket["fp"] += 1
        elif record.outcome == MatchOutcome.FALSE_NEGATIVE:
            bucket["fn"] += 1
    return {
        key: CalibrationCounts(true_positive=value["tp"], false_positive=value["fp"], false_negative=value["fn"])
        for key, value in raw.items()
    }


def _sorted_metrics(
    *, target: CalibrationTarget, counts: dict[tuple[CalibrationTarget, str], CalibrationCounts], settings: CalibrationSettings
) -> list[CalibrationMetric]:
    metrics = []
    for (record_target, key), record_counts in counts.items():
        if record_target == target:
            metrics.append(metric_from_counts(target=target, key=key, counts=record_counts, settings=settings))
    return sorted(metrics, key=lambda metric: metric.key)


def build_prior_document(
    *,
    backend: str,
    backend_version: str | None,
    generated_from: list[str],
    records: list[MatchRecord],
    settings: CalibrationSettings,
    warnings: list[str],
    metadata: dict[str, Any] | None = None,
) -> CalibrationPriorDocument:
    """Aggregate match records into a per-backend ``CalibrationPriorDocument``.

    Records are bucketed by ``(target, key)``, converted to counts, and turned
    into sorted ``CalibrationMetric`` lists for each calibration target
    (block kind, entity type, relation type, and calibration key).

    Args:
        backend: Identifier of the backend the priors describe.
        backend_version: Backend version string for traceability, or None.
        generated_from: Document identifiers contributing to the priors.
        records: Match records produced by the matching pass.
        settings: Thresholds and smoothing parameters.
        warnings: Non-fatal warnings to propagate into the prior document.
        metadata: Optional free-form payload attached to the prior document.

    Returns:
        A ``CalibrationPriorDocument`` ready to be serialised to disk.
    """
    counts = _counts_from_records(records)
    return CalibrationPriorDocument(
        backend=backend,
        backend_version=backend_version,
        generated_from=generated_from,
        min_samples=settings.min_samples,
        smoothing_alpha=settings.smoothing_alpha,
        smoothing_beta=settings.smoothing_beta,
        default_confidence=settings.default_confidence,
        block_kind_priors=_sorted_metrics(target=CalibrationTarget.BLOCK_KIND, counts=counts, settings=settings),
        entity_type_priors=_sorted_metrics(target=CalibrationTarget.ENTITY_TYPE, counts=counts, settings=settings),
        relation_type_priors=_sorted_metrics(target=CalibrationTarget.RELATION_TYPE, counts=counts, settings=settings),
        calibration_key_priors=_sorted_metrics(target=CalibrationTarget.CALIBRATION_KEY, counts=counts, settings=settings),
        warnings=warnings,
        metadata=metadata or {},
    )
