#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from run_paddleocr import run_paddleocr_cli


def parser():
    p = argparse.ArgumentParser(description="Convert PDF to Markdown via PaddleOCR CLI (local).")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--json-out")
    p.add_argument("--out-dir")
    p.add_argument("--lang", default="en")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--model-path")
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("--api", action="store_true")
    return p


def main() -> int:
    a = parser().parse_args()
    try:
        out = run_paddleocr_cli(input_path=a.input, output_path=a.output, out_dir=a.out_dir, json_out=a.json_out, lang=a.lang, device=a.device, model_path=a.model_path, allow_download=a.allow_download, api=a.api)
        print(str(out))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
