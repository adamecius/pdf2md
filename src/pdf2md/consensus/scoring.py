"""Scoring for page-local consensus candidate groups."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from pdf2md.consensus.grouping import BlockCandidate, CandidateGroup, bbox_iou, compatible_kinds, token_overlap
from pdf2md.models.entities import EntityProposal, EntityProposalDocument, EntityType
from pdf2md.models.ir import BlockKind, ConflictKind, SelectionMode
from pdf2md.models.priors import CalibrationPriorDocument, CalibrationTarget, lookup_confidence


@dataclass(frozen=True)
class ConsensusScoringSettings:
    """Weights and thresholds for consensus candidate scoring.

    The defaults reserve 55% of the weight for calibrated priors
    (backend + entity) so that backends with low calibrated confidence
    do not automatically win single-backend groups (see the inline
    weight rationale below).

    Attributes:
        text_weight: Weight for token-overlap score.
        bbox_weight: Weight for bounding-box IoU score.
        order_weight: Weight for reading-order proximity.
        kind_weight: Weight for block-kind agreement with the group
            majority.
        backend_prior_weight: Weight for the per-block-kind backend
            prior.
        entity_prior_weight: Weight for the strongest entity-level
            prior anchored on the candidate.
        unresolved_margin: Score gap below which two top candidates are
            treated as a tie and the group is marked UNRESOLVED.
        min_agreement_score: Minimum total score required to accept a
            candidate; otherwise the group falls back to FALLBACK or
            UNRESOLVED.
        default_prior_confidence: Default prior confidence used when no
            calibration entry is available.
    """

    # Weights rebalanced so calibrated priors carry 55% (was 30%). With the
    # old 0.35/0.15/0.10/0.10/0.20/0.10 split the single-backend score floor
    # was 0.625 (text_score=1.0, bbox_score=0.5, order_score=1.0,
    # kind_score=1.0, prior=0) — above min_agreement_score=0.50, so even a
    # backend with 0.0 calibrated confidence always selected. The new
    # 0.20/0.10/0.05/0.10/0.35/0.20 split gives base 0.40; a block_kind with
    # calibrated_confidence < ~0.18 (when entity_prior is also weak) falls
    # below min_agreement_score and is marked FALLBACK. See:
    #   - tools/calibrate_priors.py output for the synthetic LaTeX corpus
    #   - groundtruth/runs/calibration_run/priors/paddleocr.json
    text_weight: float = 0.20
    bbox_weight: float = 0.10
    order_weight: float = 0.05
    kind_weight: float = 0.10
    backend_prior_weight: float = 0.35
    entity_prior_weight: float = 0.20
    unresolved_margin: float = 0.05
    min_agreement_score: float = 0.50
    default_prior_confidence: float = 0.50


@dataclass(frozen=True)
class CandidateScore:
    """Score breakdown for a single candidate within a group.

    Attributes:
        candidate: The BlockCandidate being scored.
        score: Final weighted score in [0, 1].
        text_score: Best token-overlap with any peer candidate.
        bbox_score: Mean bbox IoU against peer candidates.
        order_score: Reading-order proximity to the group median.
        kind_score: Agreement with the group's majority block kind.
        backend_prior: Per-block-kind backend prior.
        entity_prior: Strongest entity-level prior for the candidate.
        metadata: Auxiliary metadata such as the inferred block kind.
    """

    candidate: BlockCandidate
    score: float
    text_score: float
    bbox_score: float
    order_score: float
    kind_score: float
    backend_prior: float
    entity_prior: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class GroupScore:
    """Outcome of scoring a CandidateGroup.

    Attributes:
        group: The scored CandidateGroup.
        candidate_scores: Per-candidate score breakdowns, sorted by
            descending score.
        selected: The winning CandidateScore, or None if the group is
            UNRESOLVED.
        agreement_score: Score of the top candidate.
        selection_mode: How the winner was chosen (AGREED,
            SINGLE_SOURCE, FALLBACK, or UNRESOLVED).
        conflict_kind: Conflict classification when the group is
            UNRESOLVED, else None.
        metadata: Auxiliary metadata about the scoring run.
    """

    group: CandidateGroup
    candidate_scores: tuple[CandidateScore, ...]
    selected: CandidateScore | None
    agreement_score: float
    selection_mode: SelectionMode
    conflict_kind: ConflictKind | None
    metadata: dict[str, Any]


_ENTITY_KIND_MAP = {
    EntityType.PAGE_NUMBER: BlockKind.PAGE_NUMBER,
    EntityType.FOOTNOTE: BlockKind.FOOTNOTE,
    EntityType.EQUATION: BlockKind.FORMULA,
    EntityType.CAPTION: BlockKind.CAPTION,
    EntityType.FIGURE: BlockKind.FIGURE,
    EntityType.TABLE: BlockKind.TABLE,
    EntityType.REFERENCE_ITEM: BlockKind.BIBITEM,
    EntityType.REFERENCE_SECTION: BlockKind.HEADING,
}


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _entities_for_candidate(
    candidate: BlockCandidate, entity_document: EntityProposalDocument | None
) -> list[EntityProposal]:
    if entity_document is None:
        return []
    ids = set(candidate.entity_ids)
    return [entity for entity in entity_document.entities if entity.id in ids or candidate.block.id in entity.block_ids]


def _confidence(prior: CalibrationPriorDocument | None, target: CalibrationTarget, key: str, default: float) -> float:
    if prior is None:
        return default
    return lookup_confidence(prior, target, key)


def infer_block_kind_from_entities(
    *,
    candidate: BlockCandidate,
    entity_document: EntityProposalDocument | None,
    prior: CalibrationPriorDocument | None,
    default_confidence: float,
) -> tuple[BlockKind, float, dict[str, Any]]:
    """Refine a candidate's block kind using entity-level evidence.

    Compares the raw block kind's prior confidence to the priors of any
    entities anchored on the block. Promotes to the entity-implied kind
    only when the gain exceeds 0.10, to avoid noisy flips.

    Args:
        candidate: The candidate whose kind may be revised.
        entity_document: Backend's entity proposals (may be None).
        prior: Backend's calibration prior (may be None).
        default_confidence: Confidence to use when no prior entry
            exists.

    Returns:
        ``(kind, confidence, metadata)`` where ``metadata`` carries
        ``kind_source``, the raw kind, and (when promoted) the
        triggering entity_type.
    """
    raw_kind = candidate.block.kind
    raw_prior = _confidence(prior, CalibrationTarget.BLOCK_KIND, _enum_value(raw_kind), default_confidence)
    best_kind = raw_kind
    best_confidence = raw_prior
    best_entity_type: str | None = None
    for entity in _entities_for_candidate(candidate, entity_document):
        entity_type = EntityType(_enum_value(entity.entity_type))
        mapped = _ENTITY_KIND_MAP.get(entity_type)
        if mapped is None:
            continue
        entity_confidence = _confidence(prior, CalibrationTarget.ENTITY_TYPE, _enum_value(entity.entity_type), default_confidence)
        if entity.calibration_key:
            entity_confidence = max(
                entity_confidence,
                _confidence(prior, CalibrationTarget.CALIBRATION_KEY, entity.calibration_key, default_confidence),
            )
        if entity_confidence > best_confidence:
            best_kind = mapped
            best_confidence = entity_confidence
            best_entity_type = _enum_value(entity.entity_type)
    metadata: dict[str, Any] = {"kind_source": "block", "raw_block_kind": _enum_value(raw_kind)}
    if best_kind != raw_kind and best_confidence >= raw_prior + 0.10:
        metadata = {"kind_source": "entity_prior", "raw_block_kind": _enum_value(raw_kind), "entity_type": best_entity_type}
        return best_kind, best_confidence, metadata
    return raw_kind, raw_prior, metadata


def _text_score(candidate: BlockCandidate, group: CandidateGroup) -> float:
    others = [other for other in group.candidates if other.block.id != candidate.block.id]
    if not others:
        return 1.0
    return max(token_overlap(candidate.block.text, other.block.text) for other in others)


def _bbox_score(candidate: BlockCandidate, group: CandidateGroup) -> float:
    raw_values = [bbox_iou(candidate.block.bbox, other.block.bbox) for other in group.candidates if other.block.id != candidate.block.id]
    values: list[float] = [value for value in raw_values if value is not None]
    if not values:
        return 0.5
    return sum(values) / len(values)


def _order_score(candidate: BlockCandidate, group: CandidateGroup) -> float:
    orders = [c.block.order for c in group.candidates]
    if len(orders) == 1:
        return 1.0
    med = median(orders)
    span = max(orders) - min(orders) or 1
    return max(0.0, 1.0 - abs(candidate.block.order - med) / span)


def _kind_score(candidate: BlockCandidate, group: CandidateGroup) -> float:
    counts: dict[BlockKind, int] = {}
    for item in group.candidates:
        counts[item.block.kind] = counts.get(item.block.kind, 0) + 1
    majority = sorted(counts.items(), key=lambda item: (-item[1], _enum_value(item[0])))[0][0]
    if candidate.block.kind == majority:
        return 1.0
    if compatible_kinds(candidate.block.kind, majority):
        return 0.75
    return 0.25


def _entity_prior(candidate: BlockCandidate, entity_document: EntityProposalDocument | None, prior: CalibrationPriorDocument | None, default: float) -> float:
    values: list[float] = []
    for entity in _entities_for_candidate(candidate, entity_document):
        values.append(_confidence(prior, CalibrationTarget.ENTITY_TYPE, _enum_value(entity.entity_type), default))
        if entity.calibration_key:
            values.append(_confidence(prior, CalibrationTarget.CALIBRATION_KEY, entity.calibration_key, default))
    return max(values) if values else default


def _conflict_kind(candidate_scores: tuple[CandidateScore, ...]) -> ConflictKind:
    raw_kinds = {_enum_value(score.candidate.block.kind) for score in candidate_scores}
    inferred_kinds = {str(score.metadata.get("inferred_kind", _enum_value(score.candidate.block.kind))) for score in candidate_scores}
    texts = {score.candidate.block.text for score in candidate_scores}
    if len(raw_kinds) > 1 or len(inferred_kinds) > 1:
        return ConflictKind.KIND_CONFLICT
    if len(texts) > 1:
        return ConflictKind.TEXT_CONFLICT
    return ConflictKind.PRESENCE_CONFLICT


def score_candidate_group(
    *,
    group: CandidateGroup,
    priors_by_backend: dict[str, CalibrationPriorDocument],
    entities_by_backend: dict[str, EntityProposalDocument],
    settings: ConsensusScoringSettings = ConsensusScoringSettings(),
) -> GroupScore:
    """Score candidates in a group and select the consensus winner.

    Computes a weighted score for each candidate using text overlap,
    bbox IoU, reading order, block-kind agreement, backend calibration
    prior, and entity-level prior. Picks the highest-scoring candidate
    or marks the group as UNRESOLVED when the margin to the runner-up
    is within :attr:`ConsensusScoringSettings.unresolved_margin`.

    Args:
        group: The candidate group to score.
        priors_by_backend: Calibration prior documents keyed by backend.
        entities_by_backend: Entity proposal documents keyed by backend.
        settings: Scoring weights and thresholds.

    Returns:
        A GroupScore with the selected candidate, agreement score,
        selection mode, per-candidate breakdown, and (if unresolved)
        the inferred conflict kind.
    """
    scores: list[CandidateScore] = []
    for candidate in group.candidates:
        prior = priors_by_backend.get(candidate.backend)
        entity_doc = entities_by_backend.get(candidate.backend)
        backend_prior = _confidence(prior, CalibrationTarget.BLOCK_KIND, _enum_value(candidate.block.kind), settings.default_prior_confidence)
        entity_prior = _entity_prior(candidate, entity_doc, prior, settings.default_prior_confidence)
        components = {
            "text_score": _text_score(candidate, group),
            "bbox_score": _bbox_score(candidate, group),
            "order_score": _order_score(candidate, group),
            "kind_score": _kind_score(candidate, group),
            "backend_prior": backend_prior,
            "entity_prior": entity_prior,
        }
        inferred_kind, inferred_confidence, inferred_metadata = infer_block_kind_from_entities(
            candidate=candidate,
            entity_document=entity_doc,
            prior=prior,
            default_confidence=settings.default_prior_confidence,
        )
        score = (
            settings.text_weight * components["text_score"]
            + settings.bbox_weight * components["bbox_score"]
            + settings.order_weight * components["order_score"]
            + settings.kind_weight * components["kind_score"]
            + settings.backend_prior_weight * backend_prior
            + settings.entity_prior_weight * entity_prior
        )
        scores.append(
            CandidateScore(
                candidate=candidate,
                score=round(score, 6),
                metadata={"inferred_kind": _enum_value(inferred_kind), "inferred_kind_confidence": inferred_confidence, **inferred_metadata},
                **components,
            )
        )
    ordered = tuple(sorted(scores, key=lambda s: (-s.score, s.candidate.backend, s.candidate.block.id)))
    top = ordered[0]
    second = ordered[1] if len(ordered) > 1 else None
    same_evidence = (
        second is not None
        and top.candidate.block.text == second.candidate.block.text
        and top.candidate.block.kind == second.candidate.block.kind
        and top.metadata.get("inferred_kind") == second.metadata.get("inferred_kind")
    )
    close = second is not None and not same_evidence and top.score - second.score <= settings.unresolved_margin
    if close:
        mode = SelectionMode.UNRESOLVED
        selected = None
    elif len(ordered) == 1 and top.score >= settings.min_agreement_score:
        mode = SelectionMode.SINGLE_SOURCE
        selected = top
    elif len(ordered) > 1 and top.score >= settings.min_agreement_score:
        mode = SelectionMode.AGREED
        selected = top
    elif top.score < settings.min_agreement_score and not close:
        mode = SelectionMode.FALLBACK
        selected = top
    else:
        mode = SelectionMode.UNRESOLVED
        selected = None
    return GroupScore(
        group=group,
        candidate_scores=ordered,
        selected=selected,
        agreement_score=top.score,
        selection_mode=mode,
        conflict_kind=_conflict_kind(ordered) if mode == SelectionMode.UNRESOLVED else None,
        metadata={"score_count": len(ordered)},
    )
