from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pdf2md.models.semantic_document import new_semantic_document

MAP = {
    "title": "title", "heading": "heading", "paragraph": "paragraph", "list_item": "list_item",
    "table": "table", "formula": "formula", "picture": "figure", "caption": "caption",
    "header": "header", "footer": "footer", "page_number": "page_number", "unknown": "unknown",
}


def build(consensus: dict[str, Any], semantic_links: dict[str, Any], media_manifest: dict[str, Any] | None, srcs: dict[str, str]) -> dict[str, Any]:
    doc = new_semantic_document(source_pdf=consensus.get("pdf_path", ""), source_consensus_report=srcs["consensus"], source_semantic_links=srcs["links"], source_media_manifest=srcs.get("media"))
    doc["anchors"] = semantic_links.get("anchors", [])
    doc["references"] = semantic_links.get("references", [])
    doc["conflicts"] = consensus.get("conflicts", [])
    media_by_gid = {a.get("source_group_id"): a for a in (media_manifest or {}).get("assets", [])}
    rel_i = 1

    for page in consensus.get("pages", []):
        page_blocks = []
        for order, g in enumerate(page.get("candidate_groups", [])):
            role = g.get("compile_role", "candidate")
            if role in {"evidence_only", "fallback_only", "duplicate_candidate"}:
                continue
            gid = g.get("group_id")
            kind = MAP.get(g.get("kind"), "unknown")
            agreement = g.get("agreement") or {}
            status = "resolved"
            if agreement.get("text") == "conflict":
                status = "resolved_with_conflict"
            elif agreement.get("text") == "single_source":
                status = "single_source"
            b = {
                "id": f"block:{gid}", "type": kind, "text": g.get("representative_text") or "", "label": None,
                "page_index": page.get("page_index", 0), "page_number": page.get("page_index", 0) + 1,
                "order": order, "bbox": g.get("representative_bbox"), "anchor_id": None, "media_id": None, "media_path": None,
                "source_group_id": gid, "source_group_members": g.get("members") or [], "sources": g.get("sources") or [],
                "agreement": agreement, "conflicts": g.get("conflicts") or [], "status": status,
                "selected_text_source": None, "selected_geometry_source": None, "selection_reason": "representative",
                "warnings": [], "metadata": {},
            }
            if agreement.get("geometry") == "conflict":
                b["warnings"].append("geometry_conflict")
            if gid in media_by_gid:
                ma = media_by_gid[gid]
                b["media_id"] = ma.get("media_id")
                b["media_path"] = ma.get("file_path")
            page_blocks.append(b)
            doc["blocks"].append(b)
        page_blocks.sort(key=lambda x: (x["page_index"], (x["bbox"] or [0, 0, 0, 0])[1], (x["bbox"] or [0, 0, 0, 0])[0], x["order"]))
        doc["pages"].append({"page_index": page.get("page_index", 0), "page_number": page.get("page_index", 0) + 1, "block_ids": [b["id"] for b in page_blocks]})

    anchor_by_gid = {a.get("target_group_id"): a for a in doc["anchors"]}
    for b in doc["blocks"]:
        gid = b["source_group_id"]
        a = anchor_by_gid.get(gid)
        if a:
            b["anchor_id"] = a.get("anchor_id")
            b["label"] = a.get("label")
            if a.get("status") == "resolved_with_conflict":
                b["status"] = "resolved_with_conflict"

    for att in semantic_links.get("attachments", []):
        rel_type = att.get("attachment_type")
        mapped = {"caption_to_figure": "caption_of", "caption_to_table": "caption_of", "equation_number_to_equation": "equation_number_to_equation"}.get(rel_type)
        if not mapped:
            continue
        doc["relations"].append({"relation_id": f"rel_{rel_i:04d}", "relation_type": mapped, "source_id": f"block:{att.get('source_group_id')}", "target_id": f"block:{att.get('target_group_id')}", "anchor_id": att.get("anchor_id"), "reference_id": None, "confidence": att.get("confidence", 0.5), "method": att.get("reason", "attachment"), "warnings": []})
        rel_i += 1
    for ref in doc["references"]:
        if ref.get("resolved") and ref.get("target_anchor_id"):
            src = f"block:{ref.get('source_group_id')}"
            tgt_anchor = next((a for a in doc["anchors"] if a.get("anchor_id") == ref.get("target_anchor_id")), None)
            tgt = f"block:{tgt_anchor.get('target_group_id')}" if tgt_anchor else ""
            doc["relations"].append({"relation_id": f"rel_{rel_i:04d}", "relation_type": "refers_to", "source_id": src, "target_id": tgt, "anchor_id": ref.get("target_anchor_id"), "reference_id": ref.get("reference_id"), "confidence": ref.get("confidence", 0.5), "method": ref.get("method", "exact_label"), "warnings": ref.get("warnings", [])})
            rel_i += 1
        else:
            doc["validation"]["unresolved_references"].append(ref.get("reference_id"))

    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("consensus_report")
    ap.add_argument("--semantic-links", required=True)
    ap.add_argument("--media-manifest")
    ap.add_argument("--output")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    cp = Path(args.consensus_report)
    sp = Path(args.semantic_links)
    mp = Path(args.media_manifest) if args.media_manifest else None
    out = Path(args.output) if args.output else cp.parent / "semantic_document.json"

    c = json.loads(cp.read_text(encoding="utf-8"))
    s = json.loads(sp.read_text(encoding="utf-8"))
    m = json.loads(mp.read_text(encoding="utf-8")) if mp and mp.exists() else None
    doc = build(c, s, m, {"consensus": str(cp), "links": str(sp), "media": str(mp) if mp else None})
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
