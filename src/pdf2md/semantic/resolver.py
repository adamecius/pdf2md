"""Deterministic resolver for semantic reference markers.

Takes a list of :class:`RefMarker` and a list of candidate targets,
and emits :class:`RefEdge` instances using these strategies, tried in
order:

1. **grobid_tei** — when the marker already carries a ``#xml-id`` target
   pointer (handled upstream by the GROBID adapter; here we only respect
   pre-set edges).
2. **exact** — case-sensitive surface form match against a candidate's
   ``label``.
3. **fuzzy** — case-insensitive comparison after stripping common
   prefixes (``Fig.``, ``Fig``, ``Figs``, ``Sec.``, etc.) and normalising
   whitespace.
4. **bibliography** — ``[15]`` → candidate with
   ``entity_type=BIBLIOGRAPHY`` and a label containing ``15``.
5. **footnote** — superscript-like ``"3"`` (very short numeric marker) →
   candidate with ``entity_type=FOOTNOTE`` on the same page (when page
   metadata is available; here, by label match).
6. **cross-chapter** — ``Chapter 5`` → candidate with
   ``entity_type=CHAPTER`` (or ``SECTION`` with depth-0 — caller decides).

Markers that no strategy resolves emit an unresolved edge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pdf2md.models.cross_ref import RefEdge, RefMarker, RefType, SemanticEntity


@dataclass(frozen=True)
class ResolverCandidate:
    """A candidate resolution target for the resolver.

    Attributes:
        target_ref: JSON pointer used as ``RefEdge.target_ref`` on a hit.
        entity_type: Canonical type of the candidate.
        label: Surface form to match the marker against (e.g. caption text
            ``"Figure 3.2"``, bibliography number ``"15"``, section
            heading ``"Chapter 5"``).
        numbering: Authoritative numeric identifier when the OCR's
            heading detector parsed one (e.g. ``"4.10"``, ``"19"``).
            When supplied, the fuzzy resolver matches against this
            instead of digging digits out of arbitrary trailing text
            — fixes wrong-resolution cases like
            ``Section 3 → APPENDIX G\\nPROOF OF PROPOSITION 3`` where
            the candidate's ``label`` happens to end in a stray "3".
    """

    target_ref: str
    entity_type: RefType
    label: str
    numbering: str | None = None


_PREFIX_PATTERNS: tuple[tuple[RefType, re.Pattern[str]], ...] = (
    (
        RefType.FIGURE,
        re.compile(r"^\s*(?:fig(?:ure|s|\.s|\.)?|figures)\s+", re.IGNORECASE),
    ),
    (
        RefType.TABLE,
        re.compile(r"^\s*tables?\s+", re.IGNORECASE),
    ),
    (
        RefType.EQUATION,
        re.compile(r"^\s*(?:eq(?:uation|s|\.s|\.)?|equations)\s*\(?", re.IGNORECASE),
    ),
    (
        RefType.SECTION,
        re.compile(r"^\s*(?:sec(?:tion|\.)?)\s+", re.IGNORECASE),
    ),
    (
        RefType.CHAPTER,
        re.compile(r"^\s*chapters?\s+", re.IGNORECASE),
    ),
    (
        RefType.THEOREM,
        re.compile(r"^\s*theorem\s+", re.IGNORECASE),
    ),
    (
        RefType.DEFINITION,
        re.compile(r"^\s*definition\s+", re.IGNORECASE),
    ),
    (
        RefType.COROLLARY,
        re.compile(r"^\s*corollary\s+", re.IGNORECASE),
    ),
    (
        RefType.EXAMPLE,
        re.compile(r"^\s*examples?\s+", re.IGNORECASE),
    ),
    (
        # ``Proof`` and ``Proof of Theorem/Lemma/Proposition/Corollary N``.
        # Strip up to and including the referenced-type keyword so the
        # trailing number survives for identity matching.
        RefType.PROOF,
        re.compile(
            r"^\s*proof(?:\s+of\s+(?:theorem|lemma|proposition|corollary|definition))?\s*",
            re.IGNORECASE,
        ),
    ),
)

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)*")
# Equation numbers accept an optional chapter/appendix letter prefix
# (``J.4``, ``E.11``, ``A.2.1``) in addition to the bare-or-dotted
# numeric form. Used by :func:`_extract_equation_number`. Bibliography
# and footnote markers never carry letter prefixes so they stay on
# the strict ``_NUMBER_RE``.
_EQUATION_NUMBER_RE = re.compile(r"(?:[A-Z]\.)?\d+(?:\.\d+)*")
# Canonical "[15]" form. Both brackets required, single number inside.
_BIB_NUMBER_RE = re.compile(r"\[\s*(\d+)\s*]")
# Broken-bracket forms emitted by GROBID when a multi-citation like
# "[14, 21]" gets split into two `<ref>` elements: "[14," and "21]".
# Each half resolves independently to its bib entry via the digit alone.
_BIB_NUMBER_BROKEN_OPEN_RE = re.compile(r"^\[\s*(\d+)\b")     # "[14," / "[14"
_BIB_NUMBER_BROKEN_CLOSE_RE = re.compile(r"^(\d+)\s*]\s*$")    # "21]" / "13]"


def _normalise(text: str) -> str:
    """Lowercase and collapse runs of whitespace."""
    return " ".join(text.lower().split())


def _strip_prefix(marker_type: RefType, text: str) -> str:
    for mt, pat in _PREFIX_PATTERNS:
        if mt is marker_type:
            stripped = pat.sub("", text)
            return stripped.strip(" ()")
    return text.strip()


def _extract_number(text: str) -> str | None:
    match = _NUMBER_RE.search(text)
    return match.group(0) if match else None


def _extract_equation_number(text: str) -> str | None:
    """Extract an equation number including optional letter prefix.

    Accepts ``J.4``, ``E.11``, ``A.2.1`` (appendix / chapter forms)
    alongside the plain ``11`` / ``15.110``. Used by
    :func:`_try_equation` so book-style equation references resolve
    against book-style equation candidates.
    """
    match = _EQUATION_NUMBER_RE.search(text)
    return match.group(0) if match else None


def _bibliography_number(marker_text: str) -> str | None:
    """Extract the leading citation number from a bibliography marker.

    Accepts the canonical ``[15]`` form **and** the broken-bracket
    forms that GROBID emits when it splits a multi-citation across
    multiple ``<ref>`` elements (``[14,`` and ``21]`` from
    ``[14, 21]``). Each half resolves independently to its bib entry.
    """
    text = marker_text.strip()
    match = _BIB_NUMBER_RE.search(text)
    if match:
        return match.group(1)
    match = _BIB_NUMBER_BROKEN_OPEN_RE.match(text)
    if match:
        return match.group(1)
    match = _BIB_NUMBER_BROKEN_CLOSE_RE.match(text)
    if match:
        return match.group(1)
    return None


def _try_exact(
    marker: RefMarker, candidates: list[ResolverCandidate]
) -> ResolverCandidate | None:
    for cand in candidates:
        if cand.entity_type != marker.marker_type:
            continue
        if cand.label == marker.marker_text:
            return cand
    return None


def _try_fuzzy(
    marker: RefMarker, candidates: list[ResolverCandidate]
) -> ResolverCandidate | None:
    marker_number = _extract_number(_strip_prefix(marker.marker_type, marker.marker_text))
    marker_norm = _normalise(_strip_prefix(marker.marker_type, marker.marker_text))
    for cand in candidates:
        if cand.entity_type != marker.marker_type:
            continue
        cand_stripped = _strip_prefix(cand.entity_type, cand.label)
        cand_norm = _normalise(cand_stripped)
        if marker_norm and marker_norm == cand_norm:
            return cand
        if marker_number is not None:
            # Authoritative ``numbering`` metadata is the strongest
            # signal — match on it first when both sides have it.
            # Doesn't suppress the label-extract fallback below
            # because some OCR backends populate numbering only on a
            # subset of headings (chapter detector wins on dotted
            # numbering, but section detector may emit candidates
            # with the same shape and no numbering metadata).
            if cand.numbering is not None and cand.numbering == marker_number:
                return cand
            cand_number = _extract_number(cand_stripped)
            if cand_number == marker_number:
                return cand
    return None


def _try_bibliography(
    marker: RefMarker, candidates: list[ResolverCandidate]
) -> ResolverCandidate | None:
    if marker.marker_type != RefType.BIBLIOGRAPHY:
        return None
    number = _bibliography_number(marker.marker_text)
    if number is None:
        return None
    for cand in candidates:
        if cand.entity_type != RefType.BIBLIOGRAPHY:
            continue
        if _extract_number(cand.label) == number:
            return cand
    return None


def _try_footnote(
    marker: RefMarker, candidates: list[ResolverCandidate]
) -> ResolverCandidate | None:
    """Resolve a footnote marker to its candidate footnote entity.

    Marker text can be a single number (``"3"``), a comma-separated
    list of numbers (``"21, 22"``) — common when OCR collapses
    adjacent superscript footnotes — or a bare-bracket form. For the
    comma list we resolve to the FIRST candidate that matches ANY of
    the listed numbers, mirroring the bibliography broken-bracket
    behaviour where each half resolves to its own bib entry. The
    resolver only emits one edge per marker today, so the first hit
    wins; the rest are flagged on the marker for downstream tooling
    that wants to fan out.
    """
    if marker.marker_type != RefType.FOOTNOTE:
        return None
    # Split comma-separated multi-number footnote markers.
    numbers = [n.strip() for n in marker.marker_text.split(",")]
    candidate_numbers: list[str] = []
    for chunk in numbers:
        n = _extract_number(chunk)
        if n is not None:
            candidate_numbers.append(n)
    if not candidate_numbers:
        return None
    for cand in candidates:
        if cand.entity_type != RefType.FOOTNOTE:
            continue
        cand_n = _extract_number(cand.label)
        if cand_n is not None and cand_n in candidate_numbers:
            return cand
    return None


def _try_equation(
    marker: RefMarker, candidates: list[ResolverCandidate]
) -> ResolverCandidate | None:
    """Match equation markers by number identity.

    GROBID / regex / VLM emit equation markers in a variety of surface
    forms: ``"Eq. (11)"``, ``"equation (15.110)"``, ``"(11)"``, or just
    the bare number ``"11"``. The OCR-side candidate labels are
    similarly varied: ``"(11)"``, ``"Eq. 11"``, ``"11"``. Number
    identity is the only reliable signal — mirror what
    :func:`_try_bibliography` does for ``[N]`` markers, but on the
    bare-or-parenthesised number form used by equations.
    """
    if marker.marker_type != RefType.EQUATION:
        return None
    number = _extract_equation_number(marker.marker_text)
    if number is None:
        return None
    for cand in candidates:
        if cand.entity_type != RefType.EQUATION:
            continue
        if _extract_equation_number(cand.label) == number:
            return cand
    return None


_THEOREM_FAMILY_TYPES: frozenset[RefType] = frozenset({
    RefType.THEOREM,
    RefType.DEFINITION,
    RefType.PROOF,
    RefType.COROLLARY,
    RefType.EXAMPLE,
})


def _try_theorem_family(
    marker: RefMarker, candidates: list[ResolverCandidate]
) -> ResolverCandidate | None:
    """Match theorem-family markers by hierarchical number identity.

    Resolves THEOREM / DEFINITION / PROOF / COROLLARY / EXAMPLE markers
    (e.g. ``"Theorem 3.2"``, ``"Corollary 3.2"``, ``"Example 4"``,
    ``"Proof of Theorem 3.2"``) against a same-type candidate carrying
    the same hierarchical number. Mirrors :func:`_try_equation` but on
    the theorem-family prefix set.

    Cross-type isolation is enforced: a theorem marker never resolves to
    a definition / corollary candidate, even at the same number.
    Hierarchical numbers (``3.2``) do not collide with their components
    (``3`` / ``2``) because :func:`_extract_number` returns the full
    dotted form.

    NOTE: Plan 006_5 added the connector-side theorem-family detector, so
    theorem-family entities are now emitted on real pipeline data and this
    matcher resolves them by hierarchical number identity. It is also
    exercised by synthetic fixtures. (Whether a given OCR backend's snapshot
    contains these entities depends on when that snapshot was generated;
    pre-006_5 snapshots will lack them.)
    """
    if marker.marker_type not in _THEOREM_FAMILY_TYPES:
        return None
    number = _extract_number(_strip_prefix(marker.marker_type, marker.marker_text))
    if number is None:
        return None
    for cand in candidates:
        if cand.entity_type != marker.marker_type:
            continue
        cand_number = _extract_number(_strip_prefix(cand.entity_type, cand.label))
        if cand_number == number:
            return cand
    return None


def resolve_markers(
    markers: list[RefMarker],
    candidates: list[ResolverCandidate] | list[SemanticEntity],
) -> list[RefEdge]:
    """Resolve ``markers`` against ``candidates``.

    Args:
        markers: Markers to resolve.
        candidates: Either a list of :class:`ResolverCandidate` or a list
            of :class:`SemanticEntity` (the latter is auto-converted; the
            entity's ``item_ref`` becomes the target_ref and
            ``label or item_ref`` becomes the resolver label).

    Returns:
        One :class:`RefEdge` per input marker, in the input order. Every
        edge is either resolved with a populated ``target_ref``, or
        unresolved with ``resolved=False`` and
        ``resolution_method="unresolved"``.
    """
    pool = _to_candidates(candidates)
    edges: list[RefEdge] = []
    for marker in markers:
        edges.append(_resolve_one(marker, pool))
    return edges


def _to_candidates(
    candidates: list[ResolverCandidate] | list[SemanticEntity],
) -> list[ResolverCandidate]:
    pool: list[ResolverCandidate] = []
    for cand in candidates:
        if isinstance(cand, ResolverCandidate):
            pool.append(cand)
            continue
        # Pydantic model exposes attributes directly.
        pool.append(
            ResolverCandidate(
                target_ref=cand.item_ref,
                entity_type=RefType(cand.entity_type)
                if not isinstance(cand.entity_type, RefType)
                else cand.entity_type,
                label=cand.label or cand.item_ref,
            )
        )
    return pool


def _resolve_one(marker: RefMarker, pool: list[ResolverCandidate]) -> RefEdge:
    hit = _try_exact(marker, pool)
    if hit is not None:
        return RefEdge(
            marker=marker,
            target_ref=hit.target_ref,
            resolved=True,
            resolution_method="exact",
        )

    hit = _try_bibliography(marker, pool)
    if hit is not None:
        return RefEdge(
            marker=marker,
            target_ref=hit.target_ref,
            resolved=True,
            resolution_method="exact",
        )

    hit = _try_equation(marker, pool)
    if hit is not None:
        return RefEdge(
            marker=marker,
            target_ref=hit.target_ref,
            resolved=True,
            resolution_method="exact",
        )

    hit = _try_footnote(marker, pool)
    if hit is not None:
        return RefEdge(
            marker=marker,
            target_ref=hit.target_ref,
            resolved=True,
            resolution_method="exact",
        )

    hit = _try_theorem_family(marker, pool)
    if hit is not None:
        return RefEdge(
            marker=marker,
            target_ref=hit.target_ref,
            resolved=True,
            resolution_method="exact",
        )

    hit = _try_fuzzy(marker, pool)
    if hit is not None:
        return RefEdge(
            marker=marker,
            target_ref=hit.target_ref,
            resolved=True,
            resolution_method="fuzzy",
        )

    return RefEdge(
        marker=marker,
        target_ref=None,
        resolved=False,
        resolution_method="unresolved",
    )
