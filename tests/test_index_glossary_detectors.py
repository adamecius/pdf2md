"""Tests for the Index + Glossary detectors and their cross-link relations.

Coverage:

* Index heading detection (``# Index``, ``# Subject Index``, ``# Author Index``).
* Glossary heading detection (``# Glossary``, ``# Terms``).
* Index-entry parsing for the canonical ``Term, 5, 17-19, 42`` shape.
* Glossary-entry parsing for both page-list and definition-only shapes.
* Section termination on next same-or-higher-level heading.
* Cross-link emission rules from Additional Plan 6:
  * INDEX_ENTRY → SECTION/CHAPTER by page AND by heading text (both
    edges, each tagged with ``match_strategy``).
  * GLOSSARY_ENTRY → body blocks ONLY on pages explicitly listed in the
    entry (no substring scan of the body).
  * TOC_ENTRY page-match cross-link (formalised in Plan 6).
"""

from __future__ import annotations

from pdf2md.connectors.common import markdown_to_pages, recognize_entities
from pdf2md.models.entities import EntityType, RelationType


def _ents(text: str):
    warnings: list[str] = []
    pages = markdown_to_pages(
        text, backend="mineru", backend_version=None,
        document_id="doc", raw_ref="output.md", warnings=warnings,
    )
    return recognize_entities(
        pages, backend="mineru", backend_version=None,
        document_id="doc", warnings=warnings,
    )


def _typed(doc, kind: str):
    out = []
    for e in doc.entities:
        et = e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type
        if et == kind:
            out.append(e)
    return out


def _rels(doc, kind: str):
    out = []
    for r in doc.relations:
        rt = r.relation_type.value if hasattr(r.relation_type, "value") else r.relation_type
        if rt == kind:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------
def test_index_heading_opens_index_section() -> None:
    md = "# Body\n\nbody text.\n\f# Index\n\nHall effect, 5, 17, 42\n"
    doc = _ents(md)
    assert len(_typed(doc, "index_section")) == 1
    assert len(_typed(doc, "index_entry")) == 1


def test_subject_and_author_index_variants() -> None:
    for heading in ("Index", "Subject Index", "Name Index", "Author Index"):
        md = f"# Body\n\nbody.\n\f# {heading}\n\nHall, 5\n"
        doc = _ents(md)
        assert len(_typed(doc, "index_section")) == 1, heading


def test_glossary_heading_opens_glossary_section() -> None:
    md = "# Body\n\nbody.\n\f# Glossary\n\nConductivity, 3, 7\n"
    doc = _ents(md)
    assert len(_typed(doc, "glossary_section")) == 1
    assert len(_typed(doc, "glossary_entry")) == 1


def test_glossary_variants() -> None:
    for heading in ("Glossary", "Terms", "Vocabulary", "Glossary of Terms"):
        md = f"# Body\n\nbody.\n\f# {heading}\n\nConductivity, 3\n"
        doc = _ents(md)
        assert len(_typed(doc, "glossary_section")) == 1, heading


def test_index_section_terminates_at_next_same_level_heading() -> None:
    md = (
        "# Body\n\nbody.\n\f"
        "# Index\n\nHall, 5\nBerry, 12\n\f"
        "# Notes\n\nKey, 7\n"  # NOT a glossary; "Key, 7" must NOT be tagged
    )
    doc = _ents(md)
    entries = _typed(doc, "index_entry")
    assert len(entries) == 2
    assert {e.metadata.get("index_term") for e in entries} == {"Hall", "Berry"}


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------
def test_index_entry_simple_pages() -> None:
    md = "# Index\n\nHall effect, 5, 17, 42\n"
    doc = _ents(md)
    entries = _typed(doc, "index_entry")
    assert len(entries) == 1
    assert entries[0].metadata.get("index_term") == "Hall effect"
    assert entries[0].metadata.get("index_pages") == [5, 17, 42]


def test_index_entry_page_range_expands() -> None:
    md = "# Index\n\nBerry phase, 12-14\n"
    doc = _ents(md)
    entries = _typed(doc, "index_entry")
    assert len(entries) == 1
    assert entries[0].metadata.get("index_pages") == [12, 13, 14]


def test_index_entry_mixed_range_and_singles() -> None:
    md = "# Index\n\nConductivity, 3, 7–9, 42\n"  # en-dash
    doc = _ents(md)
    entries = _typed(doc, "index_entry")
    assert len(entries) == 1
    assert entries[0].metadata.get("index_pages") == [3, 7, 8, 9, 42]


def test_glossary_entry_with_page_list() -> None:
    md = "# Glossary\n\nConductivity, 3, 7\n"
    doc = _ents(md)
    entries = _typed(doc, "glossary_entry")
    assert len(entries) == 1
    e = entries[0]
    assert e.metadata.get("glossary_term") == "Conductivity"
    assert e.metadata.get("glossary_pages") == [3, 7]
    assert e.metadata.get("has_page_list") is True


def test_glossary_entry_definition_only() -> None:
    md = "# Glossary\n\n**Hall** — physicist who discovered the effect.\n"
    doc = _ents(md)
    entries = _typed(doc, "glossary_entry")
    assert len(entries) == 1
    e = entries[0]
    assert e.metadata.get("glossary_term") == "Hall"
    assert "physicist" in (e.metadata.get("glossary_definition") or "")
    assert e.metadata.get("has_page_list") is False


