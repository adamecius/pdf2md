from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

MAP = {
    "title": "title", "heading": "heading", "paragraph": "paragraph", "list_item": "list_item",
    "table": "table", "formula": "formula", "picture": "figure", "caption": "caption",
    "header": "header", "footer": "footer", "page_number": "page_number", "unknown": "unknown",
}


def conflicts_for_group(group: dict[str, Any], page: dict[str, Any]) -> list[dict[str, Any]]:
    members = set(group.get("members") or [])
    gid = group.get("group_id")
    out = []
    for c in page.get("conflicts") or []:
        eids = set(c.get("evidence_ids") or [])
        if gid and gid in (c.get("group_ids") or []):
            out.append(c)
        elif members and eids and members.intersection(eids):
            out.append(c)
    return out


def build(consensus: dict[str, Any], semantic_links: dict[str, Any], media_manifest: dict[str, Any] | None, srcs: dict[str, str], strict: bool = False) -> dict[str, Any]:
    doc = {
        "schema_name": "pdf2md.semantic_document", "schema_version": "0.1.0", "source_pdf": consensus.get("pdf_path", ""),
        "source_consensus_report": srcs["consensus"], "source_semantic_links": srcs["links"], "source_media_manifest": srcs.get("media"),
        "run_id": consensus.get("run_id"),
        "upstream_sha256": {
            "consensus_report": hashlib.sha256(Path(srcs["consensus"]).read_bytes()).hexdigest() if srcs.get("consensus") and Path(srcs["consensus"]).exists() else None,
            "semantic_links": hashlib.sha256(Path(srcs["links"]).read_bytes()).hexdigest() if srcs.get("links") and Path(srcs["links"]).exists() else None,
            "media_manifest": hashlib.sha256(Path(srcs["media"]).read_bytes()).hexdigest() if srcs.get("media") and Path(srcs["media"]).exists() else None,
        },
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "pages": [], "blocks": [], "relations": [], "anchors": [], "references": [], "conflicts": [], "warnings": [],
        "validation": {"duplicate_block_ids": [], "missing_anchor_targets": [], "unresolved_references": [], "blocks_missing_provenance": [], "media_assets_missing_files": [], "warnings": []},
    }
    doc["anchors"] = semantic_links.get("anchors", [])
    doc["references"] = semantic_links.get("references", [])
    media_by_gid = {a.get("source_group_id"): a for a in (media_manifest or {}).get("assets", [])}
    rel_i = 1

    for page in consensus.get("pages", []):
        doc["conflicts"].extend(page.get("conflicts") or [])
        page_blocks = []
        for order, g in enumerate(page.get("candidate_groups", [])):
            role = g.get("compile_role", "candidate")
            if role in {"evidence_only", "fallback_only", "duplicate_candidate"}:
                continue
            gid = g.get("group_id")
            kind = MAP.get(g.get("kind"), "unknown")
            agreement = g.get("agreement") or {}
            attached_conflicts = conflicts_for_group(g, page)
            status = "resolved"
            if agreement.get("text") == "conflict" or attached_conflicts:
                status = "resolved_with_conflict"
            elif agreement.get("text") == "single_source":
                status = "single_source"
            mode = "unresolved"
            if attached_conflicts:
                mode = "consensus_with_conflict"
            elif agreement.get("text") in {"exact", "near"} and len(set(g.get("sources") or [])) > 1:
                mode = "consensus"
            elif agreement.get("text") == "single_source" or len(set(g.get("sources") or [])) == 1:
                mode = "single_source"
            b = {
                "id": f"block:{gid}", "type": kind, "text": g.get("representative_text") or "", "label": None,
                "page_index": page.get("page_index", 0), "page_number": page.get("page_index", 0) + 1,
                "order": order, "bbox": g.get("representative_bbox"), "anchor_id": None, "media_id": None, "media_path": None,
                "source_group_id": gid, "source_group_members": g.get("members") or [], "sources": g.get("sources") or [],
                "agreement": agreement, "conflicts": (g.get("conflicts") or []) + attached_conflicts, "status": status,
                "selection_mode": mode,
                "selected_text_source": (g.get("sources") or [None])[0], "selected_geometry_source": (g.get("sources") or [None])[0], "selection_reason": "representative",
                "warnings": [], "metadata": {"is_page_artifact": kind in {"header", "footer", "page_number"}},
            }
            if agreement.get("geometry") == "conflict":
                b["warnings"].append("geometry_conflict")
                if b["status"] == "resolved":
                    b["status"] = "resolved_with_conflict"
            if gid in media_by_gid:
                ma = media_by_gid[gid]
                b["media_id"] = ma.get("media_id")
                b["media_path"] = ma.get("file_path")
                b["metadata"]["media_status"] = ma.get("status")
                b["metadata"]["media_type"] = ma.get("media_type")
                b["metadata"]["media_policy"] = ma.get("policy")
                if ma.get("status") and ma.get("status") != "resolved":
                    b["warnings"].append(f"media_status:{ma.get('status')}")
                if ma.get("status") == "geometry_conflict":
                    b["status"] = "resolved_with_conflict"
            page_blocks.append(b)
            doc["blocks"].append(b)
        page_blocks.sort(key=lambda x: (x["page_index"], (x["bbox"] or [0, 0, 0, 0])[1], (x["bbox"] or [0, 0, 0, 0])[0], x["order"]))
        block_ids = [b["id"] for b in page_blocks]
        page_artifact_ids = [b["id"] for b in page_blocks if b["metadata"].get("is_page_artifact")]
        evidence_block_ids = [b["id"] for b in page_blocks if b["text"].strip().startswith("(") and b["text"].strip().endswith(")")]
        body_block_ids = [b["id"] for b in page_blocks if b["id"] not in page_artifact_ids and b["id"] not in evidence_block_ids]
        doc["pages"].append({"page_index": page.get("page_index", 0), "page_number": page.get("page_index", 0) + 1, "block_ids": block_ids, "body_block_ids": body_block_ids, "page_artifact_ids": page_artifact_ids, "evidence_block_ids": evidence_block_ids})

    anchor_by_gid = {a.get("target_group_id"): a for a in doc["anchors"]}
    for b in doc["blocks"]:
        a = anchor_by_gid.get(b["source_group_id"])
        if a:
            b["anchor_id"] = a.get("anchor_id")
            b["label"] = a.get("label")
            if a.get("anchor_type") == "footnote":
                b["type"] = "footnote"
            if a.get("status") == "resolved_with_conflict":
                b["status"] = "resolved_with_conflict"
            if b["selection_mode"] == "unresolved":
                b["selection_mode"] = "fallback_default_backend"
                b["warnings"].append("fallback_default_backend")

    for att in semantic_links.get("attachments", []):
        mapped = {"caption_to_figure": "caption_of", "caption_to_table": "caption_of", "equation_number_to_equation": "equation_number_to_equation"}.get(att.get("attachment_type"))
        if mapped:
            doc["relations"].append({"relation_id": f"rel_{rel_i:04d}", "relation_type": mapped, "source_id": f"block:{att.get('source_group_id')}", "target_id": f"block:{att.get('target_group_id')}", "anchor_id": att.get("anchor_id"), "reference_id": None, "confidence": att.get("confidence", 0.5), "method": att.get("reason", "attachment"), "warnings": []})
            rel_i += 1

    for ref in doc["references"]:
        if ref.get("resolved") and ref.get("target_anchor_id"):
            tgt_anchor = next((a for a in doc["anchors"] if a.get("anchor_id") == ref.get("target_anchor_id")), None)
            doc["relations"].append({"relation_id": f"rel_{rel_i:04d}", "relation_type": "refers_to", "source_id": f"block:{ref.get('source_group_id')}", "target_id": f"block:{tgt_anchor.get('target_group_id')}" if tgt_anchor else "", "anchor_id": ref.get("target_anchor_id"), "reference_id": ref.get("reference_id"), "confidence": ref.get("confidence", 0.5), "method": ref.get("method", "exact_label"), "warnings": ref.get("warnings", [])})
            rel_i += 1
        else:
            rid = ref.get("reference_id")
            doc["validation"]["unresolved_references"].append(rid)
            doc["warnings"].append(f"Unresolved reference: {rid}")

    checks = [
        ("semantic_links.upstream_sha256.consensus_report", (semantic_links.get("upstream_sha256") or {}).get("consensus_report"), doc["upstream_sha256"]["consensus_report"]),
        ("media_manifest.upstream_sha256.consensus_report", ((media_manifest or {}).get("upstream_sha256") or {}).get("consensus_report"), doc["upstream_sha256"]["consensus_report"]),
        ("media_manifest.upstream_sha256.semantic_links", ((media_manifest or {}).get("upstream_sha256") or {}).get("semantic_links"), doc["upstream_sha256"]["semantic_links"]),
    ]
    for name, expected, actual in checks:
        if expected and actual and expected != actual:
            msg = f"stale_upstream_hash_mismatch:{name}"
            doc["validation"]["warnings"].append(msg)
            doc["warnings"].append(msg)
    if strict and doc["validation"]["warnings"]:
        doc["validation"]["strict_error"] = True
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
    doc = build(json.loads(cp.read_text()), json.loads(sp.read_text()), json.loads(mp.read_text()) if mp and mp.exists() else None, {"consensus": str(cp), "links": str(sp), "media": str(mp) if mp else None}, strict=args.strict)
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return 2 if args.strict and doc.get("validation", {}).get("strict_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
