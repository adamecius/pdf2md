#!/usr/bin/env python3
"""PaddleOCR CLI-style runner for a single image.

Usage:
    python run_grok.py -i path/to/image.png
    python run_grok.py -i image.jpg -o out.txt --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def detect_use_gpu() -> bool:
    try:
        import paddle
    except ImportError:
        return False
    return paddle.device.is_compiled_with_cuda()


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
    parser = argparse.ArgumentParser(description="PaddleOCR: image to text")
    parser.add_argument("-i", "--input", required=True, help="path to input image")
    parser.add_argument("-o", "--output", help="path to output .txt (default: <image>.txt)")
    parser.add_argument("--force", action="store_true", help="overwrite output file")
    parser.add_argument("-l", "--lang", default="en", help="OCR language hint")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        print(f"❌ Error: input file not found: {input_path}")
        return 1

    output_path = Path(args.output).resolve() if args.output else input_path.with_suffix(".txt")
    if output_path.exists() and not args.force:
        print(f"⚠️  Output exists: {output_path}. Use --force to overwrite.")
        return 1

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("❌ paddleocr is not installed. Activate env and install requirements first.")
        return 1

    use_gpu = detect_use_gpu() if args.device == "auto" else args.device == "cuda"
    print(f"🚀 Running PaddleOCR on: {input_path.name} (device={'cuda' if use_gpu else 'cpu'})")

    ocr = PaddleOCR(use_angle_cls=True, lang=args.lang, use_gpu=use_gpu)
    result = ocr.ocr(str(input_path), cls=True)
    text = flatten_text(result)
    output_path.write_text(text, encoding="utf-8")

    print(f"✅ OCR complete: {output_path}")
    print("\n📝 Preview (first 15 lines):")
    for idx, line in enumerate(text.splitlines(), start=1):
        if idx > 15:
            break
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
