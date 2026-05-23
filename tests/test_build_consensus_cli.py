import subprocess
from pathlib import Path

import pytest

from pdf2md.consensus.factory import ConsensusFactorySettings, build_consensus_ir
from pdf2md.consensus.io import load_consensus_inputs, write_consensus_outputs
from pdf2md.models.ir import ConsensusIR

ROOT = Path("tests/data/consensus_fixtures")
CLI = Path("tools/build_consensus.py")

class TestConsensusIO:
    def test_load_consensus_inputs_reads_pages_entities_and_priors(self):
        r=load_consensus_inputs(connector_root=ROOT/"simple_agreement", document_id="doc-1", backends=["mineru","paddleocr"], priors_root=ROOT/"simple_agreement"/"priors")
        assert set(r.pages_by_backend)=={"mineru","paddleocr"} and set(r.entities_by_backend)=={"mineru","paddleocr"} and set(r.priors_by_backend)=={"mineru","paddleocr"}
    def test_load_consensus_inputs_lenient_missing_prior_adds_warning(self):
        assert "prior_missing:deepseek" in load_consensus_inputs(connector_root=ROOT/"single_source", document_id="doc-1", backends=["deepseek"], priors_root=None).warnings
    def test_load_consensus_inputs_lenient_missing_entities_adds_warning(self, tmp_path):
        d=tmp_path/"root"/"b"/"pages"; d.mkdir(parents=True); (d/"page_0001.json").write_text((ROOT/"single_source/deepseek/pages/page_0001.json").read_text().replace('"deepseek"','"b"').replace('deepseek:doc-1','b:doc-1'))
        assert "entities_missing:b" in load_consensus_inputs(connector_root=tmp_path/"root", document_id="doc-1", backends=["b"]).warnings
    def test_load_consensus_inputs_strict_invalid_page_raises(self, tmp_path):
        d=tmp_path/"root"/"b"/"pages"; d.mkdir(parents=True); (d/"bad.json").write_text("{")
        with pytest.raises(Exception): load_consensus_inputs(connector_root=tmp_path/"root", document_id="doc-1", backends=["b"], strict=True)
    def test_write_consensus_outputs_writes_consensus_and_report(self, tmp_path):
        loaded=load_consensus_inputs(connector_root=ROOT/"single_source", document_id="doc-1", backends=["deepseek"], priors_root=ROOT/"single_source"/"priors")
        result=build_consensus_ir(document_id="doc-1", pages_by_backend=loaded.pages_by_backend, entities_by_backend=loaded.entities_by_backend, priors_by_backend=loaded.priors_by_backend, settings=ConsensusFactorySettings())
        write_consensus_outputs(result=result, out_dir=tmp_path)
        assert (tmp_path/"consensus_ir.json").exists() and (tmp_path/"reports/consensus_report.json").exists()

class TestBuildConsensusCLI:
    def test_cli_help_exits_zero(self):
        assert subprocess.run(["python", str(CLI), "--help"], text=True).returncode == 0
    def test_cli_writes_consensus_and_report_for_simple_agreement(self, tmp_path):
        assert subprocess.run(["python", str(CLI), "--connector-root", str(ROOT/"simple_agreement"), "--document-id", "doc-1", "--priors-root", str(ROOT/"simple_agreement/priors"), "--backends", "mineru,paddleocr", "--out-dir", str(tmp_path)]).returncode == 0
        assert (tmp_path/"consensus_ir.json").exists() and (tmp_path/"reports/consensus_report.json").exists()
    def test_cli_writes_conflict_for_ambiguous_fixture(self, tmp_path):
        subprocess.run(["python", str(CLI), "--connector-root", str(ROOT/"ambiguous_page_number"), "--document-id", "doc-1", "--priors-root", str(ROOT/"ambiguous_page_number/priors"), "--backends", "mineru,paddleocr", "--out-dir", str(tmp_path)], check=True)
        assert ConsensusIR.model_validate_json((tmp_path/"consensus_ir.json").read_text()).conflicts
    def test_cli_single_source_fixture_writes_single_source_block(self, tmp_path):
        subprocess.run(["python", str(CLI), "--connector-root", str(ROOT/"single_source"), "--document-id", "doc-1", "--priors-root", str(ROOT/"single_source/priors"), "--backends", "deepseek", "--out-dir", str(tmp_path)], check=True)
        assert ConsensusIR.model_validate_json((tmp_path/"consensus_ir.json").read_text()).pages[0].blocks[0].selection_mode == "single_source"
    def test_cli_missing_prior_root_still_succeeds_leniently(self, tmp_path):
        assert subprocess.run(["python", str(CLI), "--connector-root", str(ROOT/"single_source"), "--document-id", "doc-1", "--backends", "deepseek", "--out-dir", str(tmp_path)]).returncode == 0
    def test_cli_strict_mode_fails_on_invalid_input(self, tmp_path):
        d=tmp_path/"root"/"b"/"pages"; d.mkdir(parents=True); (d/"bad.json").write_text("{")
        assert subprocess.run(["python", str(CLI), "--connector-root", str(tmp_path/"root"), "--document-id", "doc-1", "--backends", "b", "--out-dir", str(tmp_path/"out"), "--strict"]).returncode == 1
    def test_written_consensus_validates_as_consensus_ir(self, tmp_path):
        subprocess.run(["python", str(CLI), "--connector-root", str(ROOT/"simple_agreement"), "--document-id", "doc-1", "--priors-root", str(ROOT/"simple_agreement/priors"), "--backends", "mineru,paddleocr", "--out-dir", str(tmp_path)], check=True)
        assert ConsensusIR.model_validate_json((tmp_path/"consensus_ir.json").read_text()).document_id == "doc-1"


