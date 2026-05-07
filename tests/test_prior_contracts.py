import pytest
from pydantic import ValidationError

from pdf2md.models.priors import (
    CalibrationCounts,
    CalibrationMetric,
    CalibrationPriorDocument,
    CalibrationStatus,
    CalibrationTarget,
    CalibrationTruthDocument,
    MatchOutcome,
    lookup_confidence,
    lookup_prior,
    prior_key,
)


def counts(tp=1, fp=0, fn=0):
    return CalibrationCounts(true_positive=tp, false_positive=fp, false_negative=fn)


def metric(target=CalibrationTarget.BLOCK_KIND, key="heading", status=CalibrationStatus.UNDERPOWERED, c=None):
    c = c or counts()
    support = c.true_positive + c.false_positive + c.false_negative
    return CalibrationMetric(
        target=target,
        key=key,
        counts=c,
        precision=1.0 if c.false_positive == 0 and c.true_positive else 0.0,
        recall=1.0 if c.false_negative == 0 and c.true_positive else 0.0,
        f1=1.0 if c.false_positive == 0 and c.false_negative == 0 and c.true_positive else 0.0,
        support=support,
        calibrated_confidence=0.5,
        status=status,
        metadata={},
    )


def prior(**overrides):
    payload = dict(
        backend="mineru",
        backend_version=None,
        generated_from=["truth.json"],
        min_samples=2,
        smoothing_alpha=1.0,
        smoothing_beta=1.0,
        default_confidence=0.5,
        block_kind_priors=[metric()],
        entity_type_priors=[],
        relation_type_priors=[],
        calibration_key_priors=[],
        warnings=[],
        metadata={},
    )
    payload.update(overrides)
    return CalibrationPriorDocument(**payload)


class TestPriorEnums:
    def test_calibration_target_values_match_specification(self):
        assert [item.value for item in CalibrationTarget] == ["block_kind", "entity_type", "relation_type", "calibration_key"]

    def test_calibration_status_values_match_specification(self):
        assert [item.value for item in CalibrationStatus] == ["calibrated", "underpowered", "no_samples"]

    def test_match_outcome_values_match_specification(self):
        assert [item.value for item in MatchOutcome] == ["true_positive", "false_positive", "false_negative"]


class TestCalibrationCounts:
    def test_counts_accept_zero_and_positive_values(self):
        assert counts(0, 1, 2).false_negative == 2

    def test_counts_reject_negative_values(self):
        with pytest.raises(ValidationError):
            counts(-1, 0, 0)


class TestCalibrationMetric:
    def test_metric_accepts_valid_payload(self):
        assert metric().key == "heading"

    def test_metric_rejects_empty_key(self):
        with pytest.raises(ValidationError):
            metric(key="")

    def test_metric_rejects_scores_outside_unit_interval(self):
        with pytest.raises(ValidationError):
            CalibrationMetric(target=CalibrationTarget.BLOCK_KIND, key="heading", counts=counts(), precision=1.2, recall=1.0, f1=1.0, support=1, calibrated_confidence=0.5, status=CalibrationStatus.UNDERPOWERED, metadata={})

    def test_metric_status_no_samples_requires_zero_support(self):
        with pytest.raises(ValidationError):
            metric(status=CalibrationStatus.NO_SAMPLES, c=counts(1, 0, 0))

    def test_metric_status_underpowered_requires_positive_support_below_min_samples(self):
        assert metric(status=CalibrationStatus.UNDERPOWERED, c=counts(0, 1, 0)).support == 1

    def test_metric_status_calibrated_requires_support_at_least_min_samples(self):
        assert metric(status=CalibrationStatus.CALIBRATED, c=counts(2, 0, 0)).support == 2


class TestCalibrationPriorDocument:
    def test_minimal_prior_document_round_trip(self):
        data = prior().model_dump_json()
        assert CalibrationPriorDocument.model_validate_json(data).backend == "mineru"

    def test_prior_document_rejects_duplicate_metric_keys_within_same_list(self):
        with pytest.raises(ValidationError):
            prior(block_kind_priors=[metric(), metric()])

    def test_prior_document_rejects_invalid_default_confidence(self):
        with pytest.raises(ValidationError):
            prior(default_confidence=1.5)

    def test_json_schema_export_basic_shape(self):
        schema = CalibrationPriorDocument.model_json_schema()
        assert schema["title"] == "CalibrationPriorDocument"
        assert "backend" in schema["properties"]


