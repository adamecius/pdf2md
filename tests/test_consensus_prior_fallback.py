"""Tests for the three-level prior fallback introduced by Plan 19.

The fallback chain implemented in ``pdf2md.consensus.io._resolve_prior_with_fallback``:

    1. user-calibrated prior at ``<priors_root>/<backend>.json``  → no warning
    2. factory prior from package data                            → ``prior_factory:<backend>``
    3. uninformative prior built at runtime                       → ``prior_uninformative:<backend>``

A4 also exercises ``build_consensus_ir`` end-to-end at each level so we
know the consensus pipeline produces a valid ConsensusIR with at least
one selected block at every prior level.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from pdf2md.consensus.factory import ConsensusFactorySettings, build_consensus_ir
from pdf2md.consensus.io import load_consensus_inputs
from pdf2md.models.ir import ConsensusIR
from pdf2md.models.priors import (
    CalibrationPriorDocument,
    CalibrationStatus,
    build_uninformative_prior,
)

FIXTURE_ROOT = Path("tests/data/consensus_fixtures/simple_agreement")


def _copy_connector_only(src: Path, dst: Path) -> None:
    """Copy mineru/ and paddleocr/ from a fixture into dst, dropping priors/."""

    for backend in ("mineru", "paddleocr"):
        shutil.copytree(src / backend, dst / backend)


# ---------------------------------------------------------------------------
# Task A3 — fallback chain behaviour at the IO layer
# ---------------------------------------------------------------------------


class TestUserPriorPath:
    def test_user_prior_on_disk_is_used_with_no_fallback_warning(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        priors_root = tmp_path / "priors"
        shutil.copytree(FIXTURE_ROOT / "priors", priors_root)

        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=["mineru", "paddleocr"],
            priors_root=priors_root,
        )

        assert set(loaded.priors_by_backend) == {"mineru", "paddleocr"}
        # No fallback warnings for either backend
        assert not any(w.startswith("prior_factory:") for w in loaded.warnings)
        assert not any(w.startswith("prior_uninformative:") for w in loaded.warnings)
        # Both priors loaded as full documents
        for backend, prior in loaded.priors_by_backend.items():
            assert isinstance(prior, CalibrationPriorDocument)
            assert prior.backend == backend


class TestFactoryPriorPath:
    def test_no_user_prior_but_factory_exists_uses_factory_with_warning(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)

        # No priors_root → factory is consulted next. paddleocr and mineru
        # both have factory priors shipped with the package.
        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=["mineru", "paddleocr"],
            priors_root=None,
        )

        assert "prior_factory:paddleocr" in loaded.warnings
        assert "prior_factory:mineru" in loaded.warnings
        assert "prior_uninformative:paddleocr" not in loaded.warnings
        for backend in ("paddleocr", "mineru"):
            prior = loaded.priors_by_backend[backend]
            assert prior.metadata.get("prior_type") == "factory"


class TestUninformativePath:
    def test_no_user_no_factory_uses_uninformative_with_warning(self, tmp_path):
        connector_root = tmp_path / "connector"
        # Set the backend name to one not shipped as a factory prior so
        # load_factory_prior() returns None.
        unknown_backend = "synthetic_test_backend"
        backend_src = FIXTURE_ROOT / "paddleocr"
        backend_dst = connector_root / unknown_backend
        shutil.copytree(backend_src, backend_dst)
        # Rewrite block backend refs inside the copied pages/entities so
        # PageExtractionIR validation matches the new backend name.
        for page_file in (backend_dst / "pages").glob("*.json"):
            payload = json.loads(page_file.read_text())
            payload["backend"] = unknown_backend
            for block in payload.get("blocks", []):
                block["backend"] = unknown_backend
                if "id" in block:
                    block["id"] = block["id"].replace("paddleocr", unknown_backend, 1)
            page_file.write_text(json.dumps(payload))
        entities_path = backend_dst / "entities.json"
        if entities_path.exists():
            ent_payload = json.loads(entities_path.read_text())
            ent_payload["backend"] = unknown_backend
            for ent in ent_payload.get("entities", []):
                if "id" in ent:
                    ent["id"] = ent["id"].replace("paddleocr", unknown_backend, 1)
                ent["block_ids"] = [bid.replace("paddleocr", unknown_backend, 1) for bid in ent.get("block_ids", [])]
            entities_path.write_text(json.dumps(ent_payload))

        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=[unknown_backend],
            priors_root=None,
        )

        assert f"prior_uninformative:{unknown_backend}" in loaded.warnings
        prior = loaded.priors_by_backend[unknown_backend]
        assert prior.metadata.get("prior_type") == "uninformative"
        # All metrics are uninformative
        assert all(
            m.status == CalibrationStatus.UNINFORMATIVE.value
            for m in prior.block_kind_priors
        )


class TestMixedFallback:
    def test_mixed_per_backend_levels(self, tmp_path):
        """One backend has a user prior, one falls to factory, one to uninformative."""

        connector_root = tmp_path / "connector"
        # paddleocr (will have user prior), mineru (will fall to factory),
        # synthetic_test_backend (will fall to uninformative).
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        unknown_backend = "synthetic_test_backend"
        unknown_src = connector_root / unknown_backend
        shutil.copytree(connector_root / "paddleocr", unknown_src)
        for page_file in (unknown_src / "pages").glob("*.json"):
            payload = json.loads(page_file.read_text())
            payload["backend"] = unknown_backend
            for block in payload.get("blocks", []):
                block["backend"] = unknown_backend
                if "id" in block:
                    block["id"] = block["id"].replace("paddleocr", unknown_backend, 1)
            page_file.write_text(json.dumps(payload))
        entities_path = unknown_src / "entities.json"
        if entities_path.exists():
            ent_payload = json.loads(entities_path.read_text())
            ent_payload["backend"] = unknown_backend
            for ent in ent_payload.get("entities", []):
                if "id" in ent:
                    ent["id"] = ent["id"].replace("paddleocr", unknown_backend, 1)
                ent["block_ids"] = [bid.replace("paddleocr", unknown_backend, 1) for bid in ent.get("block_ids", [])]
            entities_path.write_text(json.dumps(ent_payload))

        # Provide a user prior for paddleocr only.
        priors_root = tmp_path / "priors"
        priors_root.mkdir()
        shutil.copy(FIXTURE_ROOT / "priors" / "paddleocr.json", priors_root / "paddleocr.json")

        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=["paddleocr", "mineru", unknown_backend],
            priors_root=priors_root,
        )

        # paddleocr: user prior → no fallback warning
        assert "prior_factory:paddleocr" not in loaded.warnings
        assert "prior_uninformative:paddleocr" not in loaded.warnings
        # mineru: factory prior
        assert "prior_factory:mineru" in loaded.warnings
        # synthetic: uninformative
        assert f"prior_uninformative:{unknown_backend}" in loaded.warnings
        # All three priors populated
        assert set(loaded.priors_by_backend) == {"paddleocr", "mineru", unknown_backend}


class TestUserOverridesFactory:
    def test_user_prior_takes_precedence_over_factory(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        priors_root = tmp_path / "priors"
        shutil.copytree(FIXTURE_ROOT / "priors", priors_root)

        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=["paddleocr"],
            priors_root=priors_root,
        )
        prior = loaded.priors_by_backend["paddleocr"]
        # Fixture user priors don't carry prior_type=factory.
        assert prior.metadata.get("prior_type") != "factory"
        # No factory warning emitted when the user prior wins.
        assert "prior_factory:paddleocr" not in loaded.warnings


class TestUninformativeFallbackWhenFactoryReturnsNone:
    def test_factory_loader_returning_none_falls_to_uninformative(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)

        with patch("pdf2md.consensus.io.load_factory_prior", return_value=None):
            loaded = load_consensus_inputs(
                connector_root=connector_root,
                document_id="doc-1",
                backends=["paddleocr"],
                priors_root=None,
            )
        assert "prior_uninformative:paddleocr" in loaded.warnings
        assert "prior_factory:paddleocr" not in loaded.warnings
        prior = loaded.priors_by_backend["paddleocr"]
        assert prior.metadata.get("prior_type") == "uninformative"


# ---------------------------------------------------------------------------
# Task A4 — end-to-end consensus build at each prior level
# ---------------------------------------------------------------------------


def _build_at(loaded) -> ConsensusIR:
    return build_consensus_ir(
        document_id="doc-1",
        pages_by_backend=loaded.pages_by_backend,
        entities_by_backend=loaded.entities_by_backend,
        priors_by_backend=loaded.priors_by_backend,
        settings=ConsensusFactorySettings(),
    ).consensus


class TestEndToEndConsensusBuilds:
    def test_user_calibrated_priors_produce_valid_consensus_ir(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        priors_root = tmp_path / "priors"
        shutil.copytree(FIXTURE_ROOT / "priors", priors_root)
        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=["mineru", "paddleocr"],
            priors_root=priors_root,
        )
        cir = _build_at(loaded)
        assert isinstance(cir, ConsensusIR)
        assert cir.page_count >= 1
        # At least one block was selected.
        selected = sum(
            1
            for page in cir.pages
            for block in page.blocks
            if block.selection_mode is not None
        )
        assert selected >= 1

    def test_factory_priors_produce_valid_consensus_ir(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=["mineru", "paddleocr"],
            priors_root=None,
        )
        # confirm factory level was used
        assert "prior_factory:mineru" in loaded.warnings
        assert "prior_factory:paddleocr" in loaded.warnings
        cir = _build_at(loaded)
        assert isinstance(cir, ConsensusIR)
        selected = sum(1 for p in cir.pages for b in p.blocks if b.selection_mode is not None)
        assert selected >= 1

    def test_uninformative_priors_produce_valid_consensus_ir(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        with patch("pdf2md.consensus.io.load_factory_prior", return_value=None):
            loaded = load_consensus_inputs(
                connector_root=connector_root,
                document_id="doc-1",
                backends=["mineru", "paddleocr"],
                priors_root=None,
            )
        assert "prior_uninformative:mineru" in loaded.warnings
        assert "prior_uninformative:paddleocr" in loaded.warnings
        cir = _build_at(loaded)
        assert isinstance(cir, ConsensusIR)
        # Uninformative still leaves the score above the AGREED floor when two
        # backends agree perfectly, so at least one block must be selected.
        selected = sum(1 for p in cir.pages for b in p.blocks if b.selection_mode is not None)
        assert selected >= 1


class TestPriorByBackendNeverEmpty:
    def test_every_backend_with_pages_gets_a_prior_no_priors_root(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        loaded = load_consensus_inputs(
            connector_root=connector_root,
            document_id="doc-1",
            backends=["mineru", "paddleocr"],
            priors_root=None,
        )
        for backend in loaded.pages_by_backend:
            assert backend in loaded.priors_by_backend, f"missing prior for backend {backend}"

    def test_every_backend_with_pages_gets_a_prior_when_factory_missing(self, tmp_path):
        connector_root = tmp_path / "connector"
        _copy_connector_only(FIXTURE_ROOT, connector_root)
        with patch("pdf2md.consensus.io.load_factory_prior", return_value=None):
            loaded = load_consensus_inputs(
                connector_root=connector_root,
                document_id="doc-1",
                backends=["mineru", "paddleocr"],
                priors_root=None,
            )
        for backend in loaded.pages_by_backend:
            assert backend in loaded.priors_by_backend
