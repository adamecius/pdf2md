#!/usr/bin/env python3
"""Batch PaddleOCR runner that writes TXT + JSON per image."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def iter_inputs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    raise FileNotFoundError(path)


def detect_use_gpu() -> bool:
    try:
        import paddle
    except ImportError:
        return False
    return paddle.device.is_compiled_with_cuda()


def to_text_and_items(result: list) -> tuple[str, list[dict]]:
    lines: list[str] = []
    items: list[dict] = []
    for block in result:
        if not block:
            continue
        for item in block:
            if len(item) < 2:
                continue
            bbox = item[0]
            text, score = item[1]
            lines.append(str(text))
            items.append({"text": text, "score": float(score), "bbox": bbox})
    return "\n".join(lines), items


def main() -> int:
    parser = argparse.ArgumentParser(description="PaddleOCR batch runner")
    parser.add_argument("-i", "--input", required=True, help="image file or directory")
    parser.add_argument("-o", "--output", default="paddleocr_output", help="output directory")
    parser.add_argument("-l", "--lang", default="en", help="OCR language")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    args = parser.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("error: paddleocr is not installed", file=sys.stderr)
        return 1

    use_gpu = detect_use_gpu() if args.device == "auto" else args.device == "cuda"
    ocr = PaddleOCR(use_angle_cls=True, lang=args.lang, use_gpu=use_gpu)

    files = iter_inputs(in_path)
    if not files:
        print(f"No supported images found under {in_path}")
        return 1

    print(f"🚀 Processing {len(files)} file(s) with PaddleOCR")
    for f in files:
        result = ocr.ocr(str(f), cls=True)
        text, items = to_text_and_items(result)

        txt_path = out_dir / f"{f.stem}.txt"
        json_path = out_dir / f"{f.stem}.json"
        txt_path.write_text(text, encoding="utf-8")
        json_path.write_text(json.dumps({"file": str(f), "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ {f.name} -> {txt_path.name}, {json_path.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
