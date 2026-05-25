"""Tests for entity-level OCR consensus (Plan 8).

Covers :func:`pdf2md.consensus.merge_entity_documents`:

* highest-confidence wins per dedup key
* merged_from_backends metadata records all contributors
* entities with no canonical identity (FIGURE, TABLE) are kept verbatim
* doc-class hint propagates from the first contributing OCR
* ``backend="consensus"`` ids are valid against the schema
* refuses empty input
"""

from __future__ import annotations

import pytest

from pdf2md.consensus import CONSENSUS_BACKEND, merge_entity_documents
from pdf2md.models.entities import (
    ConfidenceSource,
    EntityEvidence,
    EntityProposal,
    EntityProposalDocument,
    EntityType,
    EvidenceKind,
    entity_id,
)


def _ev(page_no: int = 1) -> EntityEvidence:
    return EntityEvidence(
        kind=EvidenceKind.BLOCK_TEXT,
        page_no=page_no,
        source_block_id=None,
        raw_ref="r",
        text="",
        bbox=None,
        weight=1.0,
        reason="d",
        metadata={},
    )


def _ent(
    backend: str,
    doc: str,
    et: EntityType,
    idx: int,
    *,
    confidence: float = 0.5,
    canonical_text: str = "",
    metadata: dict | None = None,
    page_no: int = 1,
) -> EntityProposal:
    return EntityProposal(
        id=entity_id(backend, doc, et, idx),
        entity_type=et,
        subtype=None,
        canonical_text=canonical_text,
        page_no=page_no,
        block_ids=[],
        confidence=confidence,
        confidence_source=ConfidenceSource.HEURISTIC,
        evidence=[_ev(page_no)],
        calibration_key=f"{backend}:{et.value}:detector",
        metadata={"detector": "detector", **(metadata or {})},
    )


