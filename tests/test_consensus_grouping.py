from pdf2md.consensus.grouping import BlockCandidate, bbox_iou, group_document_candidates, group_page_candidates, normalise_text, token_overlap
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import BBox, BlockKind, ExtractionBlock, PageExtractionIR, PageSize


def box(x=0, y=0, origin="topleft"):
    if origin == "bottomleft":
        return BBox(l=x, t=y + 20, r=x + 100, b=y, coord_origin=origin)
    return BBox(l=x, t=y, r=x + 100, b=y + 20, coord_origin=origin)


def block(backend, idx, text="Hello world", kind=BlockKind.PARAGRAPH, page=1, order=0, bb=None):
    return ExtractionBlock(id=f"{backend}:doc-1:p{page}:b{idx}", backend=backend, page_no=page, kind=kind, bbox=bb or box(), order=order, text=text)


def cand(backend, idx, **kw):
    b = block(backend, idx, **kw)
    return BlockCandidate(backend=backend, page_no=b.page_no, block=b, page_size=PageSize(width=200, height=200), entity_ids=())


class TestConsensusTextUtilities:
    def test_normalise_text_lowercases_and_collapses_whitespace(self):
        assert normalise_text("  Hello\n WORLD  ") == "hello world"

    def test_token_overlap_exact_match_is_one(self):
        assert token_overlap("A B", "a b") == 1.0

    def test_token_overlap_disjoint_is_zero(self):
        assert token_overlap("alpha", "beta") == 0.0

    def test_bbox_iou_returns_none_when_missing_bbox(self):
        assert bbox_iou(None, box()) is None

    def test_bbox_iou_computes_overlap_for_same_origin(self):
        assert bbox_iou(box(), box()) == 1.0

    def test_bbox_iou_rejects_or_returns_none_for_mixed_origin(self):
        assert bbox_iou(box(origin="topleft"), box(origin="bottomleft")) is None


class TestCandidateGrouping:
    def test_groups_same_page_same_kind_same_text_across_backends(self):
        groups = group_page_candidates(page_no=1, candidates=[cand("mineru", 0), cand("paddleocr", 0)])
        assert [len(g.candidates) for g in groups] == [2]

    def test_groups_same_page_high_text_overlap_across_backends(self):
        groups = group_page_candidates(page_no=1, candidates=[cand("mineru", 0, text="alpha beta gamma"), cand("paddleocr", 0, text="alpha beta gamma delta")], text_threshold=0.7)
        assert len(groups[0].candidates) == 2

    def test_groups_compatible_paragraph_and_heading(self):
        groups = group_page_candidates(page_no=1, candidates=[cand("mineru", 0, kind=BlockKind.HEADING), cand("paddleocr", 0, kind=BlockKind.PARAGRAPH)])
        assert len(groups[0].candidates) == 2

    def test_groups_by_bbox_when_text_is_partial(self):
        groups = group_page_candidates(page_no=1, candidates=[cand("mineru", 0, text="first paragraph", bb=box()), cand("paddleocr", 0, text="first", bb=box(1, 1))])
        assert len(groups[0].candidates) == 2

    def test_does_not_group_candidates_from_different_pages(self):
        groups = group_page_candidates(page_no=1, candidates=[cand("mineru", 0, page=1), cand("paddleocr", 0, page=2)])
        assert len(groups) == 1

    def test_does_not_group_unrelated_low_overlap_blocks(self):
        groups = group_page_candidates(page_no=1, candidates=[cand("mineru", 0, text="alpha"), cand("paddleocr", 0, text="beta", bb=box(150, 150))])
        assert len(groups) == 2

    def test_does_not_group_two_different_blocks_from_same_backend(self):
        groups = group_page_candidates(page_no=1, candidates=[cand("mineru", 0), cand("mineru", 1)])
        assert len(groups) == 2

    def test_entity_ids_are_attached_to_block_candidates(self):
        b = block("mineru", 0)
        page = PageExtractionIR(document_id="doc-1", backend="mineru", page_no=1, page_size=PageSize(width=200, height=200), blocks=[b])
        entities = EntityProposalDocument.model_validate({"document_id":"doc-1","backend":"mineru","page_count":1,"entities":[{"id":"ent:mineru:doc-1:page_number:0","entity_type":"page_number","block_ids":[b.id],"confidence":0.9,"confidence_source":"calibrated","evidence":[{"kind":"block_text","source_block_id":b.id,"weight":1,"reason":"x"}]}],"relations":[]})
        groups = group_document_candidates(pages_by_backend={"mineru":[page]}, entities_by_backend={"mineru":entities})
        assert groups[0].candidates[0].entity_ids == ("ent:mineru:doc-1:page_number:0",)
