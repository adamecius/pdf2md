from __future__ import annotations

from pathlib import Path

from pdf2md.export.docling import build_docling_document, try_validate_with_docling_core, validate_docling_like_document
from pdf2md.models.ir import ConsensusIR
from pdf2md.models.linked import LinkedStructure

FIX = Path("tests/data/export_fixtures")


def load(name: str):
    root = FIX / name
    return LinkedStructure.model_validate_json((root / "linked_structure.json").read_text()), ConsensusIR.model_validate_json((root / "consensus_ir.json").read_text())


def test_simple_docling_top_level_body_and_unique_refs():
    linked, consensus = load("simple_document")
    result = build_docling_document(linked=linked, consensus=consensus)
    doc = result.document
    for key in ["schema_name", "version", "name", "origin", "body", "groups", "texts", "tables", "pictures", "pages", "metadata"]:
        assert key in doc
    assert doc["body"]["self_ref"] == "#/body"
    refs = [doc["body"]["self_ref"], *[i["self_ref"] for k in ("groups", "texts", "tables", "pictures") for i in doc[k]]]
    assert len(refs) == len(set(refs))
    assert validate_docling_like_document(doc) == []


def test_sections_paragraphs_figures_and_captions_project():
    linked, consensus = load("simple_document")
    doc = build_docling_document(linked=linked, consensus=consensus).document
    # Plan 17: group items no longer carry a stringy `label` field; the
    # `name` carries the heading. Body paragraphs use label="text" (a
    # docling-core DocItemLabel) not the legacy "paragraph" string.
    assert any(group.get("name") == "Introduction" for group in doc["groups"])
    assert any(text["label"] == "text" and "introduction" in text["text"] for text in doc["texts"])
    assert len(doc["pictures"]) == 1
    assert doc["pictures"][0]["metadata"]["captions"]


def test_rich_tables_relations_conflicts_pages_and_core_validation():
    linked, consensus = load("rich_document")
    doc = build_docling_document(linked=linked, consensus=consensus).document
    assert len(doc["tables"]) == 1
    assert len(doc["pictures"]) == 1
    footnote = next(item for item in doc["texts"] if item["label"] == "footnote")
    # Plan 17: body paragraphs now use docling-core's "text" label, so we
    # pick the specific paragraph that has the footnote_anchor_for link
    # (the rich_document fixture also has a TOC entry mapped to "text").
    paragraph = next(
        item
        for item in doc["texts"]
        if item["label"] == "text"
        and any(
            link.get("relation_type") == "footnote_anchor_for"
            for link in item.get("metadata", {}).get("links", [])
        )
    )
    assert any(link["relation_type"] == "footnote_anchor_for" for link in footnote["metadata"].get("links", []))
    assert any(link["relation_type"] == "footnote_anchor_for" for link in paragraph["metadata"].get("links", []))
    assert paragraph["metadata"]["footnote_anchors"] == [footnote["self_ref"]]
    assert footnote["metadata"]["footnote_anchor_targets"] == [paragraph["self_ref"]]
    assert set(doc["pages"]) == {"1", "2"}
    ok, reason = try_validate_with_docling_core(doc)
    assert isinstance(ok, bool)
    assert reason is None or isinstance(reason, str)


def test_unresolved_conflicts_are_preserved():
    linked, consensus = load("unresolved_conflicts")
    result = build_docling_document(linked=linked, consensus=consensus)
    doc = result.document
    assert doc["metadata"]["pdf2md_conflicts"][0]["status"] == "unresolved"
    assert any(text["metadata"].get("status") == "unresolved" for text in doc["texts"])
    assert any(w.startswith("unresolved_node_emitted") for w in result.warnings)


def test_validate_docling_like_document_catches_broken_child_refs():
    broken = {"schema_name": "DoclingDocument", "version": "1.7.0", "name": "x", "origin": {}, "body": {"self_ref": "#/body", "children": ["#/texts/9"]}, "groups": [], "texts": [], "tables": [], "pictures": [], "pages": {}, "key_value_items": [], "form_items": [], "metadata": {"pdf2md": {}}}
    assert "broken_child_ref:#/texts/9" in validate_docling_like_document(broken)

import pytest


@pytest.mark.parametrize("key", ["schema_name", "version", "name", "origin", "body", "groups", "texts", "tables", "pictures", "pages", "key_value_items", "form_items", "metadata"])
def test_required_top_level_key_is_present(key):
    linked, consensus = load("simple_document")
    assert key in build_docling_document(linked=linked, consensus=consensus).document


@pytest.mark.parametrize("fixture", ["simple_document", "rich_document"])
def test_docling_internal_validation_clean_for_resolved_fixtures(fixture):
    linked, consensus = load(fixture)
    assert validate_docling_like_document(build_docling_document(linked=linked, consensus=consensus).document) == []
