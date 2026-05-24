"""Parse a GROBID TEI XML document into reference markers and bibliography entries.

This is a deliberately narrow parser. Plan 005 only requires extraction
of cross-reference markers (figure / table / equation / bibliography /
footnote) and bibliography entries, sufficient to validate that the
GROBID service actually returned structured data on the smoke PDF.

Plan 006 will extend this to a full ``CrossReferenceGraph`` with target
resolution; for now we emit a plain dict.
"""

from __future__ import annotations

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
        for ref in body.findall(".//tei:ref", _NS):
            ref_type_attr = ref.attrib.get("type", "")
            marker_type = _REF_TYPE_TO_MARKER.get(ref_type_attr, ref_type_attr or "unknown")
            text = (ref.text or "").strip() or _inner_text(ref)
            target = ref.attrib.get("target")
            if not text:
                continue
            result.markers.append(
                TeiMarker(marker_type=marker_type, marker_text=text, target=target)
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
