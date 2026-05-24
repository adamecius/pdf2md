"""Page-local grouping of backend extraction candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import BBox, BlockKind, ExtractionBlock, PageExtractionIR, PageSize


@dataclass(frozen=True)
class BlockCandidate:
    """One backend's extraction block proposed for consensus.

    Attributes:
        backend: Backend that produced the block.
        page_no: 1-based page number on which the block appears.
        block: The underlying ExtractionBlock.
        page_size: Page dimensions used for bbox normalisation.
        entity_ids: IDs of entities that anchor on this block.
    """

    backend: str
    page_no: int
    block: ExtractionBlock
    page_size: PageSize
    entity_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateGroup:
    """A page-local cluster of candidate blocks matched across backends.

    Attributes:
        id: Stable group identifier of the form ``grp:p<page>:<idx>``.
        page_no: Page on which all candidates appear.
        candidates: Candidates assigned to the group, sorted for
            determinism.
        reason: Reason the group was formed (e.g.
            ``same_kind_exact_text``, ``bbox_text_overlap``, or
            ``single``).
        metadata: Auxiliary metadata such as ``last_match_reason``.
    """

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
    """Lowercase, strip, and collapse whitespace in ``text``.

    Args:
        text: Input string or None.

    Returns:
        The normalised string, or an empty string if ``text`` is None.
    """
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokens(text: str | None) -> set[str]:
    return set(re.findall(r"[\w]+", normalise_text(text)))


def token_overlap(a: str | None, b: str | None) -> float:
    """Compute the Jaccard overlap of word tokens between two strings.

    Args:
        a: First string (or None).
        b: Second string (or None).

    Returns:
        Jaccard similarity in [0, 1]. Two empty inputs return 1.0; one
        empty input returns 0.0.
    """
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def bbox_iou(a: BBox | None, b: BBox | None) -> float | None:
    """Compute the intersection-over-union of two bounding boxes.

    Handles both ``topleft`` and ``bottomleft`` coordinate origins, but
    only when both boxes share the same origin.

    Args:
        a: First bounding box, or None.
        b: Second bounding box, or None.

    Returns:
        IoU in [0, 1], or None if either box is missing or the
        coordinate origins differ.
    """
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
    """Return True if two BlockKinds may match in the same group.

    Equal kinds always compatible; otherwise the unordered pair must
    appear in the curated ``_COMPATIBLE_KIND_PAIRS`` allowlist (used to
    let typed kinds match against PARAGRAPH when a backend lacks a
    specific kind detector).

    Args:
        a: First block kind.
        b: Second block kind.

    Returns:
        True if the kinds are compatible for grouping.
    """
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
    """Cluster candidates from a single page into matching groups.

    Walks candidates in deterministic order and joins each to the first
    existing group that holds a matching peer (per
    :func:`_match_reason`) without inducing a same-backend conflict.
    Unmatched candidates start a new group.

    Args:
        page_no: Page number being grouped.
        candidates: All candidates from all backends on this page.
        text_threshold: Minimum token-overlap for "same-kind" or
            "compatible-kind" matches.
        bbox_threshold: Minimum bbox IoU for "bbox + text" matches.

    Returns:
        Ordered list of CandidateGroup, one per cluster.
    """
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
            raw_reasons = [
                _match_reason(candidate, other, text_threshold, bbox_threshold)
                for other in group.candidates
            ]
            reasons: list[str] = [r for r in raw_reasons if r is not None]
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
                candidates=tuple(sorted((*group.candidates, candidate), key=lambda c: (c.block.order, c.backend, c.block.id))),
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
    """Group all candidate blocks of a document, page by page.

    Builds BlockCandidate instances for every backend block (annotated
    with any entity IDs that anchor on it), groups them page-locally via
    :func:`group_page_candidates`, and re-assigns globally stable group
    IDs.

    Args:
        pages_by_backend: Per-backend page IR keyed by backend name.
        entities_by_backend: Per-backend entity documents keyed by
            backend name, used to attach entity_ids to candidates.

    Returns:
        All candidate groups across the document, in page order with
        deterministic group IDs.
    """
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
