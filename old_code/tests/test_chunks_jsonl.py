"""Tests for chunk JSONL exports from DocIR."""

import json

from doc2md.exporters.chunks_jsonl import iter_chunks, write_chunks_jsonl
from doc2md.ir.schema import BlockIR, DocumentIR, PageIR


REQUIRED_FIELDS = {
    "chunk_id",
    "text",
    "markdown",
    "page_indexes",
    "source_block_ids",
    "media_refs",
    "heading_path",
    "block_type",
    "role",
    "include_in_benchmark",
}


def _doc_fixture() -> DocumentIR:
    return DocumentIR(
        schema_version="0.1",
        document_id="doc_fixture",
        source_path="fixture.pdf",
        pages=[PageIR(page_id="page_0000", page_index=0, width=612, height=792)],
        blocks=[
            BlockIR(
                block_id="blk_1",
                type="heading",
                role="title",
                text="Section 1",
                markdown="# Section 1",
                page_indexes=[0],
                order=0,
                media_refs=["media_1"],
                attributes={"heading_path": ["Section 1"]},
            ),
            BlockIR(
                block_id="blk_skip",
                type="paragraph",
                text="skip",
                page_indexes=[0],
                order=1,
                include_in_rag=False,
            ),
        ],
    )


def test_iter_chunks_contains_required_fields() -> None:
    chunks = list(iter_chunks(_doc_fixture()))
    assert len(chunks) == 1

    chunk = chunks[0]
    assert REQUIRED_FIELDS.issubset(chunk.keys())
    assert chunk["chunk_id"] == "doc_fixture:blk_1"
    assert chunk["source_block_ids"] == ["blk_1"]
    assert chunk["heading_path"] == ["Section 1"]


def test_write_chunks_jsonl_writes_valid_json_lines(tmp_path) -> None:
    out_file = tmp_path / "chunks.jsonl"
    write_chunks_jsonl(_doc_fixture(), out_file)

    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    payload = json.loads(lines[0])
    assert REQUIRED_FIELDS.issubset(payload.keys())
    assert payload["block_type"] == "heading"
