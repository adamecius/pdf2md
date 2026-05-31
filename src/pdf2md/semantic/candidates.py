"""OCR ``EntityProposalDocument`` → semantic ``ResolverCandidate`` bridge.

The connectors under ``backend/<name>/`` produce an
:class:`pdf2md.models.entities.EntityProposalDocument` — a flat list of
``EntityProposal`` objects with stable IDs, page numbers, and
heuristic metadata (caption numbers, equation numbers, footnote
markers, etc.).

The semantic-layer resolver
(:func:`pdf2md.semantic.resolver.resolve_markers`) consumes
:class:`pdf2md.semantic.resolver.ResolverCandidate` objects with a
``target_ref`` + ``entity_type`` + ``label`` shape.

This module is the bridge — it lets a GROBID-derived marker like
``"Figure 3.2"`` resolve to the OCR-detected caption entity whose
``caption_number == "3.2"`` on the same document, without coupling the
connector code to the semantic-layer schema.

Designed to be **book-friendly**:

- Preserves chapter-relative numbering (``"3.2"`` stays ``"3.2"``).
- Surfaces ``EntityType.CHAPTER`` as ``RefType.CHAPTER`` candidates so
  ``"Chapter 5"`` markers can resolve.
- Falls back to the canonical text when a structured number is absent
  (gracefully degrades on documents without explicit numbering).
"""

from __future__ import annotations

import re

from pdf2md.models.cross_ref import RefType
from pdf2md.models.entities import EntityProposal, EntityProposalDocument, EntityType
from pdf2md.semantic.resolver import ResolverCandidate

# Map OCR entity types to semantic RefTypes. Captions are special-cased
# (the EntityProposal's ``caption_kind`` metadata decides FIGURE vs
# TABLE), so they're not in this map directly.
_ENTITY_TYPE_TO_REF_TYPE: dict[str, RefType] = {
    EntityType.CHAPTER.value: RefType.CHAPTER,
    EntityType.SECTION.value: RefType.SECTION,
    EntityType.FIGURE.value: RefType.FIGURE,
    EntityType.TABLE.value: RefType.TABLE,
    EntityType.EQUATION.value: RefType.EQUATION,
    EntityType.THEOREM.value: RefType.THEOREM,
    EntityType.DEFINITION.value: RefType.DEFINITION,
    EntityType.COROLLARY.value: RefType.COROLLARY,
    EntityType.PROOF.value: RefType.PROOF,
    EntityType.EXAMPLE.value: RefType.EXAMPLE,
    EntityType.FOOTNOTE.value: RefType.FOOTNOTE,
    EntityType.REFERENCE_ITEM.value: RefType.BIBLIOGRAPHY,
    EntityType.BIBLIOGRAPHY_MARKER.value: RefType.BIBLIOGRAPHY,
}


def _figure_or_table_label(proposal: EntityProposal) -> tuple[RefType, str] | None:
    """Resolve a CAPTION proposal into a typed FIGURE/TABLE candidate.

    Returns ``None`` when neither ``caption_kind`` nor a usable label is
    available (the caption is too ambiguous to count as a candidate).
    """
    md = proposal.metadata or {}
    caption_kind = (md.get("caption_kind") or "").lower()
    caption_number = md.get("caption_number")
    ref_type = RefType.TABLE if caption_kind == "table" else RefType.FIGURE
    surface = "Table" if ref_type is RefType.TABLE else "Figure"
    if caption_number:
        return ref_type, f"{surface} {caption_number}"
    canonical = (proposal.canonical_text or "").strip()
    if canonical:
        return ref_type, canonical
    return None


def _section_or_chapter_label(proposal: EntityProposal, ref_type: RefType) -> str:
    """Build a label like ``"Chapter 5"`` / ``"Section 3.2"`` or fall back.

    Uses the detector's parsed ``chapter_number`` / ``numbering`` when
    present; otherwise returns the heading's canonical text so the
    resolver's fuzzy matcher can still operate on the surface form.
    """
    md = proposal.metadata or {}
    number = md.get("chapter_number") or md.get("numbering")
    canonical = (proposal.canonical_text or "").strip()
    if ref_type is RefType.CHAPTER:
        if number:
            return f"Chapter {number}"
        return canonical or "Chapter"
    # SECTION
    if number:
        return f"Section {number}"
    return canonical or "Section"


