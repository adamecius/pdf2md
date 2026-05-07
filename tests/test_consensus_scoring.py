from pdf2md.consensus.grouping import BlockCandidate, CandidateGroup
from pdf2md.consensus.scoring import ConsensusScoringSettings, infer_block_kind_from_entities, score_candidate_group
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import BBox, BlockKind, ExtractionBlock, PageSize, SelectionMode
from pdf2md.models.priors import CalibrationPriorDocument


def metric(target, key, confidence):
    return {"target":target,"key":key,"counts":{"true_positive":2,"false_positive":0,"false_negative":0},"precision":1,"recall":1,"f1":1,"support":2,"calibrated_confidence":confidence,"status":"calibrated"}

def prior(backend="mineru", blocks=None, ents=None, keys=None, default=0.5):
    return CalibrationPriorDocument.model_validate({"backend":backend,"min_samples":1,"smoothing_alpha":1,"smoothing_beta":1,"default_confidence":default,"block_kind_priors":[metric("block_kind",k,v) for k,v in (blocks or {}).items()],"entity_type_priors":[metric("entity_type",k,v) for k,v in (ents or {}).items()],"relation_type_priors":[],"calibration_key_priors":[metric("calibration_key",k,v) for k,v in (keys or {}).items()]})

def block(backend="mineru", idx=0, text="1", kind=BlockKind.PARAGRAPH, order=0, x=0):
    return ExtractionBlock(id=f"{backend}:doc-1:p1:b{idx}", backend=backend, page_no=1, kind=kind, bbox=BBox(l=x,t=0,r=x+10,b=10,coord_origin="topleft"), order=order, text=text)

def candidate(backend="mineru", idx=0, **kw):
    b=block(backend, idx, **kw)
    return BlockCandidate(backend=backend, page_no=1, block=b, page_size=PageSize(width=100,height=100), entity_ids=())

def entity_doc(candidate, typ="page_number", key="page_number_key"):
    e={"id":f"ent:{candidate.backend}:doc-1:{typ}:0","entity_type":typ,"block_ids":[candidate.block.id],"confidence":0.9,"confidence_source":"calibrated","evidence":[{"kind":"block_text","source_block_id":candidate.block.id,"weight":1,"reason":"x"}],"calibration_key":key}
    return EntityProposalDocument.model_validate({"document_id":"doc-1","backend":candidate.backend,"page_count":1,"entities":[e],"relations":[]})

def group(*cands):
    return CandidateGroup(id="grp:p1:0", page_no=1, candidates=tuple(cands), reason="test", metadata={})

class TestPriorLookupScoring:
    def test_missing_prior_uses_default_confidence(self):
        s=score_candidate_group(group=group(candidate()), priors_by_backend={}, entities_by_backend={})
        assert s.candidate_scores[0].backend_prior == 0.5
    def test_block_kind_prior_contributes_to_score(self):
        c=candidate(kind=BlockKind.HEADING)
        s=score_candidate_group(group=group(c), priors_by_backend={"mineru":prior(blocks={"heading":0.9})}, entities_by_backend={})
        assert s.candidate_scores[0].backend_prior == 0.9
    def test_entity_type_prior_contributes_to_score(self):
        c=candidate(); ed=entity_doc(c, "page_number")
        s=score_candidate_group(group=group(BlockCandidate(**{**c.__dict__, "entity_ids":(ed.entities[0].id,)})), priors_by_backend={"mineru":prior(ents={"page_number":0.8})}, entities_by_backend={"mineru":ed})
        assert s.candidate_scores[0].entity_prior == 0.8
    def test_calibration_key_prior_can_raise_entity_prior(self):
        c=candidate(); ed=entity_doc(c, "page_number", "pn_key")
        cc=BlockCandidate(c.backend,c.page_no,c.block,c.page_size,(ed.entities[0].id,))
        s=score_candidate_group(group=group(cc), priors_by_backend={"mineru":prior(ents={"page_number":0.6}, keys={"pn_key":0.95})}, entities_by_backend={"mineru":ed})
        assert s.candidate_scores[0].entity_prior == 0.95

