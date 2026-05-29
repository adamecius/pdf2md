"""Entity-level OCR consensus.

Plan 13's :func:`build_consensus_ir` produces a block-level
:class:`ConsensusIR` — useful for picking the canonical block layout
across backends but at a different abstraction than the
:class:`EntityProposalDocument` the semantic-layer resolver bridge
expects.

This module fills that gap: it merges entities (figures, captions,
equations, reference items, sections, …) from multiple
:class:`EntityProposalDocument`s into a single canonical
"consensus" document by deduplicating on per-type identity keys and
keeping the highest-confidence candidate.

Used by the webui pipeline (Additional Plan 8) so the OCR dropdown
can expose a fourth ``consensus`` option alongside the individual
``deepseek`` / ``mineru`` / ``paddleocr`` choices.
"""

from __future__ import annotations

from typing import Any

from pdf2md.models.entities import (
    EntityProposal,
    EntityProposalDocument,
    EntityType,
    entity_id,
)

CONSENSUS_BACKEND: str = "consensus"


def _entity_type_value(et: Any) -> str:
    return et.value if hasattr(et, "value") else str(et)


def _identity_key(entity: EntityProposal) -> tuple[str, ...] | None:
    """Return a dedup key for ``entity``, or ``None`` to skip dedup.

    Keys are deliberately per-type — every entity carries different
    "identity" semantics:

    * REFERENCE_ITEM: by ``marker`` (the ``[N]`` number)
    * EQUATION: by ``equation_number`` if present
    * CAPTION: by ``(caption_kind, caption_number)`` if present
    * SECTION / CHAPTER: by lowercase ``canonical_text``
    * INDEX_ENTRY / GLOSSARY_ENTRY: by lowercase ``index_term`` /
      ``glossary_term``
    * FIGURE / TABLE: ``None`` — no canonical identity at this level
      (different OCRs may detect the same picture in slightly different
      positions; we keep all proposals from all backends).
    """
    et = _entity_type_value(entity.entity_type)
    md = entity.metadata or {}
    if et == EntityType.REFERENCE_ITEM.value:
        marker = md.get("marker")
        if marker is not None:
            return (et, str(marker))
    elif et == EntityType.EQUATION.value:
        num = md.get("equation_number")
        if num is not None:
            return (et, str(num))
    elif et == EntityType.CAPTION.value:
        kind = md.get("caption_kind")
        num = md.get("caption_number")
        if kind and num:
            return (et, str(kind), str(num))
    elif et in {EntityType.SECTION.value, EntityType.CHAPTER.value}:
        text = (entity.canonical_text or "").lower().strip()
        if text:
            return (et, text)
    elif et == EntityType.INDEX_ENTRY.value:
        term = md.get("index_term")
        if term:
            return (et, str(term).lower().strip())
    elif et == EntityType.GLOSSARY_ENTRY.value:
        term = md.get("glossary_term")
        if term:
            return (et, str(term).lower().strip())
    elif et == EntityType.REFERENCE_SECTION.value:
        return (et,)  # at most one per document
    elif et == EntityType.INDEX_SECTION.value or et == EntityType.GLOSSARY_SECTION.value:
        return (et,)
    # FIGURE / TABLE / PAGE_NUMBER / HEADER / FOOTER / FOOTNOTE /
    # TOC_ENTRY / DOCUMENT_TITLE / UNKNOWN: keep every proposal.
    return None


