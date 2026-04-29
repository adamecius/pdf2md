"""End-to-end smoke test for GLM OCR backend.

Requires ZHIPU_API_KEY and an input image.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="GLM OCR smoke test")
    p.add_argument("image", type=Path, help="path to test image")
    args = p.parse_args()

    if not args.image.exists():
        print(f"FAIL: image not found: {args.image}", file=sys.stderr)
        return 1
    if not os.getenv("ZHIPU_API_KEY"):
        print("FAIL: ZHIPU_API_KEY is not set", file=sys.stderr)
        return 1

    rc = subprocess.call(["python", "run_claude.py", str(args.image)])
    if rc != 0:
        print(f"FAIL: run_claude.py exited with {rc}", file=sys.stderr)
        return rc

    md = args.image.with_suffix(".md")
    if not md.exists() or md.stat().st_size == 0:
        print("FAIL: markdown output missing or empty", file=sys.stderr)
        return 1

    print("SMOKE TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
