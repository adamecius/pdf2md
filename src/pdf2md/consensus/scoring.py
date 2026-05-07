"""Scoring for page-local consensus candidate groups."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from pdf2md.consensus.grouping import BlockCandidate, CandidateGroup, bbox_iou, compatible_kinds, token_overlap
from pdf2md.models.entities import EntityProposalDocument, EntityType
from pdf2md.models.ir import BlockKind, ConflictKind, SelectionMode
from pdf2md.models.priors import CalibrationPriorDocument, CalibrationTarget, lookup_confidence


@dataclass(frozen=True)
class ConsensusScoringSettings:
    text_weight: float = 0.35
    bbox_weight: float = 0.15
    order_weight: float = 0.10
    kind_weight: float = 0.10
    backend_prior_weight: float = 0.20
    entity_prior_weight: float = 0.10
    unresolved_margin: float = 0.05
    min_agreement_score: float = 0.50
    default_prior_confidence: float = 0.50


@dataclass(frozen=True)
class CandidateScore:
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


def _entities_for_candidate(candidate: BlockCandidate, entity_document: EntityProposalDocument | None):
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
    values = [bbox_iou(candidate.block.bbox, other.block.bbox) for other in group.candidates if other.block.id != candidate.block.id]
    values = [value for value in values if value is not None]
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
