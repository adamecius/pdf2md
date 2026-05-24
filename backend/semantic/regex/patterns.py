"""Regex / heuristic patterns for cross-reference marker detection.

This is a deterministic, stdlib-only semantic backend. It scans
already-extracted text and emits a list of reference markers
(figure, table, equation, citation, footnote, theorem-family).

The module is intentionally standalone — no imports from
``src/pdf2md/`` per Plan 005 (semantic backends are isolated at
this stage).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternHit:
    """A single regex match against an input text string.

    Attributes:
        marker_type: One of the canonical RefType slugs used by the
            planned ``CrossReferenceGraph`` (Plan 006). Plan 005 keeps
            this as a plain string and does not import any pdf2md model.
        marker_text: The literal surface form matched (e.g. "Figure 3.2",
            "[15]", "Eq. (4)", "footnote 3").
        char_offset: ``(start, end)`` indices into the input text.
    """

    marker_type: str
    marker_text: str
    char_offset: tuple[int, int]


# Ordered: longer / more specific patterns first so they win on overlap.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Bibliography citations: [15], [12, 13], [12-14]
    (
        "bibliography",
        re.compile(r"\[\s*\d+(?:\s*[,\-]\s*\d+)*\s*\]"),
    ),
    # Bibliography author-year: (Smith, 2020), (Smith et al. 2020), (Smith and Jones, 2020)
    (
        "bibliography",
        re.compile(
            r"\(\s*[A-Z][A-Za-z\-]+"
            r"(?:\s+(?:et\s+al\.?|and|&)\s+[A-Za-z\-]+)*"
            r"(?:\s*,)?\s+\d{4}[a-z]?\s*\)"
        ),
    ),
    # Figures: Figure 3, Fig. 3, Fig 3.2, Figures 1 and 2
    (
        "figure",
        re.compile(
            r"\b(?:Fig(?:ure|\.|s|\.s)?)\s+\d+(?:\.\d+)?"
            r"(?:\s*(?:and|,)\s*\d+(?:\.\d+)?)*",
            re.IGNORECASE,
        ),
    ),
    # Tables: Table 3, Table 3.2, Tables 1 and 2
    (
        "table",
        re.compile(
            r"\bTable[s]?\s+\d+(?:\.\d+)?"
            r"(?:\s*(?:and|,)\s*\d+(?:\.\d+)?)*",
            re.IGNORECASE,
        ),
    ),
    # Equations: Eq. 3, Eq. (3), Equation 3.2, (3.2)
    (
        "equation",
        re.compile(
            r"\b(?:Eq(?:uation|\.|s|\.s)?)\s*\(?\d+(?:\.\d+)?\)?",
            re.IGNORECASE,
        ),
    ),
    # Naked parenthesised equation refs like "(3.2)" — keep narrow to
    # avoid grabbing unrelated parenthesised numbers. Require the dot.
    (
        "equation",
        re.compile(r"\(\d+\.\d+\)"),
    ),
    # Sections / Chapters
    (
        "section",
        re.compile(
            r"\b(?:Section|Sec\.)\s+\d+(?:\.\d+)*",
            re.IGNORECASE,
        ),
    ),
    (
        "chapter",
        re.compile(r"\bChapter\s+\d+", re.IGNORECASE),
    ),
    # Theorem-family labels
    (
        "theorem",
        re.compile(r"\bTheorem\s+\d+(?:\.\d+)?", re.IGNORECASE),
    ),
    (
        "definition",
        re.compile(r"\bDefinition\s+\d+(?:\.\d+)?", re.IGNORECASE),
    ),
    (
        "proof",
        re.compile(r"\bProof\s+of\s+(?:Theorem|Proposition|Lemma)\s+\d+(?:\.\d+)?", re.IGNORECASE),
    ),
    (
        "corollary",
        re.compile(r"\bCorollary\s+\d+(?:\.\d+)?", re.IGNORECASE),
    ),
    (
        "example",
        re.compile(r"\bExample\s+\d+(?:\.\d+)?", re.IGNORECASE),
    ),
    # Footnotes: "footnote 3", "fn. 3", superscript-style "[3]" is handled by bibliography
    (
        "footnote",
        re.compile(
            r"\b(?:footnote|fn\.?)\s+\d+",
            re.IGNORECASE,
        ),
    ),
)


def find_markers(text: str) -> list[PatternHit]:
    """Scan ``text`` and return non-overlapping reference markers.

    When two patterns match the same span, the earlier (more specific)
    pattern wins. Overlaps are resolved by keeping the leftmost,
    longest match.

    Args:
        text: Plain-text content to scan, typically a paragraph or
            block of body text.

    Returns:
        A list of ``PatternHit`` in left-to-right order of appearance,
        with no overlapping spans.
    """
    candidates: list[PatternHit] = []
    for marker_type, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            candidates.append(
                PatternHit(
                    marker_type=marker_type,
                    marker_text=m.group(0),
                    char_offset=(m.start(), m.end()),
                )
            )

    candidates.sort(key=lambda h: (h.char_offset[0], -(h.char_offset[1] - h.char_offset[0])))

    accepted: list[PatternHit] = []
    last_end = -1
    for hit in candidates:
        start, end = hit.char_offset
        if start >= last_end:
            accepted.append(hit)
            last_end = end
    return accepted


def summarise_by_type(hits: list[PatternHit]) -> dict[str, int]:
    """Return a count per ``marker_type``."""
    counts: dict[str, int] = {}
    for h in hits:
        counts[h.marker_type] = counts.get(h.marker_type, 0) + 1
    return counts
