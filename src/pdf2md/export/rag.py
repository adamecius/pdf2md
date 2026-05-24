"""Build structure-aware RAG chunks from LinkedStructure."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from pdf2md.models.export import RagChunk, RagChunkDocument, RagChunkType, rag_chunk_id
from pdf2md.models.linked import LinkedNode, LinkedNodeType, LinkedRelation, LinkedRelationType, LinkedStructure


@dataclass(frozen=True)
class RagExportSettings:
    """Settings controlling structure-aware RAG chunk generation.

    Attributes:
        max_chars: Soft upper bound for chunk text length; longer chunks
            are split with overlap.
        overlap_chars: Character overlap kept between successive splits
            of a long chunk.
        include_captions_with_targets: Attach figure/table captions to
            the same chunk as their target rather than emitting them as
            standalone chunks.
        include_references: Emit chunks for reference items and the
            reference section.
    """

    max_chars: int = 1800
    overlap_chars: int = 150
    include_captions_with_targets: bool = True
    include_references: bool = True


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _text(node: LinkedNode) -> str:
    return (node.text or str(node.metadata.get("title") or "")).strip()


def _chunk_type_for(node: LinkedNode) -> RagChunkType:
    mapping = {
        LinkedNodeType.TITLE: RagChunkType.TITLE,
        LinkedNodeType.SECTION: RagChunkType.SECTION,
        LinkedNodeType.PARAGRAPH: RagChunkType.PARAGRAPH,
        LinkedNodeType.LIST: RagChunkType.LIST,
        LinkedNodeType.LIST_ITEM: RagChunkType.LIST,
        LinkedNodeType.TABLE: RagChunkType.TABLE,
        LinkedNodeType.FIGURE: RagChunkType.FIGURE,
        LinkedNodeType.CAPTION: RagChunkType.CAPTION,
        LinkedNodeType.EQUATION: RagChunkType.EQUATION,
        LinkedNodeType.FOOTNOTE: RagChunkType.FOOTNOTE,
        LinkedNodeType.REFERENCE_ITEM: RagChunkType.REFERENCE,
        LinkedNodeType.REFERENCE_SECTION: RagChunkType.REFERENCE,
    }
    return mapping.get(node.node_type, RagChunkType.UNKNOWN)


def _relations_for(node_ids: list[str], relations: list[LinkedRelation]) -> list[LinkedRelation]:
    nodes = set(node_ids)
    return [rel for rel in relations if rel.source_node_id in nodes or rel.target_node_id in nodes]


def _confidence(nodes: list[LinkedNode], relations: list[LinkedRelation]) -> float:
    values = [n.confidence for n in nodes] + [r.confidence for r in relations]
    return max(0.0, min(1.0, mean(values) if values else 1.0))


def _page_range(nodes: list[LinkedNode]) -> tuple[int | None, int | None]:
    pages = [node.page_no for node in nodes if node.page_no is not None]
    return (min(pages), max(pages)) if pages else (None, None)


def _section_path(node: LinkedNode) -> list[str]:
    raw = node.metadata.get("section_path", [])
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return [str(raw)] if raw else []


def _make_chunk(document_id: str, index: int, ctype: RagChunkType, nodes: list[LinkedNode], relations: list[LinkedRelation], text: str, metadata: dict[str, Any] | None = None) -> RagChunk:
    page_start, page_end = _page_range(nodes)
    first = nodes[0]
    section_path = _section_path(first)
    return RagChunk(
        id=rag_chunk_id(document_id, index),
        chunk_type=ctype,
        title=section_path[-1] if section_path else (first.text if first.node_type in {LinkedNodeType.TITLE, LinkedNodeType.SECTION} else None),
        text=text.strip(),
        node_ids=[node.id for node in nodes],
        relation_ids=[relation.id for relation in relations],
        page_start=page_start,
        page_end=page_end,
        section_path=section_path,
        breadcrumbs=section_path,
        confidence=_confidence(nodes, relations),
        metadata=metadata or {},
    )


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap_chars)
    return [chunk for chunk in chunks if chunk]


def build_rag_chunks(*, linked: LinkedStructure, settings: RagExportSettings = RagExportSettings()) -> RagChunkDocument:
    """Build structure-aware RAG chunks from a LinkedStructure.

    Walks nodes in reading order and accumulates narrative paragraphs
    into mixed chunks while emitting standalone chunks for titles,
    figures, tables, equations, footnotes and references. Captions are
    folded into their target chunk when ``include_captions_with_targets``
    is set. Overlong chunks are split with overlap and the affected ids
    are recorded as ``rag_chunk_split`` warnings.

    Args:
        linked: Linked structure to chunk.
        settings: Chunk-size and inclusion settings.

    Returns:
        A RagChunkDocument with the produced chunks, warnings, and
        provenance metadata.
    """

    nodes = sorted(linked.nodes, key=lambda n: (n.order, n.id))
    by_id = {node.id: node for node in nodes}
    caption_for: dict[str, list[LinkedNode]] = {}
    for relation in linked.relations:
        if relation.relation_type == LinkedRelationType.CAPTION_OF and relation.source_node_id in by_id:
            caption_for.setdefault(relation.target_node_id, []).append(by_id[relation.source_node_id])

    chunks: list[RagChunk] = []
    warnings: list[str] = []
    index = 0
    buffer_nodes: list[LinkedNode] = []
    buffer_texts: list[str] = []

    def flush_buffer() -> None:
        """Emit chunks for the currently buffered nodes and reset the buffer."""
        nonlocal index, buffer_nodes, buffer_texts
        if not buffer_nodes:
            return
        text = "\n\n".join(buffer_texts)
        for split_index, part in enumerate(_split_text(text, settings.max_chars, settings.overlap_chars)):
            rels = _relations_for([node.id for node in buffer_nodes], linked.relations)
            meta = {"split_index": split_index} if split_index else {}
            chunk = _make_chunk(linked.document_id, index, RagChunkType.MIXED if len(buffer_nodes) > 1 else _chunk_type_for(buffer_nodes[0]), buffer_nodes, rels, part, meta)
            chunks.append(chunk)
            if split_index:
                warnings.append(f"rag_chunk_split:{chunk.id}")
            index += 1
        buffer_nodes = []
        buffer_texts = []

    for node in nodes:
        ntype = node.node_type
        text = _text(node)
        if ntype in {LinkedNodeType.DOCUMENT, LinkedNodeType.HEADER, LinkedNodeType.FOOTER, LinkedNodeType.PAGE_NUMBER}:
            continue
        if ntype in {LinkedNodeType.CAPTION} and settings.include_captions_with_targets:
            continue
        if ntype in {LinkedNodeType.REFERENCE_ITEM, LinkedNodeType.REFERENCE_SECTION} and not settings.include_references:
            continue
        if not text and ntype not in {LinkedNodeType.FIGURE, LinkedNodeType.TABLE}:
            continue
        if _value(node.status) == "unresolved" and text:
            flush_buffer()
            rels = _relations_for([node.id], linked.relations)
            chunks.append(_make_chunk(linked.document_id, index, _chunk_type_for(node), [node], rels, text, {"status": "unresolved"}))
            index += 1
            continue
        if ntype in {LinkedNodeType.TITLE, LinkedNodeType.TABLE, LinkedNodeType.FIGURE, LinkedNodeType.EQUATION, LinkedNodeType.FOOTNOTE, LinkedNodeType.REFERENCE_ITEM, LinkedNodeType.REFERENCE_SECTION}:
            flush_buffer()
            chunk_nodes = [node]
            if ntype in {LinkedNodeType.TABLE, LinkedNodeType.FIGURE} and settings.include_captions_with_targets:
                chunk_nodes.extend(caption_for.get(node.id, []))
            body = text or f"[{_value(ntype).title()}]"
            if len(chunk_nodes) > 1:
                cap_text = "\n".join(_text(n) for n in chunk_nodes[1:] if _text(n))
                body = f"{body}\n{cap_text}".strip()
            rels = _relations_for([n.id for n in chunk_nodes], linked.relations)
            metadata: dict[str, Any] = {"status": _value(node.status)} if _value(node.status) == "unresolved" else {}
            if ntype == LinkedNodeType.FOOTNOTE:
                anchor_relations = [
                    relation
                    for relation in linked.relations
                    if relation.relation_type == LinkedRelationType.FOOTNOTE_ANCHOR_FOR and relation.source_node_id == node.id
                ]
                if anchor_relations:
                    metadata["footnote_anchor_target_node_ids"] = [relation.target_node_id for relation in anchor_relations]
                    metadata["footnote_anchor_relations"] = [relation.model_dump(mode="json") for relation in anchor_relations]
            chunks.append(_make_chunk(linked.document_id, index, _chunk_type_for(node), chunk_nodes, rels, body, metadata))
            index += 1
            continue
        if ntype == LinkedNodeType.SECTION:
            flush_buffer()
        projected = text
        prospective_len = len("\n\n".join([*buffer_texts, projected]))
        if buffer_nodes and prospective_len > settings.max_chars:
            flush_buffer()
        buffer_nodes.append(node)
        buffer_texts.append(projected)
    flush_buffer()

    return RagChunkDocument(document_id=linked.document_id, chunks=chunks, warnings=warnings, metadata={"source": "LinkedStructure"})
