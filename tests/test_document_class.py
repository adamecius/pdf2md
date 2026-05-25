"""Tests for the rule-based document-class classifier (Plan 7).

Coverage:

* Each decision branch in :func:`classify_document` fires on a
  synthetic fixture that matches its criteria.
* ``confidence`` is always in ``[0.0, 1.0]``.
* ``features`` records every signal used in the decision.
* The classifier writes its result into
  ``EntityProposalDocument.metadata`` when called from
  :func:`recognize_entities`.
* Fixture-shaped checks on ``example01`` / ``example02`` cached
  pipeline outputs (skipped when the fixtures are unavailable).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.connectors.common import markdown_to_pages, recognize_entities
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import PageExtractionIR
from pdf2md.semantic.document_class import (
    CHAPTER_HIGH_THRESHOLD,
    DocumentClass,
    DocumentClassification,
    classify_document,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ents(md: str):
    warnings: list[str] = []
    pages = markdown_to_pages(
        md, backend="mineru", backend_version=None,
        document_id="d", raw_ref="r", warnings=warnings,
    )
    doc = recognize_entities(
        pages, backend="mineru", backend_version=None,
        document_id="d", warnings=warnings,
    )
    return pages, doc


def _classify(md: str) -> DocumentClassification:
    pages, doc = _ents(md)
    return classify_document(doc, pages)


# ---------------------------------------------------------------------------
# Decision-branch tests
# ---------------------------------------------------------------------------
def test_index_section_pushes_to_book_with_high_confidence() -> None:
    md = "# Body\n\ntext.\n\f# Index\n\nHall effect, 5, 17\n"
    c = _classify(md)
    assert c.document_class == DocumentClass.BOOK
    assert c.confidence == 0.95


def test_glossary_section_pushes_to_book_with_high_confidence() -> None:
    md = "# Body\n\ntext.\n\f# Glossary\n\nConductivity, 3, 7\n"
    c = _classify(md)
    assert c.document_class == DocumentClass.BOOK
    assert c.confidence == 0.95


def test_three_chapters_classify_as_book() -> None:
    # Three `# Chapter N` headings give chapter_count >= threshold.
    md = "\f".join(
        f"# Chapter {n}\n\nBody of chapter {n}.\n"
        for n in range(1, CHAPTER_HIGH_THRESHOLD + 1)
    )
    c = _classify(md)
    assert c.document_class == DocumentClass.BOOK
    assert c.confidence == 0.85


def test_long_doc_with_one_chapter_classifies_as_book() -> None:
    # A long document (60 pages) with at least one chapter is also book.
    pages_md = "\f".join(["body text"] * 60)
    md = "# Chapter 1\n\nIntroduction.\n\f" + pages_md
    c = _classify(md)
    assert c.document_class == DocumentClass.BOOK
    assert c.confidence == 0.70


def test_short_doc_with_one_references_section_classifies_as_article() -> None:
    md = (
        "# Introduction\n\nbody.\n\f"
        "# Method\n\nbody.\n\f"
        "# References\n\n[1] a\n[2] b\n"
    )
    c = _classify(md)
    assert c.document_class == DocumentClass.ARTICLE
    assert c.confidence == 0.85


def test_mid_length_with_references_classifies_as_article_permissive() -> None:
    # Slightly over the strict-article cap but with the references
    # signal — drops to the permissive article branch (0.70).
    pages = ["body content"] * 35
    pages.append("# References\n\n[1] x\n[2] y\n")
    md = "\f".join(pages)
    c = _classify(md)
    assert c.document_class == DocumentClass.ARTICLE
    assert c.confidence == 0.70


def test_no_signal_falls_through_to_document() -> None:
    md = "Some random text on a single page.\n\nMore prose here.\n"
    c = _classify(md)
    assert c.document_class == DocumentClass.DOCUMENT
    assert c.confidence == 0.50


# ---------------------------------------------------------------------------
# Confidence + features contract
# ---------------------------------------------------------------------------
def test_confidence_in_unit_interval_for_all_branches() -> None:
    fixtures = [
        "# Body\n\nx.\n\f# Index\n\nHall, 5\n",
        "\f".join(f"# Chapter {n}\n\nbody.\n" for n in range(1, 4)),
        "# Intro\n\nbody.\n\f# References\n\n[1] x\n",
        "Random text without any structure.",
    ]
    for md in fixtures:
        c = _classify(md)
        assert 0.0 <= c.confidence <= 1.0


def test_features_dict_records_every_decision_signal() -> None:
    md = "# Body\n\nbody.\n\f# Glossary\n\nHall, 5\n"
    c = _classify(md)
    keys = {
        "page_count",
        "chapter_count",
        "section_count",
        "reference_section_count",
        "index_section_count",
        "glossary_section_count",
        "h1_count",
        "deep_heading_count",
    }
    assert keys.issubset(c.features.keys())


# ---------------------------------------------------------------------------
# Metadata-wiring contract
# ---------------------------------------------------------------------------
def test_recognize_entities_writes_class_to_metadata() -> None:
    md = "# Intro\n\nbody.\n\f# References\n\n[1] a\n"
    _, doc = _ents(md)
    assert doc.metadata.get("document_class") == "article"
    assert isinstance(doc.metadata.get("document_class_confidence"), float)
    assert "document_class_features" in doc.metadata
    feat = doc.metadata["document_class_features"]
    assert isinstance(feat, dict)
    assert "page_count" in feat


# ---------------------------------------------------------------------------
# Fixture-shaped checks (skipped if the cached pipeline output is absent).
# ---------------------------------------------------------------------------
_FIXTURE_ROOT = Path("/home/jgarcia/pdf2md/pdf2md/.tmp/papers_run")


def _classify_cached(example: str) -> DocumentClassification | None:
    md_path = _FIXTURE_ROOT / example / "raw" / "deepseek" / "output.md"
    if not md_path.is_file():
        return None
    md = md_path.read_text(encoding="utf-8")
    return _classify(md)


@pytest.mark.parametrize("example", ["example01", "example02"])
def test_cached_examples_classify_as_article(example: str) -> None:
    c = _classify_cached(example)
    if c is None:
        pytest.skip(f"{example} OCR cache absent")
    # Both example fixtures are scholarly articles.
    assert c.document_class == DocumentClass.ARTICLE
