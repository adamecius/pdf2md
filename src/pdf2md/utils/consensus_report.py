from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any

CANONICAL_BACKENDS = ("mineru", "paddleocr", "deepseek")
BACKEND_ALIASES = {"mineuro": "mineru", "paddleorc": "paddleocr", "deepsek": "deepseek"}


def canonical_backend_name(name: str) -> str:
    return BACKEND_ALIASES.get(name, name)


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        cfg = tomllib.load(f)
    cfg.setdefault("consensus", {})
    c = cfg["consensus"]
    c.setdefault("output_root", ".current/consensus")
    c.setdefault("coordinate_space", "page_normalised_1000")
    c.setdefault("text_similarity_threshold", 0.90)
    c.setdefault("weak_text_similarity_threshold", 0.75)
    c.setdefault("bbox_iou_threshold", 0.50)
    c.setdefault("weak_bbox_iou_threshold", 0.25)
    c.setdefault("include_evidence_only_blocks", False)

    raw_backends = cfg.get("backends", {})
    backends: dict[str, Any] = {}
    for key, value in raw_backends.items():
        canon = canonical_backend_name(key)
        if canon in CANONICAL_BACKENDS:
            backends[canon] = value
    for b in CANONICAL_BACKENDS:
        backends.setdefault(b, {"enabled": False, "root": f"backend/{b}", "label": b})
    cfg["backends"] = backends
    cfg.setdefault("pymupdf", {"enabled": True, "extract_text": True, "extract_images": False})
    return cfg


def resolve_backend_extraction_dirs(pdf_path: Path, config: dict[str, Any]) -> dict[str, Path]:
    stem = pdf_path.stem
    out = {}
    for name, bcfg in config["backends"].items():
        out[name] = Path(bcfg["root"]) / ".current" / "extraction_ir" / stem
    return out


def load_backend_manifest(extraction_dir: Path) -> dict[str, Any]:
    mp = extraction_dir / "manifest.json"
    return json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}


def load_backend_pages(extraction_dir: Path) -> dict[int, dict[str, Any]]:
    pages: dict[int, dict[str, Any]] = {}
    for p in sorted((extraction_dir / "pages").glob("page_*.json")):
        m = re.search(r"page_(\d+)\.json", p.name)
        if not m:
            continue
        pages[int(m.group(1))] = json.loads(p.read_text(encoding="utf-8"))
    return pages


def normalize_text(v: str | None) -> str:
    if not v:
        return ""
    return re.sub(r"\s+", " ", v).strip().lower()


