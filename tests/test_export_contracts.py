from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdf2md.models.export import (
    ExportArtefact,
    ExportArtefactType,
    ExportManifestDocument,
    ExportStatus,
    RagChunk,
    RagChunkDocument,
    RagChunkType,
    rag_chunk_id,
)

HEX = "a" * 64


def artefact(path="docling/doc.docling.json"):
    return ExportArtefact(artefact_type=ExportArtefactType.DOCLING_JSON, path=path, status=ExportStatus.WRITTEN, sha256=HEX, warnings=[], metadata={})


def chunk(cid="chunk:doc:0", page_start=1, page_end=1):
    return RagChunk(id=cid, chunk_type=RagChunkType.PARAGRAPH, title=None, text="hello", node_ids=["node:doc:1"], relation_ids=[], page_start=page_start, page_end=page_end, section_path=[], breadcrumbs=[], confidence=0.5, metadata={})


def test_export_enum_values():
    assert ExportArtefactType.DOCLING_JSON == "docling_json"
    assert ExportArtefactType.RAG_CHUNKS == "rag_chunks"
    assert ExportStatus.WRITTEN_WITH_WARNINGS == "written_with_warnings"
    assert RagChunkType.EQUATION == "equation"


def test_export_artefact_validation_and_extra_forbid():
    assert artefact().sha256 == HEX
    with pytest.raises(ValidationError):
        ExportArtefact(artefact_type="docling_json", path="", status="written", sha256=None, warnings=[], metadata={})
    with pytest.raises(ValidationError):
        ExportArtefact(artefact_type="docling_json", path="x", status="written", sha256="A" * 64, warnings=[], metadata={})
    with pytest.raises(ValidationError):
        ExportArtefact(artefact_type="docling_json", path="x", status="written", sha256=None, warnings=[], metadata={}, extra=True)


def test_manifest_round_trip_and_duplicate_paths_rejected():
    manifest = ExportManifestDocument(document_id="doc", source_linked_structure="linked.json", source_consensus_ir=None, source_pdf=None, artefacts=[artefact()], warnings=[], metadata={})
    assert ExportManifestDocument.model_validate_json(manifest.model_dump_json()).document_id == "doc"
    with pytest.raises(ValidationError):
        ExportManifestDocument(document_id="doc", source_linked_structure="linked.json", artefacts=[artefact("x"), artefact("x")], warnings=[], metadata={})


def test_rag_chunk_validation():
    assert chunk().id == "chunk:doc:0"
    with pytest.raises(ValidationError):
        chunk("bad")
    with pytest.raises(ValidationError):
        chunk(page_start=2, page_end=1)
    with pytest.raises(ValidationError):
        RagChunk(id="chunk:doc:0", chunk_type="paragraph", title=None, text="", node_ids=["node:doc:1"], relation_ids=[], page_start=1, page_end=1, section_path=[], breadcrumbs=[], confidence=0.5, metadata={})
    with pytest.raises(ValidationError):
        RagChunk(id="chunk:doc:0", chunk_type="paragraph", title=None, text="x", node_ids=[], relation_ids=[], page_start=1, page_end=1, section_path=[], breadcrumbs=[], confidence=0.5, metadata={})
    with pytest.raises(ValidationError):
        RagChunk(id="chunk:doc:0", chunk_type="paragraph", title=None, text="x", node_ids=["node:doc:1"], relation_ids=[], page_start=1, page_end=1, section_path=[], breadcrumbs=[], confidence=2.0, metadata={})


def test_rag_chunk_document_duplicate_ids_and_schema():
    doc = RagChunkDocument(document_id="doc", chunks=[chunk()], warnings=[], metadata={})
    assert RagChunkDocument.model_validate_json(doc.model_dump_json()).chunks[0].text == "hello"
    with pytest.raises(ValidationError):
        RagChunkDocument(document_id="doc", chunks=[chunk(), chunk()], warnings=[], metadata={})
    assert RagChunkDocument.model_json_schema()["title"] == "RagChunkDocument"


def test_rag_chunk_id_factory():
    assert rag_chunk_id("doc-1", 7) == "chunk:doc-1:7"

@pytest.mark.parametrize("ctype", [
    RagChunkType.TITLE,
    RagChunkType.SECTION,
    RagChunkType.PARAGRAPH,
    RagChunkType.LIST,
    RagChunkType.TABLE,
    RagChunkType.FIGURE,
    RagChunkType.CAPTION,
    RagChunkType.EQUATION,
    RagChunkType.FOOTNOTE,
    RagChunkType.REFERENCE,
    RagChunkType.MIXED,
    RagChunkType.UNKNOWN,
])
def test_each_rag_chunk_type_can_validate(ctype):
    assert chunk(cid=f"chunk:doc:{list(RagChunkType).index(ctype)}").model_copy(update={"chunk_type": ctype}).chunk_type == ctype


@pytest.mark.parametrize("atype", list(ExportArtefactType))
def test_each_export_artefact_type_can_validate(atype):
    assert artefact(path=f"x/{atype.value}.json").model_copy(update={"artefact_type": atype}).artefact_type == atype


@pytest.mark.parametrize("status", [ExportStatus.WRITTEN, ExportStatus.SKIPPED])
def test_each_export_status_can_validate(status):
    assert artefact().model_copy(update={"status": status}).status == status
