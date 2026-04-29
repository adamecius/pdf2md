"""Convert a PDF/image to markdown using the official GLM-OCR SDK."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from glmocr.config import MaaSApiConfig
from glmocr.maas_client import MaaSClient


def main() -> int:
    p = argparse.ArgumentParser(description="Run GLM-OCR over one file")
    p.add_argument("input", type=Path, help="input file path (pdf/png/jpg/jpeg)")
    p.add_argument("-o", "--output", type=Path, default=None, help="output markdown path")
    p.add_argument("--model", default="glm-ocr", help="GLM-OCR model name")
    p.add_argument("--api-url", default="https://open.bigmodel.cn/api/paas/v4/layout_parsing")
    args = p.parse_args()

    if not args.input.exists():
        sys.exit(f"error: input not found: {args.input}")

    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        sys.exit("error: ZHIPU_API_KEY is not set")

    cfg = MaaSApiConfig(api_key=api_key, api_url=args.api_url, model=args.model)
    with MaaSClient(cfg) as client:
        result = client.parse(str(args.input))

    md = result.get("md_results") if isinstance(result, dict) else None
    if not md:
        sys.exit("error: GLM-OCR response did not include md_results")

    out = args.output or args.input.with_suffix(".md")
    out.write_text(md, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
