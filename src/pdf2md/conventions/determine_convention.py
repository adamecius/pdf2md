from __future__ import annotations
import argparse, json, re
from collections import defaultdict
from pathlib import Path
from .latex_groundtruth import extract_groundtruth_objects
from .reporting import write_report


def _read_tex(root: Path) -> dict[str, dict]:
    out = {}
    for tex in root.rglob("*.tex"):
        out[tex.parent.name] = extract_groundtruth_objects(tex.read_text())
    return out


def _infer(blocks: list[dict], backend: str, doc_id: str) -> tuple[dict, list[dict], dict]:
    s = defaultdict(int)
    examples = []
    proposed = defaultdict(lambda: {"support": 0, "doc_ids": set(), "block_ids": set(), "example_before": "", "example_after": "", "reason": ""})
    for i, b in enumerate(blocks):
        t = (b.get("type") or "").lower()
        txt = ((b.get("content") or {}).get("text") or b.get("text") or "")
        bid = b.get("block_id", f"{doc_id}:{i}")
        has_geo = bool((b.get("geometry") or {}).get("bbox"))
        s["geometry_available" if has_geo else "geometry_missing"] += 1
        if re.match(r"^\s*(Figure|Fig\.|Table)\s+\d+", txt):
            key = "caption_as_paragraph" if t == "paragraph" else ("caption_as_unknown" if t == "unknown" else "caption_as_caption")
            s[key] += 1
            examples.append({"doc_id": doc_id, "convention": key, "object_type": "caption", "backend_blocks": [{"block_id": bid, "type": t, "text": txt}], "groundtruth_hint": "caption"})
            proposed["caption.figure_or_table_prefix"].update(reason="caption prefix detected", example_before=txt, example_after=txt)
            proposed["caption.figure_or_table_prefix"]["support"] += 1
            proposed["caption.figure_or_table_prefix"]["doc_ids"].add(doc_id)
            proposed["caption.figure_or_table_prefix"]["block_ids"].add(bid)
        if re.match(r"^\s*FIG\s*$", txt):
            near = any(re.match(r"^\s*(Figure|Fig\.)\s+\d+", ((blocks[j].get("content") or {}).get("text") or blocks[j].get("text") or "")) for j in range(max(0, i-3), min(len(blocks), i+4)) if j != i)
            if near:
                s["figure_as_text_fig"] += 1
                proposed["figure.placeholder_fig_near_caption"]["support"] += 1
                proposed["figure.placeholder_fig_near_caption"]["doc_ids"].add(doc_id)
                proposed["figure.placeholder_fig_near_caption"]["block_ids"].add(bid)
                proposed["figure.placeholder_fig_near_caption"].update(reason="FIG near figure caption", example_before=txt, example_after="picture")
        if "\\tag{" in txt:
            s["formula_with_latex_tag"] += 1
        if re.search(r"\(\s*\d+(?:\.\d+)*\s*\)\s*$", txt):
            s["formula_with_parenthesised_label"] += 1
        if backend == "paddleocr" and re.match(r"^\s*\(\s*\d+(?:\.\d+)*\s*\)\s*$", txt):
            s["formula_number_split_block"] += 1
            proposed["equation.number_split_block"]["support"] += 1
            proposed["equation.number_split_block"]["doc_ids"].add(doc_id)
            proposed["equation.number_split_block"]["block_ids"].add(bid)
            proposed["equation.number_split_block"].update(reason="number-only equation block", example_before=txt, example_after=txt)
    return dict(s), examples[:20], proposed


def _write_proposed_toml(path: Path, backend_rules: dict) -> None:
    lines = ["# evidence-derived rules"]
    for rid, item in backend_rules.items():
        lines += [f"# support_count={item['support']} docs={sorted(item['doc_ids'])} block_ids={sorted(item['block_ids'])}", "[[rules]]"]
        if rid == "equation.number_split_block":
            lines += [f'id = "{rid}"', 'backend = "paddleocr"', 'object_type = "*"', "text_regex = '''^\\s*\\(\\s*\\d+(\\.\\d+)*\\s*\\)\\s*$'''", 'normalised_type = "equation_number"']
        elif rid == "figure.placeholder_fig_near_caption":
            lines += [f'id = "{rid}"', 'backend = "*"', 'object_type = "*"', "text_regex = '''^\\s*FIG\\s*$'''", "requires_near_caption_regex = \'\'^\\s*(Figure|Fig\\.)\\s+\\d+\'\'\'", 'normalised_type = "picture"']
        else:
            lines += [f'id = "{rid}"', 'backend = "*"', 'object_type = "*"', "text_regex = '''^\\s*(Figure|Fig\\.|Table)\\s+\\d+'''", 'normalised_type = "caption"']
        lines.append("")
    path.write_text("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--batch", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--backend", action="append")
    p.add_argument("--write-proposed-config", action="store_true")
    p.add_argument("--emit-markdown-report", action="store_true")
    p.add_argument("--min-support", type=int, default=1)
    args = p.parse_args()
    batch_root = Path(args.root) / args.batch
    gt = _read_tex(batch_root)
    backends = args.backend or ["mineru", "paddleocr", "deepseek", "pymupdf"]
    report = {"batch": args.batch, "fixture_provenance": sorted(gt.keys()), "backends": {}}
    merged = {}
    for backend in backends:
        summary = defaultdict(int)
        examples, prules = [], {}
        for f in (batch_root / "backend_ir" / backend).rglob("*.json"):
            d = json.loads(f.read_text())
            s, ex, proposed = _infer(d.get("blocks", []), backend, f.parent.name)
            for k, v in s.items():
                summary[k] += v
            examples.extend(ex)
            for rid, pinfo in proposed.items():
                existing = prules.setdefault(rid, {"support": 0, "doc_ids": set(), "block_ids": set(), "reason": pinfo["reason"], "example_before": pinfo["example_before"], "example_after": pinfo["example_after"]})
                existing["support"] += pinfo["support"]
                existing["doc_ids"].update(pinfo["doc_ids"])
                existing["block_ids"].update(pinfo["block_ids"])
        report["backends"][backend] = {"summary": dict(summary), "examples": examples[:30], "proposed_rules": [{"rule_id": rid, "support": info["support"], "supporting_doc_ids": sorted(info["doc_ids"]), "supporting_backend_block_ids": sorted(info["block_ids"]), "groundtruth_source": "latex_fixture+backend_ir", "example_before": info["example_before"], "example_after": info["example_after"], "reason": info["reason"]} for rid, info in prules.items()]}
        merged.update(prules)
    out = Path(args.output)
    write_report(out, report, emit_markdown=args.emit_markdown_report)
    if args.write_proposed_config:
        keep = {k: v for k, v in merged.items() if v["support"] >= args.min_support}
        _write_proposed_toml(out / "ocr_conventions.proposed.toml", keep)


if __name__ == "__main__":
    main()
