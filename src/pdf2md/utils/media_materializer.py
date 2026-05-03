from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

DEFAULTS = {"allow_single_source_geometry": True}


def _to_rect(bbox: list[float], w: float, h: float, padding_px: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    return (
        max(0, int((x0 / 1000.0) * w) - padding_px),
        max(0, int((y0 / 1000.0) * h) - padding_px),
        min(int(w), int((x1 / 1000.0) * w) + padding_px),
        min(int(h), int((y1 / 1000.0) * h) + padding_px),
    )


def build_manifest(consensus: dict[str, Any], output_root: Path, source_consensus_report: Path, source_semantic_links: Path) -> dict[str, Any]:
    return {"schema_name": "pdf2md.media_manifest", "schema_version": "0.1.0", "source_pdf": consensus.get("pdf_path"), "source_consensus_report": str(source_consensus_report), "source_semantic_links": str(source_semantic_links), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "assets": [], "warnings": []}


def materialize(consensus: dict[str, Any], semantic: dict[str, Any], output_root: Path, *, source_consensus_report: Path, source_semantic_links: Path, strict: bool = False, render_dpi: int = 200, padding_px: int = 8) -> tuple[dict[str, Any], int]:
    manifest = build_manifest(consensus, output_root, source_consensus_report, source_semantic_links)
    pdf_path = Path(consensus.get("pdf_path", ""))
    if not pdf_path.exists():
        manifest["warnings"].append(f"Missing source PDF: {pdf_path}")
        return manifest, (2 if strict else 0)
    try:
        import fitz  # type: ignore
    except Exception:
        manifest["warnings"].append("PyMuPDF unavailable; no media assets created")
        return manifest, (2 if strict else 0)

    media_dir = output_root / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    groups = {}
    for page in consensus.get("pages", []):
        for g in page.get("candidate_groups", []):
            groups[g.get("group_id")] = (page, g)

    anchors = {a.get("target_group_id"): a for a in semantic.get("anchors", []) if a.get("anchor_type") == "figure" and a.get("target_group_id")}
    crop_ids = set(anchors.keys())
    for gid, (_, g) in groups.items():
        if g.get("kind") == "picture":
            crop_ids.add(gid)

    doc = fitz.open(str(pdf_path))
    for gid in sorted(crop_ids):
        page, g = groups.get(gid, ({}, {}))
        if not g:
            continue
        if g.get("compile_role") in {"evidence_only", "fallback_only", "duplicate_candidate"}:
            continue
        agr = g.get("agreement") or {}
        gs = agr.get("geometry")
        if gs == "conflict":
            manifest["warnings"].append(f"Geometry conflict for {gid}; skipped")
            continue
        if gs == "single_source" and not DEFAULTS["allow_single_source_geometry"]:
            continue
        bbox = g.get("representative_bbox")
        if not bbox:
            manifest["warnings"].append(f"No bbox for {gid}")
            continue
        pidx = int(page.get("page_index", 0))
        pix = doc.load_page(pidx).get_pixmap(matrix=fitz.Matrix(render_dpi / 72.0, render_dpi / 72.0), alpha=False)
        rect = _to_rect(bbox, pix.width, pix.height, padding_px)
        fitz.Pixmap(pix, fitz.IRect(*rect)).save(str(media_dir / f"{gid}.png"))
        anchor = anchors.get(gid)
        manifest["assets"].append({"media_id": f"media:{gid}", "media_type": "figure", "page_index": pidx, "page_number": pidx + 1, "bbox": bbox, "bbox_space": "page_normalised_1000", "file_path": f"media/{gid}.png", "source_group_id": gid, "anchor_id": (anchor or {}).get("anchor_id"), "caption_group_id": None, "status": "single_source_geometry" if gs == "single_source" else "resolved", "confidence": 1.0, "sources": g.get("sources") or [], "warnings": []})
    return manifest, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("consensus_report")
    ap.add_argument("--semantic-links", required=True)
    ap.add_argument("--output-root")
    ap.add_argument("--render-dpi", type=int, default=200)
    ap.add_argument("--padding-px", type=int, default=8)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    cp = Path(args.consensus_report)
    sp = Path(args.semantic_links)
    out_root = Path(args.output_root) if args.output_root else cp.parent
    manifest, code = materialize(json.loads(cp.read_text()), json.loads(sp.read_text()), out_root, source_consensus_report=cp, source_semantic_links=sp, strict=args.strict, render_dpi=args.render_dpi, padding_px=args.padding_px)
    (out_root / "media_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.verbose:
        print(json.dumps(manifest, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
