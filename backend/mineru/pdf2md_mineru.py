#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build_parser():
    p = argparse.ArgumentParser(description="Convert a PDF to Markdown using the official MinerU CLI.")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--json-out")
    p.add_argument("--out-dir")
    p.add_argument("--lang", default="en")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--model-path")
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("--api", action="store_true")
    p.add_argument("--backend", default="hybrid-auto-engine", choices=["hybrid-auto-engine", "pipeline", "vlm-auto-engine"])
    p.add_argument("--api-url")
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


def plan_mineru_command(input_pdf: Path, out_dir: Path, args: argparse.Namespace) -> list[str]:
    cmd = ["mineru", "-p", str(input_pdf), "-o", str(out_dir)]
    if args.backend:
        cmd.extend(["-b", args.backend])
    if args.lang:
        cmd.extend(["-l", args.lang])
    if args.api_url:
        cmd.extend(["--api-url", args.api_url])
    return cmd


def select_markdown(out_dir: Path, input_stem: str) -> Path:
    by_stem = sorted(out_dir.rglob(f"{input_stem}.md"))
    if len(by_stem) == 1:
        return by_stem[0]
    if len(by_stem) > 1:
        raise RuntimeError(f"MinerU generated multiple markdown files matching stem '{input_stem}' under: {out_dir}")
    all_md = sorted(out_dir.rglob("*.md"))
    if len(all_md) == 1:
        return all_md[0]
    if not all_md:
        raise RuntimeError(f"MinerU completed but no markdown found under: {out_dir}")
    raise RuntimeError(f"MinerU generated multiple markdown files under {out_dir}; unable to choose safely.")


def main() -> int:
    args = build_parser().parse_args()
    try:
        input_pdf = _validate_pdf(args.input)
        if args.allow_download:
            raise RuntimeError("--allow-download is not implemented for MinerU wrapper.")
        if args.api and not args.api_url:
            raise RuntimeError("API mode requires --api-url explicitly.")

        out_md = Path(args.output).expanduser().resolve() if args.output else input_pdf.with_suffix(".md")
        out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (out_md.parent / f"{out_md.stem}_mineru")
        out_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        if args.model_path:
            env["MINERU_MODEL_PATH"] = args.model_path

        cmd = plan_mineru_command(input_pdf, out_dir, args)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"mineru failed with code {result.returncode}")

        selected_md = select_markdown(out_dir, input_pdf.stem)
        shutil.copyfile(selected_md, out_md)

        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps(
                    {
                        "backend": "mineru",
                        "input": str(input_pdf),
                        "output_md": str(out_md),
                        "mineru_output_dir": str(out_dir),
                        "selected_markdown": str(selected_md),
                        "command": cmd,
                        "returncode": result.returncode,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        print(str(out_md))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
