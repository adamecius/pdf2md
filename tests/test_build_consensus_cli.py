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
