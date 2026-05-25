"""Parse a GROBID TEI XML document into reference markers and bibliography entries.

This is a deliberately narrow parser. Plan 005 only requires extraction
of cross-reference markers (figure / table / equation / bibliography /
footnote) and bibliography entries, sufficient to validate that the
GROBID service actually returned structured data on the smoke PDF.

Plan 006 will extend this to a full ``CrossReferenceGraph`` with target
resolution; for now we emit a plain dict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET


TEI_NS = "http://www.tei-c.org/ns/1.0"
_NS = {"tei": TEI_NS}


# Map GROBID's ``ref type`` attribute values to our canonical marker types.
# GROBID uses: "figure", "table", "formula", "bibr", "section".
_REF_TYPE_TO_MARKER: dict[str, str] = {
    "figure": "figure",
    "table": "table",
    "formula": "equation",
    "bibr": "bibliography",
    "section": "section",
    "biblio": "bibliography",  # not standard in TEI, but handle defensively
}


# Canonical surface forms for bibliography markers. GROBID's TEI
# parser occasionally tags non-bibliography fragments with
# ``type="bibr"`` (e.g. broken brackets on Example/Corollary refs,
# bare equation numbers, "p. 539;" page-ref fragments). These would
# otherwise propagate downstream as bibliography markers that cannot
# resolve against any candidate. The patterns below capture the two
# canonical bib citation forms used in scientific writing:
#
# - Numeric brackets: "[15]", "[15, 17]", "[12, 14-16]", "[12-14]"
# - Author-year:      "(Smith, 2020)", "(Smith et al., 2020a)",
#                     "(Smith and Jones, 2020)"
#
# Markers tagged ``bibr`` whose text matches NEITHER pattern are
# re-routed to a more specific marker_type when possible (equation /
# example / corollary, based on simple surface-form hints) or dropped
# entirely (page references like "p. 539;" carry no semantic-layer
# meaning).
_BIB_NUMERIC_RE = re.compile(r"^\[\s*\d+(\s*[,–—-]\s*\d+)*\s*]$")
_BIB_AUTHOR_YEAR_RE = re.compile(
    r"^\(\s*[A-Z][A-Za-z\-]+"          # First author surname
    # Optional continuation: either ", and SURNAME" / "& SURNAME" OR
    # the standalone "et al." (no trailing surname). Either form may
    # repeat zero or more times.
    r"(?:"
    r"\s+(?:and|&)\s+[A-Za-z\-]+"
    r"|"
    r"\s+et\s+al\.?"
    r")*"
    r"(?:\s*,)?\s+\d{4}[a-z]?\s*\)$"   # year, optional disambiguator
)

# Broken-bracket forms that show up when GROBID splits a multi-citation
# like ``[14, 21]`` across two ``<ref>`` elements (``[14,`` + ``21]``) are
# handled by the default-keep clause in :func:`_classify_bibr` — they
# fail the canonical regexes, don't match any reroute keyword, don't
# match the drop patterns, and so fall through to bibliography. The
# resolver's :func:`pdf2md.semantic.resolver._bibliography_number`
# accepts these via a loosened number extractor so each broken half
# still resolves to its bib entry independently.

# When a bibr marker fails the bib regexes, try these keyword-based
# patterns to re-route to a more specific marker_type. The patterns
# require a *keyword* (Eq., Theorem, Corollary, …) — bare numbers or
# bare parenthesised numbers are NOT rerouted. GROBID frequently
# emits a bibliography citation as bare digits (when the brackets are
# rendered outside the `<ref>` element), so a pattern like `^\d+$`
# would wrongly steal hundreds of legitimate bibliography markers.
# We deliberately do NOT use a word-boundary at the end of these
# prefix patterns — GROBID's mis-typed bibr fragments often have
# punctuation glyphs immediately after the type keyword (e.g.
# "Ex. 3.3]"), and `\b` does not trigger between `.` and ` `.
_REROUTE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("equation",    re.compile(r"^Eq(?:s|\.|uation|\.s)?[\s.\d(]", re.IGNORECASE)),
    ("example",     re.compile(r"^Ex(?:ample|\.)", re.IGNORECASE)),
    ("corollary",   re.compile(r"^Corollary", re.IGNORECASE)),
    ("theorem",     re.compile(r"^Theorem", re.IGNORECASE)),
    ("definition",  re.compile(r"^Definition", re.IGNORECASE)),
    ("proof",       re.compile(r"^Proof", re.IGNORECASE)),
    ("section",     re.compile(r"^Sec(?:tion|\.)", re.IGNORECASE)),
    ("chapter",     re.compile(r"^Chapter", re.IGNORECASE)),
]

# Drop patterns — text that is clearly NOT a cross-reference of any
# kind. Conservative: only catches the failure modes we've actually
# observed in the wild (GROBID example02 produced exactly these).
_DROP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^p\.\s*\d", re.IGNORECASE),  # page references: "p. 539;", "p.42"
    re.compile(r"^\[[A-Z]\]$"),                # single-letter brackets: "[L]"
]


def _classify_bibr(marker_text: str) -> str | None:
    """Validate or re-route a TEI ``<ref type="bibr">`` marker.

    Strategy is **default-keep** — if GROBID tagged a fragment as
    ``bibr`` we trust that classification unless there's positive
    evidence to reroute or drop. This avoids the trap of moving
    legitimate bibliography markers (often rendered as bare digits
    like ``15`` when GROBID stripped the brackets) into other types
    where they have no candidate to resolve against.

    Returns:
        ``"bibliography"`` when the marker is canonical or unclassifiable
        (the safe default — GROBID's bibr tag is honoured),
        a different marker_type string when the text contains a clear
        keyword that identifies it as something else (e.g. "Eq.",
        "Theorem"),
        ``None`` when the text matches one of the few known garbage
        patterns (page-references, single-letter brackets).
    """
    text = marker_text.strip()
    if not text:
        return None
    # Canonical bibliography forms — definite keep.
    if _BIB_NUMERIC_RE.match(text) or _BIB_AUTHOR_YEAR_RE.match(text):
        return "bibliography"
    # Strong evidence to reroute (a math/cross-ref keyword).
    for target_type, pattern in _REROUTE_PATTERNS:
        if pattern.match(text):
            return target_type
    # Strong evidence to drop (known garbage patterns).
    for pattern in _DROP_PATTERNS:
        if pattern.match(text):
            return None
    # Default: honour GROBID's bibr classification. Bare numbers,
    # parenthesised numbers, and other ambiguous forms stay as
    # bibliography — better unresolved than miscategorised.
    return "bibliography"


@dataclass(frozen=True)
class TeiMarker:
    """A reference marker extracted from a TEI ``<ref>`` element.

    Attributes:
        marker_type: Canonical marker-type slug used across the three
            Plan 005 semantic backends.
        marker_text: Inner text of the ``<ref>`` element.
        target: The ``target`` attribute (e.g. ``"#fig_0"``), or ``None``
            if absent.
    """

    marker_type: str
    marker_text: str
    target: str | None


@dataclass(frozen=True)
class TeiBibEntry:
    """A bibliography entry extracted from ``<listBibl>``.

    Attributes:
        ref_id: Value of the ``xml:id`` attribute on the ``<biblStruct>``.
        raw_text: Concatenated inner text of the entry (best-effort).
    """

    ref_id: str
    raw_text: str


@dataclass(frozen=True)
class TeiParseResult:
    """Parsed view of a GROBID TEI document.

    Attributes:
        markers: All cross-reference markers found in body text.
        bib_entries: All bibliography entries.
        warnings: Non-fatal issues encountered while parsing.
    """

    markers: list[TeiMarker] = field(default_factory=list)
    bib_entries: list[TeiBibEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _xml_id(elem: ET.Element) -> str | None:
    """Return the ``xml:id`` attribute, regardless of namespace prefix."""
    return elem.attrib.get("{http://www.w3.org/XML/1998/namespace}id")


def _inner_text(elem: ET.Element) -> str:
    """Return the concatenated text of ``elem`` and its descendants."""
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_inner_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(p.strip() for p in parts if p and p.strip())


def parse_tei(tei_xml: str) -> TeiParseResult:
    """Parse GROBID TEI XML into a :class:`TeiParseResult`.

    Args:
        tei_xml: The TEI XML body returned by
            ``/api/processFulltextDocument``.

    Returns:
        A :class:`TeiParseResult` with markers, bibliography entries, and
        any parser warnings. Never raises on malformed inner content;
        only an outright XML parse failure (``ParseError``) propagates.
    """
    result = TeiParseResult()

    try:
        root = ET.fromstring(tei_xml)
    except ET.ParseError as exc:
        raise ValueError(f"GROBID returned invalid XML: {exc}") from exc

    body = root.find(".//tei:body", _NS)
    if body is None:
        result.warnings.append("no <body> element in TEI; backend returned a header-only document")
    else:
        dropped_garbage = 0
        rerouted: dict[str, int] = {}
        for ref in body.findall(".//tei:ref", _NS):
            ref_type_attr = ref.attrib.get("type", "")
            marker_type = _REF_TYPE_TO_MARKER.get(ref_type_attr, ref_type_attr or "unknown")
            text = (ref.text or "").strip() or _inner_text(ref)
            target = ref.attrib.get("target")
            if not text:
                continue

            # Tighten bibliography classification — GROBID occasionally
            # tags page-refs, orphan brackets, and bare equation numbers
            # as ``<ref type="bibr">``. Drop the garbage and re-route the
            # mis-typed ones so they don't poison the downstream
            # bibliography → reference_item resolution.
            if marker_type == "bibliography":
                classified = _classify_bibr(text)
                if classified is None:
                    dropped_garbage += 1
                    continue
                if classified != "bibliography":
                    marker_type = classified
                    rerouted[classified] = rerouted.get(classified, 0) + 1

            result.markers.append(
                TeiMarker(marker_type=marker_type, marker_text=text, target=target)
            )
        if dropped_garbage:
            result.warnings.append(
                f"dropped {dropped_garbage} non-canonical bibr marker(s) from TEI parse",
            )
        for new_type, n in rerouted.items():
            result.warnings.append(
                f"rerouted {n} bibr marker(s) to type={new_type}",
            )

    list_bibl = root.find(".//tei:listBibl", _NS)
    if list_bibl is not None:
        for entry in list_bibl.findall("tei:biblStruct", _NS):
            ref_id = _xml_id(entry) or ""
            raw_text = _inner_text(entry)
            if not ref_id and not raw_text:
                continue
            result.bib_entries.append(TeiBibEntry(ref_id=ref_id, raw_text=raw_text))

    return result


def summarise(parsed: TeiParseResult) -> dict[str, int]:
    """Return a count of markers grouped by ``marker_type``, plus bib count."""
    counts: dict[str, int] = {}
    for m in parsed.markers:
        counts[m.marker_type] = counts.get(m.marker_type, 0) + 1
    counts["_bib_entries"] = len(parsed.bib_entries)
    return counts