def _doc(backend: str, doc_id: str, entities, *, metadata=None) -> EntityProposalDocument:
    return EntityProposalDocument(
        document_id=doc_id,
        backend=backend,
        backend_version=None,
        page_count=1,
        entities=entities,
        relations=[],
        warnings=[],
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Highest-confidence-wins dedup
# ---------------------------------------------------------------------------
def test_reference_item_marker_dedup_keeps_highest_confidence() -> None:
    low = _ent(
        "mineru", "d", EntityType.REFERENCE_ITEM, 1,
        confidence=0.6, canonical_text="[1] Smith",
        metadata={"marker": "1"},
    )
    high = _ent(
        "deepseek", "d", EntityType.REFERENCE_ITEM, 1,
        confidence=0.9, canonical_text="[1] Smith, J.",
        metadata={"marker": "1"},
    )
    merged = merge_entity_documents(
        [_doc("mineru", "d", [low]), _doc("deepseek", "d", [high])],
        document_id="d",
    )
    assert len(merged.entities) == 1
    e = merged.entities[0]
    assert e.confidence == 0.9
    assert e.canonical_text == "[1] Smith, J."
    assert sorted(e.metadata["merged_from_backends"]) == ["deepseek", "mineru"]
    assert e.metadata["original_backend"] == "deepseek"


def test_equation_dedup_by_equation_number() -> None:
    a = _ent(
        "mineru", "d", EntityType.EQUATION, 1, confidence=0.5,
        metadata={"equation_number": "11"},
    )
    b = _ent(
        "deepseek", "d", EntityType.EQUATION, 1, confidence=0.8,
        metadata={"equation_number": "11"},
    )
    c = _ent(
        "deepseek", "d", EntityType.EQUATION, 2, confidence=0.7,
        metadata={"equation_number": "12"},
    )
    merged = merge_entity_documents(
        [_doc("mineru", "d", [a]), _doc("deepseek", "d", [b, c])],
        document_id="d",
    )
    nums = sorted(e.metadata.get("equation_number") for e in merged.entities)
    assert nums == ["11", "12"]


def test_caption_dedup_uses_kind_and_number() -> None:
    fig1 = _ent(
        "mineru", "d", EntityType.CAPTION, 1, confidence=0.6,
        metadata={"caption_kind": "figure", "caption_number": "1"},
    )
    fig1_high = _ent(
        "deepseek", "d", EntityType.CAPTION, 1, confidence=0.85,
        metadata={"caption_kind": "figure", "caption_number": "1"},
    )
    tab1 = _ent(
        "deepseek", "d", EntityType.CAPTION, 2, confidence=0.7,
        metadata={"caption_kind": "table", "caption_number": "1"},
    )
    merged = merge_entity_documents(
        [_doc("mineru", "d", [fig1]), _doc("deepseek", "d", [fig1_high, tab1])],
        document_id="d",
    )
    # Both kept (figure/1 + table/1) since kind distinguishes them.
    assert len(merged.entities) == 2


def test_section_dedup_uses_lowercase_canonical_text() -> None:
    a = _ent(
        "mineru", "d", EntityType.SECTION, 1, confidence=0.5,
        canonical_text="Introduction",
    )
    b = _ent(
        "deepseek", "d", EntityType.SECTION, 1, confidence=0.9,
        canonical_text="INTRODUCTION",
    )
    c = _ent(
        "deepseek", "d", EntityType.SECTION, 2, confidence=0.8,
        canonical_text="Method",
    )
    merged = merge_entity_documents(
        [_doc("mineru", "d", [a]), _doc("deepseek", "d", [b, c])],
        document_id="d",
    )
    assert len(merged.entities) == 2  # Intro + Method


# ---------------------------------------------------------------------------
# No-key types are kept verbatim
# ---------------------------------------------------------------------------
def test_figure_and_table_entities_are_kept_verbatim() -> None:
    fig_a = _ent("mineru", "d", EntityType.FIGURE, 1, confidence=0.7)
    fig_b = _ent("deepseek", "d", EntityType.FIGURE, 1, confidence=0.7)
    tab_c = _ent("paddleocr", "d", EntityType.TABLE, 1, confidence=0.5)
    merged = merge_entity_documents(
        [
            _doc("mineru", "d", [fig_a]),
            _doc("deepseek", "d", [fig_b]),
            _doc("paddleocr", "d", [tab_c]),
        ],
        document_id="d",
    )
    figures = [e for e in merged.entities if e.entity_type == EntityType.FIGURE]
    tables = [e for e in merged.entities if e.entity_type == EntityType.TABLE]
    assert len(figures) == 2  # both kept
    assert len(tables) == 1


# ---------------------------------------------------------------------------
# Result-shape contracts
# ---------------------------------------------------------------------------
def test_backend_is_consensus_and_ids_validate() -> None:
    e = _ent(
        "mineru", "d", EntityType.REFERENCE_ITEM, 1, confidence=0.6,
        metadata={"marker": "1"},
    )
    merged = merge_entity_documents([_doc("mineru", "d", [e])], document_id="d")
    assert merged.backend == CONSENSUS_BACKEND
    for ent in merged.entities:
        # Pydantic validator on EntityProposal.id is the schema check;
        # the model_copy in merge_entity_documents must produce valid
        # ids or construction would have raised.
        assert ent.id.startswith(f"ent:{CONSENSUS_BACKEND}:d:")


def test_document_class_hint_propagates_from_first_source() -> None:
    e = _ent(
        "mineru", "d", EntityType.REFERENCE_ITEM, 1, confidence=0.6,
        metadata={"marker": "1"},
    )
    src = _doc(
        "mineru", "d", [e],
        metadata={
            "document_class": "article",
            "document_class_confidence": 0.85,
            "document_class_features": {"page_count": 8},
        },
    )
    merged = merge_entity_documents([src], document_id="d")
    assert merged.metadata.get("document_class") == "article"
    assert merged.metadata.get("document_class_confidence") == 0.85
    assert merged.metadata.get("document_class_features") == {"page_count": 8}


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError):
        merge_entity_documents([], document_id="d")


def test_consensus_inputs_are_ignored() -> None:
    """Avoids accidental recursive merges."""
    e = _ent(
        "mineru", "d", EntityType.REFERENCE_ITEM, 1, confidence=0.6,
        metadata={"marker": "1"},
    )
    cons = _doc(CONSENSUS_BACKEND, "d", [_ent(CONSENSUS_BACKEND, "d", EntityType.REFERENCE_ITEM, 1)])
    merged = merge_entity_documents(
        [_doc("mineru", "d", [e]), cons], document_id="d",
    )
    # Only mineru's entity contributes.
    assert sorted(merged.metadata["merged_backends"]) == ["mineru"]