def compute_text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def compute_bbox_iou(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0, ix1, iy1 = max(ax0, bx0), max(ay0, by0), min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    au = (ax1 - ax0) * (ay1 - ay0)
    bu = (bx1 - bx0) * (by1 - by0)
    return inter / max(au + bu - inter, 1e-9)


def _kind(block: dict[str, Any]) -> str:
    tokens = " ".join(str(block.get(k, "")) for k in ("type", "subtype", "semantic_role"))
    tokens += " " + str((block.get("docling") or {}).get("label_hint", ""))
    t = tokens.lower()
    mapping = [("doc_title", "title"), ("title", "title"), ("section_header", "heading"), ("heading", "heading"),
               ("body_text", "paragraph"), ("paragraph", "paragraph"), ("text", "paragraph"), ("list_item", "list_item"),
               ("list", "list_item"), ("table", "table"), ("formula", "formula"), ("equation", "formula"), ("math", "formula"),
               ("chart", "picture"), ("picture", "picture"), ("image", "picture"), ("figure", "picture"), ("caption", "caption"),
               ("page_header", "header"), ("header", "header"), ("page_footer", "footer"), ("footer", "footer"), ("page_number", "page_number")]
    for k, v in mapping:
        if k in t:
            return v
    return "unknown"


def compatible_kinds(a: str, b: str, text_sim: float) -> bool:
    if a == b:
        return True
    if {a, b} == {"title", "heading"}:
        return True
    if {a, b} == {"paragraph", "list_item"}:
        return text_sim >= 0.90
    if "unknown" in {a, b}:
        return a == b
    return False


def normalise_backend_block(source: str, page_index: int, order: int, block: dict[str, Any], source_path: str, ptr: str) -> dict[str, Any]:
    txt = block.get("text") or block.get("markdown") or ""
    kind = _kind(block)
    role = block.get("compile_role", "candidate")
    if source == "deepseek" and ((block.get("docling") or {}).get("excluded_from_docling") is True):
        role = "evidence_only"
    if source == "paddleocr" and block.get("compile_role"):
        role = block["compile_role"]
    bbox = block.get("bbox")
    nt = normalize_text(txt)
    return {
        "evidence_id": f"{source}:p{page_index:04d}:b{order:04d}", "source_backend": source, "source_type": "backend_extraction_ir",
        "source_block_id": block.get("id"), "page_index": page_index, "page_number": page_index + 1, "order": order,
        "kind": kind, "native_type": block.get("type"), "semantic_role": block.get("semantic_role"), "docling_label_hint": (block.get("docling") or {}).get("label_hint"),
        "text": txt, "normalised_text": nt, "bbox": bbox, "has_geometry": bool(bbox),
        "confidence": {"overall": None, "text": None, "layout": None, "reading_order": None, "structure": None},
        "comparison": {"text_hash": hashlib.sha1(nt.encode()).hexdigest() if nt else None, "geometry_hash": hashlib.sha1(str(bbox).encode()).hexdigest() if bbox else None, "compare_as": kind},
        "compile_role": role, "source_path": source_path, "json_pointer": ptr, "flags": block.get("flags", []), "metadata": block.get("metadata", {}),
    }


def build_candidate_groups(page_evidence: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = [e for e in page_evidence if e["compile_role"] != "excluded"]
    if not config["consensus"].get("include_evidence_only_blocks", False):
        candidates = [e for e in candidates if e["compile_role"] != "evidence_only"]
    groups: list[list[dict[str, Any]]] = []
    ungrouped: list[dict[str, Any]] = []
    for e in candidates:
        placed = False
        for g in groups:
            ok = False
            for m in g:
                ts = compute_text_similarity(e["normalised_text"], m["normalised_text"])
                iou = compute_bbox_iou(e["bbox"], m["bbox"])
                comp = compatible_kinds(e["kind"], m["kind"], ts)
                if not comp:
                    continue
                if (e["normalised_text"] and e["normalised_text"] == m["normalised_text"]) or ts >= config["consensus"]["text_similarity_threshold"] or iou >= config["consensus"]["bbox_iou_threshold"] or (ts >= config["consensus"]["weak_text_similarity_threshold"] and iou >= config["consensus"]["weak_bbox_iou_threshold"]):
                    ok = True
                    break
            if ok:
                g.append(e)
                placed = True
                break
        if not placed:
            groups.append([e])
    out = []
    for i, g in enumerate(groups, start=1):
        if len(g) == 1:
            ungrouped.append(g[0])
        ms = [x["evidence_id"] for x in g]
        srcs = sorted({x["source_backend"] for x in g})
        out.append({"group_id": f"p{g[0]['page_index']:04d}_g{i:04d}", "page_index": g[0]["page_index"], "kind": g[0]["kind"], "members": ms, "sources": srcs, "support_count": len(srcs), "has_pymupdf_support": "pymupdf" in srcs, "representative_text": g[0]["text"], "representative_bbox": g[0]["bbox"], "agreement": {"text": "exact" if len({x['normalised_text'] for x in g if x['normalised_text']}) <= 1 else "near", "geometry": "missing", "kind": "agree" if len({x['kind'] for x in g}) == 1 else "conflict"}, "scores": {"max_text_similarity": max([compute_text_similarity(a['normalised_text'], b['normalised_text']) for a in g for b in g] or [0.0]), "max_bbox_iou": max([compute_bbox_iou(a['bbox'], b['bbox']) for a in g for b in g] or [0.0])}, "provisional_selection": {"source_backend": None, "reason": "not_selected_in_report_only_mode"}, "conflicts": []})
    return out, ungrouped


def detect_conflicts(page_report: dict[str, Any], all_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts = []
    cid = 1
    for g in page_report["candidate_groups"]:
        members = [e for e in all_evidence if e["evidence_id"] in g["members"]]
        if len({m["source_backend"] for m in members}) < len(members):
            conflicts.append({"conflict_id": f"p{page_report['page_index']:04d}_c{cid:04d}", "page_index": page_report["page_index"], "severity": "medium", "type": "possible_duplicate", "message": "Multiple blocks from same source in group", "sources": g["sources"], "evidence_ids": g["members"]}); cid += 1
        has_geo = [m for m in members if m["has_geometry"]]
        if has_geo and len(has_geo) < len(members):
            conflicts.append({"conflict_id": f"p{page_report['page_index']:04d}_c{cid:04d}", "page_index": page_report["page_index"], "severity": "low", "type": "missing_geometry", "message": "Mixed geometry availability", "sources": g["sources"], "evidence_ids": g["members"]}); cid += 1
        if g["kind"] == "formula" and len({m["normalised_text"] for m in members}) > 1:
            conflicts.append({"conflict_id": f"p{page_report['page_index']:04d}_c{cid:04d}", "page_index": page_report["page_index"], "severity": "medium", "type": "formula_disagreement", "message": "Formula text differs", "sources": g["sources"], "evidence_ids": g["members"]}); cid += 1
        if g["kind"] == "table" and len({m["normalised_text"] for m in members}) > 1:
            conflicts.append({"conflict_id": f"p{page_report['page_index']:04d}_c{cid:04d}", "page_index": page_report["page_index"], "severity": "medium", "type": "table_disagreement", "message": "Table signatures differ", "sources": g["sources"], "evidence_ids": g["members"]}); cid += 1
    return conflicts


def load_pymupdf_evidence(pdf_path: Path, config: dict[str, Any]) -> tuple[dict[int, list[dict[str, Any]]], dict[str, Any]]:
    if not config.get("pymupdf", {}).get("enabled", True):
        return {}, {"source_name": "pymupdf", "source_type": "native_pdf", "enabled": False, "status": "disabled", "page_count": 0, "warnings": []}
    try:
        import fitz  # type: ignore
    except Exception:
        return {}, {"source_name": "pymupdf", "source_type": "native_pdf", "enabled": True, "status": "unavailable", "page_count": 0, "warnings": ["PyMuPDF not installed"]}
    doc = fitz.open(pdf_path)
    pages: dict[int, list[dict[str, Any]]] = {}
    for i, page in enumerate(doc):
        pitems = []
        if config.get("pymupdf", {}).get("extract_text", True):
            data = page.get_text("dict")
            for j, b in enumerate(data.get("blocks", [])):
                bb = b.get("bbox")
                txt = " ".join(span.get("text", "") for line in b.get("lines", []) for span in line.get("spans", []))
                pitems.append(normalise_backend_block("pymupdf", i, j, {"type": "text", "text": txt, "bbox": [max(0,min(1000,bb[0]/page.rect.width*1000)), max(0,min(1000,bb[1]/page.rect.height*1000)), max(0,min(1000,bb[2]/page.rect.width*1000)), max(0,min(1000,bb[3]/page.rect.height*1000))] if bb else None}, str(pdf_path), f"/pages/{i}/blocks/{j}"))
                pitems[-1]["source_type"] = "native_pdf"
        pages[i] = pitems
    return pages, {"source_name": "pymupdf", "source_type": "native_pdf", "enabled": True, "status": "loaded", "page_count": len(pages), "warnings": []}


def build_consensus_report(pdf_path: Path, config: dict[str, Any], config_path: Path, fail_on_missing_backend: bool = False) -> tuple[dict[str, Any], int]:
    if not pdf_path.exists():
        return {}, 1
    dirs = resolve_backend_extraction_dirs(pdf_path, config)
    sources: dict[str, Any] = {}
    backend_pages: dict[str, dict[int, dict[str, Any]]] = {}
    loadable = 0
    for name, edir in dirs.items():
        bcfg = config["backends"][name]
        if not bcfg.get("enabled", False):
            sources[name] = {"source_name": name, "source_type": "backend_extraction_ir", "enabled": False, "root": str(bcfg.get("root")), "extraction_dir": str(edir), "manifest_path": str(edir / "manifest.json"), "status": "disabled", "page_count": 0, "warnings": []}
            continue
        if not edir.exists():
            if fail_on_missing_backend:
                return {}, 1
            sources[name] = {"source_name": name, "source_type": "backend_extraction_ir", "enabled": True, "root": str(bcfg.get("root")), "extraction_dir": str(edir), "manifest_path": str(edir / "manifest.json"), "status": "missing", "page_count": 0, "warnings": ["Extraction directory missing"]}
            continue
        pages = load_backend_pages(edir)
        backend_pages[name] = pages
        loadable += 1
        sources[name] = {"source_name": name, "source_type": "backend_extraction_ir", "enabled": True, "root": str(bcfg.get("root")), "extraction_dir": str(edir), "manifest_path": str(edir / "manifest.json"), "status": "loaded", "page_count": len(pages), "warnings": []}
        _ = load_backend_manifest(edir)
    pym_pages, pym_src = load_pymupdf_evidence(pdf_path, config)
    sources["pymupdf"] = pym_src
    if pym_src["status"] == "loaded":
        loadable += 1
    if loadable == 0:
        return {}, 2
    max_page = max([*([max(p.keys()) if p else -1 for p in backend_pages.values()]), *([max(pym_pages.keys()) if pym_pages else -1])])
    pages_report = []
    for pi in range(max_page + 1):
        evidence = []
        present, missing = [], []
        for s in CANONICAL_BACKENDS:
            if sources[s]["status"] == "loaded" and pi in backend_pages.get(s, {}):
                present.append(s)
                blocks = backend_pages[s][pi].get("blocks", [])
                for i, b in enumerate(blocks):
                    evidence.append(normalise_backend_block(s, pi, i, b, str(dirs[s] / "pages" / f"page_{pi:04d}.json"), f"/blocks/{i}"))
            elif sources[s]["status"] in {"loaded", "missing"}:
                missing.append(s)
        if pi in pym_pages:
            present.append("pymupdf")
            evidence.extend(pym_pages[pi])
        groups, ungrouped = build_candidate_groups(evidence, config)
        page = {"page_index": pi, "page_number": pi + 1, "sources_present": present, "sources_missing": missing, "pymupdf_page": {"text_similarity_by_source": {}}, "counts": {"blocks_by_source": {s: sum(1 for e in evidence if e['source_backend'] == s) for s in present}, "text_blocks_by_source": {}, "geometry_blocks_by_source": {}, "tables_by_source": {}, "formulas_by_source": {}, "pictures_by_source": {}, "captions_by_source": {}}, "candidate_groups": groups, "ungrouped_candidates": [u["evidence_id"] for u in ungrouped], "conflicts": [], "warnings": [], "notes": []}
        page["conflicts"].extend(detect_conflicts(page, evidence))
        for m in missing:
            page["conflicts"].append({"conflict_id": f"p{pi:04d}_c{len(page['conflicts'])+1:04d}", "page_index": pi, "severity": "medium", "type": "missing_backend_page", "message": "Backend page missing", "sources": [m], "evidence_ids": []})
        pages_report.append(page)
    report = {"schema_name": "pdf2md.consensus_report", "schema_version": "0.1.0", "pdf_path": str(pdf_path), "pdf_stem": pdf_path.stem, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "config_path": str(config_path), "coordinate_space": config["consensus"]["coordinate_space"], "sources": sources, "document_summary": {"page_count": len(pages_report)}, "pages": pages_report}
    return report, 0


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def print_summary(report: dict[str, Any], output_path: Path, verbose: bool = False) -> None:
    print(f"Consensus report: {output_path}")
    print(f"PDF: {report['pdf_path']}")
    print("Sources:")
    for s, v in report["sources"].items():
        print(f"  {s}: {v['status']}, {v.get('page_count', 0)} pages")
    for p in report["pages"]:
        print(f"Page {p['page_number']}:")
        print(f"  present: {', '.join(p['sources_present'])}")
        print(f"  blocks: " + ", ".join(f"{k}={v}" for k, v in p['counts']['blocks_by_source'].items()))
        print(f"  groups: {len(p['candidate_groups'])}")
        print(f"  conflicts: {len(p['conflicts'])}")
        if verbose:
            print(f"  warnings: {len(p['warnings'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--fail-on-missing-backend", action="store_true")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(Path(args.config))
        report, rc = build_consensus_report(Path(args.pdf_path), cfg, Path(args.config), args.fail_on_missing_backend)
        if rc != 0:
            return rc
        out = Path(args.output) if args.output else Path(cfg["consensus"]["output_root"]) / Path(args.pdf_path).stem / "consensus_report.json"
        write_report(report, out)
        if not args.json_only:
            print_summary(report, out, verbose=args.verbose)
        return 0
    except (ValueError, FileNotFoundError, tomllib.TOMLDecodeError):
        return 1
    except Exception:
        return 3


if __name__ == "__main__":
    sys.exit(main())
