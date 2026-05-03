from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

MEDIA_POLICY_DEFAULTS = {
    "enabled": True,
    "render_dpi": 200,
    "format": "png",
    "padding_px": 8,
    "crop_from_pdf": True,
    "materialize_primary_figures": True,
    "materialize_orphan_images": False,
    "materialize_tables_as_visual_fallback": False,
    "allow_near_geometry": True,
    "allow_single_source_geometry": True,
    "allow_missing_geometry": False,
    "allow_conflicted_geometry": False,
    "default_geometry_backend": "paddleocr",
    "prefer_anchor_targets": True,
    "min_bbox_width": 5.0,
    "min_bbox_height": 5.0,
    "max_bbox_area_ratio": 0.90,
    "skip_evidence_only": True,
    "skip_fallback_only": True,
    "skip_duplicate_candidate": True,
    "deduplicate_by_source_group": True,
}


def _sanitize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def _normalised_bbox_to_page_rect(bbox: list[float], page_rect: Any, *, padding_points: float = 0.0) -> Any:
    import fitz  # type: ignore

    x0, y0, x1, y1 = bbox
    width = float(page_rect.width)
    height = float(page_rect.height)
    rx0 = page_rect.x0 + (x0 / 1000.0) * width
    ry0 = page_rect.y0 + (y0 / 1000.0) * height
    rx1 = page_rect.x0 + (x1 / 1000.0) * width
    ry1 = page_rect.y0 + (y1 / 1000.0) * height
    rx0 = max(page_rect.x0, rx0 - padding_points)
    ry0 = max(page_rect.y0, ry0 - padding_points)
    rx1 = min(page_rect.x1, rx1 + padding_points)
    ry1 = min(page_rect.y1, ry1 + padding_points)
    return fitz.Rect(rx0, ry0, rx1, ry1)


def _warn(manifest: dict[str, Any], gid: str, reason: str, page_index: int | None = None) -> None:
    manifest["warnings"].append(f"group_id={gid} page_index={page_index} reason={reason}")


def build_manifest(consensus: dict[str, Any], source_consensus_report: Path, source_semantic_links: Path, policy: dict[str, Any]) -> dict[str, Any]:
    return {"schema_name": "pdf2md.media_manifest", "schema_version": "0.1.0", "run_id": consensus.get("run_id"), "upstream_sha256": {"consensus_report": hashlib.sha256(source_consensus_report.read_bytes()).hexdigest() if source_consensus_report.exists() else None, "semantic_links": hashlib.sha256(source_semantic_links.read_bytes()).hexdigest() if source_semantic_links.exists() else None}, "source_pdf": consensus.get("pdf_path"), "source_consensus_report": str(source_consensus_report), "source_semantic_links": str(source_semantic_links), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "policy": policy, "assets": [], "warnings": []}