class TestCalibrationTruthDocument:
    def test_truth_document_round_trip(self):
        truth = CalibrationTruthDocument(document_id="doc1", blocks=[{"id": "b1", "block_kind": "heading", "text": "Intro", "page_no": 1, "metadata": {}}], entities=[{"id": "e1", "entity_type": "section", "canonical_text": "Intro", "page_no": 1, "metadata": {}}], relations=[], metadata={})
        assert CalibrationTruthDocument.model_validate_json(truth.model_dump_json()).document_id == "doc1"

    def test_truth_document_rejects_duplicate_truth_entity_ids(self):
        with pytest.raises(ValidationError):
            CalibrationTruthDocument(document_id="doc1", blocks=[], entities=[{"id": "e1", "entity_type": "section", "canonical_text": "A", "page_no": 1, "metadata": {}}, {"id": "e1", "entity_type": "section", "canonical_text": "B", "page_no": 1, "metadata": {}}], relations=[], metadata={})

    def test_truth_document_rejects_duplicate_truth_relation_ids(self):
        with pytest.raises(ValidationError):
            CalibrationTruthDocument(document_id="doc1", blocks=[], entities=[{"id": "e1", "entity_type": "section", "canonical_text": "A", "page_no": 1, "metadata": {}}, {"id": "e2", "entity_type": "page_number", "canonical_text": "1", "page_no": 1, "metadata": {}}], relations=[{"id": "r1", "relation_type": "toc_points_to", "source_truth_id": "e1", "target_truth_id": "e2", "metadata": {}}, {"id": "r1", "relation_type": "toc_points_to", "source_truth_id": "e1", "target_truth_id": "e2", "metadata": {}}], metadata={})

    def test_truth_document_rejects_relation_with_unknown_source(self):
        with pytest.raises(ValidationError):
            CalibrationTruthDocument(document_id="doc1", blocks=[], entities=[{"id": "e1", "entity_type": "section", "canonical_text": "A", "page_no": 1, "metadata": {}}], relations=[{"id": "r1", "relation_type": "toc_points_to", "source_truth_id": "missing", "target_truth_id": "e1", "metadata": {}}], metadata={})

    def test_truth_document_rejects_relation_with_unknown_target(self):
        with pytest.raises(ValidationError):
            CalibrationTruthDocument(document_id="doc1", blocks=[], entities=[{"id": "e1", "entity_type": "section", "canonical_text": "A", "page_no": 1, "metadata": {}}], relations=[{"id": "r1", "relation_type": "toc_points_to", "source_truth_id": "e1", "target_truth_id": "missing", "metadata": {}}], metadata={})

    def test_truth_document_rejects_duplicate_truth_block_ids(self):
        with pytest.raises(ValidationError):
            CalibrationTruthDocument(document_id="doc1", blocks=[{"id": "b1", "block_kind": "heading", "text": "A", "page_no": 1, "metadata": {}}, {"id": "b1", "block_kind": "paragraph", "text": "B", "page_no": 1, "metadata": {}}], entities=[], relations=[], metadata={})


class TestPriorLookup:
    def test_prior_key_format(self):
        assert prior_key(CalibrationTarget.BLOCK_KIND, "heading") == "block_kind:heading"

    def test_lookup_prior_finds_existing_metric(self):
        assert lookup_prior(prior(), CalibrationTarget.BLOCK_KIND, "heading") is not None

    def test_lookup_confidence_returns_metric_confidence(self):
        assert lookup_confidence(prior(), CalibrationTarget.BLOCK_KIND, "heading") == 0.5

    def test_lookup_confidence_returns_default_for_missing_metric(self):
        assert lookup_confidence(prior(), CalibrationTarget.BLOCK_KIND, "paragraph") == 0.5
