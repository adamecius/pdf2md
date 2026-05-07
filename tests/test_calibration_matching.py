from pathlib import Path

from pdf2md.calibration.io import CalibrationDocumentInput, load_calibration_document
from pdf2md.calibration.matching import match_blocks, match_entities, match_relations, normalise_text, token_overlap
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import PageExtractionIR
from pdf2md.models.priors import CalibrationTarget, CalibrationTruthDocument, MatchOutcome

FIX = Path("tests/data/calibration_fixtures/mixed_predictions")


def load(backend="mineru"):
    return load_calibration_document(item=CalibrationDocumentInput("mixed", FIX / "truth.json", {backend: FIX / backend}))


def page_with_blocks(blocks):
    return PageExtractionIR(document_id="doc1", backend="mineru", backend_version="test", page_no=1, page_size={"width": 600, "height": 800}, blocks=blocks, metadata={})


def block(i, text="Introduction", kind="heading", order=None):
    return {"id": f"mineru:doc1:p1:b{i}", "backend": "mineru", "page_no": 1, "kind": kind, "bbox": None, "order": i if order is None else order, "text": text, "confidence": 0.8, "spans": None, "raw_ref": None, "metadata": {}}


def truth_with(blocks=None, entities=None, relations=None):
    return CalibrationTruthDocument(document_id="doc1", blocks=blocks or [], entities=entities or [], relations=relations or [], metadata={})


def entity_doc(entities, relations=None):
    return EntityProposalDocument(document_id="doc1", backend="mineru", backend_version="test", page_count=1, entities=entities, relations=relations or [], warnings=[], metadata={})


def evidence():
    return [{"kind": "block_text", "page_no": 1, "source_block_id": None, "raw_ref": None, "text": "evidence", "bbox": None, "weight": 1.0, "reason": "test", "metadata": {}}]


def entity(i, typ="section", text="Introduction", page_no=1, key=None, metadata=None):
    return {"id": f"ent:mineru:doc1:{typ}:{i}", "entity_type": typ, "subtype": None, "canonical_text": text, "page_no": page_no, "block_ids": [], "confidence": 0.8, "confidence_source": "heuristic", "evidence": evidence(), "calibration_key": key, "metadata": metadata or {}}


def relation(i, source, target, typ="caption_of"):
    return {"id": f"rel:mineru:doc1:{i}", "relation_type": typ, "source_entity_id": source, "target_entity_id": target, "confidence": 0.8, "confidence_source": "heuristic", "evidence": evidence(), "metadata": {}}


class TestTextNormalisation:
    def test_normalise_text_lowercases_and_collapses_whitespace(self):
        assert normalise_text("  Figure  1: SAMPLE! ") == "figure 1 sample"

    def test_token_overlap_exact_match_is_one(self):
        assert token_overlap("Sample text", "sample text") == 1.0

    def test_token_overlap_disjoint_is_zero(self):
        assert token_overlap("alpha", "beta") == 0.0

    def test_token_overlap_partial_match_is_fractional(self):
        assert token_overlap("sample paragraph", "sample table") == 1 / 3


class TestBlockMatching:
    def test_matching_block_kind_true_positive(self):
        result = load("mineru")
        records = match_blocks(backend="mineru", pages=result.pages_by_backend["mineru"], truth=result.truth)
        assert any(r.key == "heading" and r.outcome == MatchOutcome.TRUE_POSITIVE for r in records)

    def test_unmatched_prediction_block_is_false_positive(self):
        result = load("paddleocr")
        records = match_blocks(backend="paddleocr", pages=result.pages_by_backend["paddleocr"], truth=result.truth)
        assert any(r.key == "table" and r.outcome == MatchOutcome.FALSE_POSITIVE for r in records)

    def test_unmatched_truth_block_is_false_negative(self):
        result = load("paddleocr")
        records = match_blocks(backend="paddleocr", pages=result.pages_by_backend["paddleocr"], truth=result.truth)
        assert any(r.key == "paragraph" and r.outcome == MatchOutcome.FALSE_NEGATIVE for r in records)

    def test_same_truth_block_not_matched_twice(self):
        truth = truth_with(blocks=[{"id": "tb1", "block_kind": "heading", "text": "Introduction", "page_no": 1, "metadata": {}}])
        records = match_blocks(backend="mineru", pages=[page_with_blocks([block(1), block(2)])], truth=truth)
        assert sum(r.outcome == MatchOutcome.TRUE_POSITIVE for r in records) == 1
        assert sum(r.outcome == MatchOutcome.FALSE_POSITIVE for r in records) == 1


