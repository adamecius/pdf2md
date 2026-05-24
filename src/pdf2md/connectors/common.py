"""Shared connector implementation for backend raw-output adapters."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pdf2md.models.entities import (
    ConfidenceSource,
    EntityEvidence,
    EntityProposal,
    EntityProposalDocument,
    EntityType,
    EvidenceKind,
    RelationProposal,
    RelationType,
    entity_id,
    relation_id,
)
from pdf2md.models.ir import BlockKind, ExtractionBlock, PageExtractionIR, PageSize, extraction_id


@dataclass(frozen=True)
class ConnectorResult:
    pages: list[PageExtractionIR]
    entities: EntityProposalDocument
    warnings: list[str]


@dataclass(frozen=True)
class BackendConnectorConfig:
    backend: str
    default_backend_version: str | None
    markdown_file_candidates: tuple[str, ...] = ("output.md", "output.mmd", "result.md", "result.mmd")
    manifest_file_candidates: tuple[str, ...] = ("manifest.json", "status.json", "command.json")


def connect_raw_dir(*, raw_dir: Path, document_id: str, config: BackendConnectorConfig, out_dir: Path | None = None) -> ConnectorResult:
    raw_dir = Path(raw_dir)
    if not raw_dir.exists() or not raw_dir.is_dir():
        raise ValueError(f"raw_dir does not exist: {raw_dir}")
    warnings: list[str] = []
    manifest_path = _find_manifest(raw_dir, config)
    manifest = _read_manifest(manifest_path, warnings) if manifest_path else {}
    if manifest_path is None:
        warnings.append("manifest_missing")
    backend_version = manifest.get("backend_version") or config.default_backend_version
    markdown_path = _find_markdown(raw_dir, config)
    if markdown_path is None:
        warnings.append("raw_text_missing")
        pages: list[PageExtractionIR] = []
    else:
        text = markdown_path.read_text(encoding="utf-8")
        pages = markdown_to_pages(text, backend=config.backend, backend_version=backend_version, document_id=document_id, raw_ref=_relative(markdown_path, raw_dir), warnings=warnings)
    entities = recognize_entities(pages, backend=config.backend, backend_version=backend_version, document_id=document_id, warnings=warnings)
    result = ConnectorResult(pages=pages, entities=entities, warnings=warnings)
    if out_dir is not None:
        write_connector_result(result=result, backend=config.backend, document_id=document_id, raw_dir=raw_dir, out_dir=Path(out_dir))
    return result


def write_connector_result(*, result: ConnectorResult, backend: str, document_id: str, raw_dir: Path, out_dir: Path) -> Path:
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"out_dir is not a directory: {out_dir}")
    target = out_dir / backend
    pages_dir = target / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_files: list[str] = []
    for page in result.pages:
        rel = Path("pages") / f"page_{page.page_no:04d}.json"
        (target / rel).write_text(page.model_dump_json(indent=2), encoding="utf-8")
        page_files.append(rel.as_posix())
    entity_file = "entities.json"
    (target / entity_file).write_text(result.entities.model_dump_json(indent=2), encoding="utf-8")
    manifest = {
        "schema_name": "pdf2md.ConnectorManifest",
        "schema_version": "1.0.0",
        "document_id": document_id,
        "backend": backend,
        "backend_version": result.entities.backend_version,
        "raw_dir": str(raw_dir),
        "page_count": len(result.pages),
        "page_ir_files": page_files,
        "entity_file": entity_file,
        "warnings": result.warnings,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


# Pre-compiled deepseek-OCR tag patterns. DeepSeek-OCR-2 prefixes every
# block with `<|ref|>tag<|/ref|><|det|>[[bbox]]<|/det|>\n<content>` where
# `tag` is one of title / sub_title / text / figure_title / image /
# equation / table / footnote / page-header / page-footer / list /
# list_item. We use these tags as the primary block-kind signal and
# strip the prefix from the block text so downstream text comparison is
# clean.
_DEEPSEEK_REF_RE = re.compile(r"<\|ref\|>([^<]+)<\|/ref\|>")
_DEEPSEEK_DET_RE = re.compile(r"<\|det\|>[^<]*<\|/det\|>")
_DEEPSEEK_TAG_TO_BLOCK_KIND: dict[str, BlockKind] = {
    "title": BlockKind.HEADING,
    "sub_title": BlockKind.HEADING,
    "section_header": BlockKind.HEADING,
    "text": BlockKind.PARAGRAPH,
    "paragraph": BlockKind.PARAGRAPH,
    "figure_title": BlockKind.CAPTION,
    "caption": BlockKind.CAPTION,
    "image": BlockKind.FIGURE,
    "figure": BlockKind.FIGURE,
    "equation": BlockKind.FORMULA,
    "formula": BlockKind.FORMULA,
    "table": BlockKind.TABLE,
    "list": BlockKind.LIST,
    "list_item": BlockKind.LIST_ITEM,
    "footnote": BlockKind.FOOTNOTE,
    "page-header": BlockKind.HEADER,
    "page_header": BlockKind.HEADER,
    "page-footer": BlockKind.FOOTER,
    "page_footer": BlockKind.FOOTER,
    "page_number": BlockKind.PAGE_NUMBER,
    "header": BlockKind.HEADER,
    "footer": BlockKind.FOOTER,
}


def _strip_deepseek_tags(chunk: str) -> tuple[str, str | None]:
    """Strip leading deepseek-OCR `<|ref|>` / `<|det|>` tags from a chunk.

    Returns (clean_text, ref_tag) — ``ref_tag`` is the value inside
    `<|ref|>...<|/ref|>`, lowercased, or None if no tag was found. The
    rest of any embedded `<|det|>` markers are also dropped so the block
    text doesn't carry bbox noise into text-overlap matching.
    """

    m = _DEEPSEEK_REF_RE.match(chunk.strip())
    if not m:
        return chunk, None
    tag = m.group(1).strip().lower()
    # Drop the leading ref tag and any det tag that follows on the same line.
    cleaned = _DEEPSEEK_REF_RE.sub("", chunk, count=1)
    cleaned = _DEEPSEEK_DET_RE.sub("", cleaned, count=1)
    return cleaned.strip(), tag


def markdown_to_pages(text: str, *, backend: str, backend_version: str | None, document_id: str, raw_ref: str | None, warnings: list[str]) -> list[PageExtractionIR]:
    if not text.strip():
        warnings.append("raw_text_missing")
        return []
    warnings.append("page_size_missing")
    # Page split markers we know about:
    #   - paddleocr-style "<--- Page Split --->" / "<!-- pagebreak -->" / form-feed
    #   - deepseek-style "<!-- page N -->" (one per page, inclusive of page 1)
    chunks = re.split(r"<---\s*Page Split\s*--->|\f|<!--\s*pagebreak\s*-->|<!--\s*page\s+\d+\s*-->", text, flags=re.I)
    # Drop the leading empty chunk that appears when text starts with a marker
    # (e.g. deepseek emits `<!-- page 1 -->` at the very top).
    chunks = [c for c in chunks if c.strip()]
    pages: list[PageExtractionIR] = []
    for page_no, page_text in enumerate(chunks, start=1):
        blocks = []
        for order, chunk in enumerate([c.strip() for c in re.split(r"\n\s*\n", page_text) if c.strip()]):
            cleaned, ref_tag = _strip_deepseek_tags(chunk)
            kind, metadata = classify_block(cleaned, ref_tag=ref_tag)
            blocks.append(ExtractionBlock(id=extraction_id(backend, document_id, page_no, order), backend=backend, page_no=page_no, kind=kind, order=order, text=cleaned, raw_ref=raw_ref, metadata=metadata))
        pages.append(PageExtractionIR(document_id=document_id, backend=backend, backend_version=backend_version, page_no=page_no, page_size=PageSize(width=1.0, height=1.0), blocks=blocks, raw_artifact_ref=raw_ref, metadata={"connector": "markdown_fallback"}))
    return pages


def classify_block(text: str, *, ref_tag: str | None = None) -> tuple[BlockKind, dict[str, Any]]:
    if ref_tag is not None:
        mapped = _DEEPSEEK_TAG_TO_BLOCK_KIND.get(ref_tag)
        if mapped is not None:
            metadata: dict[str, Any] = {"source_tag": ref_tag}
            if mapped == BlockKind.HEADING:
                first = text.strip().splitlines()[0].strip() if text.strip() else ""
                if m := re.match(r"^(#{1,6})\s+(.+)$", first):
                    metadata["markdown_heading_level"] = len(m.group(1))
                elif ref_tag == "title":
                    metadata["markdown_heading_level"] = 1
                elif ref_tag == "sub_title":
                    metadata["markdown_heading_level"] = 2
            return mapped, metadata
    first = text.strip().splitlines()[0].strip() if text.strip() else ""
    if m := re.match(r"^(#{1,6})\s+(.+)$", first):
        return BlockKind.HEADING, {"markdown_heading_level": len(m.group(1))}
    if re.search(r"^\\\[.*\\\]$", text.strip(), re.S) or re.search(r"\$\$.*\$\$", text.strip(), re.S):
        return BlockKind.FORMULA, {}
    if re.search(r"<table\b.*?</table>", text.strip(), re.I | re.S):
        return BlockKind.TABLE, {}
    if re.match(r"!\[[^\]]*\]\([^)]+\)", first):
        return BlockKind.FIGURE, {}
    if re.match(r"^(Figure|Fig\.|Table)\s+\d+[\.:]?.*", first, re.I):
        return BlockKind.CAPTION, {}
    if re.match(r"^([-*+]\s+|\d+[.)]\s+)", first):
        return BlockKind.LIST_ITEM, {}
    return BlockKind.PARAGRAPH, {}


def recognize_entities(pages: list[PageExtractionIR], *, backend: str, backend_version: str | None, document_id: str, warnings: list[str]) -> EntityProposalDocument:
    entities: list[EntityProposal] = []
    idx = 0

    def add(entity_type: EntityType, block: ExtractionBlock, confidence: float, detector: str, *, subtype: str | None = None, metadata: dict[str, Any] | None = None, evidence_kind: EvidenceKind = EvidenceKind.BLOCK_TEXT) -> EntityProposal:
        nonlocal idx
        idx += 1
        md = {"detector": detector, **(metadata or {})}
        ev = EntityEvidence(kind=evidence_kind, page_no=block.page_no, source_block_id=block.id, raw_ref=block.raw_ref, text=block.text, bbox=block.bbox, weight=1.0, reason=detector, metadata={})
        ent = EntityProposal(id=entity_id(backend, document_id, entity_type, idx), entity_type=entity_type, subtype=subtype, canonical_text=_strip_heading(block.text), page_no=block.page_no, block_ids=[block.id], confidence=confidence, confidence_source=ConfidenceSource.HEURISTIC, evidence=[ev], calibration_key=f"{backend}:{entity_type.value}:{detector}", metadata=md)
        entities.append(ent)
        return ent

    refs_started = False
    for page in pages:
        for pos, block in enumerate(page.blocks):
            text = block.text.strip()
            plain = _strip_heading(text)
            lower = plain.lower()
            if block.kind == BlockKind.HEADING:
                add(EntityType.SECTION, block, 0.75, "heading_section_detector", metadata={"heading_level": block.metadata.get("markdown_heading_level"), "numbering": _numbering(plain)})
                if lower in {"references", "bibliography", "works cited"}:
                    refs_started = True
                    add(EntityType.REFERENCE_SECTION, block, 0.88, "reference_section_detector")
            if m := re.match(r"^(.+?)\s+\.{3,}\s+(\d+)\s*$", plain):
                add(EntityType.TOC_ENTRY, block, 0.74, "toc_entry_detector", metadata={"target_page_candidate": int(m.group(2)), "target_title_candidate": m.group(1).strip()})
            if re.fullmatch(r"\d+|[ivxlcdm]+", lower) and (pos == 0 or pos == len(page.blocks) - 1):
                add(EntityType.PAGE_NUMBER, block, 0.68, "page_number_detector", evidence_kind=EvidenceKind.POSITION)
            if m := re.match(r"^(?:\[(\d+)\]|(\d+)\.|([¹²³]))\s+.+", plain):
                marker = next(g for g in m.groups() if g)
                add(EntityType.FOOTNOTE if not refs_started else EntityType.REFERENCE_ITEM, block, 0.70, "footnote_detector" if not refs_started else "reference_item_detector", metadata={"marker": marker})
            elif refs_started and block.kind == BlockKind.PARAGRAPH and plain:
                add(EntityType.REFERENCE_ITEM, block, 0.62, "reference_item_detector")
            if block.kind == BlockKind.FORMULA or re.search(r"\([0-9]+(?:\.[0-9]+)*\)\s*$", plain):
                num = (re.search(r"\(([0-9]+(?:\.[0-9]+)*)\)\s*$", plain) or [None, None])[1]
                add(EntityType.EQUATION, block, 0.76, "equation_detector", metadata={"equation_number": num, "sequence_key": f"equation:{num}" if num else None})
            if block.kind == BlockKind.CAPTION:
                cm = re.match(r"^(Figure|Fig\.|Table)\s+(\d+)", plain, re.I)
                kind = "table" if cm and cm.group(1).lower().startswith("table") else "figure"
                add(EntityType.CAPTION, block, 0.78, "caption_detector", metadata={"caption_kind": kind, "caption_number": cm.group(2) if cm else None})
            if block.kind == BlockKind.FIGURE:
                add(EntityType.FIGURE, block, 0.82, "figure_table_detector")
            if block.kind == BlockKind.TABLE:
                add(EntityType.TABLE, block, 0.82, "figure_table_detector")
    entities.extend(_header_footer_entities(pages, backend, document_id, idx))
    relations = _relations(entities, backend, document_id)
    return EntityProposalDocument(document_id=document_id, backend=backend, backend_version=backend_version, page_count=len(pages), entities=entities, relations=relations, warnings=warnings, metadata={"connector": "markdown_fallback"})


def _relations(entities: list[EntityProposal], backend: str, document_id: str) -> list[RelationProposal]:
    relations: list[RelationProposal] = []
    by_page: dict[int, list[EntityProposal]] = {}
    for ent in entities:
        if ent.page_no is not None:
            by_page.setdefault(ent.page_no, []).append(ent)
    for ents in by_page.values():
        for i, ent in enumerate(ents[:-1]):
            nxt = ents[i + 1]
            if ent.entity_type == EntityType.CAPTION and nxt.entity_type in {EntityType.FIGURE, EntityType.TABLE} or nxt.entity_type == EntityType.CAPTION and ent.entity_type in {EntityType.FIGURE, EntityType.TABLE}:
                relations.append(_rel(backend, document_id, len(relations) + 1, RelationType.CAPTION_OF, ent, nxt, 0.55, "adjacent caption and media"))
            relations.append(_rel(backend, document_id, len(relations) + 1, RelationType.NEAR, ent, nxt, 0.25, "adjacent entities"))
    sections = [e for e in entities if e.entity_type == EntityType.SECTION]
    for toc in [e for e in entities if e.entity_type == EntityType.TOC_ENTRY]:
        target = str(toc.metadata.get("target_title_candidate", "")).lower()
        for sec in sections:
            title = str(sec.canonical_text or "").lower()
            if title and (title in target or target in title or _tokens_overlap(title, target)):
                relations.append(_rel(backend, document_id, len(relations) + 1, RelationType.TOC_POINTS_TO, toc, sec, 0.50, "toc title matches section")); break
    sequence_groups = [
        [e for e in entities if e.entity_type == EntityType.EQUATION],
        [e for e in entities if e.entity_type == EntityType.CAPTION and e.metadata.get("caption_kind") == "figure"],
        [e for e in entities if e.entity_type == EntityType.CAPTION and e.metadata.get("caption_kind") == "table"],
        [e for e in entities if e.entity_type == EntityType.REFERENCE_ITEM],
    ]
    for seq in sequence_groups:
        numbered = [(entity, _sequence_number(entity)) for entity in seq]
        numbered = [(entity, number) for entity, number in numbered if number is not None]
        for (a, a_number), (b, b_number) in zip(numbered, numbered[1:]):
            if _numbers_are_consecutive(a_number, b_number):
                relations.append(_rel(backend, document_id, len(relations) + 1, RelationType.SEQUENCE_NEXT, a, b, 0.45, "consecutive numbered sequence"))
    return relations


def _rel(backend: str, document_id: str, index: int, rtype: RelationType, source: EntityProposal, target: EntityProposal, confidence: float, reason: str) -> RelationProposal:
    ev = EntityEvidence(kind=EvidenceKind.DOCUMENT_CONTEXT, page_no=source.page_no, source_block_id=source.block_ids[0] if source.block_ids else None, raw_ref=None, text=None, bbox=None, weight=1.0, reason=reason, metadata={})
    return RelationProposal(id=relation_id(backend, document_id, index), relation_type=rtype, source_entity_id=source.id, target_entity_id=target.id, confidence=confidence, confidence_source=ConfidenceSource.HEURISTIC, evidence=[ev], metadata={"detector": f"{rtype.value}_detector"})


def _sequence_number(entity: EntityProposal) -> tuple[int, ...] | None:
    value = None
    if entity.entity_type == EntityType.EQUATION:
        value = entity.metadata.get("equation_number")
    elif entity.entity_type == EntityType.CAPTION:
        value = entity.metadata.get("caption_number")
    elif entity.entity_type == EntityType.REFERENCE_ITEM:
        value = entity.metadata.get("marker")
    if value is None:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)*", text):
        return None
    return tuple(int(part) for part in text.split("."))


def _numbers_are_consecutive(first: tuple[int, ...], second: tuple[int, ...]) -> bool:
    if len(first) != len(second):
        return False
    if first[:-1] != second[:-1]:
        return False
    return second[-1] == first[-1] + 1


def _header_footer_entities(pages: list[PageExtractionIR], backend: str, document_id: str, start: int) -> list[EntityProposal]:
    if len(pages) < 2:
        return []
    out: list[EntityProposal] = []
    for pos, etype, detector in [(0, EntityType.HEADER, "header_footer_detector"), (-1, EntityType.FOOTER, "header_footer_detector")]:
        values: dict[str, list[ExtractionBlock]] = {}
        for page in pages:
            if page.blocks:
                b = page.blocks[pos]
                if len(b.text.strip()) <= 80:
                    values.setdefault(b.text.strip(), []).append(b)
        for text, blocks in values.items():
            if text and len(blocks) >= 2:
                for block in blocks:
                    start += 1
                    ev = EntityEvidence(kind=EvidenceKind.POSITION, page_no=block.page_no, source_block_id=block.id, raw_ref=block.raw_ref, text=block.text, bbox=None, weight=1.0, reason=detector, metadata={})
                    out.append(EntityProposal(id=entity_id(backend, document_id, etype, start), entity_type=etype, canonical_text=text, page_no=block.page_no, block_ids=[block.id], confidence=0.52, confidence_source=ConfidenceSource.HEURISTIC, evidence=[ev], calibration_key=f"{backend}:{etype.value}:{detector}", metadata={"detector": detector}))
    return out


def _find_markdown(raw_dir: Path, config: BackendConnectorConfig) -> Path | None:
    for name in config.markdown_file_candidates:
        candidate = raw_dir / name
        if candidate.is_file():
            return candidate
    matches = sorted([*raw_dir.glob("*.md"), *raw_dir.glob("*.mmd")])
    return matches[0] if len(matches) == 1 else None


def _find_manifest(raw_dir: Path, config: BackendConnectorConfig) -> Path | None:
    for name in config.manifest_file_candidates:
        candidate = raw_dir / name
        if candidate.is_file():
            return candidate
    return None


def _read_manifest(path: Path, warnings: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        warnings.append("manifest_invalid")
        return {}


def _relative(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _strip_heading(text: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", text.strip())


def _numbering(text: str) -> str | None:
    m = re.match(r"^(\d+(?:\.\d+)*)\s+", text)
    return m.group(1) if m else None


def _tokens_overlap(a: str, b: str) -> bool:
    aset = set(re.findall(r"[a-z0-9]+", a.lower()))
    bset = set(re.findall(r"[a-z0-9]+", b.lower()))
    return bool(aset and bset and len(aset & bset) / max(len(aset), len(bset)) >= 0.5)
