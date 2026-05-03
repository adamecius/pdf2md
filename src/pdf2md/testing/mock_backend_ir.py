from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

TYPE_MAP = {
    "paragraph": "paragraph",
    "title": "title",
    "section": "section",
    "subsection": "subsection",
    "caption": "caption",
    "footnote": "footnote",
    "list_item": "list_item",
    "figure": "picture",
    "table": "table",
    "equation": "equation",
    "reference": "paragraph",
}


@dataclass
class GTNode:
    text: str
    kind: str
    used: bool = False


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _sha(v: str) -> str:
    return "sha256:" + hashlib.sha256((v or "").encode("utf-8")).hexdigest()


def _bbox_norm(rect: list[float], w: float, h: float) -> list[float]:
    x0, y0, x1, y1 = rect
    vals = [x0 / w * 1000.0, y0 / h * 1000.0, x1 / w * 1000.0, y1 / h * 1000.0]
    return [max(0.0, min(1000.0, round(v, 3))) for v in vals]


def _token_overlap(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / (len(sa | sb) or 1)


def _match_kind(text: str, nodes: list[GTNode]) -> str:
    nt = _norm_text(text)
    if not nt:
        return "paragraph"
    best_i, best_s = None, 0.0
    for i, node in enumerate(nodes):
        if node.used:
            continue
        nn = _norm_text(node.text)
        if not nn:
            continue
        score = min(len(nt), len(nn)) / max(len(nt), len(nn)) if (nt in nn or nn in nt) else _token_overlap(nt, nn)
        if score > best_s:
            best_i, best_s = i, score
    if best_i is not None and best_s >= 0.25:
        nodes[best_i].used = True
        return TYPE_MAP.get(nodes[best_i].kind, "paragraph")
    return "paragraph"


def _build_block(doc_id: str, page_index: int, order: int, text: str, bbox: list[float], block_type: str) -> dict[str, Any]:
    ntext = _norm_text(text)
    return {
        "block_id": f"groundtruth_{doc_id}_p{page_index:04d}_b{order:04d}",
        "page_index": page_index,
        "page_number": page_index + 1,
        "order": order,
        "type": block_type,
        "subtype": None,
        "semantic_role": block_type,
        "docling_label_hint": block_type,
        "docling": {"label_hint": block_type, "excluded_from_docling": False},
        "geometry": {"bbox": bbox, "coordinate_space": "page_normalised_1000", "origin": "top_left"},
        "content": {"text": text, "normalised_text": ntext, "markdown": text},
        "structure": {},
        "confidence": {"overall": 0.99, "layout": 0.99, "text": 0.99},
        "comparison": {"compare_as": block_type, "text_hash": _sha(ntext), "geometry_hash": _sha(",".join(map(str, bbox)))},
        "compile_role": "candidate",
        "source_refs": [],
        "flags": [],
    }


def generate_mock_backend_ir(fixture_dir: Path, out_dir: Path, backend_name: str = "groundtruth") -> tuple[Path, Path]:
    fixture_dir, out_dir = Path(fixture_dir), Path(out_dir)
    gt = json.loads((fixture_dir / "groundtruth" / "source_groundtruth_ir.json").read_text())
    nodes = [GTNode(text=n.get("text", ""), kind=n.get("type", "paragraph")) for n in gt.get("nodes", [])]
    pdf_path = fixture_dir / "input" / f"{fixture_dir.name}.pdf"

    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_refs: list[str] = []

    with fitz.open(pdf_path) as doc:
        for pidx, page in enumerate(doc):
            pw, ph = page.rect.width, page.rect.height
            blocks: list[dict[str, Any]] = []
            order = 0

            for b in page.get_text("dict").get("blocks", []):
                if b.get("type") != 0:
                    continue
                txt = "\n".join("".join(sp.get("text", "") for sp in ln.get("spans", [])) for ln in b.get("lines", [])).strip()
                if not txt:
                    continue
                btype = _match_kind(txt, nodes)
                blocks.append(_build_block(fixture_dir.name, pidx, order, txt, _bbox_norm(b["bbox"], pw, ph), btype))
                order += 1

            for d in page.get_drawings() or []:
                r = d.get("rect")
                if not r:
                    continue
                blocks.append(_build_block(fixture_dir.name, pidx, order, "", _bbox_norm([r.x0, r.y0, r.x1, r.y1], pw, ph), "picture"))
                order += 1

            for img in page.get_images(full=True) or []:
                try:
                    rects = page.get_image_rects(img[0])
                except Exception:
                    rects = []
                for r in rects:
                    blocks.append(_build_block(fixture_dir.name, pidx, order, "", _bbox_norm([r.x0, r.y0, r.x1, r.y1], pw, ph), "picture"))
                    order += 1

            pf = pages_dir / f"page_{pidx:04d}.json"
            pf.write_text(json.dumps({"schema_name": "pdf2md.extraction_ir_page", "page_index": pidx, "page_number": pidx + 1, "blocks": blocks}, indent=2), encoding="utf-8")
            page_refs.append(str(pf))

    manifest = {
        "schema_name": "pdf2md.extraction_ir_manifest",
        "backend": {"id": backend_name, "name": backend_name},
        "document_id": fixture_dir.name,
        "pdf_path": str(pdf_path),
        "page_refs": page_refs,
    }
    mf = out_dir / "manifest.json"
    mf.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return pages_dir, mf