# ---------------------------------------------------------------------------
# Plan 13 hardening tests
# ---------------------------------------------------------------------------

import json as _json

from pdf2md.consensus.reporting import (
    INSPECTION_STATUSES,
    build_consensus_report,
    build_consensus_summary,
)


class TestPlan13ReportHardening:
    def _result(self, name: str = "simple_agreement"):
        loaded = load_consensus_inputs(
            connector_root=ROOT / name,
            document_id="doc-1",
            backends=None,
            priors_root=ROOT / name / "priors",
        )
        result = build_consensus_ir(
            document_id="doc-1",
            pages_by_backend=loaded.pages_by_backend,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            settings=ConsensusFactorySettings(),
        )
        return result, loaded

    def test_report_contains_backend_contributions(self):
        result, _ = self._result("simple_agreement")
        contributions = result.report["backend_contributions"]
        assert set(contributions.keys()) >= {"mineru", "paddleocr"}
        for backend, detail in contributions.items():
            for field in (
                "accepted_blocks",
                "single_source_blocks",
                "fallback_blocks",
                "unresolved_blocks",
                "conflict_participations",
            ):
                assert field in detail

    def test_report_contains_confidence_summary(self):
        result, _ = self._result("simple_agreement")
        summary = result.report["confidence_summary"]
        assert summary["block_count"] >= 1
        assert summary["mean_agreement_score"] is not None
        assert 0.0 <= summary["min_agreement_score"] <= 1.0
        assert 0.0 <= summary["max_agreement_score"] <= 1.0
        assert summary["low_confidence_threshold"] == 0.5
        assert "low_confidence_blocks" in summary

    def test_report_contains_plan14_readiness(self):
        result, _ = self._result("simple_agreement")
        plan14 = result.report["plan14_readiness"]
        for field in (
            "consensus_block_count",
            "consensus_page_count",
            "consensus_conflict_count",
            "consensus_unresolved_conflict_count",
            "backends_with_priors_loaded",
            "backends_included",
            "low_confidence_blocks",
            "linkedstructure_handed_off_by",
        ):
            assert field in plan14
        assert plan14["linkedstructure_handed_off_by"] == "plan_14"
        assert plan14["backends_with_priors_loaded"] == sorted(["mineru", "paddleocr"])

    def test_report_includes_conflict_details_when_conflicts_present(self):
        result, _ = self._result("ambiguous_page_number")
        assert result.report["conflict_count"] >= 0
        for detail in result.report["conflict_details"]:
            for field in (
                "id",
                "kind",
                "page_no",
                "candidate_ids",
                "description",
                "resolution",
                "selected_candidate_id",
            ):
                assert field in detail

    def test_default_inspection_status_is_diagnostic_only(self):
        result, _ = self._result("simple_agreement")
        # Factory default omits inspection_status; reporting fills in diagnostic_only.
        assert result.report["inspection_status"] == "diagnostic_only"
        assert result.report["ground_truth_ref"] is None
        assert result.report["inspection_notes"] == []

    def test_build_consensus_report_accepts_all_inspection_statuses(self):
        result, _ = self._result("simple_agreement")
        for status in INSPECTION_STATUSES:
            r = build_consensus_report(
                consensus=result.consensus,
                warnings=[],
                backend_summary=result.report["backend_summary"],
                inspection_status=status,
            )
            assert r["inspection_status"] == status

    def test_build_consensus_report_rejects_unknown_inspection_status(self):
        result, _ = self._result("simple_agreement")
        with pytest.raises(ValueError):
            build_consensus_report(
                consensus=result.consensus,
                warnings=[],
                backend_summary=result.report["backend_summary"],
                inspection_status="totally_made_up",
            )

    def test_build_consensus_report_records_ground_truth_ref_and_notes(self):
        result, _ = self._result("simple_agreement")
        r = build_consensus_report(
            consensus=result.consensus,
            warnings=[],
            backend_summary=result.report["backend_summary"],
            inspection_status="appears_equivalent_to_best_backend",
            ground_truth_ref="groundtruth/corpus/latex/sample/truth.json",
            inspection_notes=["mineru and paddleocr agreed on the heading"],
        )
        assert r["ground_truth_ref"] == "groundtruth/corpus/latex/sample/truth.json"
        assert "mineru and paddleocr agreed on the heading" in r["inspection_notes"]


