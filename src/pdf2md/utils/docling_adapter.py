from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


def _load_docling() -> Any:
    try:
        import docling  # type: ignore
        return docling
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Docling adapter requires docling/docling-core to be installed. "
            "Install with: pip install docling docling-core"
        ) from e


def _as_text_item(block: dict[str, Any], label: str | None = None) -> dict[str, Any]:
    txt = (block.get("text") or "").strip()
    if label:
        txt = f"[{label}] {txt}" if txt else f"[{label}]"
    return {"text": txt, "page": block.get("page_number"), "bbox": block.get("bbox")}


def adapt_semantic_document(semantic: dict[str, Any], *, include_orphan_media: bool = False, mode: str = "inspection") -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    doc = {"schema_name": "pdf2md.docling_document", "schema_version": "0.1.0", "body": [], "texts": [], "pictures": [], "tables": [], "furniture": []}
    relations = {
        "schema_name": "pdf2md.docling_relations",
        "schema_version": "0.1.0",
        "source_semantic_document": semantic.get("source_consensus_report") or "",
        "source_docling_document": "docling_document.json",
        "id_map": {}, "nodes": [], "anchors": semantic.get("anchors", []), "references": semantic.get("references", []),
        "relations": semantic.get("relations", []), "conflicts": semantic.get("conflicts", []), "warnings": list(semantic.get("warnings", [])),
    }
    report = {"mode": mode, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "warnings": [], "stats": {"blocks_total": len(semantic.get("blocks", [])), "mapped": 0, "degraded": 0}}

    anchor_by_gid = {a.get("target_group_id"): a for a in semantic.get("anchors", [])}
    fig_caps: dict[str, list[dict[str, Any]]] = {}
    for r in semantic.get("relations", []):
        if r.get("relation_type") == "caption_of":
            fig_caps.setdefault(r.get("target_id", ""), []).append(r)

    eq_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for b in semantic.get("blocks", []):
        if b.get("type") == "formula" and b.get("anchor_id"):
            eq_by_anchor.setdefault(b["anchor_id"], []).append(b)

    for aid, cands in eq_by_anchor.items():
        if len(cands) > 1:
            msg = f"duplicate_formula_candidates:{aid}"
            relations["warnings"].append(msg); report["warnings"].append(msg)

    for b in semantic.get("blocks", []):
        bid = b.get("id")
        btype = b.get("type")
        node = {k: b.get(k) for k in ["id", "type", "page_number", "bbox", "source_group_id", "sources", "status", "selection_mode", "selected_text_source", "selected_geometry_source", "media_id", "media_path", "anchor_id", "warnings"]}
        relations["nodes"].append(node)

        if not b.get("bbox"):
            w = f"missing_bbox:{bid}"; relations["warnings"].append(w); report["warnings"].append(w)

        if b.get("selection_mode") == "fallback_default_backend":
            report["warnings"].append(f"fallback_default_backend:{bid}")
        if any("single_source_geometry" in str(x) for x in (b.get("warnings") or [])):
            report["warnings"].append(f"single_source_geometry media:{bid}")

        if btype in {"header", "footer", "page_number"}:
            ptr = f"#/furniture/{len(doc['furniture'])}"
            doc["furniture"].append(_as_text_item(b))
            relations["id_map"][bid] = {"docling_ref": ptr, "docling_type": "furniture", "semantic_type": btype}
            report["stats"]["mapped"] += 1
            continue

        if btype == "figure":
            if b.get("media_path") and (b.get("anchor_id") or include_orphan_media):
                ptr = f"#/pictures/{len(doc['pictures'])}"
                doc["pictures"].append({"image_path": b.get("media_path"), "page": b.get("page_number"), "bbox": b.get("bbox"), "caption": b.get("label")})
                relations["id_map"][bid] = {"docling_ref": ptr, "docling_type": "picture", "semantic_type": btype}
                report["stats"]["mapped"] += 1
            elif b.get("media_path") and not include_orphan_media:
                w = f"orphan_media_suppressed:{bid}"; relations["warnings"].append(w); report["warnings"].append(w)
            else:
                w = f"missing_media_file:{bid}"; relations["warnings"].append(w); report["warnings"].append(w)
                ptr = f"#/texts/{len(doc['texts'])}"
                doc["texts"].append(_as_text_item(b, "FIGURE_PLACEHOLDER")); report["stats"]["degraded"] += 1
                relations["id_map"][bid] = {"docling_ref": ptr, "docling_type": "text", "semantic_type": btype}
            continue

        if btype == "table":
            w = f"table_structure_degraded:{bid}"; relations["warnings"].append(w); report["warnings"].append(w)
            ptr = f"#/texts/{len(doc['texts'])}"
            doc["texts"].append(_as_text_item(b, "TABLE")); report["stats"]["degraded"] += 1
            relations["id_map"][bid] = {"docling_ref": ptr, "docling_type": "text", "semantic_type": btype}
            continue

        if btype == "formula":
            if not b.get("anchor_id"):
                report["warnings"].append(f"formula_text_geometry_not_fused:{bid}")
            ptr = f"#/texts/{len(doc['texts'])}"
            doc["texts"].append(_as_text_item(b, "FORMULA")); report["stats"]["degraded"] += 1
            relations["id_map"][bid] = {"docling_ref": ptr, "docling_type": "text", "semantic_type": btype}
            continue

        if btype == "caption":
            ptr = f"#/texts/{len(doc['texts'])}"
            doc["texts"].append(_as_text_item(b, "CAPTION"))
            relations["id_map"][bid] = {"docling_ref": ptr, "docling_type": "text", "semantic_type": btype}
            report["stats"]["mapped"] += 1
            continue

        ptr = f"#/texts/{len(doc['texts'])}"
        doc["texts"].append(_as_text_item(b))
        relations["id_map"][bid] = {"docling_ref": ptr, "docling_type": "text", "semantic_type": btype}
        report["stats"]["mapped"] += 1

    unresolved = semantic.get("validation", {}).get("unresolved_references", [])
    for rid in unresolved:
        report["warnings"].append(f"unresolved_reference:{rid}")

    # fragmented captions by shared anchor_id
    caps_by_anchor: dict[str, list[str]] = {}
    for b in semantic.get("blocks", []):
        if b.get("type") == "caption" and b.get("anchor_id"):
            caps_by_anchor.setdefault(b["anchor_id"], []).append(b.get("id"))
    for a, ids in caps_by_anchor.items():
        if len(ids) > 1:
            w = f"fragmented_caption:{a}:{','.join(ids)}"
            relations["warnings"].append(w); report["warnings"].append(w)

    return doc, relations, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("semantic_document_json")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--mode", choices=["inspection", "strict"], default="inspection")
    ap.add_argument("--include-orphan-media", action="store_true")
    ap.add_argument("--export-markdown", action="store_true")
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    _load_docling()
    inp = Path(args.semantic_document_json)
    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    semantic = json.loads(inp.read_text(encoding="utf-8"))
    doc, rel, rep = adapt_semantic_document(semantic, include_orphan_media=args.include_orphan_media, mode=args.mode)
    (out_root / "docling_document.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    (out_root / "docling_relations.json").write_text(json.dumps(rel, indent=2), encoding="utf-8")
    (out_root / "docling_adapter_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    if args.export_markdown:
        try:
            lines = [x.get("text", "") for x in doc.get("texts", []) if x.get("text")]
            (out_root / "docling_preview.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
        except Exception as e:
            rep["warnings"].append(f"markdown_export_unavailable:{e}")
            (out_root / "docling_adapter_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
            if args.mode == "strict":
                return 2
    if args.verbose:
        print(json.dumps(rep, indent=2))
    return 2 if args.mode == "strict" and rep.get("warnings") else 0


if __name__ == "__main__":
    raise SystemExit(main())
