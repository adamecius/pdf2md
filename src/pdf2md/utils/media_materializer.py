from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


DEFAULTS = {
    "enabled": True,
    "render_dpi": 200,
    "format": "png",
    "padding_px": 8,
    "crop_from_pdf": True,
    "allow_single_source_geometry": True,
    "default_geometry_backend": "paddleocr",
    "emit_conflicted_geometry": False,
    "crop_tables_as_visual_fallback": False,
}


def _to_rect(bbox: list[float], w: float, h: float, padding_px: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    px0 = max(0, int((x0 / 1000.0) * w) - padding_px)
    py0 = max(0, int((y0 / 1000.0) * h) - padding_px)
    px1 = min(int(w), int((x1 / 1000.0) * w) + padding_px)
    py1 = min(int(h), int((y1 / 1000.0) * h) + padding_px)
    return (px0, py0, px1, py1)


def build_manifest(consensus: dict[str, Any], semantic: dict[str, Any], output_root: Path) -> dict[str, Any]:
    return {
        "schema_name": "pdf2md.media_manifest",
        "schema_version": "0.1.0",
        "source_pdf": consensus.get("pdf_path"),
        "source_consensus_report": str(output_root / "consensus_report.json"),
        "source_semantic_links": str(output_root / "semantic_links.json"),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "assets": [],
        "warnings": [],
    }


def materialize(consensus: dict[str, Any], semantic: dict[str, Any], output_root: Path, *, strict: bool = False, render_dpi: int = 200, padding_px: int = 8, verbose: bool = False) -> tuple[dict[str, Any], int]:
    manifest = build_manifest(consensus, semantic, output_root)
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
    groups_by_id = {}
    for page in consensus.get("pages", []):
        for g in page.get("candidate_groups", []):
            groups_by_id[g.get("group_id")] = (page, g)

    figure_anchors = [a for a in semantic.get("anchors", []) if a.get("anchor_type") == "figure"]
    doc = fitz.open(str(pdf_path))

    for anchor in figure_anchors:
        gid = anchor.get("target_group_id")
        if gid not in groups_by_id:
            manifest["warnings"].append(f"Missing figure target group for anchor {anchor.get('anchor_id')}")
            continue
        page, group = groups_by_id[gid]
        if group.get("compile_role") in {"evidence_only", "fallback_only", "duplicate_candidate"}:
            continue
        agr = group.get("agreement") or {}
        geometry_status = agr.get("geometry")
        if geometry_status == "conflict":
            manifest["warnings"].append(f"Geometry conflict for {gid}; skipped")
            continue
        if geometry_status == "single_source" and not DEFAULTS["allow_single_source_geometry"]:
            continue
        bbox = group.get("representative_bbox")
        if not bbox:
            manifest["warnings"].append(f"No bbox for {gid}")
            continue
        pidx = int(page.get("page_index", anchor.get("page_index", 0)))
        pg = doc.load_page(pidx)
        mat = fitz.Matrix(render_dpi / 72.0, render_dpi / 72.0)
        pix = pg.get_pixmap(matrix=mat, alpha=False)
        rect = _to_rect(bbox, pix.width, pix.height, padding_px)
        cropped = fitz.Pixmap(pix, fitz.IRect(*rect))
        label = (anchor.get("label") or gid).replace(".", "_")
        fname = f"p{pidx+1:04d}_fig_{label}.png"
        rel = Path("media") / fname
        out_path = output_root / rel
        cropped.save(str(out_path))
        manifest["assets"].append({
            "media_id": f"media:p{pidx+1:04d}_fig_{label}",
            "media_type": "figure",
            "page_index": pidx,
            "page_number": pidx + 1,
            "bbox": bbox,
            "bbox_space": "page_normalised_1000",
            "file_path": str(rel),
            "source_group_id": gid,
            "anchor_id": anchor.get("anchor_id"),
            "caption_group_id": None,
            "status": "single_source_geometry" if geometry_status == "single_source" else "resolved",
            "confidence": 1.0,
            "sources": group.get("sources") or [],
            "warnings": [],
        })
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
    consensus = json.loads(cp.read_text(encoding="utf-8"))
    semantic = json.loads(sp.read_text(encoding="utf-8"))
    manifest, code = materialize(consensus, semantic, out_root, strict=args.strict, render_dpi=args.render_dpi, padding_px=args.padding_px, verbose=args.verbose)
    (out_root / "media_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.verbose:
        print(json.dumps(manifest, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
