"""Tests for the UNINFORMATIVE prior level introduced by Plan 19."""

from __future__ import annotations

import json

import pytest

from pdf2md.models.ir import BlockKind
from pdf2md.models.priors import (
    CalibrationCounts,
    CalibrationMetric,
    CalibrationPriorDocument,
    CalibrationStatus,
    CalibrationTarget,
    build_uninformative_prior,
    lookup_confidence,
)


def test_uninformative_status_exists_and_is_distinct_from_no_samples():
    assert CalibrationStatus.UNINFORMATIVE.value == "uninformative"
    assert CalibrationStatus.UNINFORMATIVE is not CalibrationStatus.NO_SAMPLES


def test_uninformative_metric_with_zero_support_validates():
    metric = CalibrationMetric(
        target=CalibrationTarget.BLOCK_KIND,
        key="paragraph",
        counts=CalibrationCounts(true_positive=0, false_positive=0, false_negative=0),
        precision=0.0,
        recall=0.0,
        f1=0.0,
        support=0,
        calibrated_confidence=0.5,
        status=CalibrationStatus.UNINFORMATIVE,
    )
    # _PriorBaseModel has use_enum_values=True so status is stored as the
    # underlying string after validation. Compare against the enum value.
    assert metric.status == CalibrationStatus.UNINFORMATIVE.value


def test_uninformative_metric_with_positive_support_rejected():
    with pytest.raises(ValueError, match="uninformative status requires zero support"):
        CalibrationMetric(
            target=CalibrationTarget.BLOCK_KIND,
            key="paragraph",
            counts=CalibrationCounts(true_positive=1, false_positive=0, false_negative=0),
            precision=1.0,
            recall=1.0,
            f1=1.0,
            support=1,
            calibrated_confidence=0.5,
            status=CalibrationStatus.UNINFORMATIVE,
        )


def test_build_uninformative_prior_emits_one_metric_per_block_kind():
    prior = build_uninformative_prior("paddleocr")
    assert prior.backend == "paddleocr"
    assert len(prior.block_kind_priors) == len(list(BlockKind))
    keys = {metric.key for metric in prior.block_kind_priors}
    assert keys == {bk.value for bk in BlockKind}


def test_build_uninformative_prior_metadata_and_warning():
    prior = build_uninformative_prior("mineru")
    assert prior.metadata.get("prior_type") == "uninformative"
    assert any("uninformative_prior" in w for w in prior.warnings)


def test_build_uninformative_prior_round_trips_through_pydantic():
    prior = build_uninformative_prior("deepseek")
    payload = prior.model_dump_json()
    reloaded = CalibrationPriorDocument.model_validate_json(payload)
    assert reloaded.backend == "deepseek"
    assert len(reloaded.block_kind_priors) == len(list(BlockKind))


def test_lookup_confidence_returns_default_for_every_block_kind():
    prior = build_uninformative_prior("paddleocr", default_confidence=0.42)
    for bk in BlockKind:
        assert lookup_confidence(prior, CalibrationTarget.BLOCK_KIND, bk.value) == 0.42


def test_lookup_confidence_returns_default_for_unknown_keys():
    prior = build_uninformative_prior("paddleocr", default_confidence=0.50)
    # Unknown block-kind keys fall back to prior.default_confidence via
    # lookup_confidence's None-metric path.
    assert lookup_confidence(prior, CalibrationTarget.BLOCK_KIND, "no_such_kind") == 0.50
    # Other target types have no metrics in the uninformative prior, so
    # they should also fall through to the default.
    assert lookup_confidence(prior, CalibrationTarget.ENTITY_TYPE, "section") == 0.50
    assert lookup_confidence(prior, CalibrationTarget.CALIBRATION_KEY, "anything") == 0.50


def test_build_uninformative_prior_honours_smoothing_overrides():
    prior = build_uninformative_prior(
        "paddleocr",
        default_confidence=0.6,
        min_samples=10,
        smoothing_alpha=2.0,
        smoothing_beta=3.0,
    )
    assert prior.default_confidence == 0.6
    assert prior.min_samples == 10
    assert prior.smoothing_alpha == 2.0
    assert prior.smoothing_beta == 3.0
    # all metrics inherit the default_confidence
    assert all(metric.calibrated_confidence == 0.6 for metric in prior.block_kind_priors)


def test_uninformative_metrics_have_zero_support_and_zero_metrics():
    prior = build_uninformative_prior("paddleocr")
    for metric in prior.block_kind_priors:
        assert metric.support == 0
        assert metric.precision == 0.0
        assert metric.recall == 0.0
        assert metric.f1 == 0.0
        assert metric.counts.true_positive == 0
        assert metric.counts.false_positive == 0
        assert metric.counts.false_negative == 0


