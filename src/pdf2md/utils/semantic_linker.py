from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
from typing import Any

EQ_NUM_RE = re.compile(r"^\(?\s*(\d+(?:\.\d+)+)\s*\)?$")
EQ_TAG_RE = re.compile(r"\\tag\{\s*(\d+(?:\.\d+)*)\s*\}")
EQ_REF_RE = re.compile(r"\b(?:Eq\.?|Equation)\s*\(?\s*(\d+(?:\.\d+)*)\s*\)?", re.IGNORECASE)
FIG_LABEL_RE = re.compile(r"\b(?:Figure|Fig\.)\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
TABLE_LABEL_RE = re.compile(r"\bTable\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
SECTION_REF_RE = re.compile(r"\b(?:Section|Chap\.?|Chapter)\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
BIB_REF_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")
FOOTNOTE_BODY_RE = re.compile(r"^\s*(\d+)\s+")


def load_consensus_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_consensus_report(report: Any) -> list[str]:
    warnings: list[str] = []
    if not isinstance(report, dict):
        return ["Report is not a dictionary"]
    if report.get("schema_name") != "pdf2md.consensus_report":
        warnings.append("Unexpected schema_name")
    if not isinstance(report.get("pages"), list):
        warnings.append("Missing or invalid pages list")
    return warnings


def extract_equation_number(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip()
    for rex in (EQ_TAG_RE, EQ_REF_RE):
        m = rex.search(t)
        if m:
            return m.group(1)
    m = re.search(r"\(\s*(\d+(?:\.\d+)+)\s*\)$", t)
    if m:
        return m.group(1)
    m = EQ_NUM_RE.match(t)
    return m.group(1) if m else None


def extract_figure_label(text: str | None) -> str | None:
    m = FIG_LABEL_RE.search(text or "")
    return m.group(1) if m else None


def extract_table_label(text: str | None) -> str | None:
    m = TABLE_LABEL_RE.search(text or "")
    return m.group(1) if m else None


def extract_footnote_marker(text: str | None) -> list[str]:
    if not text:
        return []
    hits = set()
    for r in [re.finditer(r"\^\{?(\d+)\}?", text), re.finditer(r"\(\s*\^\{?(\d+)\}?\s*\)", text)]:
        for m in r:
            n = int(m.group(1))
            if 1 <= n <= 99:
                hits.add(m.group(1))
    return sorted(hits)


def normalise_latex(text: str | None) -> dict[str, str | None]:
    t = (text or "").strip()
    label = extract_equation_number(t)
    t = EQ_TAG_RE.sub("", t)
    t = re.sub(r"\(\s*\d+(?:\.\d+)+\s*\)\s*$", "", t)
    t = t.replace("\\left", "").replace("\\right", "")
    t = re.sub(r"\{\s*\\bf\s+([^}]+)\}", r"\\mathbf{\1}", t)
    t = re.sub(r"\\(?:quad|,|\s)", "", t)
    t = re.sub(r"\s+", "", t)
    return {"body_key": t.strip(" .;,"), "label": label}


def _center(b: list[float] | None) -> tuple[float, float] | None:
    if not b:
        return None
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def _conflicts_for_group(g: dict[str, Any], page: dict[str, Any]) -> list[dict[str, Any]]:
    gid = g.get("group_id")
    members = set(g.get("members") or [])
    out: list[dict[str, Any]] = []
    for c in page.get("conflicts") or []:
        if gid in c.get("group_ids", []) or gid == c.get("group_id"):
            out.append(c)
            continue
        evidence_ids = set(c.get("evidence_ids") or [])
        if members and evidence_ids and members.intersection(evidence_ids):
            out.append(c)
    return out


def _has_conflict(g: dict[str, Any], page: dict[str, Any]) -> bool:
    return bool(g.get("conflicts") or _conflicts_for_group(g, page))


def _anchor_source_fields(g: dict[str, Any], page: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_group_id": g.get("group_id"),
        "source_group_kind": g.get("kind"),
        "source_group_sources": g.get("sources") or [],
        "source_group_members": g.get("members") or [],
        "source_group_agreement": g.get("agreement"),
        "source_group_conflicts": g.get("conflicts") or _conflicts_for_group(g, page),
    }


def build_semantic_links(report: dict[str, Any], source_path: Path) -> dict[str, Any]:
    anchors: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    page_reports = []
    anchor_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    eq_anchor_by_target: dict[str, dict[str, Any]] = {}

    for page in report.get("pages", []):
        pidx = int(page.get("page_index", 0))
        pnum = pidx + 1
        groups = page.get("candidate_groups") or []
        formulas = [g for g in groups if g.get("kind") == "formula"]
        pictures = [g for g in groups if g.get("kind") == "picture"]
        tables = [g for g in groups if g.get("kind") == "table"]
        page_anchor_ids, page_ref_ids, page_att_ids = [], [], []

        for gi, g in enumerate(groups):
            gid = g.get("group_id", f"p{pidx:04d}_g{gi:04d}")
            text = g.get("representative_text") or ""
            kind = g.get("kind")
            bbox = g.get("representative_bbox")

            if kind == "formula" or any(tok in text for tok in ["\\frac", "\\mathbf", "\\begin", "\\boxed", "=", "\\tag", "\\quad"]):
                norm = normalise_latex(text)
                label = norm["label"]
                aid = f"eq:{label}" if label else f"eq:{gid}"
                status = "resolved_with_conflict" if _has_conflict(g, page) and label else ("resolved" if label else "unlabelled")
                src = _anchor_source_fields(g, page)
                a = {"anchor_id": aid, "anchor_type": "equation", "label": label, "canonical_text": text, "target_group_id": gid, "page_index": pidx, "page_number": pnum, "bbox": bbox, "source_groups": [gid], "confidence": 0.8 if label else 0.5, "status": status, "warnings": [], "formula_candidates": [{"representative_text": text, "group_id": gid, "sources": g.get("sources") or [], "members": g.get("members") or [], "agreement": g.get("agreement"), "conflicts": g.get("conflicts") or []}], **src}
                anchors.append(a); page_anchor_ids.append(aid)
                eq_anchor_by_target[gid] = a
                if label:
                    anchor_map.setdefault(("equation", label), []).append(a)

            eq_num = extract_equation_number(text)
            if eq_num and kind != "formula" and EQ_NUM_RE.match(text.strip()):
                best = None
                for f in formulas:
                    score = 0.3
                    fb, nb = f.get("representative_bbox"), bbox
                    if fb and nb:
                        fy0, fy1 = fb[1], fb[3]
                        nyc = _center(nb)[1]
                        if fy0 <= nyc <= fy1:
                            score += 0.3
                        if _center(nb)[0] > _center(fb)[0]:
                            score += 0.2
                    if len(formulas) == 1:
                        score += 0.1
                    if not fb or not nb:
                        score += 0.2
                    score += 0.1
                    if best is None or score > best[0]:
                        best = (score, f)
                if best and best[0] >= 0.55:
                    f = best[1]
                    target_gid = f.get("group_id")
                    aid = f"eq:{eq_num}"
                    existing = eq_anchor_by_target.get(target_gid)
                    if existing:
                        if existing["anchor_id"] != aid:
                            existing.setdefault("alias_ids", []).append(existing["anchor_id"])
                            old_id = existing["anchor_id"]
                            existing["anchor_id"] = aid
                            existing["label"] = eq_num
                            page_anchor_ids[:] = [aid if x == old_id else x for x in page_anchor_ids]
                            if existing["status"] == "unlabelled":
                                existing["status"] = "resolved_with_conflict" if _has_conflict(f, page) else "resolved"
                            anchor_map.setdefault(("equation", eq_num), []).append(existing)
                    else:
                        src = _anchor_source_fields(f, page)
                        a = {"anchor_id": aid, "anchor_type": "equation", "label": eq_num, "canonical_text": f.get("representative_text") or "", "target_group_id": target_gid, "page_index": pidx, "page_number": pnum, "bbox": f.get("representative_bbox"), "source_groups": [target_gid, gid], "confidence": min(1.0, best[0]), "status": "resolved_with_conflict" if _has_conflict(f, page) else "resolved", "warnings": [], "formula_candidates": [{"representative_text": f.get("representative_text") or "", "group_id": target_gid, "sources": f.get("sources") or [], "members": f.get("members") or [], "agreement": f.get("agreement"), "conflicts": f.get("conflicts") or []}], **src}
                        anchors.append(a); page_anchor_ids.append(aid)
                        eq_anchor_by_target[target_gid] = a
                        anchor_map.setdefault(("equation", eq_num), []).append(a)
                    att_id = f"attach_p{pidx:04d}_{len(attachments)+1:04d}"
                    attachments.append({"attachment_id": att_id, "attachment_type": "equation_number_to_equation", "source_group_id": gid, "target_group_id": target_gid, "anchor_id": aid, "page_index": pidx, "confidence": min(1.0, best[0]), "reason": "geometry/reading-order"})
                    page_att_ids.append(att_id)
                else:
                    unresolved.append({"type": "equation_number_unattached", "group_id": gid, "label": eq_num, "page_index": pidx})

            fl = extract_figure_label(text)
            create_fig_anchor = bool(fl) and (kind in {"caption", "picture"} or (kind == "title" and (pictures or tables)))
            if create_fig_anchor:
                target = pictures[0] if pictures else g
                aid = f"fig:{fl}"
                src = _anchor_source_fields(g, page)
                a = {"anchor_id": aid, "anchor_type": "figure", "label": fl, "canonical_text": text, "target_group_id": target.get("group_id"), "page_index": pidx, "page_number": pnum, "bbox": target.get("representative_bbox"), "source_groups": [gid], "confidence": 0.7 if pictures else 0.45, "status": "resolved_with_conflict" if _has_conflict(g, page) and pictures else ("resolved" if pictures else "caption_only"), "warnings": [], **src}
                anchors.append(a); page_anchor_ids.append(aid); anchor_map.setdefault(("figure", fl), []).append(a)
                if pictures and gid != target.get("group_id"):
                    att_id = f"attach_p{pidx:04d}_{len(attachments)+1:04d}"
                    attachments.append({"attachment_id": att_id, "attachment_type": "caption_to_figure", "source_group_id": gid, "target_group_id": target.get("group_id"), "anchor_id": aid, "page_index": pidx, "confidence": 0.7, "reason": "caption label + nearest picture"})
                    page_att_ids.append(att_id)

            tl = extract_table_label(text)
            create_table_anchor = bool(tl) and (kind in {"caption", "table"} or (kind == "title" and tables))
            if create_table_anchor:
                target = tables[0] if tables else g
                aid = f"table:{tl}"
                src = _anchor_source_fields(g, page)
                a = {"anchor_id": aid, "anchor_type": "table", "label": tl, "canonical_text": text, "target_group_id": target.get("group_id"), "page_index": pidx, "page_number": pnum, "bbox": target.get("representative_bbox"), "source_groups": [gid], "confidence": 0.7 if tables else 0.45, "status": "resolved_with_conflict" if _has_conflict(g, page) and tables else ("resolved" if tables else "caption_only"), "warnings": [], **src}
                anchors.append(a); page_anchor_ids.append(aid); anchor_map.setdefault(("table", tl), []).append(a)

            is_footnote_body = isinstance(bbox, list) and len(bbox) == 4 and bbox[1] > 800 and FOOTNOTE_BODY_RE.match(text) and kind in {"unknown", "paragraph", "footer", "caption"}
            if is_footnote_body:
                num = FOOTNOTE_BODY_RE.match(text).group(1)
                src = _anchor_source_fields(g, page)
                aid = f"footnote:{num}"
                a = {"anchor_id": aid, "anchor_type": "footnote", "label": num, "canonical_text": text, "target_group_id": gid, "page_index": pidx, "page_number": pnum, "bbox": bbox, "source_groups": [gid], "confidence": 0.75, "status": "resolved_with_conflict" if _has_conflict(g, page) else "resolved", "warnings": [], **src}
                anchors.append(a); page_anchor_ids.append(aid); anchor_map.setdefault(("footnote", num), []).append(a)

            if kind in {"caption", "picture", "table", "formula", "footer"} and (fl or tl or is_footnote_body):
                continue

            ref_specs = []
            ref_specs += [("equation", m.group(1), m.group(0)) for m in EQ_REF_RE.finditer(text)]
            ref_specs += [("figure", m.group(1), m.group(0)) for m in FIG_LABEL_RE.finditer(text)]
            ref_specs += [("table", m.group(1), m.group(0)) for m in TABLE_LABEL_RE.finditer(text)]
            ref_specs += [("section", m.group(1), m.group(0)) for m in SECTION_REF_RE.finditer(text)]
            ref_specs += [("bibliography", m.group(1), m.group(0)) for m in BIB_REF_RE.finditer(text)]
            for marker in extract_footnote_marker(text):
                ref_specs.append(("footnote", marker, marker))

            for rtype, lbl, rtxt in ref_specs:
                cands = anchor_map.get((rtype, lbl), [])
                resolved = len(cands) == 1
                rid = f"ref_p{pidx:04d}_{len(references)+1:04d}"
                ref = {"reference_id": rid, "reference_type": rtype, "reference_text": rtxt, "label": lbl, "source_group_id": gid, "page_index": pidx, "page_number": pnum, "target_anchor_id": cands[0]["anchor_id"] if resolved else None, "resolved": resolved, "confidence": 0.9 if resolved else 0.2, "method": "exact_label" if resolved else "unresolved", "warnings": ["ambiguous"] if len(cands) > 1 else ([] if resolved else ["not_found"])}
                references.append(ref); page_ref_ids.append(rid)
                if not resolved:
                    unresolved.append(ref)

        page_reports.append({"page_index": pidx, "page_number": pnum, "anchors": page_anchor_ids, "references": page_ref_ids, "attachments": page_att_ids, "unresolved": [u.get("reference_id") for u in unresolved if u.get("page_index") == pidx and u.get("reference_id")], "warnings": []})

    for r in references:
        if (not r["resolved"]) and r["reference_type"] in {"equation", "figure", "table", "footnote", "section"}:
            cands = anchor_map.get((r["reference_type"], r["label"]), [])
            if len(cands) == 1:
                r["resolved"] = True
                r["target_anchor_id"] = cands[0]["anchor_id"]
                r["confidence"] = max(r["confidence"], 0.75)
                r["method"] = "exact_label"
                r["warnings"] = []

    summary = {
        "equation_anchors": sum(1 for a in anchors if a["anchor_type"] == "equation"),
        "figure_anchors": sum(1 for a in anchors if a["anchor_type"] == "figure"),
        "table_anchors": sum(1 for a in anchors if a["anchor_type"] == "table"),
        "footnote_anchors": sum(1 for a in anchors if a["anchor_type"] == "footnote"),
        "references_detected": len(references),
        "references_resolved": sum(1 for r in references if r["resolved"]),
        "references_unresolved": sum(1 for r in references if not r["resolved"]),
        "equation_numbers_attached": sum(1 for a in attachments if a["attachment_type"] == "equation_number_to_equation"),
        "equation_numbers_unattached": sum(1 for u in unresolved if u.get("type") == "equation_number_unattached"),
        "footnote_markers_detected": sum(1 for r in references if r["reference_type"] == "footnote"),
        "footnote_markers_resolved": sum(1 for r in references if r["reference_type"] == "footnote" and r["resolved"]),
    }
    return {"schema_name": "pdf2md.semantic_links", "schema_version": "0.1.0", "source_report": str(source_path), "pdf_path": report.get("pdf_path"), "pdf_stem": report.get("pdf_stem"), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "summary": summary, "anchors": anchors, "references": references, "attachments": attachments, "unresolved": unresolved, "pages": page_reports}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("consensus_report")
    ap.add_argument("--output")
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--fail-on-unresolved", action="store_true")
    args = ap.parse_args()
    inp = Path(args.consensus_report)
    report = load_consensus_report(inp)
    _ = validate_consensus_report(report)
    out = Path(args.output) if args.output else inp.parent / "semantic_links.json"
    links = build_semantic_links(report, inp)
    out.write_text(json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.json_only:
        s = links["summary"]
        print(f"Semantic links: {out}")
        print(f"Source consensus: {inp}")
        print("Anchors:")
        print(f"  equations: {s['equation_anchors']}")
        print(f"  figures: {s['figure_anchors']}")
        print(f"  tables: {s['table_anchors']}")
        print(f"  footnotes: {s['footnote_anchors']}")
        print("References:")
        print(f"  detected: {s['references_detected']}")
        print(f"  resolved: {s['references_resolved']}")
        print(f"  unresolved: {s['references_unresolved']}")
        print("Attachments:")
        print(f"  equation numbers: {s['equation_numbers_attached']} attached, {s['equation_numbers_unattached']} unattached")
        print(f"  captions: {sum(1 for a in links['attachments'] if a['attachment_type'] in {'caption_to_figure', 'caption_to_table'})} attached")
        print(f"Warnings: {len(links['unresolved'])}")
    if args.fail_on_unresolved and links["summary"]["references_unresolved"] > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
