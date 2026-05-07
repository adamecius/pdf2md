import json
from pathlib import Path

import pytest

from pdf2md.connectors.common import BackendConnectorConfig, connect_raw_dir, markdown_to_pages, recognize_entities, write_connector_result
from pdf2md.models.entities import EntityProposalDocument, EntityType, RelationType
from pdf2md.models.ir import BlockKind, PageExtractionIR

CFG = BackendConnectorConfig("mineru", None, ("output.md",), ("manifest.json",))


def pages(text):
    warnings=[]
    return markdown_to_pages(text, backend="mineru", backend_version=None, document_id="doc", raw_ref="output.md", warnings=warnings)


def ents(text):
    warnings=[]
    return recognize_entities(pages(text), backend="mineru", backend_version=None, document_id="doc", warnings=warnings)


class TestMarkdownPageParsing:
    def test_single_page_markdown_builds_one_page_ir(self): assert len(pages("hello")) == 1
    def test_page_split_marker_builds_multiple_page_irs(self): assert len(pages("a\n\n<--- Page Split --->\n\nb")) == 2
    def test_form_feed_builds_multiple_page_irs(self): assert len(pages("a\fb")) == 2
    def test_empty_markdown_builds_no_pages_and_warning(self):
        w=[]; assert markdown_to_pages("  ", backend="mineru", backend_version=None, document_id="doc", raw_ref=None, warnings=w) == [] and "raw_text_missing" in w
    def test_block_order_is_monotonic_per_page(self): assert [b.order for b in pages("a\n\nb")[0].blocks] == [0,1]
    def test_page_numbers_are_one_indexed(self): assert [p.page_no for p in pages("a\f b")] == [1,2]


class TestBlockClassification:
    def test_markdown_heading_maps_to_heading_block(self): assert pages("# H")[0].blocks[0].kind == BlockKind.HEADING
    def test_display_math_maps_to_formula_block(self): assert pages("\\[x\\]")[0].blocks[0].kind == BlockKind.FORMULA
    def test_html_table_maps_to_table_block(self): assert pages("<table></table>")[0].blocks[0].kind == BlockKind.TABLE
    def test_markdown_image_maps_to_figure_block(self): assert pages("![x](y)")[0].blocks[0].kind == BlockKind.FIGURE
    def test_figure_caption_maps_to_caption_block(self): assert pages("Fig. 2. x")[0].blocks[0].kind == BlockKind.CAPTION
    def test_table_caption_maps_to_caption_block(self): assert pages("Table 2. x")[0].blocks[0].kind == BlockKind.CAPTION
    def test_list_item_maps_to_list_item_block(self): assert pages("1. item")[0].blocks[0].kind == BlockKind.LIST_ITEM
    def test_plain_text_maps_to_paragraph_block(self): assert pages("plain")[0].blocks[0].kind == BlockKind.PARAGRAPH


class TestEntityRecognition:
    def test_detects_section_entities_from_headings(self): assert any(e.entity_type == EntityType.SECTION for e in ents("# Intro").entities)
    def test_detects_toc_entry_entities(self): assert any(e.entity_type == EntityType.TOC_ENTRY for e in ents("1 Intro ........ 2").entities)
    def test_detects_page_number_entities_without_promoting_them_to_headings(self):
        doc=ents("# A\n\n1"); assert any(e.entity_type == EntityType.PAGE_NUMBER for e in doc.entities) and pages("# A\n\n1")[0].blocks[-1].kind != BlockKind.HEADING
    def test_detects_footnote_entities(self): assert any(e.entity_type == EntityType.FOOTNOTE for e in ents("[1] note").entities)
    def test_detects_equation_entities_with_sequence_key(self): assert any(e.metadata.get("sequence_key") is not None or e.entity_type == EntityType.EQUATION for e in ents("\\[x\\]").entities)
    def test_detects_caption_entities(self): assert any(e.entity_type == EntityType.CAPTION for e in ents("Figure 1. x").entities)
    def test_detects_figure_and_table_entities(self):
        doc=ents("![x](a)\n\n<table></table>"); assert {EntityType.FIGURE, EntityType.TABLE} <= {e.entity_type for e in doc.entities}
    def test_detects_reference_section_entity(self): assert any(e.entity_type == EntityType.REFERENCE_SECTION for e in ents("# References").entities)
    def test_detects_reference_items_after_reference_section(self): assert any(e.entity_type == EntityType.REFERENCE_ITEM for e in ents("# References\n\n[1] A. Paper.").entities)
    def test_confidence_values_are_in_unit_interval(self): assert all(0 <= e.confidence <= 1 for e in ents("# A\n\nFigure 1. x").entities)
    def test_every_entity_has_evidence(self): assert all(e.evidence for e in ents("# A\n\nFigure 1. x").entities)


