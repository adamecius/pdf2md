from pathlib import Path

from pdf2md.consensus.factory import ConsensusFactorySettings, build_consensus_ir
from pdf2md.consensus.io import load_consensus_inputs
from pdf2md.models.ir import ConflictKind, ConsensusIR, SelectionMode

ROOT = Path("tests/data/consensus_fixtures")

def build(name, backends=None):
    loaded = load_consensus_inputs(connector_root=ROOT/name, document_id="doc-1", backends=backends, priors_root=ROOT/name/"priors")
    return build_consensus_ir(document_id="doc-1", pages_by_backend=loaded.pages_by_backend, entities_by_backend=loaded.entities_by_backend, priors_by_backend=loaded.priors_by_backend, settings=ConsensusFactorySettings())

class TestConsensusFactory:
    def test_simple_agreement_builds_valid_consensus_ir(self):
        assert isinstance(build("simple_agreement").consensus, ConsensusIR)
    def test_consensus_pages_are_contiguous_from_one(self):
        c=build("simple_agreement").consensus
        assert [p.page_no for p in c.pages] == [1]
    def test_agreed_group_creates_agreed_consensus_block(self):
        assert build("simple_agreement").consensus.pages[0].blocks[0].selection_mode == SelectionMode.AGREED
    def test_single_source_group_creates_single_source_consensus_block(self):
        assert all(b.selection_mode == SelectionMode.SINGLE_SOURCE for b in build("single_source", ["deepseek"]).consensus.pages[0].blocks)
    def test_ambiguous_group_creates_unresolved_block_and_conflict(self):
        c=build("ambiguous_page_number").consensus
        assert c.pages[0].blocks[0].selection_mode == SelectionMode.UNRESOLVED and len(c.conflicts)==1
        assert c.conflicts[0].kind == ConflictKind.KIND_CONFLICT
    def test_conflict_ids_exist_in_top_level_conflicts(self):
        c=build("ambiguous_page_number").consensus
        assert c.pages[0].blocks[0].conflict_ids[0] == c.conflicts[0].id
    def test_candidate_ids_are_preserved_on_consensus_blocks(self):
        ids=build("simple_agreement").consensus.pages[0].blocks[0].candidate_ids
        assert "mineru:doc-1:p1:b0" in ids and "paddleocr:doc-1:p1:b0" in ids
    def test_backend_manifest_entries_are_created(self):
        assert [b.backend for b in build("simple_agreement").consensus.backends] == ["mineru","paddleocr"]
    def test_agreement_summary_counts_selection_modes(self):
        assert build("simple_agreement").consensus.agreement_summary["selection_counts"]["agreed"] == 2
    def test_missing_entities_file_warns_but_still_builds_consensus(self):
        loaded=load_consensus_inputs(connector_root=ROOT/"single_source", document_id="doc-1", backends=["deepseek"], priors_root=ROOT/"single_source"/"priors")
        result=build_consensus_ir(document_id="doc-1", pages_by_backend=loaded.pages_by_backend, entities_by_backend={}, priors_by_backend=loaded.priors_by_backend, settings=ConsensusFactorySettings())
        assert "entities_missing:deepseek" in result.warnings and result.consensus.page_count == 1
    def test_missing_prior_warns_and_uses_default(self):
        loaded=load_consensus_inputs(connector_root=ROOT/"single_source", document_id="doc-1", backends=["deepseek"], priors_root=None)
        result=build_consensus_ir(document_id="doc-1", pages_by_backend=loaded.pages_by_backend, entities_by_backend=loaded.entities_by_backend, priors_by_backend={}, settings=ConsensusFactorySettings())
        assert "prior_missing:deepseek" in result.warnings
    def test_consensus_ir_round_trips_through_pydantic(self):
        c=build("simple_agreement").consensus
        assert ConsensusIR.model_validate_json(c.model_dump_json()).document_id == "doc-1"

class TestConsensusReport:
    def test_report_contains_document_backend_and_conflict_summary(self):
        r=build("ambiguous_page_number").report
        assert r["document_id"] == "doc-1" and r["backend_count"] == 2 and r["conflict_count"] == 1
    def test_report_conflicts_match_consensus_conflicts(self):
        result=build("ambiguous_page_number")
        assert result.report["conflicts"][0]["id"] == result.consensus.conflicts[0].id
