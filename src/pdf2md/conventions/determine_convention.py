from __future__ import annotations
import argparse, json
from pathlib import Path
from .latex_groundtruth import extract_groundtruth_objects
from .reporting import write_report
from .rules import default_rules


def _read_tex(root: Path) -> dict[str, dict]:
    out = {}
    for tex in root.rglob("*.tex"):
        out[tex.stem] = extract_groundtruth_objects(tex.read_text())
    return out


def _scan_backend(root: Path, backend: str) -> dict:
    examples = []
    blocks_seen = 0
    for f in (root / "backend_ir" / backend).rglob("*.json"):
        d = json.loads(f.read_text())
        for b in d.get("blocks", []):
            blocks_seen += 1
            txt = (b.get("content") or {}).get("text") or b.get("text") or ""
            if txt.strip():
                examples.append({"doc_id": f.parent.name, "block_id": b.get("block_id", ""), "before": txt[:80], "after": txt[:80]})
    return {"block_count": blocks_seen, "examples": examples[:20]}


def _write_proposed_toml(path: Path) -> None:
    lines = []
    for r in default_rules():
        lines += ["[[rules]]", f'id = "{r.id}"', f'backend = "{r.backend}"', f'object_type = "{r.object_type}"', f"text_regex = '''{r.text_regex}'''"]
        if r.normalised_type:
            lines.append(f'normalised_type = "{r.normalised_type}"')
        if r.normalised_text_rewrite:
            lines.append(f"normalised_text_rewrite = '''{r.normalised_text_rewrite}'''")
        if r.extract_equation_label:
            lines.append("extract_equation_label = true")
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
    p.add_argument("--strict", action="store_true")
    p.add_argument("--include-normalised-preview", action="store_true")
    args = p.parse_args()
    batch_root = Path(args.root) / args.batch
    gts = _read_tex(batch_root)
    backends = args.backend or ["mineru", "paddleocr", "deepseek", "pymupdf"]
    report = {"batch": args.batch, "fixture_provenance": list(gts.keys()), "backends": {}}
    for b in backends:
        report["backends"][b] = _scan_backend(batch_root, b)
    output = Path(args.output)
    write_report(output, report, emit_markdown=args.emit_markdown_report)
    if args.write_proposed_config:
        _write_proposed_toml(output / "ocr_conventions.proposed.toml")


if __name__ == "__main__":
    main()