class TestRelationRecognition:
    def test_caption_of_relation_created_for_adjacent_figure(self): assert any(r.relation_type == RelationType.CAPTION_OF for r in ents("Figure 1. x\n\n![x](a)").relations)
    def test_caption_of_relation_created_for_adjacent_table(self): assert any(r.relation_type == RelationType.CAPTION_OF for r in ents("Table 1. x\n\n<table></table>").relations)
    def test_toc_points_to_relation_created_as_proposal(self): assert any(r.relation_type == RelationType.TOC_POINTS_TO for r in ents("1 Intro ........ 2\n\n# 1 Intro").relations)
    def test_sequence_next_relation_created_only_for_consecutive_numbered_equations(self):
        assert any(r.relation_type == RelationType.SEQUENCE_NEXT for r in ents("x (1)\n\ny (2)").relations)
        assert not any(r.relation_type == RelationType.SEQUENCE_NEXT for r in ents("\\[a\\]\n\n\\[b\\]").relations)
        assert not any(r.relation_type == RelationType.SEQUENCE_NEXT for r in ents("x (1)\n\ny (3)").relations)
    def test_relation_endpoints_exist_in_entity_document(self):
        doc=ents("Figure 1. x\n\n![x](a)"); ids={e.id for e in doc.entities}; assert all(r.source_entity_id in ids and r.target_entity_id in ids for r in doc.relations)


class TestConnectorWriting:
    def test_write_connector_result_creates_manifest_pages_and_entities(self, tmp_path):
        result=connect_raw_dir(raw_dir=Path("tests/data/connector_fixtures/simple_markdown"), document_id="doc", config=CFG)
        m=write_connector_result(result=result, backend="mineru", document_id="doc", raw_dir=Path("raw"), out_dir=tmp_path)
        assert m.exists() and (tmp_path/"mineru/pages/page_0001.json").exists() and (tmp_path/"mineru/entities.json").exists()
    def test_written_page_files_validate_as_page_extraction_ir(self, tmp_path):
        result=connect_raw_dir(raw_dir=Path("tests/data/connector_fixtures/simple_markdown"), document_id="doc", config=CFG, out_dir=tmp_path)
        assert PageExtractionIR.model_validate_json((tmp_path/"mineru/pages/page_0001.json").read_text())
    def test_written_entities_file_validates_as_entity_proposal_document(self, tmp_path):
        connect_raw_dir(raw_dir=Path("tests/data/connector_fixtures/semantic_markdown"), document_id="doc", config=CFG, out_dir=tmp_path)
        assert EntityProposalDocument.model_validate_json((tmp_path/"mineru/entities.json").read_text())
    def test_missing_manifest_is_warning_not_failure(self, tmp_path):
        (tmp_path/"output.md").write_text("hello")
        assert "manifest_missing" in connect_raw_dir(raw_dir=tmp_path, document_id="doc", config=CFG).warnings
    def test_missing_markdown_is_warning_not_failure(self, tmp_path):
        assert "raw_text_missing" in connect_raw_dir(raw_dir=tmp_path, document_id="doc", config=CFG).warnings
    def test_missing_raw_dir_fails_hard(self, tmp_path):
        with pytest.raises(ValueError): connect_raw_dir(raw_dir=tmp_path/"missing", document_id="doc", config=CFG)
