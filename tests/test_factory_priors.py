"""Tests for the factory-prior layer introduced by Plan 19."""

from __future__ import annotations

import json
from importlib import resources

import pytest

from pdf2md.models.priors import (
    CalibrationPriorDocument,
    CalibrationStatus,
    build_uninformative_prior,
    load_factory_prior,
)


_FACTORY_BACKENDS = ("paddleocr", "deepseek", "mineru")


@pytest.mark.parametrize("backend", _FACTORY_BACKENDS)
def test_factory_prior_file_is_present_in_package_data(backend):
    """Every backend named in the plan has a packaged JSON file."""

    ref = resources.files("pdf2md.data.factory_priors").joinpath(f"{backend}.json")
    assert ref.is_file()


@pytest.mark.parametrize("backend", _FACTORY_BACKENDS)
def test_factory_prior_validates_against_pydantic_schema(backend):
    """The shipped JSON validates as a CalibrationPriorDocument."""

    prior = load_factory_prior(backend)
    assert isinstance(prior, CalibrationPriorDocument)
    assert prior.backend == backend


@pytest.mark.parametrize("backend", _FACTORY_BACKENDS)
def test_factory_prior_metadata_prior_type_is_factory(backend):
    """Factory priors must declare prior_type='factory' so the consensus io
    can distinguish them from calibrated and uninformative priors."""

    prior = load_factory_prior(backend)
    assert prior is not None
    assert prior.metadata.get("prior_type") == "factory"


def test_load_factory_prior_returns_none_for_unknown_backend():
    """Unknown backends fall through to None so callers can fall back to
    the uninformative prior."""

    assert load_factory_prior("not_a_real_backend") is None


def test_load_factory_prior_returns_none_for_corrupt_json(tmp_path, monkeypatch):
    """Loader must swallow JSON / validation errors and return None so
    the consensus pipeline can still fall back."""

    # Drop a corrupt file inside the live package-data dir and confirm
    # the loader returns None instead of raising.
    pkg_dir = resources.files("pdf2md.data.factory_priors")
    corrupt = pkg_dir.joinpath("_test_corrupt.json")
    try:
        with corrupt.open("w") as f:
            f.write("not json at all{")
        assert load_factory_prior("_test_corrupt") is None
    finally:
        try:
            corrupt.unlink()
        except Exception:
            pass


def test_factory_paddleocr_carries_real_calibration_data():
    """The paddleocr factory prior comes from a real calibration run, so
    it should have positive support on at least one block kind."""

    prior = load_factory_prior("paddleocr")
    assert prior is not None
    total_support = sum(m.support for m in prior.block_kind_priors)
    assert total_support > 0, "expected real calibrated paddleocr priors to have support"


def test_factory_mineru_placeholder_has_uninformative_statuses():
    """The mineru factory prior is a placeholder until the benchmark run
    completes — every block-kind metric should be UNINFORMATIVE with zero
    support."""

    prior = load_factory_prior("mineru")
    assert prior is not None
    assert prior.metadata.get("source") == "uninformative_placeholder"
    for metric in prior.block_kind_priors:
        assert metric.support == 0
        assert metric.status == CalibrationStatus.UNINFORMATIVE.value


def test_uninformative_helper_produces_distinct_prior_type():
    """The uninformative helper itself must carry prior_type=uninformative
    so it is distinguishable from a factory prior that happens to be all
    uninformative."""

    prior = build_uninformative_prior("paddleocr")
    assert prior.metadata.get("prior_type") == "uninformative"


def test_factory_paddleocr_json_round_trip(tmp_path):
    """A copy of the shipped JSON re-validates."""

    ref = resources.files("pdf2md.data.factory_priors").joinpath("paddleocr.json")
    payload = json.loads(ref.read_text(encoding="utf-8"))
    CalibrationPriorDocument.model_validate(payload)