class TestEntityKindInference:
    def test_page_number_entity_can_infer_page_number_block_kind(self):
        c=candidate(); ed=entity_doc(c,"page_number"); cc=BlockCandidate(c.backend,c.page_no,c.block,c.page_size,(ed.entities[0].id,))
        assert infer_block_kind_from_entities(candidate=cc, entity_document=ed, prior=prior(blocks={"paragraph":0.5}, ents={"page_number":0.8}), default_confidence=0.5)[0] == BlockKind.PAGE_NUMBER
    def test_footnote_entity_can_infer_footnote_block_kind(self):
        c=candidate(); ed=entity_doc(c,"footnote"); cc=BlockCandidate(c.backend,c.page_no,c.block,c.page_size,(ed.entities[0].id,))
        assert infer_block_kind_from_entities(candidate=cc, entity_document=ed, prior=prior(blocks={"paragraph":0.5}, ents={"footnote":0.8}), default_confidence=0.5)[0] == BlockKind.FOOTNOTE
    def test_small_prior_margin_does_not_rewrite_kind(self):
        c=candidate(); ed=entity_doc(c,"page_number"); cc=BlockCandidate(c.backend,c.page_no,c.block,c.page_size,(ed.entities[0].id,))
        assert infer_block_kind_from_entities(candidate=cc, entity_document=ed, prior=prior(blocks={"paragraph":0.72}, ents={"page_number":0.8}), default_confidence=0.5)[0] == BlockKind.PARAGRAPH
    def test_kind_rewrite_metadata_records_raw_kind_and_entity_type(self):
        c=candidate(); ed=entity_doc(c,"page_number"); cc=BlockCandidate(c.backend,c.page_no,c.block,c.page_size,(ed.entities[0].id,))
        metadata=infer_block_kind_from_entities(candidate=cc, entity_document=ed, prior=prior(blocks={"paragraph":0.5}, ents={"page_number":0.8}), default_confidence=0.5)[2]
        assert metadata["kind_source"] == "entity_prior" and metadata["raw_block_kind"] == "paragraph"

class TestCandidateGroupScoring:
    def test_single_source_group_scores_as_single_source(self):
        assert score_candidate_group(group=group(candidate()), priors_by_backend={}, entities_by_backend={}).selection_mode == SelectionMode.SINGLE_SOURCE
    def test_two_strong_candidates_score_as_agreed(self):
        c1,c2=candidate("mineru",0,text="hello"),candidate("paddleocr",0,text="hello")
        s=score_candidate_group(group=group(c1,c2), priors_by_backend={"mineru":prior("mineru"),"paddleocr":prior("paddleocr")}, entities_by_backend={}, settings=ConsensusScoringSettings(unresolved_margin=0.0))
        assert s.selection_mode == SelectionMode.AGREED
    def test_close_top_scores_become_unresolved(self):
        c1,c2=candidate("mineru",0, text="1", kind=BlockKind.PAGE_NUMBER),candidate("paddleocr",0, text="1", kind=BlockKind.FOOTNOTE)
        assert score_candidate_group(group=group(c1,c2), priors_by_backend={}, entities_by_backend={}, settings=ConsensusScoringSettings(unresolved_margin=0.2)).selection_mode == SelectionMode.UNRESOLVED
    def test_low_score_without_close_competitor_becomes_fallback(self):
        c1,c2=candidate("mineru",0,text="alpha",x=0),candidate("paddleocr",0,text="beta",x=50)
        s=score_candidate_group(group=group(c1,c2), priors_by_backend={"mineru":prior("mineru",default=0.1),"paddleocr":prior("paddleocr",default=0.0)}, entities_by_backend={}, settings=ConsensusScoringSettings(min_agreement_score=0.95, unresolved_margin=0.01))
        assert s.selection_mode == SelectionMode.FALLBACK
    def test_scoring_is_deterministic_for_same_inputs(self):
        c1,c2=candidate("mineru",0),candidate("paddleocr",0)
        a=score_candidate_group(group=group(c1,c2), priors_by_backend={}, entities_by_backend={}).candidate_scores
        b=score_candidate_group(group=group(c1,c2), priors_by_backend={}, entities_by_backend={}).candidate_scores
        assert [x.score for x in a] == [x.score for x in b]
