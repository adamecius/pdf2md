from __future__ import annotations
import argparse, json, re
from pathlib import Path
import tomllib
from .latex_groundtruth import equation_body_key
from .rules import default_rules, rule_matches
from .schemas import Rule


def _load_rules(path: Path | None) -> list[Rule]:
    if not path or not path.exists():
        return default_rules()
    data = tomllib.loads(path.read_text())
    return [Rule(**r) for r in data.get("rules", [])] or default_rules()


def _near_caption(blocks: list[dict], i: int, regex: str) -> bool:
    rx = re.compile(regex)
    lo, hi = max(0, i - 3), min(len(blocks), i + 4)
    for j in range(lo, hi):
        if j == i:
            continue
        t = ((blocks[j].get("content") or {}).get("text") or blocks[j].get("text") or "")
        if rx.search(t):
            return True
    return False


def _formula_info(text: str, rules_applied: list[dict]) -> dict | None:
    tag = re.search(r"\\tag\{\s*(\d+(?:\.\d+)*)\s*\}", text)
    paren = re.search(r"\(\s*(\d+(?:\.\d+)*)\s*\)\s*$", text)
    label = tag.group(1) if tag else (paren.group(1) if paren else None)
    source = "latex_tag" if tag else ("parenthesised_suffix" if paren else None)
    if any(r["rule_id"] == "equation.number_split_block" for r in rules_applied):
        source = "split_number_block"
    key = equation_body_key(text)
    if key or label:
        return {"body_key": key, "equation_label": label, "label_source": source}
    return None


def normalise_blocks(blocks: list[dict], backend: str, rules: list[Rule]) -> list[dict]:
    out = []
    for i, b in enumerate(blocks):
        nb = json.loads(json.dumps(b))
        text = ((nb.get("content") or {}).get("text") or nb.get("text") or "")
        typ = nb.get("type", "paragraph")
        y = (((nb.get("geometry") or {}).get("bbox") or [None, None, None, None])[1])
        applied = []
        for r in rules:
            m = rule_matches(r, backend, typ, text, y)
            if not m:
                continue
            if r.requires_near_caption_regex and not _near_caption(blocks, i, r.requires_near_caption_regex):
                continue
            if r.normalised_type:
                if not (nb.get("type") == "caption" and r.id == "table.flattened_paragraph"):
                    nb["type"] = r.normalised_type
            if r.normalised_text_rewrite:
                text = re.sub(r.text_regex, r.normalised_text_rewrite, text)
                if "content" in nb:
                    nb["content"]["text"] = text
            applied.append({"rule_id": r.id, "source": "ocr_conventions.proposed.toml", "reason": f"text matched {r.text_regex}"})
        formula = _formula_info(text, applied) if ("=" in text or "tag{" in text or typ in {"equation", "formula", "equation_number"}) else None
        if applied or formula:
            nb["normalisation"] = {"backend": backend, "original_type": typ, "normalised_type": nb.get("type", typ), "original_text": ((b.get('content') or {}).get('text') or b.get('text') or ''), "normalised_text": ((nb.get('content') or {}).get('text') or nb.get('text') or ''), "rules_applied": applied}
            if formula:
                nb["formula"] = formula
        out.append(nb)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-root", required=True)
    p.add_argument("--config")
    p.add_argument("--output-root", required=True)
    args = p.parse_args()
    inp, out = Path(args.input_root), Path(args.output_root)
    out.mkdir(parents=True, exist_ok=True)
    rules = _load_rules(Path(args.config) if args.config else None)
    preview = []
    for doc_dir in inp.iterdir():
        if not doc_dir.is_dir() or doc_dir.name.startswith('.'):
            continue
        backend_root = doc_dir / 'backend_ir'
        if not backend_root.exists():
            continue
        doc_id = doc_dir.name
        for backend_dir in backend_root.iterdir():
            if not backend_dir.is_dir():
                continue
            backend = backend_dir.name
            extraction_root = backend_dir / '.current' / 'extraction_ir' / doc_id
            if not extraction_root.exists():
                continue
            for f in extraction_root.rglob('*.json'):
                data = json.loads(f.read_text())
                blocks = data.get('blocks') if isinstance(data, dict) else None
                if not isinstance(blocks, list):
                    continue
                nblocks = normalise_blocks(blocks, backend, rules)
                dest = out / doc_id / 'backend_ir' / backend / '.current' / 'extraction_ir' / doc_id / f.relative_to(extraction_root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                new_data = dict(data)
                new_data['blocks'] = nblocks
                dest.write_text(json.dumps(new_data, indent=2))
                preview.extend([b for b in nblocks if b.get('normalisation')])
    (out.parent / "diagnostics" / "conventions").mkdir(parents=True, exist_ok=True)
    (out.parent / "diagnostics" / "conventions" / "normalised_blocks_preview.json").write_text(json.dumps(preview, indent=2))


if __name__ == "__main__":
    main()