class TestPlan13IOHardening:
    def test_write_consensus_outputs_emits_summary_file(self, tmp_path):
        loaded = load_consensus_inputs(
            connector_root=ROOT / "simple_agreement",
            document_id="doc-1",
            backends=None,
            priors_root=ROOT / "simple_agreement" / "priors",
        )
        result = build_consensus_ir(
            document_id="doc-1",
            pages_by_backend=loaded.pages_by_backend,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            settings=ConsensusFactorySettings(),
        )
        write_consensus_outputs(result=result, out_dir=tmp_path)
        summary_path = tmp_path / "consensus_summary.txt"
        assert summary_path.exists()
        text = summary_path.read_text()
        assert "Plan 13" in text
        assert "Plan 14 readiness" in text
        assert "LinkedStructure cross-page semantic linking is deferred to Plan 14" in text

    def test_summary_renders_for_no_conflict_run(self, tmp_path):
        loaded = load_consensus_inputs(
            connector_root=ROOT / "single_source",
            document_id="doc-1",
            backends=None,
            priors_root=ROOT / "single_source" / "priors",
        )
        result = build_consensus_ir(
            document_id="doc-1",
            pages_by_backend=loaded.pages_by_backend,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            settings=ConsensusFactorySettings(),
        )
        text = build_consensus_summary(result.report)
        assert "selection counts:" in text
        assert "backend contributions:" in text
        assert "Plan 14 readiness:" in text


class TestPlan13CLI:
    def test_cli_accepts_inspection_status_and_writes_into_report(self, tmp_path):
        out_dir = tmp_path / "out"
        result = subprocess.run(
            [
                "python",
                str(CLI),
                "--connector-root",
                str(ROOT / "simple_agreement"),
                "--document-id",
                "doc-1",
                "--priors-root",
                str(ROOT / "simple_agreement" / "priors"),
                "--backends",
                "mineru,paddleocr",
                "--out-dir",
                str(out_dir),
                "--inspection-status",
                "appears_equivalent_to_best_backend",
                "--ground-truth",
                "tests/data/some/truth.json",
                "--inspection-note",
                "the agent ran a synthetic diagnostic",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report_payload = _json.loads((out_dir / "reports" / "consensus_report.json").read_text())
        assert report_payload["inspection_status"] == "appears_equivalent_to_best_backend"
        assert report_payload["ground_truth_ref"] == "tests/data/some/truth.json"
        assert "the agent ran a synthetic diagnostic" in report_payload["inspection_notes"]
        assert (out_dir / "consensus_summary.txt").is_file()

    def test_cli_rejects_unknown_inspection_status(self, tmp_path):
        rc = subprocess.run(
            [
                "python",
                str(CLI),
                "--connector-root",
                str(ROOT / "simple_agreement"),
                "--document-id",
                "doc-1",
                "--priors-root",
                str(ROOT / "simple_agreement" / "priors"),
                "--backends",
                "mineru,paddleocr",
                "--out-dir",
                str(tmp_path / "out"),
                "--inspection-status",
                "totally_made_up",
            ]
        ).returncode
        assert rc == 1

    def test_cli_default_inspection_status_is_diagnostic_only(self, tmp_path):
        out_dir = tmp_path / "out"
        subprocess.run(
            [
                "python",
                str(CLI),
                "--connector-root",
                str(ROOT / "simple_agreement"),
                "--document-id",
                "doc-1",
                "--priors-root",
                str(ROOT / "simple_agreement" / "priors"),
                "--backends",
                "mineru,paddleocr",
                "--out-dir",
                str(out_dir),
            ],
            check=True,
        )
        payload = _json.loads((out_dir / "reports" / "consensus_report.json").read_text())
        assert payload["inspection_status"] == "diagnostic_only"
        assert payload["ground_truth_ref"] is None
