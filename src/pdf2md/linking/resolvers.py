"""Heuristic semantic relation resolvers for link candidates."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from pdf2md.linking.extract import LinkCandidate, normalise_text
from pdf2md.models.linked import LinkEvidence, LinkEvidenceKind, LinkedNodeType, LinkedRelationType, LinkStatus


@dataclass(frozen=True)
class ResolvedLink:
    relation_type: LinkedRelationType
    source_candidate_id: str
    target_candidate_id: str
    confidence: float
    status: LinkStatus
    evidence: tuple[LinkEvidence, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolverResult:
    links: tuple[ResolvedLink, ...] = ()
    warnings: tuple[str, ...] = ()


def _e(kind: LinkEvidenceKind, source_id: str | None, page_no: int | None, confidence: float, reason: str, **meta: Any) -> LinkEvidence:
    return LinkEvidence(kind=kind, source_id=source_id, page_no=page_no, confidence=confidence, reason=reason, metadata=meta)


def _sorted(candidates: Iterable[LinkCandidate]) -> list[LinkCandidate]:
    return sorted(candidates, key=lambda c: (c.page_no, c.order, c.consensus_block_id))


def _link(rt: LinkedRelationType, src: LinkCandidate, tgt: LinkCandidate, conf: float, kind: LinkEvidenceKind, reason: str, status: LinkStatus = LinkStatus.RESOLVED, **meta: Any) -> ResolvedLink:
    return ResolvedLink(rt, src.consensus_block_id, tgt.consensus_block_id, conf, status, (_e(kind, src.consensus_block_id, src.page_no, conf, reason, **meta),), meta)


def resolve_reading_order(candidates: list[LinkCandidate]) -> ResolverResult:
    excluded = {LinkedNodeType.PAGE_NUMBER, LinkedNodeType.HEADER, LinkedNodeType.FOOTER, LinkedNodeType.DOCUMENT}
    body = [c for c in _sorted(candidates) if c.node_type not in excluded]
    links = [_link(LinkedRelationType.FOLLOWS, body[i], body[i + 1], 0.95, LinkEvidenceKind.READING_ORDER, "adjacent reading order") for i in range(len(body) - 1)]
    return ResolverResult(tuple(links), ())


def _section_level(candidate: LinkCandidate) -> int | None:
    if "section_level" in candidate.metadata:
        return int(candidate.metadata["section_level"])
    text = candidate.text.strip()
    m = re.match(r"^(\d+(?:\.\d+)*)\b", text)
    if m:
        return len(m.group(1).split("."))
    return None


def resolve_section_hierarchy(candidates: list[LinkCandidate]) -> ResolverResult:
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    stack: list[tuple[int, LinkCandidate]] = []
    current: LinkCandidate | None = None
    body_types = {LinkedNodeType.PARAGRAPH, LinkedNodeType.LIST, LinkedNodeType.LIST_ITEM, LinkedNodeType.FIGURE, LinkedNodeType.TABLE, LinkedNodeType.CAPTION, LinkedNodeType.EQUATION, LinkedNodeType.FOOTNOTE, LinkedNodeType.REFERENCE_ITEM}
    for c in _sorted(candidates):
        if c.node_type in {LinkedNodeType.SECTION, LinkedNodeType.REFERENCE_SECTION}:
            level = _section_level(c)
            if level is None:
                level = 1
                warnings.append(f"section_level_missing:{c.consensus_block_id}")
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                links.append(_link(LinkedRelationType.PARENT_OF, stack[-1][1], c, 0.85, LinkEvidenceKind.SECTION_HIERARCHY, "section nesting", level=level))
            stack.append((level, c))
            current = c
        elif c.node_type in body_types and current is not None:
            links.append(_link(LinkedRelationType.CONTAINS, current, c, 0.80, LinkEvidenceKind.SECTION_HIERARCHY, "nearest preceding section"))
    return ResolverResult(tuple(links), tuple(warnings))


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", normalise_text(text)) if len(t) > 1}


def _toc_title_page(text: str) -> tuple[str, int | None]:
    m = re.match(r"\s*(?:\d+(?:\.\d+)*\s+)?(.+?)\s*(?:\.{2,}|\s{2,})\s*(\d+)\s*$", text)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return text.strip(), None


def resolve_toc_links(candidates: list[LinkCandidate]) -> ResolverResult:
    sections = [c for c in candidates if c.node_type in {LinkedNodeType.SECTION, LinkedNodeType.REFERENCE_SECTION}]
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    for toc in [c for c in candidates if c.node_type == LinkedNodeType.TOC_ENTRY]:
        title, page = _toc_title_page(toc.text)
        title_norm = normalise_text(re.sub(r"^\d+(?:\.\d+)*\s+", "", title))
        exact = [s for s in sections if normalise_text(re.sub(r"^\d+(?:\.\d+)*\s+", "", s.text)) == title_norm]
        if page is not None:
            page_exact = [s for s in exact if s.page_no == page]
            if page_exact:
                exact = page_exact
        if not exact:
            tt = _tokens(title)
            scored = [(len(tt & _tokens(s.text)), s) for s in sections if len(tt & _tokens(s.text)) > 0]
            scored.sort(key=lambda x: x[0], reverse=True)
            exact = [s for score, s in scored if score == (scored[0][0] if scored else -1)]
        if len(exact) == 1:
            links.append(_link(LinkedRelationType.TOC_POINTS_TO, toc, exact[0], 0.82, LinkEvidenceKind.TOC_PATTERN, "toc target match", title=title, target_page=page))
        elif len(exact) > 1:
            warnings.append(f"toc_target_ambiguous:{toc.consensus_block_id}")
        else:
            warnings.append(f"toc_target_missing:{toc.consensus_block_id}")
    return ResolverResult(tuple(links), tuple(warnings))

_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def _clean_number_text(text: str) -> str:
    return normalise_text(text).strip(" .[]()")


def _is_roman_number(text: str) -> bool:
    token = _clean_number_text(text)
    return bool(token) and all(ch in _ROMAN for ch in token)


def _number_value(text: str) -> int | None:
    token = _clean_number_text(text)
    if token.isdigit():
        return int(token)
    total = prev = 0
    if token and all(ch in _ROMAN for ch in token):
        for ch in reversed(token):
            val = _ROMAN[ch]
            total += -val if val < prev else val
            prev = max(prev, val)
        return total
    return None


def resolve_page_number_sequence(candidates: list[LinkCandidate]) -> ResolverResult:
    nums = [c for c in _sorted(candidates) if c.node_type == LinkedNodeType.PAGE_NUMBER and _number_value(c.text) is not None]
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    for a, b in zip(nums, nums[1:]):
        av, bv = _number_value(a.text), _number_value(b.text)
        assert av is not None and bv is not None
        is_front_matter_switch = _is_roman_number(a.text) and _clean_number_text(b.text).isdigit() and b.page_no == a.page_no + 1
        if bv == av + 1:
            links.append(_link(LinkedRelationType.PAGE_NUMBER_SEQUENCE_NEXT, a, b, 0.86, LinkEvidenceKind.PAGE_SEQUENCE, "page number sequence", source_value=av, target_value=bv))
        elif is_front_matter_switch:
            links.append(_link(LinkedRelationType.PAGE_NUMBER_SEQUENCE_NEXT, a, b, 0.62, LinkEvidenceKind.PAGE_SEQUENCE, "roman front matter switches to arabic numbering", status=LinkStatus.RESOLVED_LOW_CONFIDENCE, source_value=av, target_value=bv))
        elif b.page_no <= a.page_no:
            warnings.append(f"page_number_sequence_conflict:{a.consensus_block_id}")
        else:
            warnings.append(f"page_number_sequence_gap:{a.consensus_block_id}")
    return ResolverResult(tuple(links), tuple(warnings))


def resolve_repeating_headers_footers(candidates: list[LinkCandidate]) -> ResolverResult:
    links: list[ResolvedLink] = []
    for node_type, rel_type in ((LinkedNodeType.HEADER, LinkedRelationType.HEADER_REPEATS_AS), (LinkedNodeType.FOOTER, LinkedRelationType.FOOTER_REPEATS_AS)):
        groups: dict[str, list[LinkCandidate]] = defaultdict(list)
        for c in candidates:
            text = normalise_text(c.text)
            if c.node_type == node_type and text and _number_value(text) is None:
                groups[text].append(c)
        for group in groups.values():
            for a, b in zip(_sorted(group), _sorted(group)[1:]):
                links.append(_link(rel_type, a, b, 0.82, LinkEvidenceKind.TEXT_PATTERN, "repeating header/footer"))
    return ResolverResult(tuple(links), ())


def resolve_captions(candidates: list[LinkCandidate]) -> ResolverResult:
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    figures = [c for c in candidates if c.node_type == LinkedNodeType.FIGURE]
    tables = [c for c in candidates if c.node_type == LinkedNodeType.TABLE]
    for cap in [c for c in candidates if c.node_type == LinkedNodeType.CAPTION]:
        low = normalise_text(cap.text)
        pool = tables if low.startswith("table") else figures if low.startswith("figure") else figures + tables
        same = [t for t in pool if t.page_no == cap.page_no]
        if not same:
            same = [t for t in pool if abs(t.page_no - cap.page_no) == 1]
            conf = 0.55
            status = LinkStatus.RESOLVED_LOW_CONFIDENCE
        else:
            conf = 0.84
            status = LinkStatus.RESOLVED
        if same:
            same.sort(key=lambda t: (abs(t.order - cap.order), abs(t.page_no - cap.page_no)))
            if len(same) > 1 and abs(same[0].order - cap.order) == abs(same[1].order - cap.order):
                warnings.append(f"caption_target_ambiguous:{cap.consensus_block_id}")
            else:
                links.append(_link(LinkedRelationType.CAPTION_OF, cap, same[0], conf, LinkEvidenceKind.CAPTION_PATTERN, "nearest caption target", status=status))
        else:
            warnings.append(f"caption_target_missing:{cap.consensus_block_id}")
    return ResolverResult(tuple(links), tuple(warnings))


def _markers(text: str) -> set[str]:
    return set(re.findall(r"\[(\d+)\]|\b(\d+)\.", text)) | {(m, "") for m in re.findall(r"(?<!\d)(\d)(?!\d)", text)}


def _flat_markers(text: str) -> set[str]:
    out = set()
    for a, b in _markers(text):
        out.add(a or b)
    return out


def resolve_footnotes(candidates: list[LinkCandidate]) -> ResolverResult:
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    anchors = [c for c in candidates if c.node_type not in {LinkedNodeType.FOOTNOTE, LinkedNodeType.PAGE_NUMBER, LinkedNodeType.HEADER, LinkedNodeType.FOOTER, LinkedNodeType.SECTION, LinkedNodeType.REFERENCE_SECTION}]
    for fn in [c for c in candidates if c.node_type == LinkedNodeType.FOOTNOTE]:
        marks = _flat_markers(fn.text)
        matches = [a for a in anchors if a.page_no == fn.page_no and marks & _flat_markers(a.text)]
        bracket_matches = [a for a in matches if any(f"[{mark}]" in a.text for mark in marks)]
        if bracket_matches:
            matches = bracket_matches
        if len(matches) == 1:
            links.append(_link(LinkedRelationType.FOOTNOTE_ANCHOR_FOR, matches[0], fn, 0.78, LinkEvidenceKind.FOOTNOTE_PATTERN, "same-page footnote marker"))
        elif len(matches) > 1:
            warnings.append(f"footnote_anchor_ambiguous:{fn.consensus_block_id}")
        else:
            warnings.append(f"footnote_anchor_missing:{fn.consensus_block_id}")
    return ResolverResult(tuple(links), tuple(warnings))


def _eq_no(c: LinkCandidate) -> int | None:
    if "number" in c.metadata:
        return int(c.metadata["number"])
    m = re.search(r"\((\d+)\)", c.text)
    return int(m.group(1)) if m else None


def resolve_equation_sequence(candidates: list[LinkCandidate]) -> ResolverResult:
    eqs = [c for c in _sorted(candidates) if c.node_type == LinkedNodeType.EQUATION]
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    for a, b in zip(eqs, eqs[1:]):
        av, bv = _eq_no(a), _eq_no(b)
        if av is not None and bv is not None and bv != av + 1:
            warnings.append(f"equation_sequence_gap:{a.consensus_block_id}")
            continue
        links.append(_link(LinkedRelationType.EQUATION_SEQUENCE_NEXT, a, b, 0.83, LinkEvidenceKind.TEXT_PATTERN, "equation sequence", source_number=av, target_number=bv))
    return ResolverResult(tuple(links), tuple(warnings))


def _object_no(candidate: LinkCandidate, caption_lookup: dict[str, LinkCandidate] | None = None) -> int | None:
    if "number" in candidate.metadata:
        return int(candidate.metadata["number"])
    if "sequence_number" in candidate.metadata:
        return int(candidate.metadata["sequence_number"])
    m = re.search(r"\b(?:figure|fig\.?|table)\s*(\d+)\b", candidate.text, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    if caption_lookup and candidate.consensus_block_id in caption_lookup:
        return _object_no(caption_lookup[candidate.consensus_block_id])
    return None


def resolve_figure_table_sequence(candidates: list[LinkCandidate]) -> ResolverResult:
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    # If extraction metadata supplied a caption target id, use it to infer an object number.
    caption_lookup = {
        str(c.metadata["caption_target_id"]): c
        for c in candidates
        if c.node_type == LinkedNodeType.CAPTION and "caption_target_id" in c.metadata
    }
    for nt, rt, warning_prefix in (
        (LinkedNodeType.FIGURE, LinkedRelationType.FIGURE_SEQUENCE_NEXT, "figure_sequence_gap"),
        (LinkedNodeType.TABLE, LinkedRelationType.TABLE_SEQUENCE_NEXT, "table_sequence_gap"),
    ):
        nodes = [c for c in _sorted(candidates) if c.node_type == nt]
        for a, b in zip(nodes, nodes[1:]):
            av, bv = _object_no(a, caption_lookup), _object_no(b, caption_lookup)
            if av is not None and bv is not None and bv != av + 1:
                warnings.append(f"{warning_prefix}:{a.consensus_block_id}")
                continue
            links.append(_link(rt, a, b, 0.80, LinkEvidenceKind.CAPTION_PATTERN, "object sequence", source_number=av, target_number=bv))
    return ResolverResult(tuple(links), tuple(warnings))


def _author_years(text: str) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for author, year in re.findall(r"\(([A-Z][A-Za-z-]+)(?:\s+et\s+al\.)?,\s*((?:19|20)\d{2})\)", text):
        pairs.add((author.casefold(), year))
    return pairs


def resolve_references(candidates: list[LinkCandidate]) -> ResolverResult:
    links: list[ResolvedLink] = []
    warnings: list[str] = []
    ref_sections = [c for c in candidates if c.node_type == LinkedNodeType.REFERENCE_SECTION or normalise_text(c.text) in {"references", "bibliography", "works cited"}]
    items = [c for c in _sorted(candidates) if c.node_type == LinkedNodeType.REFERENCE_ITEM]
    if not ref_sections and items:
        warnings.append("reference_section_missing")
    for a, b in zip(items, items[1:]):
        links.append(_link(LinkedRelationType.REFERENCE_SEQUENCE_NEXT, a, b, 0.82, LinkEvidenceKind.REFERENCE_PATTERN, "reference item sequence"))
    by_marker: dict[str, list[LinkCandidate]] = defaultdict(list)
    by_author_year: dict[tuple[str, str], list[LinkCandidate]] = defaultdict(list)
    for item in items:
        marker = re.match(r"\s*\[(\d+)\]", item.text)
        if marker:
            by_marker[marker.group(1)].append(item)
        lowered = item.text.casefold()
        years = re.findall(r"(?:19|20)\d{2}", item.text)
        first_author = re.match(r"\s*(?:\[\d+\]\s*)?([A-Z][A-Za-z-]+)", item.text)
        if first_author:
            for year in years:
                by_author_year[(first_author.group(1).casefold(), year)].append(item)
        for author, year in _author_years(item.text):
            by_author_year[(author, year)].append(item)
    for c in candidates:
        if c.node_type in {LinkedNodeType.PARAGRAPH, LinkedNodeType.SECTION}:
            for marker in re.findall(r"\[(\d+)\]", c.text):
                targets = by_marker.get(marker, [])
                if len(targets) == 1:
                    links.append(_link(LinkedRelationType.REFERENCES, c, targets[0], 0.77, LinkEvidenceKind.REFERENCE_PATTERN, "bibliographic marker", marker=marker))
                elif len(targets) > 1:
                    warnings.append(f"reference_target_ambiguous:{c.consensus_block_id}")
                elif items:
                    warnings.append(f"reference_target_missing:{c.consensus_block_id}")
            for author_year in _author_years(c.text):
                targets = by_author_year.get(author_year, [])
                if len(targets) == 1:
                    links.append(_link(LinkedRelationType.REFERENCES, c, targets[0], 0.72, LinkEvidenceKind.REFERENCE_PATTERN, "author-year bibliographic marker", author=author_year[0], year=author_year[1]))
                elif len(targets) > 1:
                    warnings.append(f"reference_target_ambiguous:{c.consensus_block_id}")
                elif items:
                    warnings.append(f"reference_target_missing:{c.consensus_block_id}")
    return ResolverResult(tuple(links), tuple(warnings))


def run_all_resolvers(candidates: list[LinkCandidate]) -> ResolverResult:
    all_links: list[ResolvedLink] = []
    all_warnings: list[str] = []
    for resolver in (resolve_reading_order, resolve_section_hierarchy, resolve_toc_links, resolve_page_number_sequence, resolve_repeating_headers_footers, resolve_captions, resolve_footnotes, resolve_equation_sequence, resolve_figure_table_sequence, resolve_references):
        result = resolver(candidates)
        all_links.extend(result.links)
        all_warnings.extend(result.warnings)
    seen = set()
    deduped = []
    for link in all_links:
        key = (link.relation_type, link.source_candidate_id, link.target_candidate_id)
        if key not in seen:
            seen.add(key)
            deduped.append(link)
    return ResolverResult(tuple(deduped), tuple(all_warnings))
