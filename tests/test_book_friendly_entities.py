"""Book-friendly entity detection + OCR→semantic candidate bridge.

Covers the changes that make the OCR-side entity output a proper
input to the semantic-layer resolver on long documents:

* ``EntityType.CHAPTER`` exists and is emitted by ``chapter_detector``
  on H1 headings with explicit "Chapter N" prefixes (matches LaTeX
  ``\\chapter{...}`` in the book class) AND on H1 headings with
  numeric top-level numbering (article-style books).
* The caption detector preserves chapter-relative numbering
  ("Figure 3.2" stays "3.2", not "3").
* ``entities_to_candidates`` maps each OCR EntityType to the right
  semantic RefType and produces resolver-ready labels.
"""

from __future__ import annotations

from pdf2md.connectors.common import markdown_to_pages, recognize_entities
from pdf2md.models.cross_ref import RefMarker, RefType
from pdf2md.models.entities import EntityType
from pdf2md.semantic.candidates import entities_to_candidates
from pdf2md.semantic.resolver import resolve_markers


def _ents(text: str):
    warnings: list[str] = []
    pages = markdown_to_pages(
        text,
        backend="mineru",
        backend_version=None,
        document_id="doc",
        raw_ref="output.md",
        warnings=warnings,
    )
    return recognize_entities(
        pages,
        backend="mineru",
        backend_version=None,
        document_id="doc",
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# CHAPTER detector
# ---------------------------------------------------------------------------
def test_chapter_detector_fires_on_explicit_chapter_prefix() -> None:
    doc = _ents("# Chapter 5: Topology")
    chapters = [e for e in doc.entities if e.entity_type == EntityType.CHAPTER]
    assert len(chapters) == 1
    assert chapters[0].metadata.get("chapter_number") == "5"
    assert chapters[0].metadata.get("match") == "keyword"
    # SECTION still emitted alongside (backwards compat).
    sections = [e for e in doc.entities if e.entity_type == EntityType.SECTION]
    assert len(sections) == 1


def test_chapter_detector_fires_on_h1_top_level_numbering() -> None:
    """Article-style books (single-digit H1 numbering) are also chapters."""
    doc = _ents("# 1 Introduction")
    chapters = [e for e in doc.entities if e.entity_type == EntityType.CHAPTER]
    assert len(chapters) == 1
    assert chapters[0].metadata.get("chapter_number") == "1"
    assert chapters[0].metadata.get("match") == "h1_top_level"


def test_chapter_detector_does_not_fire_on_subsection() -> None:
    doc = _ents("## 3.2 Bands")
    chapters = [e for e in doc.entities if e.entity_type == EntityType.CHAPTER]
    assert chapters == []


def test_chapter_detector_does_not_fire_on_dotted_h1() -> None:
    """H1 with dotted numbering is a *section* under another chapter, not a chapter."""
    doc = _ents("# 3.2 Bands")
    chapters = [e for e in doc.entities if e.entity_type == EntityType.CHAPTER]
    assert chapters == []


# ---------------------------------------------------------------------------
# Caption numbering preserved
# ---------------------------------------------------------------------------
def test_caption_detector_preserves_chapter_relative_numbering() -> None:
    doc = _ents("Figure 3.2 The bands.")
    caps = [e for e in doc.entities if e.entity_type == EntityType.CAPTION]
    assert len(caps) == 1
    assert caps[0].metadata.get("caption_number") == "3.2"


def test_caption_detector_still_handles_flat_numbering() -> None:
    doc = _ents("Figure 7. The bands.")
    caps = [e for e in doc.entities if e.entity_type == EntityType.CAPTION]
    assert len(caps) == 1
    assert caps[0].metadata.get("caption_number") == "7"


def test_caption_detector_table_with_dotted_number() -> None:
    doc = _ents("Table 5.1 Summary.")
    caps = [e for e in doc.entities if e.entity_type == EntityType.CAPTION]
    assert len(caps) == 1
    assert caps[0].metadata.get("caption_kind") == "table"
    assert caps[0].metadata.get("caption_number") == "5.1"


# ---------------------------------------------------------------------------
# entities_to_candidates bridge
# ---------------------------------------------------------------------------
def test_bridge_maps_chapter_to_ref_type_chapter() -> None:
    doc = _ents("# Chapter 5: Topology")
    cands = entities_to_candidates(doc)
    chapter_cands = [c for c in cands if c.entity_type == RefType.CHAPTER]
    assert len(chapter_cands) == 1
    assert chapter_cands[0].label == "Chapter 5"


def test_bridge_maps_caption_to_figure_or_table() -> None:
    doc = _ents("Figure 3.2 The bands.\n\nTable 5.1 Summary.")
    cands = entities_to_candidates(doc)
    figs = [c for c in cands if c.entity_type == RefType.FIGURE]
    tabs = [c for c in cands if c.entity_type == RefType.TABLE]
    assert any(c.label == "Figure 3.2" for c in figs)
    assert any(c.label == "Table 5.1" for c in tabs)


def test_bridge_skips_layout_only_entities() -> None:
    # Page numbers / headers / footers / TOC entries / reference sections
    # are useful for layout but not as resolver targets.
    doc = _ents("# References\n\n[1] some bib entry")
    cands = entities_to_candidates(doc)
    # The reference_section entity should NOT appear as a candidate;
    # the [1] reference item SHOULD.
    types = {c.entity_type for c in cands}
    assert RefType.BIBLIOGRAPHY in types


def test_bridge_emits_equation_candidates_only_when_numbered() -> None:
    # The equation detector matches a `(N)` only at the end of a block,
    # and emits an EQUATION entity. The numbered case gets a candidate
    # with label "(2.1)"; the unnumbered display-math case has no
    # equation_number metadata and the bridge skips it.
    doc = _ents("E = m c^2 (2.1)\n\n\\[x = 1\\]")
    cands = entities_to_candidates(doc)
    eq_labels = [c.label for c in cands if c.entity_type == RefType.EQUATION]
    assert "(2.1)" in eq_labels
    # The unnumbered display-math block was detected as an entity
    # (BlockKind.FORMULA fires the detector) but with `equation_number=None`,
    # so the bridge drops it.
    assert eq_labels.count("(2.1)") == 1
    assert all(lbl == "(2.1)" for lbl in eq_labels)


# ---------------------------------------------------------------------------
# End-to-end: OCR candidates + GROBID-style markers → resolved edges
# ---------------------------------------------------------------------------
def _marker(text: str, marker_type: RefType) -> RefMarker:
    return RefMarker(
        source_ref="#/document",
        marker_text=text,
        marker_type=marker_type,
        char_offset=(0, len(text)),
        confidence=1.0,
        backend="grobid",
    )


def test_grobid_markers_resolve_against_ocr_candidates() -> None:
    """End-to-end: simulate GROBID-detected markers and OCR-detected
    captions/refs/chapters on a multi-chapter document, and confirm
    the resolver pairs them correctly."""
    book = (
        "# Chapter 5: Topology\n"
        "\n"
        "Figure 5.2 The bands.\n"
        "\n"
        "# References\n"
        "\n"
        "[15] A foundational citation.\n"
    )
    doc = _ents(book)
    candidates = entities_to_candidates(doc)

    markers = [
        _marker("Figure 5.2", RefType.FIGURE),
        _marker("Chapter 5", RefType.CHAPTER),
        _marker("[15]", RefType.BIBLIOGRAPHY),
    ]
    edges = resolve_markers(markers, candidates)
    assert len(edges) == 3

    by_text = {edge.marker.marker_text: edge for edge in edges}
    assert by_text["Figure 5.2"].resolved is True
    assert by_text["Figure 5.2"].target_ref is not None
    assert by_text["Chapter 5"].resolved is True
    assert by_text["[15]"].resolved is True
