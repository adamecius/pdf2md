if __name__ != "__main__":
    import pytest
    pytest.skip("integration script; requires external backend dependencies", allow_module_level=True)

"""End-to-end smoke test for PaddleOCR.

Synthesizes a one-page image with text, runs PaddleOCR, and checks output.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WORKDIR = Path(__file__).parent / "smoke_test_workdir"


def make_test_image(path: Path) -> None:
    img = Image.new("RGB", (1280, 720), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 52)
    except OSError:
        font = ImageFont.load_default()

    text = (
        "PaddleOCR Smoke Test\n\n"
        "This is a synthetic test image.\n"
        "If this text is extracted, the OCR pipeline is healthy.\n\n"
        "Equation: E = m * c^2\n"
        "Reference number: 42"
    )
    draw.multiline_text((70, 80), text, fill="black", font=font, spacing=16)
    img.save(path)


def flatten_text(result: list) -> str:
    lines: list[str] = []
    for block in result:
        if not block:
            continue
        for item in block:
            if len(item) >= 2 and isinstance(item[1], tuple):
                lines.append(str(item[1][0]))
    return "\n".join(lines)


def main() -> int:
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("FAIL: paddleocr is not installed — activate the env first", file=sys.stderr)
        return 1

    if WORKDIR.exists():
        import shutil

        shutil.rmtree(WORKDIR)
    WORKDIR.mkdir(parents=True)

    img = WORKDIR / "smoke.png"
    make_test_image(img)
    print(f"[1/3] synthesized {img} ({img.stat().st_size} bytes)")

    print("[2/3] running PaddleOCR (first run downloads models)...")
    ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
    result = ocr.ocr(str(img), cls=True)

    text = flatten_text(result)
    if not text.strip():
        print("FAIL: no OCR text produced", file=sys.stderr)
        return 1

    print("[3/3] OK — OCR produced non-empty output")
    print("\n--- OCR preview (first 400 chars) ---")
    print(text[:400])
    print("--------------------------------------")

    expected = ["PaddleOCR", "synthetic", "42"]
    missing = [kw for kw in expected if kw.lower() not in text.lower()]
    if missing:
        print(f"FAIL: missing expected tokens: {missing}", file=sys.stderr)
        return 1

    print("\nSMOKE TEST: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
