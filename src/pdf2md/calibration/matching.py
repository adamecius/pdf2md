"""Deterministic matching between backend predictions and calibration truth."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pdf2md.models.entities import EntityProposal, EntityProposalDocument
from pdf2md.models.ir import ExtractionBlock, PageExtractionIR
from pdf2md.models.priors import CalibrationTarget, CalibrationTruthDocument, MatchOutcome, TruthEntity, TruthRelation


@dataclass(frozen=True)
class MatchRecord:
    """One match outcome between a prediction and the calibration truth.

    Attributes:
        target: Calibration target this record contributes to (block kind,
            entity type, relation type, or calibration key).
        key: Target-specific bucket identifier (e.g. block-kind value, entity
            type name, calibration key).
        backend: Backend whose prediction produced the record.
        prediction_id: Identifier of the predicted item, or None for false
            negatives (truth-only items).
        truth_id: Identifier of the truth item, or None for false positives
            (predictions with no truth counterpart).
        outcome: True positive, false positive, or false negative.
        confidence: Predicted confidence if available, else None.
        metadata: Free-form per-record annotations (e.g. token-overlap score
            or warning markers).
    """

    target: CalibrationTarget
    key: str
    backend: str
    prediction_id: str | None
    truth_id: str | None
    outcome: MatchOutcome
    confidence: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def normalise_text(text: str | None) -> str:
    """Return a casefolded, whitespace-collapsed word-token form of text.

    Args:
        text: Input string, or None.

    Returns:
        The lowercase tokens joined by single spaces, or an empty string if
        ``text`` is None or contains no word characters.
    """
    if text is None:
        return ""
    return " ".join(_WORD_RE.findall(text.casefold()))


def token_overlap(a: str | None, b: str | None) -> float:
    """Return the Jaccard overlap of word tokens between two strings.

    Both inputs are normalised by :func:`normalise_text` before comparison.
    Two empty inputs are treated as identical (score 1.0); a single empty
    input scores 0.0.

    Args:
        a: First string, or None.
        b: Second string, or None.

    Returns:
        Token-set Jaccard similarity in the range ``[0.0, 1.0]``.
    """
    a_tokens = set(_WORD_RE.findall(normalise_text(a)))
    b_tokens = set(_WORD_RE.findall(normalise_text(b)))
    if not a_tokens and not b_tokens:
        return 1.0
    if not a_tokens or not b_tokens:
        return 0.0
    # TODO: Make the overlap threshold configurable once calibration has a shared
    # config surface; Jaccard keeps short substrings from matching noisy text too easily.
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _block_score(prediction: ExtractionBlock, truth_text: str | None) -> float:
    pred = normalise_text(prediction.text)
    truth = normalise_text(truth_text)
    if pred == truth:
        return 1.0
    return token_overlap(prediction.text, truth_text)


def match_blocks(*, backend: str, pages: list[PageExtractionIR], truth: CalibrationTruthDocument) -> list[MatchRecord]:
    """Greedily match predicted blocks against truth blocks by kind and text.

    Predicted and truth blocks must share the same page number and the same
    block kind, and their text token-overlap must reach ``0.80`` to count as
    a true positive. Unmatched predictions become false positives and
    unmatched truth blocks become false negatives, all bucketed by block
    kind.

    Args:
        backend: Backend name to attach to every emitted record.
        pages: Per-page extraction IRs containing predicted blocks.
        truth: Ground-truth document.

    Returns:
        One ``MatchRecord`` per outcome (true positive, false positive, false
        negative) for the ``BLOCK_KIND`` calibration target.
    """
    predictions = [block for page in pages for block in sorted(page.blocks, key=lambda b: b.order)]
    candidates: list[tuple[float, int, str, ExtractionBlock, Any]] = []
    for order, prediction in enumerate(predictions):
        for truth_block in truth.blocks:
            if prediction.page_no != truth_block.page_no:
                continue
            if _value(prediction.kind) != _value(truth_block.block_kind):
                continue
            score = _block_score(prediction, truth_block.text)
            if score >= 0.80:
                candidates.append((score, order, truth_block.id, prediction, truth_block))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_predictions: set[str] = set()
    used_truth: set[str] = set()
    records: list[MatchRecord] = []
    for score, _, _, prediction, truth_block in candidates:
        if prediction.id in used_predictions or truth_block.id in used_truth:
            continue
        used_predictions.add(prediction.id)
        used_truth.add(truth_block.id)
        records.append(MatchRecord(CalibrationTarget.BLOCK_KIND, _value(prediction.kind), backend, prediction.id, truth_block.id, MatchOutcome.TRUE_POSITIVE, prediction.confidence, {"score": score}))
    for prediction in predictions:
        if prediction.id not in used_predictions:
            records.append(MatchRecord(CalibrationTarget.BLOCK_KIND, _value(prediction.kind), backend, prediction.id, None, MatchOutcome.FALSE_POSITIVE, prediction.confidence, {}))
    for truth_block in truth.blocks:
        if truth_block.id not in used_truth:
            records.append(MatchRecord(CalibrationTarget.BLOCK_KIND, _value(truth_block.block_kind), backend, None, truth_block.id, MatchOutcome.FALSE_NEGATIVE, None, {}))
    return records


def _metadata_match(prediction: EntityProposal, truth_entity: TruthEntity) -> float | None:
    pred_equation = prediction.metadata.get("equation_number")
    truth_equation = truth_entity.metadata.get("equation_number")
    if pred_equation is not None and truth_equation is not None and str(pred_equation) == str(truth_equation):
        return 1.0

    pred_marker = prediction.metadata.get("marker")
    truth_marker = truth_entity.metadata.get("marker")
    if pred_marker is not None and truth_marker is not None and str(pred_marker) == str(truth_marker):
        return 1.0

    pred_caption_number = prediction.metadata.get("caption_number")
    truth_caption_number = truth_entity.metadata.get("caption_number")
    pred_caption_kind = prediction.metadata.get("caption_kind")
    truth_caption_kind = truth_entity.metadata.get("caption_kind")
    if (
        pred_caption_number is not None
        and truth_caption_number is not None
        and pred_caption_kind is not None
        and truth_caption_kind is not None
        and str(pred_caption_number) == str(truth_caption_number)
        and str(pred_caption_kind) == str(truth_caption_kind)
    ):
        return 1.0
    return None


def _entity_score(prediction: EntityProposal, truth_entity: TruthEntity) -> float:
    meta = _metadata_match(prediction, truth_entity)
    if meta is not None:
        return meta
    if normalise_text(prediction.canonical_text) == normalise_text(truth_entity.canonical_text):
        return 1.0
    return token_overlap(prediction.canonical_text, truth_entity.canonical_text)


def _entity_match_map(predictions: EntityProposalDocument, truth: CalibrationTruthDocument) -> dict[str, str]:
    candidates: list[tuple[float, str, EntityProposal, TruthEntity]] = []
    for prediction in predictions.entities:
        for truth_entity in truth.entities:
            if _value(prediction.entity_type) != _value(truth_entity.entity_type):
                continue
            if _value(prediction.entity_type) == "page_number":
                if prediction.page_no != truth_entity.page_no:
                    continue
                if normalise_text(prediction.canonical_text) != normalise_text(truth_entity.canonical_text):
                    continue
            if prediction.page_no is not None and truth_entity.page_no is not None and prediction.page_no != truth_entity.page_no:
                continue
            score = _entity_score(prediction, truth_entity)
            if score >= 0.75:
                candidates.append((score, truth_entity.id, prediction, truth_entity))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2].id))
    mapping: dict[str, str] = {}
    used_truth: set[str] = set()
    for _, _, prediction, truth_entity in candidates:
        if prediction.id in mapping or truth_entity.id in used_truth:
            continue
        mapping[prediction.id] = truth_entity.id
        used_truth.add(truth_entity.id)
    return mapping


def match_entities(*, backend: str, predictions: EntityProposalDocument, truth: CalibrationTruthDocument) -> list[MatchRecord]:
    """Match predicted entities to truth entities and emit per-entity records.

    Entities must share an entity type and (when known) a page number;
    page-number entities additionally require canonical-text equality.
    Beyond exact metadata signals (equation/caption numbers, markers),
    matching falls back to canonical-text token overlap with a threshold of
    ``0.75``. Each matched prediction emits both an ``ENTITY_TYPE`` record
    and, if it carries a ``calibration_key``, an extra
    ``CALIBRATION_KEY`` record. Unmatched truth entities emit false
    negatives.

    Args:
        backend: Backend name to attach to every emitted record.
        predictions: Backend's entity proposal document.
        truth: Ground-truth document.

    Returns:
        One ``MatchRecord`` per outcome, possibly with paired records for
        entries that carry a calibration key.
    """
    mapping = _entity_match_map(predictions, truth)
    used_truth = set(mapping.values())
    records: list[MatchRecord] = []
    for prediction in predictions.entities:
        outcome = MatchOutcome.TRUE_POSITIVE if prediction.id in mapping else MatchOutcome.FALSE_POSITIVE
        truth_id = mapping.get(prediction.id)
        records.append(MatchRecord(CalibrationTarget.ENTITY_TYPE, _value(prediction.entity_type), backend, prediction.id, truth_id, outcome, prediction.confidence, {}))
        if prediction.calibration_key:
            records.append(MatchRecord(CalibrationTarget.CALIBRATION_KEY, prediction.calibration_key, backend, prediction.id, truth_id, outcome, prediction.confidence, {"entity_type": _value(prediction.entity_type)}))
    for truth_entity in truth.entities:
        if truth_entity.id not in used_truth:
            records.append(MatchRecord(CalibrationTarget.ENTITY_TYPE, _value(truth_entity.entity_type), backend, None, truth_entity.id, MatchOutcome.FALSE_NEGATIVE, None, {}))
    return records


def match_relations(*, backend: str, predictions: EntityProposalDocument, truth: CalibrationTruthDocument) -> list[MatchRecord]:
    """Match predicted relations to truth relations via their entity mapping.

    A predicted relation matches a truth relation when the relation type, the
    truth ids of the resolved source entity, and the resolved target entity
    all agree. Predictions whose source or target entity did not match a
    truth entity are still emitted as false positives but tagged with a
    ``warning`` metadata flag. Unmatched truth relations emit false
    negatives.

    Args:
        backend: Backend name to attach to every emitted record.
        predictions: Backend's entity proposal document (carries relations).
        truth: Ground-truth document.

    Returns:
        One ``MatchRecord`` per outcome for the ``RELATION_TYPE`` calibration
        target.
    """
    entity_mapping = _entity_match_map(predictions, truth)
    records: list[MatchRecord] = []
    truth_by_key: dict[tuple[str, str | None, str | None], TruthRelation] = {
        (_value(rel.relation_type), rel.source_truth_id, rel.target_truth_id): rel for rel in truth.relations
    }
    used_truth: set[str] = set()
    for relation in predictions.relations:
        source_truth = entity_mapping.get(relation.source_entity_id)
        target_truth = entity_mapping.get(relation.target_entity_id)
        key_tuple: tuple[str, str | None, str | None] = (_value(relation.relation_type), source_truth, target_truth)
        truth_relation = truth_by_key.get(key_tuple)
        if truth_relation is None or truth_relation.id in used_truth:
            metadata: dict[str, str] = {}
            if source_truth is None or target_truth is None:
                metadata["warning"] = "relation_matching_without_entity_matches"
            records.append(MatchRecord(CalibrationTarget.RELATION_TYPE, _value(relation.relation_type), backend, relation.id, None, MatchOutcome.FALSE_POSITIVE, relation.confidence, metadata))
        else:
            used_truth.add(truth_relation.id)
            records.append(MatchRecord(CalibrationTarget.RELATION_TYPE, _value(relation.relation_type), backend, relation.id, truth_relation.id, MatchOutcome.TRUE_POSITIVE, relation.confidence, {}))
    for truth_rel in truth.relations:
        if truth_rel.id not in used_truth:
            records.append(MatchRecord(CalibrationTarget.RELATION_TYPE, _value(truth_rel.relation_type), backend, None, truth_rel.id, MatchOutcome.FALSE_NEGATIVE, None, {}))
    return records