def merge_entity_documents(
    documents: list[EntityProposalDocument],
    *,
    document_id: str,
) -> EntityProposalDocument:
    """Merge per-OCR entity proposals into a single consensus document.

    Strategy:

    1. For each entity, compute an :func:`_identity_key`.
    2. Entities with a key are bucketed; for each bucket the
       highest-confidence proposal wins, and the source backend(s)
       are recorded in ``metadata.merged_from_backends`` so audits can
       see where the consensus pick came from.
    3. Entities without a key (no canonical identity at this level,
       e.g. FIGURE / TABLE) are kept verbatim — every backend's
       proposal is included.
    4. All surviving entities are reminted with
       ``backend=consensus`` ids so the downstream resolver bridge
       can attribute them correctly.

    Args:
        documents: Per-OCR entity proposal documents to merge. Must be
            non-empty; documents whose backend is ``"consensus"`` are
            silently ignored (avoids accidental recursive merges).
        document_id: Stable document identifier used in the new ids
            and recorded on the result.

    Returns:
        A fresh :class:`EntityProposalDocument` with ``backend="consensus"``,
        merged entities, no relations (relations are per-backend and
        not currently merged), and a ``metadata.merged_backends`` list
        recording which backends contributed.

    Raises:
        ValueError: If ``documents`` is empty after filtering.
    """
    inputs = [d for d in documents if d.backend != CONSENSUS_BACKEND]
    if not inputs:
        raise ValueError("merge_entity_documents requires at least one non-consensus document")

    # Bucket entities by dedup key. Within each bucket the
    # highest-confidence proposal wins; ties broken by insertion
    # order (which equals input-list order).
    keyed_best: dict[tuple[str, ...], tuple[EntityProposal, set[str]]] = {}
    unkeyed: list[tuple[EntityProposal, str]] = []
    for doc in inputs:
        for proposal in doc.entities:
            key = _identity_key(proposal)
            if key is None:
                unkeyed.append((proposal, doc.backend))
                continue
            existing = keyed_best.get(key)
            if existing is None or proposal.confidence > existing[0].confidence:
                contributors = (existing[1] if existing else set()) | {doc.backend}
                keyed_best[key] = (proposal, contributors)
            else:
                existing[1].add(doc.backend)

    # Rebuild entities with consensus-attributed ids and merged-from
    # metadata.
    out: list[EntityProposal] = []
    idx = 0
    for proposal, contributors in keyed_best.values():
        idx += 1
        et = _entity_type_value(proposal.entity_type)
        md = {
            **(proposal.metadata or {}),
            "merged_from_backends": sorted(contributors),
            "original_backend": proposal.id.split(":")[1] if ":" in proposal.id else None,
        }
        out.append(
            proposal.model_copy(
                update={
                    "id": entity_id(CONSENSUS_BACKEND, document_id, et, idx),
                    "metadata": md,
                    "calibration_key": f"{CONSENSUS_BACKEND}:{et}:{md.get('detector', 'consensus')}",
                }
            )
        )
    for proposal, source_backend in unkeyed:
        idx += 1
        et = _entity_type_value(proposal.entity_type)
        md = {
            **(proposal.metadata or {}),
            "merged_from_backends": [source_backend],
            "original_backend": source_backend,
        }
        out.append(
            proposal.model_copy(
                update={
                    "id": entity_id(CONSENSUS_BACKEND, document_id, et, idx),
                    "metadata": md,
                    "calibration_key": f"{CONSENSUS_BACKEND}:{et}:{md.get('detector', 'consensus')}",
                }
            )
        )

    contributors_total = sorted({d.backend for d in inputs})
    page_count = max((d.page_count or 0) for d in inputs)
    warnings: list[str] = []
    for d in inputs:
        warnings.extend(d.warnings)

    # Carry the document-class hint from the first input that has one
    # (all OCRs read the same source so the class shouldn't differ —
    # but if it does, the first non-None wins for determinism).
    doc_class: str | None = None
    doc_class_conf: float | None = None
    doc_class_features: dict[str, Any] | None = None
    for d in inputs:
        if d.metadata.get("document_class") and doc_class is None:
            doc_class = d.metadata["document_class"]
            doc_class_conf = d.metadata.get("document_class_confidence")
            doc_class_features = d.metadata.get("document_class_features")

    metadata: dict[str, Any] = {
        "connector": "consensus_entity_merge",
        "merged_backends": contributors_total,
    }
    if doc_class is not None:
        metadata["document_class"] = doc_class
        metadata["document_class_confidence"] = doc_class_conf
        metadata["document_class_features"] = doc_class_features

    return EntityProposalDocument(
        document_id=document_id,
        backend=CONSENSUS_BACKEND,
        backend_version=None,
        page_count=page_count,
        entities=out,
        relations=[],
        warnings=warnings,
        metadata=metadata,
    )


__all__ = ["CONSENSUS_BACKEND", "merge_entity_documents"]