class TestEntityMatching:
    def test_matching_section_entity_true_positive(self):
        result = load("mineru")
        records = match_entities(backend="mineru", predictions=result.entities_by_backend["mineru"], truth=result.truth)
        assert any(r.key == "section" and r.outcome == MatchOutcome.TRUE_POSITIVE for r in records)

    def test_matching_page_number_requires_same_page(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "page_number", "canonical_text": "1", "page_no": 2, "metadata": {}}])
        records = match_entities(backend="mineru", predictions=entity_doc([entity(1, "page_number", "1", page_no=1)]), truth=truth)
        assert {r.outcome for r in records} == {MatchOutcome.FALSE_POSITIVE, MatchOutcome.FALSE_NEGATIVE}


    def test_matching_page_number_requires_exact_text(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "page_number", "canonical_text": "1", "page_no": 1, "metadata": {}}])
        records = match_entities(backend="mineru", predictions=entity_doc([entity(1, "page_number", "1 of 2", page_no=1)]), truth=truth)
        assert {r.outcome for r in records} == {MatchOutcome.FALSE_POSITIVE, MatchOutcome.FALSE_NEGATIVE}

    def test_matching_caption_can_use_caption_number_metadata(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "caption", "canonical_text": "ignored", "page_no": 1, "metadata": {"caption_number": "1", "caption_kind": "figure"}}])
        records = match_entities(backend="mineru", predictions=entity_doc([entity(1, "caption", "different", metadata={"caption_number": "1", "caption_kind": "figure"})]), truth=truth)
        assert any(r.outcome == MatchOutcome.TRUE_POSITIVE for r in records)

    def test_matching_equation_can_use_equation_number_metadata(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "equation", "canonical_text": "x", "page_no": 1, "metadata": {"equation_number": "7"}}])
        records = match_entities(backend="mineru", predictions=entity_doc([entity(1, "equation", "y", metadata={"equation_number": "7"})]), truth=truth)
        assert any(r.outcome == MatchOutcome.TRUE_POSITIVE for r in records)

    def test_unmatched_entity_prediction_is_false_positive(self):
        records = match_entities(backend="mineru", predictions=entity_doc([entity(1, "section", "Other")]), truth=truth_with())
        assert records[0].outcome == MatchOutcome.FALSE_POSITIVE

    def test_unmatched_truth_entity_is_false_negative(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "section", "canonical_text": "Intro", "page_no": 1, "metadata": {}}])
        records = match_entities(backend="mineru", predictions=entity_doc([]), truth=truth)
        assert records[0].outcome == MatchOutcome.FALSE_NEGATIVE

    def test_entity_with_calibration_key_emits_detector_record(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "section", "canonical_text": "Introduction", "page_no": 1, "metadata": {}}])
        records = match_entities(backend="mineru", predictions=entity_doc([entity(1, key="mineru:section:detector")]), truth=truth)
        assert any(r.target == CalibrationTarget.CALIBRATION_KEY and r.key == "mineru:section:detector" for r in records)


class TestRelationMatching:
    def test_matching_caption_of_relation_true_positive_when_endpoints_match(self):
        result = load("mineru")
        records = match_relations(backend="mineru", predictions=result.entities_by_backend["mineru"], truth=result.truth)
        assert any(r.key == "caption_of" and r.outcome == MatchOutcome.TRUE_POSITIVE for r in records)

    def test_unmatched_relation_prediction_is_false_positive(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "figure", "canonical_text": "Figure 1", "page_no": 1, "metadata": {}}])
        doc = entity_doc([entity(1, "figure", "Figure 1"), entity(2, "footnote", "noise")], [relation(1, "ent:mineru:doc1:footnote:2", "ent:mineru:doc1:figure:1")])
        records = match_relations(backend="mineru", predictions=doc, truth=truth)
        assert records[0].outcome == MatchOutcome.FALSE_POSITIVE

    def test_unmatched_truth_relation_is_false_negative(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "caption", "canonical_text": "Caption", "page_no": 1, "metadata": {}}, {"id": "te2", "entity_type": "figure", "canonical_text": "Figure", "page_no": 1, "metadata": {}}], relations=[{"id": "tr1", "relation_type": "caption_of", "source_truth_id": "te1", "target_truth_id": "te2", "metadata": {}}])
        records = match_relations(backend="mineru", predictions=entity_doc([]), truth=truth)
        assert records[0].outcome == MatchOutcome.FALSE_NEGATIVE

    def test_relation_matching_without_entity_matches_warns_or_marks_unmatched(self):
        truth = truth_with(entities=[{"id": "te1", "entity_type": "figure", "canonical_text": "Figure", "page_no": 1, "metadata": {}}])
        doc = entity_doc([entity(1, "figure", "Different"), entity(2, "footnote", "noise")], [relation(1, "ent:mineru:doc1:footnote:2", "ent:mineru:doc1:figure:1")])
        records = match_relations(backend="mineru", predictions=doc, truth=truth)
        assert records[0].metadata.get("warning") == "relation_matching_without_entity_matches"