# ---------------------------------------------------------------------------
# Cross-link emission
# ---------------------------------------------------------------------------
def _spread_pages(items: list[str], pages: int) -> str:
    if pages < 2:
        return "\n\n".join(items)
    per = max(1, len(items) // pages + (1 if len(items) % pages else 0))
    out = []
    for i in range(pages):
        chunk = items[i * per : (i + 1) * per]
        if chunk:
            out.append("\n\n".join(chunk))
    return "\f".join(out)


def test_index_entry_emits_page_match_cross_link() -> None:
    # Body across 5 pages; page 3 holds a section anchored on a heading.
    md = (
        "# Intro\n\nbody.\n\f"
        "# Setup\n\nbody.\n\f"
        "# Hall effect\n\nbody about the Hall effect.\n\f"
        "# Results\n\nbody.\n\f"
        "# Index\n\nHall effect, 3, 5\n"
    )
    doc = _ents(md)
    # Find INDEX_ENTRY edges that point at sections.
    toc_edges = _rels(doc, "toc_points_to")
    page_strategy = [e for e in toc_edges if e.metadata.get("match_strategy") == "page"]
    heading_strategy = [e for e in toc_edges if e.metadata.get("match_strategy") == "heading_text"]
    # Two page-match edges (pages 3 and 5).
    assert len(page_strategy) >= 2
    # At least one heading-text-match edge (matches "Hall effect" section).
    assert len(heading_strategy) >= 1


def test_glossary_entry_links_only_to_listed_pages() -> None:
    # Body on 4 pages. The word "conductivity" appears on EVERY page,
    # but the glossary entry only lists pages 2 and 4. The cross-link
    # must hit body content on pages 2 and 4 only.
    md = (
        "# Intro\n\nA discussion of conductivity here.\n\f"
        "# Background\n\nMore on conductivity in this section.\n\f"
        "# Method\n\nWe study conductivity again.\n\f"
        "# Results\n\nResults about conductivity.\n\f"
        "# Glossary\n\nConductivity, 2, 4\n"
    )
    doc = _ents(md)
    glossary_edges = _rels(doc, "glossary_defines")
    assert len(glossary_edges) >= 1
    target_pages = {e.metadata.get("glossary_target_page") for e in glossary_edges}
    # Must only reference pages 2 and 4.
    assert target_pages.issubset({2, 4})
    assert 1 not in target_pages
    assert 3 not in target_pages


def test_glossary_definition_only_entry_emits_no_cross_links() -> None:
    md = (
        "# Body\n\nConductivity is mentioned here.\n\f"
        "# Glossary\n\n**Conductivity** — the property of a material.\n"
    )
    doc = _ents(md)
    edges = _rels(doc, "glossary_defines")
    assert edges == []
    glossary_entries = _typed(doc, "glossary_entry")
    assert len(glossary_entries) == 1
    assert glossary_entries[0].metadata.get("has_page_list") is False


def test_toc_entry_page_match_cross_link() -> None:
    # Synthetic TOC + body with a section on page 3.
    md = (
        "# Contents\n\n"
        "Introduction ........ 1\n"
        "Hall effect ........ 3\n"
        "\f# Intro\n\nbody.\n\f"
        "# Bridge\n\nbody.\n\f"
        "# Hall effect\n\nbody about the Hall effect.\n"
    )
    doc = _ents(md)
    toc_edges = _rels(doc, "toc_points_to")
    page_strategy = [e for e in toc_edges if e.metadata.get("match_strategy") == "page"]
    # At least one TOC entry resolved to its page-matching section.
    assert len(page_strategy) >= 1


# ---------------------------------------------------------------------------
# End-to-end synthetic book fixture (Plan 6 §5 acceptance criterion 2 + 3).
# ---------------------------------------------------------------------------
def test_synthetic_book_index_round_trip() -> None:
    md = (
        "# Intro\n\nbody.\n\f"
        "# Hall effect\n\nbody on Hall effect.\n\f"
        "# Bridge\n\nbody.\n\f"
        "# Berry phase\n\nbody on Berry phase.\n\f"
        "# Index\n\nHall effect, 2, 5\nBerry phase, 4\n"
    )
    doc = _ents(md)
    entries = _typed(doc, "index_entry")
    assert {e.metadata.get("index_term") for e in entries} == {"Hall effect", "Berry phase"}
    edges = _rels(doc, "toc_points_to")
    strategies = {e.metadata.get("match_strategy") for e in edges}
    # Both strategies fire on at least one edge.
    assert "page" in strategies
    assert "heading_text" in strategies


def test_synthetic_glossary_round_trip() -> None:
    md = (
        "# Body\n\nbody page 1.\n\f"
        "# Background\n\nbody page 2.\n\f"
        "# Method\n\nbody page 3.\n\f"
        "# Results\n\nbody page 4.\n\f"
        "# Glossary\n\n"
        "Conductivity, 3, 4\n\n"
        "**Hall** — physicist (no page reference).\n"
    )
    doc = _ents(md)
    entries = _typed(doc, "glossary_entry")
    by_term = {e.metadata.get("glossary_term"): e for e in entries}
    assert "Conductivity" in by_term
    assert "Hall" in by_term
    # Conductivity has a page list → emits edges; Hall does not.
    cond = by_term["Conductivity"]
    hall = by_term["Hall"]
    assert cond.metadata.get("has_page_list") is True
    assert hall.metadata.get("has_page_list") is False
    cond_edges = [r for r in _rels(doc, "glossary_defines") if r.source_entity_id == cond.id]
    hall_edges = [r for r in _rels(doc, "glossary_defines") if r.source_entity_id == hall.id]
    assert len(cond_edges) >= 1
    assert hall_edges == []
