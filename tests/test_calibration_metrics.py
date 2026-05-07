import pytest

from pdf2md.calibration.matching import MatchRecord
from pdf2md.calibration.metrics import (
    CalibrationSettings,
    build_prior_document,
    compute_f1,
    compute_precision,
    compute_recall,
    metric_from_counts,
    smoothed_precision,
)
from pdf2md.models.priors import CalibrationCounts, CalibrationStatus, CalibrationTarget, MatchOutcome


class TestScalarMetrics:
    def test_precision_regular_case(self):
        assert compute_precision(2, 1) == pytest.approx(2 / 3)

    def test_precision_zero_denominator_returns_zero(self):
        assert compute_precision(0, 0) == 0.0

    def test_recall_regular_case(self):
        assert compute_recall(2, 2) == 0.5

    def test_recall_zero_denominator_returns_zero(self):
        assert compute_recall(0, 0) == 0.0

    def test_f1_regular_case(self):
        assert compute_f1(0.5, 0.5) == 0.5

    def test_f1_zero_denominator_returns_zero(self):
        assert compute_f1(0.0, 0.0) == 0.0

    def test_smoothed_precision_uses_alpha_beta(self):
        assert smoothed_precision(1, 1, 1.0, 1.0) == 0.5


class TestMetricFromCounts:
    def test_metric_from_counts_computes_precision_recall_f1(self):
        metric = metric_from_counts(target=CalibrationTarget.BLOCK_KIND, key="heading", counts=CalibrationCounts(true_positive=2, false_positive=1, false_negative=2), settings=CalibrationSettings(min_samples=2))
        assert metric.precision == pytest.approx(2 / 3)
        assert metric.recall == pytest.approx(0.5)
        assert metric.f1 == pytest.approx(4 / 7)

    def test_metric_from_counts_marks_no_samples(self):
        metric = metric_from_counts(target=CalibrationTarget.BLOCK_KIND, key="heading", counts=CalibrationCounts(true_positive=0, false_positive=0, false_negative=0), settings=CalibrationSettings())
        assert metric.status == CalibrationStatus.NO_SAMPLES

    def test_metric_from_counts_marks_underpowered(self):
        metric = metric_from_counts(target=CalibrationTarget.BLOCK_KIND, key="heading", counts=CalibrationCounts(true_positive=1, false_positive=0, false_negative=0), settings=CalibrationSettings(min_samples=2))
        assert metric.status == CalibrationStatus.UNDERPOWERED

    def test_metric_from_counts_marks_calibrated(self):
        metric = metric_from_counts(target=CalibrationTarget.BLOCK_KIND, key="heading", counts=CalibrationCounts(true_positive=2, false_positive=0, false_negative=0), settings=CalibrationSettings(min_samples=2))
        assert metric.status == CalibrationStatus.CALIBRATED


class TestBuildPriorDocument:
    def test_build_prior_document_groups_records_by_target_and_key(self):
        records = [MatchRecord(CalibrationTarget.BLOCK_KIND, "heading", "mineru", "p1", "t1", MatchOutcome.TRUE_POSITIVE, 0.9, {}), MatchRecord(CalibrationTarget.BLOCK_KIND, "heading", "mineru", "p2", None, MatchOutcome.FALSE_POSITIVE, 0.9, {})]
        prior = build_prior_document(backend="mineru", backend_version="v", generated_from=["truth.json"], records=records, settings=CalibrationSettings(min_samples=2), warnings=[])
        assert prior.block_kind_priors[0].counts.true_positive == 1
        assert prior.block_kind_priors[0].counts.false_positive == 1

    def test_build_prior_document_separates_block_entity_relation_and_calibration_key_priors(self):
        records = [
            MatchRecord(CalibrationTarget.BLOCK_KIND, "heading", "mineru", "p1", "t1", MatchOutcome.TRUE_POSITIVE, 0.9, {}),
            MatchRecord(CalibrationTarget.ENTITY_TYPE, "section", "mineru", "e1", "te1", MatchOutcome.TRUE_POSITIVE, 0.9, {}),
            MatchRecord(CalibrationTarget.RELATION_TYPE, "caption_of", "mineru", "r1", "tr1", MatchOutcome.TRUE_POSITIVE, 0.9, {}),
            MatchRecord(CalibrationTarget.CALIBRATION_KEY, "mineru:section:detector", "mineru", "e1", "te1", MatchOutcome.TRUE_POSITIVE, 0.9, {}),
        ]
        prior = build_prior_document(backend="mineru", backend_version="v", generated_from=[], records=records, settings=CalibrationSettings(), warnings=[])
        assert prior.block_kind_priors[0].key == "heading"
        assert prior.entity_type_priors[0].key == "section"
        assert prior.relation_type_priors[0].key == "caption_of"
        assert prior.calibration_key_priors[0].key == "mineru:section:detector"

    def test_build_prior_document_preserves_backend_and_generated_from(self):
        prior = build_prior_document(backend="mineru", backend_version="1", generated_from=["truth.json"], records=[], settings=CalibrationSettings(), warnings=[])
        assert prior.backend == "mineru"
        assert prior.backend_version == "1"
        assert prior.generated_from == ["truth.json"]

    def test_build_prior_document_uses_default_confidence(self):
        prior = build_prior_document(backend="mineru", backend_version=None, generated_from=[], records=[], settings=CalibrationSettings(default_confidence=0.42), warnings=[])
        assert prior.default_confidence == 0.42
