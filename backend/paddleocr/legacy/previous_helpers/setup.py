"""Ready-to-run PaddleOCR backend helper.

Runs OCR over image files in an input directory and writes plain-text
transcriptions into an output directory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def detect_device() -> str:
    try:
        import paddle
    except ImportError:
        return "cpu"
    return "cuda" if paddle.device.is_compiled_with_cuda() else "cpu"


def iter_images(input_dir: Path) -> list[Path]:
    return sorted(
        p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def flatten_text(result: list) -> str:
    lines: list[str] = []
    for block in result:
        if not block:
            continue
        for item in block:
            if len(item) >= 2 and isinstance(item[1], tuple):
                lines.append(str(item[1][0]))
    return "\n".join(lines)


def run(input_dir: Path, output_dir: Path, lang: str, use_gpu: bool) -> int:
    if not input_dir.exists():
        sys.exit(f"error: input directory does not exist: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        sys.exit("error: paddleocr is not installed in this environment")

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu)
    images = iter_images(input_dir)
    if not images:
        print(f"[warn] no images found under {input_dir}")
        return 0

    for img in images:
        print(f"[run] OCR {img}")
        result = ocr.ocr(str(img), cls=True)
        text = flatten_text(result)
        out_file = output_dir / f"{img.stem}.txt"
        out_file.write_text(text, encoding="utf-8")
        print(f"[ok] wrote {out_file}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="PaddleOCR backend runner")
    parser.add_argument("-i", "--input", default="data/images", help="input dir")
    parser.add_argument("-o", "--output", default="data/output", help="output dir")
    parser.add_argument("-l", "--lang", default="en", help="OCR language (en, ch, ...)")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    args = parser.parse_args()

    device = detect_device() if args.device == "auto" else args.device
    rc = run(Path(args.input), Path(args.output), args.lang, use_gpu=(device == "cuda"))
    sys.exit(rc)


if __name__ == "__main__":
    main()