def _equation_label(proposal: EntityProposal) -> str | None:
    md = proposal.metadata or {}
    number = md.get("equation_number")
    if not number:
        return None
    return f"({number})"


def _footnote_label(proposal: EntityProposal) -> str | None:
    md = proposal.metadata or {}
    marker = md.get("marker")
    if marker:
        return str(marker)
    canonical = (proposal.canonical_text or "").strip()
    return canonical or None


def _theorem_label(proposal: EntityProposal) -> str | None:
    """Build a theorem-family label from detector metadata.

    Numbered theorem-family entities use the canonical semantic prefix
    for their mapped RefType (for example, lemmas and propositions are
    surfaced as ``Theorem N`` candidates). Unnumbered environments keep
    enough canonical text for fuzzy fallback without bloating candidate
    labels.
    """
    md = proposal.metadata or {}
    number = md.get("theorem_number")
    entity_type_str = (
        proposal.entity_type.value
        if hasattr(proposal.entity_type, "value")
        else str(proposal.entity_type)
    )
    kind = {
        EntityType.THEOREM.value: "Theorem",
        EntityType.DEFINITION.value: "Definition",
        EntityType.COROLLARY.value: "Corollary",
        EntityType.PROOF.value: "Proof",
        EntityType.EXAMPLE.value: "Example",
    }.get(entity_type_str)
    if kind is not None and number:
        return f"{kind} {number}"
    canonical = (proposal.canonical_text or "").strip()
    if not canonical:
        return None
    sentence = re.split(r"(?<=[.!?])\s+", canonical, maxsplit=1)[0].strip()
    return (sentence or canonical)[:80].rstrip() or None


def _bibliography_label(proposal: EntityProposal) -> str | None:
    """Bibliography candidates: prefer the marker number, else canonical text.

    The resolver's ``_try_bibliography`` strategy extracts a number from
    a ``"[15]"``-style marker and matches against any candidate whose
    label CONTAINS that number — so a label of just ``"15"`` works, but
    so does the full bib entry text. We send the marker number when we
    have it (more selective), otherwise the full text (gracefully
    degrades).
    """
    md = proposal.metadata or {}
    marker = md.get("marker")
    if marker:
        return str(marker)
    canonical = (proposal.canonical_text or "").strip()
    return canonical or None


