from pdf2md.models.cross_ref import RefMarker, RefType
from pdf2md.models.entities import (
    ConfidenceSource,
    EntityEvidence,
    EntityProposal,
    EntityProposalDocument,
    EntityType,
    EvidenceKind,
    entity_id,
)
from pdf2md.semantic.candidates import entities_to_candidates
from pdf2md.semantic.resolver import resolve_markers


def _proposal(entity_type: EntityType, number: str, canonical_text: str, *, index: int = 1) -> EntityProposal:
    block_id = f"mineru:doc:p1:b{index}"
    return EntityProposal(
        id=entity_id("mineru", "doc", entity_type, index),
        entity_type=entity_type,
        canonical_text=canonical_text,
        page_no=1,
        block_ids=[block_id],
        confidence=0.75,
        confidence_source=ConfidenceSource.HEURISTIC,
        evidence=[
            EntityEvidence(
                kind=EvidenceKind.BLOCK_TEXT,
                page_no=1,
                source_block_id=block_id,
                raw_ref="output.md",
                text=canonical_text,
                weight=1.0,
                reason="theorem_family_detector",
            )
        ],
        calibration_key=f"mineru:{entity_type.value}:theorem_family_detector",
        metadata={
            "detector": "theorem_family_detector",
            "theorem_number": number,
            "theorem_kind": entity_type.value.title(),
        },
    )


def _document(proposal: EntityProposal) -> EntityProposalDocument:
    return EntityProposalDocument(
        document_id="doc",
        backend="mineru",
        backend_version=None,
        page_count=1,
        entities=[proposal],
        relations=[],
        warnings=[],
        metadata={},
    )


def _marker(marker_type: RefType, marker_text: str) -> RefMarker:
    return RefMarker(
        source_ref="#/texts/1",
        marker_text=marker_text,
        marker_type=marker_type,
        char_offset=(0, len(marker_text)),
        confidence=1.0,
        backend="regex",
    )


def _assert_roundtrip(
    entity_type: EntityType,
    ref_type: RefType,
    number: str,
    canonical_text: str,
    expected_label: str,
    marker_text: str,
) -> None:
    proposal = _proposal(entity_type, number, canonical_text)
    candidates = entities_to_candidates(_document(proposal))

    assert len(candidates) == 1
    assert candidates[0].entity_type == ref_type
    assert candidates[0].label == expected_label
    assert candidates[0].numbering == number

    edges = resolve_markers([_marker(ref_type, marker_text)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == proposal.id
    assert edges[0].resolution_method == "exact"


def test_theorem_family_entities_roundtrip_through_candidates_and_resolver() -> None:
    cases = [
        (EntityType.THEOREM, RefType.THEOREM, "3.2", "Theorem 3.2. Let X...", "Theorem 3.2", "Theorem 3.2"),
        (EntityType.DEFINITION, RefType.DEFINITION, "1", "Definition 1. A space...", "Definition 1", "Definition 1"),
        (EntityType.COROLLARY, RefType.COROLLARY, "3.2", "Corollary 3.2. It follows...", "Corollary 3.2", "Corollary 3.2"),
        (EntityType.PROOF, RefType.PROOF, "3", "Proof of Theorem 3. We proceed...", "Proof 3", "Proof of Theorem 3"),
        (EntityType.EXAMPLE, RefType.EXAMPLE, "4", "Example 4. Consider...", "Example 4", "Example 4"),
    ]
    for case in cases:
        _assert_roundtrip(*case)


def test_theorem_family_cross_type_isolation() -> None:
    proposal = _proposal(EntityType.THEOREM, "3.2", "Theorem 3.2. Let X...")
    candidates = entities_to_candidates(_document(proposal))

    edges = resolve_markers([_marker(RefType.DEFINITION, "Definition 3.2")], candidates)

    assert edges[0].resolved is False
    assert edges[0].target_ref is None
    assert edges[0].resolution_method == "unresolved"
