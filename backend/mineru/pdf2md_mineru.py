#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

try:
    from run_mineru import run_mineru_cli
except Exception:
    from backend.mineru.run_mineru import run_mineru_cli


def build_parser():
    p = argparse.ArgumentParser(description="Convert a PDF to Markdown using MinerU CLI.")
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
    return p


def main() -> int:
    a = build_parser().parse_args()
    try:
        out = run_mineru_cli(
            input_path=a.input,
            output_path=a.output,
            out_dir=a.out_dir,
            json_out=a.json_out,
            lang=a.lang,
            device=a.device,
            model_path=a.model_path,
            allow_download=a.allow_download,
            api=a.api,
            backend=a.backend,
            api_url=a.api_url,
        )
        print(str(out))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