def _candidate_for(proposal: EntityProposal) -> ResolverCandidate | None:
    """Build a :class:`ResolverCandidate` for one OCR entity proposal.

    Returns ``None`` when the entity has no semantic-layer counterpart
    (e.g. PAGE_NUMBER, HEADER, FOOTER, TOC_ENTRY, REFERENCE_SECTION,
    UNKNOWN — all useful for layout/structure but not as resolver
    targets).
    """
    entity_type_str = (
        proposal.entity_type.value
        if hasattr(proposal.entity_type, "value")
        else str(proposal.entity_type)
    )

    if entity_type_str == EntityType.CAPTION.value:
        caption_result = _figure_or_table_label(proposal)
        if caption_result is None:
            return None
        cap_ref_type, cap_label = caption_result
        # Captions: the caption_number metadata IS the authoritative
        # numbering for the figure/table — surface it so the fuzzy
        # resolver doesn't fall back to digit-scraping.
        cap_md = proposal.metadata or {}
        cap_numbering = str(cap_md["caption_number"]) if cap_md.get("caption_number") else None
        return ResolverCandidate(
            target_ref=proposal.id,
            entity_type=cap_ref_type,
            label=cap_label,
            numbering=cap_numbering,
        )

    looked_up = _ENTITY_TYPE_TO_REF_TYPE.get(entity_type_str)
    if looked_up is None:
        return None
    ref_type: RefType = looked_up
    # Chapter → Section downcast: when the OCR / VLM tagged a heading
    # as CHAPTER but its canonical text starts with a dotted number
    # (``1.6 Electronic Structure ...``), it's really a section, not
    # a chapter. The book-fixture (example3) has ~90 such mis-tagged
    # entries — downcasting here lets ``Section 1.6`` markers
    # resolve against them. Top-level numbering (``1 Overview``)
    # stays as a chapter.
    if ref_type is RefType.CHAPTER:
        canonical = (proposal.canonical_text or "").strip()
        if re.match(r"^\d+\.\d", canonical):
            ref_type = RefType.SECTION
    label: str | None
    if ref_type in (RefType.CHAPTER, RefType.SECTION):
        label = _section_or_chapter_label(proposal, ref_type)
    elif ref_type is RefType.EQUATION:
        label = _equation_label(proposal)
        if label is None:
            return None
    elif ref_type is RefType.FOOTNOTE:
        label = _footnote_label(proposal)
        if label is None:
            return None
    elif ref_type is RefType.BIBLIOGRAPHY:
        label = _bibliography_label(proposal)
        if label is None:
            return None
    elif ref_type in (
        RefType.THEOREM,
        RefType.DEFINITION,
        RefType.COROLLARY,
        RefType.PROOF,
        RefType.EXAMPLE,
    ):
        label = _theorem_label(proposal)
        if label is None:
            return None
    elif ref_type in (RefType.FIGURE, RefType.TABLE):
        # Bare FIGURE/TABLE entities (not their captions) — use canonical text.
        label = (proposal.canonical_text or "").strip()
        if not label:
            return None
    else:
        label = (proposal.canonical_text or "").strip()
        if not label:
            return None

    # Pull the authoritative numbering off the proposal when the
    # detector wrote one. The fuzzy resolver uses this in preference
    # to scraping digits out of arbitrary trailing text (which was
    # the source of the ``Section 3 → APPENDIX G PROOF OF PROPOSITION 3``
    # wrong-resolution class).
    md_n = proposal.metadata or {}
    numbering: str | None
    if ref_type is RefType.CHAPTER:
        numbering = md_n.get("chapter_number") or md_n.get("numbering")
    elif ref_type is RefType.SECTION:
        numbering = md_n.get("numbering")
    elif ref_type is RefType.EQUATION:
        numbering = md_n.get("equation_number")
    elif ref_type is RefType.FOOTNOTE:
        numbering = md_n.get("marker")
    elif ref_type is RefType.BIBLIOGRAPHY:
        numbering = md_n.get("marker")
    elif ref_type in (
        RefType.THEOREM,
        RefType.DEFINITION,
        RefType.COROLLARY,
        RefType.PROOF,
        RefType.EXAMPLE,
    ):
        numbering = md_n.get("theorem_number")
    else:
        numbering = None
    return ResolverCandidate(
        target_ref=proposal.id,
        entity_type=ref_type,
        label=label,
        numbering=str(numbering) if numbering is not None else None,
    )


def entities_to_candidates(
    proposals: EntityProposalDocument,
) -> list[ResolverCandidate]:
    """Convert an :class:`EntityProposalDocument` to resolver candidates.

    Filters out entity types that have no semantic-layer counterpart
    (HEADER, FOOTER, PAGE_NUMBER, TOC_ENTRY, REFERENCE_SECTION,
    DOCUMENT_TITLE, UNKNOWN) and builds ``ResolverCandidate`` objects
    for the rest, with book-friendly labels.

    Args:
        proposals: The OCR-side entity proposals (one connector's
            output, or a merged document from
            ``consensus.merge_entity_documents`` upstream).

    Returns:
        A list of :class:`ResolverCandidate` ready to pass to
        :func:`pdf2md.semantic.resolver.resolve_markers`.
    """
    out: list[ResolverCandidate] = []
    for proposal in proposals.entities:
        cand = _candidate_for(proposal)
        if cand is not None:
            out.append(cand)
    return out


__all__ = ["entities_to_candidates"]
