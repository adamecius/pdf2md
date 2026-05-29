"""Rule-based document-class classifier.

Inspects an :class:`EntityProposalDocument` (with its supporting
:class:`PageExtractionIR` list) and tags the document as one of:

* ``article`` — single contribution, ≤ ~50 pages, one bibliography,
  no chapters, no index, no glossary.
* ``book`` — multi-chapter, often ≥ ~50 pages, may have an index
  and/or glossary, may have a per-chapter bibliography.
* ``document`` — anything else (reports, notes, manuals, slides
  exported to PDF, …) — the catch-all when we don't have a clean
  match for ``article`` or ``book``.

Why rule-based: deterministic, fast (single pass over the entity
list), inspectable. If accuracy is insufficient on real fixtures, a
future plan can train an ML classifier on labelled data and swap in
:func:`classify_document`'s implementation.

Downstream consumers (the ensemble mixer in
:mod:`pdf2md.semantic.ensemble`, per-backend adapters, the resolver)
read the result from ``EntityProposalDocument.metadata["document_class"]``
and adapt their behaviour — e.g. the ensemble down-weights GROBID on
``book``-class inputs because GROBID is article-trained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pdf2md.models.entities import EntityProposalDocument, EntityType
from pdf2md.models.ir import PageExtractionIR

# Decision-tree thresholds. Each is exported so callers can override
# for fixture-specific testing without code surgery.

#: A document with this many CHAPTER entities is almost certainly a book.
CHAPTER_HIGH_THRESHOLD: int = 3

#: A document with ≥1 chapter AND this many pages is likely a book.
PAGE_COUNT_BOOK_THRESHOLD: int = 50

#: An article's typical maximum length. Above this, we lean book-ish
#: even when chapter count is low.
PAGE_COUNT_ARTICLE_THRESHOLD: int = 30

#: An article with a single ``References`` section under this page
#: count gets the high-confidence ``article`` classification.
PAGE_COUNT_ARTICLE_PERMISSIVE: int = 50


class DocumentClass(str, Enum):
    """Canonical document classes used across the semantic layer."""

    ARTICLE = "article"
    BOOK = "book"
    DOCUMENT = "document"


@dataclass(frozen=True)
class DocumentClassification:
    """Result of a single classify_document call.

    Attributes:
        document_class: One of :class:`DocumentClass`.
        confidence: Classifier confidence in ``[0.0, 1.0]``.
        features: Raw signals that drove the decision, for audits.
    """

    document_class: DocumentClass
    confidence: float
    features: dict[str, Any] = field(default_factory=dict)


def _entity_type_value(et: Any) -> str:
    """Return the entity_type as a plain string regardless of pydantic mode."""
    return et.value if hasattr(et, "value") else str(et)


def _count_by_type(proposals: EntityProposalDocument) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity in proposals.entities:
        et = _entity_type_value(entity.entity_type)
        counts[et] = counts.get(et, 0) + 1
    return counts


def _gather_features(
    proposals: EntityProposalDocument,
    pages: list[PageExtractionIR],
) -> dict[str, Any]:
    counts = _count_by_type(proposals)
    chapters = counts.get(EntityType.CHAPTER.value, 0)
    sections = counts.get(EntityType.SECTION.value, 0)
    ref_sections = counts.get(EntityType.REFERENCE_SECTION.value, 0)
    index_sections = counts.get(EntityType.INDEX_SECTION.value, 0)
    glossary_sections = counts.get(EntityType.GLOSSARY_SECTION.value, 0)
    page_count = len(pages) if pages else (proposals.page_count or 0)

    # Heading hierarchy — H1 count vs deeper.
    h1_count = 0
    deep_heading_count = 0
    for entity in proposals.entities:
        if _entity_type_value(entity.entity_type) != EntityType.SECTION.value:
            continue
        level = entity.metadata.get("heading_level")
        if isinstance(level, int):
            if level == 1:
                h1_count += 1
            elif level >= 2:
                deep_heading_count += 1

    return {
        "page_count": page_count,
        "chapter_count": chapters,
        "section_count": sections,
        "reference_section_count": ref_sections,
        "index_section_count": index_sections,
        "glossary_section_count": glossary_sections,
        "h1_count": h1_count,
        "deep_heading_count": deep_heading_count,
    }


def classify_document(
    proposals: EntityProposalDocument,
    pages: list[PageExtractionIR],
) -> DocumentClassification:
    """Classify a document as :class:`DocumentClass`.

    Args:
        proposals: Entity proposals from :func:`recognize_entities`.
        pages: The per-page IR list. May be empty; in that case
            ``proposals.page_count`` is used.

    Returns:
        A :class:`DocumentClassification` with the class, a confidence
        in ``[0.0, 1.0]``, and the raw feature dictionary that drove
        the decision (useful for audits and threshold tuning).
    """
    features = _gather_features(proposals, pages)

    # Strongest signal: presence of an Index or Glossary section. A
    # document with these is almost always a book by any working
    # definition. Plan 6 emits these from the connector layer.
    if features["index_section_count"] > 0 or features["glossary_section_count"] > 0:
        return DocumentClassification(
            DocumentClass.BOOK,
            confidence=0.95,
            features=features,
        )

    # Multiple chapters → book.
    if features["chapter_count"] >= CHAPTER_HIGH_THRESHOLD:
        return DocumentClassification(
            DocumentClass.BOOK,
            confidence=0.85,
            features=features,
        )

    # Page count + chapter signal → likely book.
    if (
        features["page_count"] >= PAGE_COUNT_BOOK_THRESHOLD
        and features["chapter_count"] >= 1
    ):
        return DocumentClassification(
            DocumentClass.BOOK,
            confidence=0.70,
            features=features,
        )

    # Short with a single References section → article.
    if (
        features["reference_section_count"] == 1
        and features["page_count"] <= PAGE_COUNT_ARTICLE_THRESHOLD
    ):
        return DocumentClassification(
            DocumentClass.ARTICLE,
            confidence=0.85,
            features=features,
        )

    # Article-shaped with permissive page count.
    if (
        features["reference_section_count"] >= 1
        and features["page_count"] <= PAGE_COUNT_ARTICLE_PERMISSIVE
    ):
        return DocumentClassification(
            DocumentClass.ARTICLE,
            confidence=0.70,
            features=features,
        )

    # Default — not enough signal.
    return DocumentClassification(
        DocumentClass.DOCUMENT,
        confidence=0.50,
        features=features,
    )
