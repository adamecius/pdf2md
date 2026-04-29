#!/usr/bin/env python3
"""DeepSeek-OCR PDF -> Markdown + JSON (standalone).

Uses the official Hugging Face model `deepseek-ai/DeepSeek-OCR` directly.
No local DeepSeek-OCR repo clone is required.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz
import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer


PROMPT = "<image>\n<|grounding|>Convert the document to markdown."


def pdf_to_images(pdf_path: Path, dpi: int = 150) -> list[Image.Image]:
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    images: list[Image.Image] = []
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
    finally:
        doc.close()
    return images


def load_model(model_name: str, device: str, local_only: bool = False):
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, local_files_only=local_only)
    model = AutoModel.from_pretrained(
        model_name,
        trust_remote_code=True,
        use_safetensors=True,
        _attn_implementation="flash_attention_2",
        local_files_only=local_only,
    )
    model = model.eval()
    if device.startswith("cuda"):
        model = model.to(device).to(torch.bfloat16)
    return tokenizer, model


def run_ocr_on_pdf(input_pdf: Path, output_dir: Path, model_name: str, device: str, local_only: bool) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    page_images = pdf_to_images(input_pdf)
    if not page_images:
        raise ValueError(f"No pages found in PDF: {input_pdf}")

    tokenizer, model = load_model(model_name=model_name, device=device, local_only=local_only)

    page_markdowns: list[str] = []
    for idx, img in enumerate(page_images, start=1):
        tmp_img = output_dir / f"{input_pdf.stem}_page_{idx:04d}.png"
        img.save(tmp_img)
        result = model.infer(
            tokenizer,
            prompt=PROMPT,
            image_file=str(tmp_img),
            output_path=str(output_dir),
            base_size=1024,
            image_size=640,
            crop_mode=True,
            save_results=False,
            test_compress=True,
        )
        page_markdowns.append(f"\n\n<!-- page {idx} -->\n{result}")

    full_markdown = "".join(page_markdowns).strip()
    md_path = output_dir / f"{input_pdf.stem}.md"
    md_path.write_text(full_markdown, encoding="utf-8")

    json_path = output_dir / f"{input_pdf.stem}.json"
    payload = {
        "backend": "deepseek-ocr",
        "model": model_name,
        "source_pdf": str(input_pdf),
        "pages": len(page_images),
        "markdown_file": str(md_path),
        "markdown": full_markdown,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return md_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek-OCR PDF -> Markdown + JSON")
    parser.add_argument("-i", "--input", required=True, help="Input PDF path")
    parser.add_argument("-o", "--output", default="deepseek_output", help="Output directory")
    parser.add_argument("-m", "--model", default="deepseek-ai/DeepSeek-OCR", help="HF model id or local model dir")
    parser.add_argument("--local-model-path", default=None, help="Local path to DeepSeek-OCR model files")
    parser.add_argument("--local-only", action="store_true", help="Do not access Hugging Face; load local files only")
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu", help="Device")
    args = parser.parse_args()

    input_pdf = Path(args.input).expanduser().resolve()
    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {input_pdf}")

    model_ref = str(Path(args.local_model_path).expanduser().resolve()) if args.local_model_path else args.model

    out_dir = Path(args.output).expanduser().resolve()
    md_path, json_path = run_ocr_on_pdf(input_pdf, out_dir, model_ref, args.device, args.local_only or bool(args.local_model_path))

    print("✅ Conversion complete")
    print(f"Markdown: {md_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
