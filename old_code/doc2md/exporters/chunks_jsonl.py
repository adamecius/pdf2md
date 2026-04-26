"""Chunked JSONL exporter for RAG/benchmarking workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from doc2md.ir.schema import BlockIR, DocumentIR


def _sort_key(block: BlockIR) -> tuple[int, int, str]:
    first_page = min(block.page_indexes) if block.page_indexes else 0
    return (first_page, block.order, block.block_id)


def iter_chunks(doc: DocumentIR) -> Iterator[dict[str, Any]]:
    """Yield one chunk payload per content block in deterministic order."""

    for block in sorted(doc.blocks, key=_sort_key):
        if not block.include_in_rag:
            continue

        text = (block.text or "").strip()
        markdown = (block.markdown or text).strip()

        yield {
            "chunk_id": f"{doc.document_id}:{block.block_id}",
            "text": text,
            "markdown": markdown,
            "page_indexes": list(block.page_indexes),
            "source_block_ids": [block.block_id],
            "media_refs": list(block.media_refs),
            "heading_path": list(block.attributes.get("heading_path", [])),
            "block_type": block.type,
            "role": block.role,
            "include_in_benchmark": block.include_in_benchmark,
        }


def write_chunks_jsonl(doc: DocumentIR, path: str | Path) -> None:
    """Write chunk payloads as line-delimited JSON."""

    out_path = Path(path)
    with out_path.open("w", encoding="utf-8") as fh:
        for chunk in iter_chunks(doc):
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")
