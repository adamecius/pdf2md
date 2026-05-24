"""Extract link candidates from page-level consensus and entity evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pdf2md.models.entities import EntityProposal, EntityProposalDocument, EntityType
from pdf2md.models.ir import BlockKind, ConsensusBlock, ConsensusIR
from pdf2md.models.linked import LinkedNodeType
from pdf2md.models.priors import CalibrationPriorDocument, CalibrationTarget, lookup_confidence


@dataclass(frozen=True)
class LinkCandidate:
    """A consensus block prepared for promotion to a linked node.

    Attributes:
        consensus_block_id: Identifier of the source consensus block.
        node_type: Linked node type assigned (refined by entity evidence
            when available).
        text: Verbatim text of the consensus block.
        page_no: Page number on which the block appears.
        order: Reading-order index inside the page.
        source_backend: Backend selected by consensus for this block, or None.
        source_entity_ids: Entity ids that support this candidate's typing.
        confidence: Blended confidence in the typing and selection.
        metadata: Free-form metadata copied from the consensus block plus
            ``candidate_ids`` and (optionally) ``entity_types``.
    """

    consensus_block_id: str
    node_type: LinkedNodeType
    text: str
    page_no: int
    order: int
    source_backend: str | None
    source_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


_BLOCK_KIND_MAP = {
    BlockKind.HEADING: LinkedNodeType.SECTION,
    BlockKind.PARAGRAPH: LinkedNodeType.PARAGRAPH,
    BlockKind.FORMULA: LinkedNodeType.EQUATION,
    BlockKind.FIGURE: LinkedNodeType.FIGURE,
    BlockKind.TABLE: LinkedNodeType.TABLE,
    BlockKind.CAPTION: LinkedNodeType.CAPTION,
    BlockKind.LIST: LinkedNodeType.LIST,
    BlockKind.LIST_ITEM: LinkedNodeType.LIST_ITEM,
    BlockKind.FOOTNOTE: LinkedNodeType.FOOTNOTE,
    BlockKind.PAGE_NUMBER: LinkedNodeType.PAGE_NUMBER,
    BlockKind.HEADER: LinkedNodeType.HEADER,
    BlockKind.FOOTER: LinkedNodeType.FOOTER,
    BlockKind.REFERENCE: LinkedNodeType.REFERENCE_ITEM,
    BlockKind.BIBITEM: LinkedNodeType.REFERENCE_ITEM,
    BlockKind.CODE: LinkedNodeType.CODE,
    BlockKind.UNKNOWN: LinkedNodeType.UNKNOWN,
}

_ENTITY_TYPE_MAP = {
    EntityType.DOCUMENT_TITLE: LinkedNodeType.TITLE,
    EntityType.SECTION: LinkedNodeType.SECTION,
    EntityType.TOC_ENTRY: LinkedNodeType.TOC_ENTRY,
    EntityType.PAGE_NUMBER: LinkedNodeType.PAGE_NUMBER,
    EntityType.HEADER: LinkedNodeType.HEADER,
    EntityType.FOOTER: LinkedNodeType.FOOTER,
    EntityType.FOOTNOTE: LinkedNodeType.FOOTNOTE,
    EntityType.EQUATION: LinkedNodeType.EQUATION,
    EntityType.FIGURE: LinkedNodeType.FIGURE,
    EntityType.TABLE: LinkedNodeType.TABLE,
    EntityType.CAPTION: LinkedNodeType.CAPTION,
    EntityType.REFERENCE_SECTION: LinkedNodeType.REFERENCE_SECTION,
    EntityType.REFERENCE_ITEM: LinkedNodeType.REFERENCE_ITEM,
    EntityType.BIBLIOGRAPHY_MARKER: LinkedNodeType.BIBLIOGRAPHY_MARKER,
    EntityType.UNKNOWN: LinkedNodeType.UNKNOWN,
}


def normalise_text(text: str | None) -> str:
    """Return a whitespace-collapsed, casefolded form of text for comparisons."""
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def consensus_block_to_node_type(block: ConsensusBlock) -> LinkedNodeType:
    """Map a consensus block kind to the corresponding ``LinkedNodeType``.

    Args:
        block: Consensus block whose kind drives the mapping.

    Returns:
        The matching ``LinkedNodeType``, or ``LinkedNodeType.UNKNOWN`` when
        the kind has no defined mapping.
    """
    return _BLOCK_KIND_MAP.get(block.kind, LinkedNodeType.UNKNOWN)


def entity_support_for_block(
    *, consensus_block: ConsensusBlock, entities_by_backend: dict[str, EntityProposalDocument]
) -> list[EntityProposal]:
    """Return entity proposals whose blocks overlap the consensus block's candidates.

    Used during link extraction to refine node typing and contribute to the
    blended confidence of a link candidate.

    Args:
        consensus_block: Consensus block whose candidate ids drive the lookup.
        entities_by_backend: Entity proposal documents keyed by backend name.

    Returns:
        Supporting entity proposals across all backends, sorted by descending
        confidence.
    """
    candidate_ids = set(consensus_block.candidate_ids)
    supported: list[EntityProposal] = []
    for document in entities_by_backend.values():
        for entity in document.entities:
            if candidate_ids.intersection(entity.block_ids):
                supported.append(entity)
    supported.sort(key=lambda entity: entity.confidence, reverse=True)
    return supported


def _refined_type(base_type: LinkedNodeType, support: list[EntityProposal]) -> LinkedNodeType:
    if not support:
        return base_type
    best = support[0]
    return _ENTITY_TYPE_MAP.get(EntityType(best.entity_type), base_type)


def _prior_confidence(
    *, block: ConsensusBlock, support: list[EntityProposal], priors_by_backend: dict[str, CalibrationPriorDocument]
) -> float:
    values: list[float] = [block.agreement_score]
    for entity in support:
        values.append(entity.confidence)
        backend = entity.id.split(":", 2)[1]
        prior = priors_by_backend.get(backend)
        if prior is not None:
            key = entity.calibration_key or str(entity.entity_type)
            values.append(lookup_confidence(prior, CalibrationTarget.ENTITY_TYPE, key))
    selected = block.selected_source
    if selected and selected in priors_by_backend:
        values.append(lookup_confidence(priors_by_backend[selected], CalibrationTarget.BLOCK_KIND, str(block.kind)))
    return max(0.0, min(1.0, sum(values) / len(values)))


def extract_link_candidates(
    *,
    consensus: ConsensusIR,
    entities_by_backend: dict[str, EntityProposalDocument],
    priors_by_backend: dict[str, CalibrationPriorDocument],
) -> list[LinkCandidate]:
    """Build one ``LinkCandidate`` per consensus block in reading order.

    Walks every page and block of the consensus IR, looks up supporting entity
    evidence, refines the linked node type from the highest-confidence entity,
    and computes a blended confidence using the block's agreement score,
    entity confidences, and per-backend calibration priors.

    Args:
        consensus: Consensus IR for the document.
        entities_by_backend: Entity proposal documents keyed by backend name.
        priors_by_backend: Calibration prior documents keyed by backend name.

    Returns:
        Link candidates in the same page/order traversal as the input
        consensus IR.
    """
    candidates: list[LinkCandidate] = []
    for page in consensus.pages:
        for block in page.blocks:
            support = entity_support_for_block(consensus_block=block, entities_by_backend=entities_by_backend)
            node_type = _refined_type(consensus_block_to_node_type(block), support)
            metadata = dict(block.metadata)
            metadata["candidate_ids"] = list(block.candidate_ids)
            if support:
                metadata["entity_types"] = [str(entity.entity_type) for entity in support]
            candidates.append(
                LinkCandidate(
                    consensus_block_id=block.id,
                    node_type=node_type,
                    text=block.text,
                    page_no=page.page_no,
                    order=block.order,
                    source_backend=block.selected_source,
                    source_entity_ids=tuple(entity.id for entity in support),
                    confidence=_prior_confidence(block=block, support=support, priors_by_backend=priors_by_backend),
                    metadata=metadata,
                )
            )
    return candidates
