"""Setup helper for GLM OCR backend."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main() -> int:
    py = shutil.which("python") or sys.executable

    print("[1/3] Python:", py)
    rc = subprocess.call([py, "-c", "import glmocr; print('glmocr import ok')"])
    if rc != 0:
        print("error: glmocr import failed")
        return rc

    print("[2/3] checking API key env...")
    if not os.getenv("ZHIPU_API_KEY"):
        print("warning: ZHIPU_API_KEY is not set")
    else:
        print("ok: ZHIPU_API_KEY is set")

    print("[3/3] setup looks good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
