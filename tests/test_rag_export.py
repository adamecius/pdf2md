from __future__ import annotations

from pathlib import Path

from pdf2md.export.rag import RagExportSettings, build_rag_chunks
from pdf2md.models.export import RagChunkDocument
from pdf2md.models.linked import LinkedStructure

FIX = Path("tests/data/export_fixtures")


def load(name: str) -> LinkedStructure:
    return LinkedStructure.model_validate_json((FIX / name / "linked_structure.json").read_text())


def test_rich_rag_chunks_preserve_structure_and_types():
    doc = build_rag_chunks(linked=load("rich_document"))
    types = [chunk.chunk_type for chunk in doc.chunks]
    assert "title" in types
    assert "table" in types
    assert "figure" in types
    assert "equation" in types
    assert "footnote" in types
    assert "reference" in types
    footnote = next(chunk for chunk in doc.chunks if chunk.chunk_type == "footnote")
    assert footnote.metadata["footnote_anchor_target_node_ids"] == ["node:doc-rich:4"]
    relations = footnote.metadata["footnote_anchor_relations"]
    assert relations[0]["relation_type"] == "footnote_anchor_for"
    assert relations[0]["source_node_id"] == "node:doc-rich:10"
    assert relations[0]["target_node_id"] == "node:doc-rich:4"
    assert RagChunkDocument.model_validate_json(doc.model_dump_json()).document_id == "doc-rich"


def test_captions_are_included_with_targets_and_relations():
    doc = build_rag_chunks(linked=load("simple_document"))
    figure = next(chunk for chunk in doc.chunks if chunk.chunk_type == "figure")
    assert "Figure 1" in figure.text
    assert len(figure.node_ids) == 2
    assert figure.relation_ids


def test_references_can_be_excluded():
    doc = build_rag_chunks(linked=load("rich_document"), settings=RagExportSettings(include_references=False))
    assert "reference" not in [chunk.chunk_type for chunk in doc.chunks]


def test_max_chars_split_records_overlap_metadata():
    doc = build_rag_chunks(linked=load("rich_document"), settings=RagExportSettings(max_chars=20, overlap_chars=5))
    assert any(chunk.metadata.get("split_index") for chunk in doc.chunks)
    assert any(w.startswith("rag_chunk_split") for w in doc.warnings)


def test_unresolved_nodes_mark_status_and_confidence():
    doc = build_rag_chunks(linked=load("unresolved_conflicts"))
    chunk = next(chunk for chunk in doc.chunks if chunk.metadata.get("status") == "unresolved")
    assert chunk.confidence < 0.7
    assert chunk.page_start == 1 and chunk.page_end == 1

import pytest


@pytest.mark.parametrize("expected", ["title", "mixed", "table", "figure", "equation", "footnote", "reference"])
def test_rich_document_has_expected_chunk_type(expected):
    doc = build_rag_chunks(linked=load("rich_document"))
    assert expected in [chunk.chunk_type for chunk in doc.chunks]


@pytest.mark.parametrize("field", ["node_ids", "relation_ids", "section_path", "breadcrumbs"])
def test_chunks_expose_provenance_lists(field):
    doc = build_rag_chunks(linked=load("simple_document"))
    assert isinstance(getattr(doc.chunks[0], field), list)
