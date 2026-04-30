#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


def build_parser():
    p = argparse.ArgumentParser(description="Convert a PDF to Markdown using MinerU.")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--json-out")
    p.add_argument("--out-dir")
    p.add_argument("--lang", default="en")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--model-path")
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("--api", action="store_true", help="Explicitly use remote API mode.")
    p.add_argument("--backend", default="hybrid-auto-engine", choices=["hybrid-auto-engine", "pipeline", "vlm-auto-engine"])
    p.add_argument("--api-url", default=None)
    p.add_argument("--no-formula", action="store_true")
    p.add_argument("--no-table", action="store_true")
    p.add_argument("--start-page", type=int, default=0)
    p.add_argument("--end-page", type=int, default=None)
    return p


def _validate_pdf(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file() or p.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {p}")
    return p


def _load_pdf_to_md_json_module():
    module_path = Path(__file__).with_name("pdf_to_md_json.py")
    spec = importlib.util.spec_from_file_location("mineru_pdf_to_md_json", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _select_markdown(out_dir: Path, input_stem: str) -> Path:
    matches = sorted(out_dir.rglob(f"{input_stem}.md"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise RuntimeError(f"MinerU generated multiple markdown files matching stem '{input_stem}' under: {out_dir}")
    all_md = sorted(out_dir.rglob("*.md"))
    if len(all_md) == 1:
        return all_md[0]
    if not all_md:
        raise RuntimeError(f"MinerU completed but no markdown found under: {out_dir}")
    raise RuntimeError(f"MinerU generated multiple markdown files under {out_dir}; unable to choose safely.")


def main():
    args = build_parser().parse_args()
    try:
        input_pdf = _validate_pdf(args.input)
        out_md = Path(args.output).expanduser().resolve() if args.output else input_pdf.with_suffix(".md")
        out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else out_md.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        if args.model_path:
            os.environ["MINERU_MODEL_PATH"] = args.model_path
        if args.allow_download:
            print("warning: --allow-download is accepted for compatibility; MinerU wrapper does not auto-download models.", file=sys.stderr)

        if args.api and not args.api_url:
            raise RuntimeError("API mode requires --api-url explicitly.")

        mineru_module = _load_pdf_to_md_json_module()
        import asyncio

        asyncio.run(
            mineru_module.convert_with_mineru(
                input_path=input_pdf,
                output_dir=out_dir,
                backend=args.backend,
                language=args.lang,
                formula=not args.no_formula,
                table=not args.no_table,
                start_page=args.start_page,
                end_page=args.end_page,
                api_url=args.api_url if args.api else None,
            )
        )

        generated_md = _select_markdown(out_dir, input_pdf.stem)
        out_md.write_text(generated_md.read_text(encoding="utf-8"), encoding="utf-8")

        if args.json_out:
            payload = {
                "backend": "mineru",
                "input": str(input_pdf),
                "output_md": str(out_md),
                "generated_md": str(generated_md),
                "out_dir": str(out_dir),
                "backend_mode": args.backend,
                "api_mode": args.api,
                "start_page": args.start_page,
                "end_page": args.end_page,
            }
            Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print(str(out_md))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
