"""Tests for Plan 17 export-wiring hardening (A3 / A4 / A5).

A1 (origin block), A2 (PARAGRAPH -> "text" label) and A6 (schema
version) were merged via PR #101 and have existing test coverage in
``tests/test_docling_export_wiring.py``. This file fills the
remaining three defects:

* A3 — heading detection on HTML ``<h1>``, LaTeX ``\\section{...}``,
  and the formatting heuristic (short title-case lines).
* A4 — footnote post-processing: ``\\footnote{...}`` residual + the
  bottom-of-page numbered-line heuristic.
* A5 — inline ``<img>`` HTML lifted into FIGURE blocks with
  ``image_src`` / ``image_origin`` metadata.
"""

from __future__ import annotations

from pdf2md.connectors.common import classify_block, markdown_to_pages
from pdf2md.models.ir import BlockKind


def _pages(md: str, backend: str = "paddleocr"):
    return markdown_to_pages(
        md,
        backend=backend,
        backend_version=None,
        document_id="doc",
        raw_ref="r",
        warnings=[],
    )


def _blocks(md: str, backend: str = "paddleocr"):
    pages = _pages(md, backend=backend)
    return [b for p in pages for b in p.blocks]


# ---------------------------------------------------------------------------
# A3 — heading detection
# ---------------------------------------------------------------------------
def test_classify_block_recognises_html_h1() -> None:
    kind, md = classify_block("<h1>Introduction</h1>")
    assert kind == BlockKind.HEADING
    assert md["heading_source"] == "html_tag"
    assert md["markdown_heading_level"] == 1


def test_classify_block_recognises_html_h3() -> None:
    kind, md = classify_block("<h3>Methods</h3>")
    assert kind == BlockKind.HEADING
    assert md["heading_source"] == "html_tag"
    assert md["markdown_heading_level"] == 3


def test_classify_block_recognises_latex_section() -> None:
    kind, md = classify_block("\\section{Background}")
    assert kind == BlockKind.HEADING
    assert md["heading_source"] == "latex_command"
    assert md["markdown_heading_level"] == 1


def test_classify_block_recognises_latex_subsection_level_2() -> None:
    kind, md = classify_block("\\subsection{Algorithm}")
    assert kind == BlockKind.HEADING
    assert md["markdown_heading_level"] == 2


def test_classify_block_formatting_heuristic_uppercase_short_line() -> None:
    kind, md = classify_block("INTRODUCTION")
    # 1 word, hits the lower bound of 2 — should NOT be heading.
    assert kind == BlockKind.PARAGRAPH

    kind, md = classify_block("Method And Results")
    assert kind == BlockKind.HEADING
    assert md["heading_source"] == "formatting_heuristic"


def test_classify_block_formatting_heuristic_rejects_long_lines() -> None:
    long_line = "We propose a new technique for non-equilibrium hall transport calculations"
    kind, _ = classify_block(long_line)
    assert kind == BlockKind.PARAGRAPH


def test_classify_block_formatting_heuristic_rejects_trailing_punctuation() -> None:
    kind, _ = classify_block("Introduction To Methods.")
    assert kind == BlockKind.PARAGRAPH


def test_classify_block_keeps_existing_markdown_hash_heading() -> None:
    kind, md = classify_block("# Section One")
    assert kind == BlockKind.HEADING
    assert md["heading_source"] == "markdown_hash"


# ---------------------------------------------------------------------------
# A4 — footnote post-processing
# ---------------------------------------------------------------------------
def test_latex_footnote_lifts_into_footnote_block_with_anchor() -> None:
    md = "This is some body text.\\footnote{A note about the body.}"
    blocks = _blocks(md)
    paragraphs = [b for b in blocks if b.kind == BlockKind.PARAGRAPH]
    footnotes = [b for b in blocks if b.kind == BlockKind.FOOTNOTE]
    assert len(paragraphs) == 1
    assert "[^1]" in paragraphs[0].text
    assert "\\footnote" not in paragraphs[0].text
    assert len(footnotes) == 1
    assert footnotes[0].text == "A note about the body."
    assert footnotes[0].metadata.get("footnote_marker") == "1"
    assert footnotes[0].metadata.get("footnote_host_block_id") == paragraphs[0].id


