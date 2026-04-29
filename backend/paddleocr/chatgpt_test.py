#!/usr/bin/env python3
"""Minimal PaddleOCR smoke test.

Creates an image with known text and verifies PaddleOCR returns expected
keywords.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def make_test_image(path: Path) -> None:
    img = Image.new("RGB", (1200, 400), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 56)
    except OSError:
        font = ImageFont.load_default()
    text = "PaddleOCR smoke test 42"
    draw.text((80, 150), text, fill="black", font=font)
    img.save(path)


def flatten_text(result: list) -> str:
    parts: list[str] = []
    for line in result:
        if not line:
            continue
        for item in line:
            if len(item) >= 2 and isinstance(item[1], tuple):
                parts.append(str(item[1][0]))
    return " ".join(parts)


def main() -> int:
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("ERROR: paddleocr is not installed. Activate the environment first.")
        return 1

    with tempfile.TemporaryDirectory(prefix="paddleocr_smoke_") as tmp:
        img_path = Path(tmp) / "smoke.png"
        make_test_image(img_path)

        ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
        result = ocr.ocr(str(img_path), cls=True)
        text = flatten_text(result)

        print("--- OCR output ---")
        print(text)

        expected = ["PaddleOCR", "smoke", "42"]
        missing = [kw for kw in expected if kw.lower() not in text.lower()]
        if missing:
            print(f"FAIL: missing expected keywords: {missing}")
            return 1

    print("PASS: PaddleOCR smoke test succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
