#!/usr/bin/env python3
"""Minimal smoke test for GLM OCR backend (local checks only)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main() -> int:
    py = shutil.which("python") or sys.executable
    print("+", py, "-c import glmocr")
    rc = subprocess.call([py, "-c", "import glmocr"])
    if rc != 0:
        print("ERROR: glmocr import failed")
        return rc

    if not os.getenv("ZHIPU_API_KEY"):
        print("WARN: ZHIPU_API_KEY not set; skipping remote API smoke test")
        return 0

    print("SUCCESS: local GLM OCR smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
