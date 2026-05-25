"""Tests for the implicit-bibliography detector (Case A).

When a document's bibliography starts with `[1] Author ...` and no
"References" / "Bibliography" heading precedes it, the main entity
detector misclassifies every bibliography entry as
:class:`EntityType.FOOTNOTE`. The post-pass
:func:`pdf2md.connectors.common._detect_implicit_bibliography`
identifies the tail run and re-tags it.

End-to-end impact (measured on the cached arxiv example01
`pdf2md/.tmp/papers_run/example01/raw/deepseek/`): bibliography
resolution via GROBID + the bridge lifted from 12/101 (11.9%) to
45/101 (44.6%) with no other code changes.
"""

from __future__ import annotations

from pdf2md.connectors.common import markdown_to_pages, recognize_entities
from pdf2md.models.entities import EntityType


def _ents(text: str):
    warnings: list[str] = []
    p = markdown_to_pages(
        text,
        backend="mineru",
        backend_version=None,
        document_id="doc",
        raw_ref="output.md",
        warnings=warnings,
    )
    return recognize_entities(
        p,
        backend="mineru",
        backend_version=None,
        document_id="doc",
        warnings=warnings,
    )


def _spread_over_pages(items: list[str], pages: int) -> str:
    """Glue `items` into a multi-page markdown using form-feed page breaks."""
    if pages < 2:
        return "\n\n".join(items)
    per = max(1, len(items) // pages + (1 if len(items) % pages else 0))
    out = []
    for i in range(pages):
        chunk = items[i * per : (i + 1) * per]
        if chunk:
            out.append("\n\n".join(chunk))
    return "\f".join(out)


def test_implicit_detector_retags_tail_footnotes_to_reference_items() -> None:
    """A tail run of `[N]`-prefixed paragraphs becomes REFERENCE_ITEMs."""
    body = ["# Introduction", "Some text body."] * 5  # bulk body
    refs = [
        "[1] Smith, J. (2020). A title. Journal X.",
        "[2] Doe, A. (2019). Another title. Journal Y.",
        "[3] Roe, R. (2018). Third title. Journal Z.",
        "[4] Adams, B. (2017). Fourth title.",
        "[5] Lee, K. (2016). Fifth title.",
    ]
    md = _spread_over_pages(body + refs, pages=4)
    doc = _ents(md)
    types = [
        (e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type)
        for e in doc.entities
    ]
    # All 5 refs should be REFERENCE_ITEM, not FOOTNOTE.
    ref_items = [
        e for e in doc.entities
        if (e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type) == "reference_item"
    ]
    assert len(ref_items) == 5
    # And every one of them should carry the audit trail.
    for e in ref_items:
        assert e.metadata.get("detector") == "implicit_bibliography_detector"
        assert e.metadata.get("previous_detector") == "footnote_detector"


def test_implicit_detector_emits_synthetic_reference_section() -> None:
    body = ["# Body", "x"] * 5
    refs = ["[1] r1", "[2] r2", "[3] r3", "[4] r4"]
    md = _spread_over_pages(body + refs, pages=4)
    doc = _ents(md)
    ref_sections = [
        e for e in doc.entities
        if (e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type) == "reference_section"
    ]
    assert len(ref_sections) == 1
    s = ref_sections[0]
    assert s.metadata.get("detector") == "implicit_bibliography_detector"
    assert s.metadata.get("trigger") == "tail_run_of_numbered_paragraphs"
    assert s.metadata.get("run_size") == 4


def test_implicit_detector_does_not_fire_when_explicit_heading_present() -> None:
    """When a real "References" heading exists, the main loop already
    flips refs_started — the post-pass must not double-act."""
    md = (
        "# Introduction\n\nbody\n\f"
        "more body\n\f"
        "# References\n\n"
        "[1] r1\n\n[2] r2\n\n[3] r3\n\n[4] r4"
    )
    doc = _ents(md)
    # The reference_section came from the explicit heading detector.
    ref_sections = [
        e for e in doc.entities
        if (e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type) == "reference_section"
    ]
    assert len(ref_sections) == 1
    assert ref_sections[0].metadata.get("detector") == "reference_section_detector"
    # The implicit detector must NOT have re-tagged anything (no entity
    # should carry the implicit_bibliography_detector marker on its
    # metadata, because the main loop already classified them as
    # REFERENCE_ITEM via the normal `refs_started` path).
    implicit_count = sum(
        1 for e in doc.entities
        if e.metadata.get("detector") == "implicit_bibliography_detector"
    )
    assert implicit_count == 0


def test_implicit_detector_ignores_short_runs() -> None:
    """A 2-item tail run is below the minimum threshold (3) and the
    detector should leave the entities classified as FOOTNOTE."""
    body = ["# Body", "x"] * 5
    refs = ["[1] r1", "[2] r2"]
    md = _spread_over_pages(body + refs, pages=4)
    doc = _ents(md)
    types = [
        (e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type)
        for e in doc.entities
    ]
    # The two `[N]` lines stay as FOOTNOTE (no run-of-3 tail).
    assert types.count("reference_item") == 0
    assert types.count("footnote") == 2


def test_implicit_detector_ignores_runs_in_document_body() -> None:
    """A long `[N]` run that lives in the FIRST half of the document
    is unlikely to be a bibliography — typically it's a footnote
    cluster or a numbered list. The detector restricts itself to the
    tail (last 30%)."""
    refs_in_body = ["[1] r1", "[2] r2", "[3] r3", "[4] r4", "[5] r5"]
    bulk_tail = ["body text"] * 30
    md = _spread_over_pages(refs_in_body + bulk_tail, pages=10)
    doc = _ents(md)
    # No REFERENCE_ITEM emissions because the refs aren't in the tail.
    ref_items = [
        e for e in doc.entities
        if (e.entity_type.value if hasattr(e.entity_type, "value") else e.entity_type) == "reference_item"
    ]
    assert ref_items == []