def test_latex_footnote_multiple_in_same_block_get_unique_markers() -> None:
    md = "Body one.\\footnote{first note} Body two.\\footnote{second note}"
    blocks = _blocks(md)
    footnotes = [b for b in blocks if b.kind == BlockKind.FOOTNOTE]
    assert {b.metadata.get("footnote_marker") for b in footnotes} == {"1", "2"}
    assert [b.text for b in footnotes] == ["first note", "second note"]


def test_bottom_of_page_numbered_line_becomes_footnote() -> None:
    md = (
        "# Introduction\n\n"
        "This paragraph is long enough to count as a real body paragraph that "
        "anchors the page so the bottom-third heuristic can find footnotes "
        "later on.\n\n"
        "Method paragraph also long enough not to be mistaken for a stray "
        "line. We elaborate on the procedure here.\n\n"
        "Results paragraph again with enough substance to trip the "
        "non-trivial-paragraph threshold.\n\n"
        "1. A clarification on the method."
    )
    blocks = _blocks(md)
    footnotes = [b for b in blocks if b.kind == BlockKind.FOOTNOTE]
    assert len(footnotes) == 1
    assert footnotes[0].metadata.get("footnote_marker") == "1"
    assert footnotes[0].metadata.get("footnote_source") == "bottom_of_page_number"


def test_numbered_line_NOT_at_bottom_stays_paragraph() -> None:
    md = "1. First step\n\nSome body content here."
    blocks = _blocks(md)
    footnotes = [b for b in blocks if b.kind == BlockKind.FOOTNOTE]
    assert footnotes == []


# ---------------------------------------------------------------------------
# A5 — inline <img> lift
# ---------------------------------------------------------------------------
def test_inline_img_lifted_into_figure_block() -> None:
    md = (
        "Some prose before the picture.\n\n"
        '<img src="images/foo.png"/>\n\n'
        "And some prose after."
    )
    blocks = _blocks(md)
    figures = [b for b in blocks if b.kind == BlockKind.FIGURE]
    assert len(figures) == 1
    assert figures[0].metadata.get("image_src") == "images/foo.png"
    assert figures[0].metadata.get("image_origin") == "inline_html"


def test_inline_img_inside_div_wrapper_lifted_too() -> None:
    md = (
        "Body text.\n\n"
        '<div class="figure"><img src="pic.jpg"/></div>\n\n'
        "More body."
    )
    blocks = _blocks(md)
    figures = [b for b in blocks if b.kind == BlockKind.FIGURE]
    assert len(figures) == 1
    assert figures[0].metadata.get("image_src") == "pic.jpg"


def test_inline_img_embedded_in_paragraph_lifted_out() -> None:
    """An ``<img>`` mid-paragraph gets pulled out — the surrounding
    text stays in its own paragraph block."""
    md = "Some prose <img src=\"a.png\"/> with more text inline."
    blocks = _blocks(md)
    kinds = [b.kind for b in blocks]
    assert BlockKind.FIGURE in kinds
    paras = [b for b in blocks if b.kind == BlockKind.PARAGRAPH]
    assert paras
    assert "<img" not in (paras[0].text + (paras[-1].text if len(paras) > 1 else ""))


def test_multiple_inline_imgs_each_become_their_own_figure() -> None:
    md = (
        "Header text.\n\n"
        '<img src="a.png"/>\n\n'
        '<img src="b.png"/>\n\n'
        "Footer text."
    )
    blocks = _blocks(md)
    srcs = [b.metadata.get("image_src") for b in blocks if b.kind == BlockKind.FIGURE]
    assert sorted(srcs) == ["a.png", "b.png"]
