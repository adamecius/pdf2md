"""Page-local grouping of backend extraction candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import BBox, BlockKind, ExtractionBlock, PageExtractionIR, PageSize


@dataclass(frozen=True)
class BlockCandidate:
    backend: str
    page_no: int
    block: ExtractionBlock
    page_size: PageSize
    entity_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateGroup:
    id: str
    page_no: int
    candidates: tuple[BlockCandidate, ...]
    reason: str
    metadata: dict[str, Any]


_COMPATIBLE_KIND_PAIRS = {
    frozenset((BlockKind.HEADING, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.FORMULA, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.CAPTION, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.PAGE_NUMBER, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.FOOTNOTE, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.REFERENCE, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.BIBITEM, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.FIGURE, BlockKind.PARAGRAPH)),
    frozenset((BlockKind.TABLE, BlockKind.PARAGRAPH)),
}


def normalise_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokens(text: str | None) -> set[str]:
    return set(re.findall(r"[\w]+", normalise_text(text)))


def token_overlap(a: str | None, b: str | None) -> float:
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def bbox_iou(a: BBox | None, b: BBox | None) -> float | None:
    if a is None or b is None or a.coord_origin != b.coord_origin:
        return None
    left = max(a.l, b.l)
    right = min(a.r, b.r)
    top = max(a.t, b.t) if a.coord_origin == "topleft" else min(a.t, b.t)
    bottom = min(a.b, b.b) if a.coord_origin == "topleft" else max(a.b, b.b)
    if a.coord_origin == "topleft":
        inter_h = bottom - top
        ha = a.b - a.t
        hb = b.b - b.t
    else:
        inter_h = top - bottom
        ha = a.t - a.b
        hb = b.t - b.b
    inter_w = right - left
    if inter_w <= 0 or inter_h <= 0:
        return 0.0
    inter = inter_w * inter_h
    area_a = (a.r - a.l) * ha
    area_b = (b.r - b.l) * hb
    return inter / (area_a + area_b - inter)


def compatible_kinds(a: BlockKind, b: BlockKind) -> bool:
    return a == b or frozenset((a, b)) in _COMPATIBLE_KIND_PAIRS


def _same_backend_conflict(candidate: BlockCandidate, group: CandidateGroup) -> bool:
    for other in group.candidates:
        if other.backend == candidate.backend and other.block.id != candidate.block.id:
            return True
    return False


def _match_reason(a: BlockCandidate, b: BlockCandidate, text_threshold: float, bbox_threshold: float) -> str | None:
    if a.page_no != b.page_no:
        return None
    ta = normalise_text(a.block.text)
    tb = normalise_text(b.block.text)
    overlap = token_overlap(a.block.text, b.block.text)
    iou = bbox_iou(a.block.bbox, b.block.bbox)
    if a.block.kind == b.block.kind and ta == tb:
        return "same_kind_exact_text"
    if a.block.kind == b.block.kind and overlap >= text_threshold:
        return "same_kind_text_overlap"
    if compatible_kinds(a.block.kind, b.block.kind) and overlap >= text_threshold:
        return "compatible_kind_text_overlap"
    if iou is not None and iou >= bbox_threshold and overlap >= 0.25:
        return "bbox_text_overlap"
    return None


def group_page_candidates(
    *,
    page_no: int,
    candidates: list[BlockCandidate],
    text_threshold: float = 0.75,
    bbox_threshold: float = 0.50,
) -> list[CandidateGroup]:
    groups: list[CandidateGroup] = []
    sorted_candidates = sorted(
        [c for c in candidates if c.page_no == page_no],
        key=lambda c: (c.block.order, c.backend, c.block.id),
    )
    for candidate in sorted_candidates:
        matched_index: int | None = None
        matched_reason = "single"
        for index, group in enumerate(groups):
            if _same_backend_conflict(candidate, group):
                continue
            reasons = [
                _match_reason(candidate, other, text_threshold, bbox_threshold)
                for other in group.candidates
            ]
            reasons = [reason for reason in reasons if reason]
            if reasons:
                matched_index = index
                matched_reason = reasons[0]
                break
        if matched_index is None:
            groups.append(
                CandidateGroup(
                    id=f"grp:p{page_no}:{len(groups)}",
                    page_no=page_no,
                    candidates=(candidate,),
                    reason="single",
                    metadata={},
                )
            )
        else:
            group = groups[matched_index]
            groups[matched_index] = CandidateGroup(
                id=group.id,
                page_no=group.page_no,
                candidates=tuple(sorted(group.candidates + (candidate,), key=lambda c: (c.block.order, c.backend, c.block.id))),
                reason=matched_reason if group.reason == "single" else group.reason,
                metadata={**group.metadata, "last_match_reason": matched_reason},
            )
    return groups


def _entity_ids_by_block(entity_doc: EntityProposalDocument | None) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    if entity_doc is None:
        return {}
    for entity in entity_doc.entities:
        for block_id in entity.block_ids:
            mapping.setdefault(block_id, []).append(entity.id)
    return {block_id: tuple(ids) for block_id, ids in mapping.items()}


def group_document_candidates(
    *,
    pages_by_backend: dict[str, list[PageExtractionIR]],
    entities_by_backend: dict[str, EntityProposalDocument],
) -> list[CandidateGroup]:
    candidates_by_page: dict[int, list[BlockCandidate]] = {}
    for backend, pages in sorted(pages_by_backend.items()):
        entity_map = _entity_ids_by_block(entities_by_backend.get(backend))
        for page in pages:
            for block in page.blocks:
                candidates_by_page.setdefault(page.page_no, []).append(
                    BlockCandidate(
                        backend=backend,
                        page_no=page.page_no,
                        block=block,
                        page_size=page.page_size,
                        entity_ids=entity_map.get(block.id, ()),
                    )
                )
    groups: list[CandidateGroup] = []
    for page_no in sorted(candidates_by_page):
        groups.extend(group_page_candidates(page_no=page_no, candidates=candidates_by_page[page_no]))
    return [
        CandidateGroup(id=f"grp:p{group.page_no}:{index}", page_no=group.page_no, candidates=group.candidates, reason=group.reason, metadata=group.metadata)
        for index, group in enumerate(groups)
    ]