def materialize(consensus: dict[str, Any], semantic: dict[str, Any], output_root: Path, *, source_consensus_report: Path, source_semantic_links: Path, strict: bool = False, render_dpi: int = 200, padding_px: int = 8, allow_conflicted_geometry: bool = False, allow_single_source_geometry: bool = True, crop_tables_as_visual_fallback: bool = False, materialize_orphan_images: bool = False) -> tuple[dict[str, Any], int]:
    policy = dict(MEDIA_POLICY_DEFAULTS)
    policy.update({"render_dpi": render_dpi, "padding_px": padding_px, "allow_conflicted_geometry": allow_conflicted_geometry, "allow_single_source_geometry": allow_single_source_geometry, "materialize_tables_as_visual_fallback": crop_tables_as_visual_fallback})
    manifest = build_manifest(consensus, source_consensus_report, source_semantic_links, policy)
    pdf_path = Path(consensus.get("pdf_path", ""))
    if not pdf_path.exists():
        manifest["warnings"].append(f"Missing source PDF: {pdf_path}")
        return manifest, (2 if strict else 0)
    try:
        import fitz  # type: ignore
    except Exception:
        manifest["warnings"].append("PyMuPDF unavailable; no media assets created")
        return manifest, (2 if strict else 0)

    groups: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for page in consensus.get("pages", []):
        for g in page.get("candidate_groups", []):
            groups[g.get("group_id")] = (page, g)

    candidates: dict[str, dict[str, Any]] = {}
    for a in semantic.get("anchors", []):
        if a.get("anchor_type") == "figure" and a.get("target_group_id") in groups:
            candidates[a["target_group_id"]] = {"gid": a["target_group_id"], "anchor": a, "candidate_type": "figure"}
    for gid, (_, g) in groups.items():
        if g.get("kind") == "picture" and materialize_orphan_images:
            candidates.setdefault(gid, {"gid": gid, "anchor": None, "candidate_type": "image"})
        if crop_tables_as_visual_fallback and g.get("kind") == "table":
            candidates.setdefault(gid, {"gid": gid, "anchor": None, "candidate_type": "table_visual_fallback"})

    output_root.joinpath("media").mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    failures = 0
    success = 0
    for gid, c in sorted(candidates.items()):
        page, g = groups[gid]
        pidx = int(page.get("page_index", 0))
        role = g.get("compile_role")
        if role in {"excluded"} or (policy["skip_evidence_only"] and role == "evidence_only") or (policy["skip_fallback_only"] and role == "fallback_only") or (policy["skip_duplicate_candidate"] and role == "duplicate_candidate"):
            _warn(manifest, gid, f"compile_role:{role}", pidx); continue
        bbox = g.get("representative_bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox)):
            _warn(manifest, gid, "invalid_bbox", pidx); continue
        bw, bh = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if bw <= 0 or bh <= 0 or bw < policy["min_bbox_width"] or bh < policy["min_bbox_height"]:
            _warn(manifest, gid, "bbox_too_small", pidx); continue
        if (bw*bh)/1_000_000 > policy["max_bbox_area_ratio"]:
            _warn(manifest, gid, "bbox_too_large", pidx); continue

        gs = (g.get("agreement") or {}).get("geometry", "missing")
        status = "unknown_geometry"
        if gs == "near": status = "resolved"
        elif gs == "single_source": status = "single_source_geometry"
        elif gs == "conflict": status = "geometry_conflict"
        elif gs in {"missing", "unavailable", None}: status = "missing_geometry"
        if status == "single_source_geometry" and not allow_single_source_geometry:
            _warn(manifest, gid, "single_source_disallowed", pidx); continue
        if status == "geometry_conflict" and not allow_conflicted_geometry:
            _warn(manifest, gid, "geometry_conflict", pidx); continue
        if status in {"missing_geometry", "unknown_geometry"} and not policy["allow_missing_geometry"]:
            _warn(manifest, gid, status, pidx); continue

        anchor = c.get("anchor")
        media_type = "figure" if anchor else c["candidate_type"]
        base = _sanitize((anchor.get("anchor_id") if anchor else gid).replace(":", "_").replace(".", "_"))
        file_rel = f"media/{base}.png"
        media_id = f"media:{base}" if anchor else f"media:{gid}"
        conf = 0.90 if status == "resolved" else (0.65 if status == "single_source_geometry" else 0.40)
        if anchor: conf += 0.05
        conf = max(0.0, min(1.0, conf))
        aw = []
        if status != "resolved": aw.append(f"non_near_geometry:{status}")
        if status == "single_source_geometry":
            aw.append("single_source_geometry_warning")
        try:
            pg = doc.load_page(pidx)
            mat = fitz.Matrix(render_dpi / 72.0, render_dpi / 72.0)
            clip = _normalised_bbox_to_page_rect(bbox, pg.rect, padding_points=padding_px * 72.0 / render_dpi)
            pix = pg.get_pixmap(matrix=mat, clip=clip, alpha=False)
            pix.save(str(output_root / file_rel))
            manifest["assets"].append({"media_id": media_id, "media_type": media_type, "page_index": pidx, "page_number": pidx + 1, "bbox": bbox, "bbox_space": "page_normalised_1000", "file_path": file_rel, "source_group_id": gid, "anchor_id": (anchor or {}).get("anchor_id"), "caption_group_id": None, "status": status, "confidence": conf, "sources": g.get("sources") or [], "warnings": aw, "policy": {"render_dpi": render_dpi, "padding_px": padding_px, "geometry_agreement": gs}})
            success += 1
        except Exception as e:
            failures += 1
            _warn(manifest, gid, f"crop_exception:{e}", pidx)

    if strict and (failures > 0 or (candidates and success == 0)):
        return manifest, 2
    return manifest, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("consensus_report")
    ap.add_argument("--semantic-links", required=True)
    ap.add_argument("--output-root")
    ap.add_argument("--render-dpi", type=int, default=200)
    ap.add_argument("--padding-px", type=int, default=8)
    ap.add_argument("--allow-conflicted-geometry", action="store_true")
    ap.add_argument("--no-single-source-geometry", action="store_true")
    ap.add_argument("--crop-tables-as-visual-fallback", action="store_true")
    ap.add_argument("--materialize-orphan-images", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    cp = Path(args.consensus_report)
    sp = Path(args.semantic_links)
    out_root = Path(args.output_root) if args.output_root else cp.parent
    try:
        c = json.loads(cp.read_text())
        s = json.loads(sp.read_text())
    except Exception:
        if args.strict:
            return 2
        raise
    manifest, code = materialize(c, s, out_root, source_consensus_report=cp, source_semantic_links=sp, strict=args.strict, render_dpi=args.render_dpi, padding_px=args.padding_px, allow_conflicted_geometry=args.allow_conflicted_geometry, allow_single_source_geometry=not args.no_single_source_geometry, crop_tables_as_visual_fallback=args.crop_tables_as_visual_fallback, materialize_orphan_images=args.materialize_orphan_images)
    (out_root / "media_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.verbose:
        print(json.dumps(manifest, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