def test_round_trip_through_disk_preserves_uninformative_status(tmp_path):
    prior = build_uninformative_prior("paddleocr")
    path = tmp_path / "paddleocr.json"
    path.write_text(prior.model_dump_json(), encoding="utf-8")
    raw = json.loads(path.read_text(encoding="utf-8"))
    # On disk every block-kind metric should carry the new status string.
    statuses = {m["status"] for m in raw["block_kind_priors"]}
    assert statuses == {"uninformative"}
    # And the document still validates.
    CalibrationPriorDocument.model_validate(raw)


# ---------------------------------------------------------------------------
# Task A5 — --from-scratch flag in calibrate_priors.py
# ---------------------------------------------------------------------------


def test_calibrate_priors_has_from_scratch_flag_in_help():
    """The --from-scratch flag is documented in the CLI help."""

    import subprocess

    out = subprocess.run(
        ["python", "tools/calibrate_priors.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    combined = (out.stdout or "") + (out.stderr or "")
    assert "--from-scratch" in combined
    assert "uninformative baseline" in combined or "factory priors" in combined


def test_calibrate_priors_from_scratch_stamps_calibration_mode(tmp_path):
    """--from-scratch sets calibration_mode=from_scratch in the report and
    in each per-backend prior file; the default is "incremental"."""

    import subprocess

    # Build a minimal calibration corpus with one doc that has a truth
    # and an empty paddleocr predictions dir so the calibrator runs end-
    # to-end and writes its outputs.
    corpus = tmp_path / "corpus"
    doc = corpus / "smoke_doc"
    doc.mkdir(parents=True)
    truth = {
        "schema_name": "pdf2md.CalibrationTruthDocument",
        "schema_version": "1.0.0",
        "document_id": "smoke_doc",
        "blocks": [
            {
                "id": "t1",
                "block_kind": "paragraph",
                "page_no": 1,
                "text": "hello",
                "metadata": {},
            }
        ],
        "entities": [],
        "relations": [],
        "metadata": {},
    }
    (doc / "truth.json").write_text(json.dumps(truth), encoding="utf-8")

    pages_dir = doc / "paddleocr" / "pages"
    pages_dir.mkdir(parents=True)
    page = {
        "schema_name": "pdf2md.PageExtractionIR",
        "schema_version": "1.0.0",
        "document_id": "smoke_doc",
        "backend": "paddleocr",
        "page_no": 1,
        "page_size": {"width": 100, "height": 100},
        "blocks": [
            {
                "id": "paddleocr:smoke_doc:p1:b0",
                "backend": "paddleocr",
                "page_no": 1,
                "kind": "paragraph",
                "bbox": {"l": 0, "t": 0, "r": 10, "b": 10, "coord_origin": "topleft"},
                "order": 0,
                "text": "hello",
                "confidence": 0.9,
                "metadata": {},
            }
        ],
        "metadata": {},
    }
    (pages_dir / "page_0001.json").write_text(json.dumps(page), encoding="utf-8")
    (doc / "paddleocr" / "entities.json").write_text(
        json.dumps(
            {
                "schema_name": "pdf2md.EntityProposalDocument",
                "schema_version": "1.0.0",
                "document_id": "smoke_doc",
                "backend": "paddleocr",
                "page_count": 1,
                "entities": [],
                "relations": [],
            }
        ),
        encoding="utf-8",
    )

    out_dir_default = tmp_path / "out_default"
    cp = subprocess.run(
        [
            "python",
            "tools/calibrate_priors.py",
            "--root",
            str(corpus),
            "--out-dir",
            str(out_dir_default),
            "--backends",
            "paddleocr",
            "--min-samples",
            "1",
            "--skip-vocabulary-gate",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr
    report = json.loads((out_dir_default / "reports" / "calibration_report.json").read_text())
    assert report.get("calibration_mode") == "incremental"
    paddle_prior = json.loads((out_dir_default / "priors" / "paddleocr.json").read_text())
    assert paddle_prior["metadata"].get("calibration_mode") == "incremental"

    out_dir_scratch = tmp_path / "out_scratch"
    cp = subprocess.run(
        [
            "python",
            "tools/calibrate_priors.py",
            "--root",
            str(corpus),
            "--out-dir",
            str(out_dir_scratch),
            "--backends",
            "paddleocr",
            "--min-samples",
            "1",
            "--skip-vocabulary-gate",
            "--from-scratch",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr
    report = json.loads((out_dir_scratch / "reports" / "calibration_report.json").read_text())
    assert report.get("calibration_mode") == "from_scratch"
    paddle_prior = json.loads((out_dir_scratch / "priors" / "paddleocr.json").read_text())
    assert paddle_prior["metadata"].get("calibration_mode") == "from_scratch"
