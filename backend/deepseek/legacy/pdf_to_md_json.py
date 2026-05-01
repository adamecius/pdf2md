#!/usr/bin/env python3
"""DeepSeek-OCR PDF -> Markdown + JSON.

Workflow requested by user:
1) Download official GitHub repo (deepseek-ai/DeepSeek-OCR).
2) Follow official HF-style inference (AutoModel/AutoTokenizer).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import fitz
import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer


DEFAULT_REPO_URL = "https://github.com/deepseek-ai/DeepSeek-OCR"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-OCR"
PROMPT = "<image>\n<|grounding|>Convert the document to markdown."


def ensure_repo(repo_url: str, repo_cache_dir: Path) -> Path:
    repo_cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = repo_cache_dir / "DeepSeek-OCR"
    if not (repo_dir / ".git").exists():
        subprocess.run(["git", "clone", repo_url, str(repo_dir)], check=True)
    else:
        subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only"], check=True)
    return repo_dir


def pdf_to_images(pdf_path: Path, dpi: int = 150) -> list[Image.Image]:
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    images: list[Image.Image] = []
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    finally:
        doc.close()
    return images


def load_model(model_name: str, device: str, local_only: bool) -> tuple[AutoTokenizer, AutoModel]:
    attn_impl = "flash_attention_2" if device.startswith("cuda") else "eager"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, local_files_only=local_only)
    model = AutoModel.from_pretrained(
        model_name,
        trust_remote_code=True,
        use_safetensors=True,
        _attn_implementation=attn_impl,
        local_files_only=local_only,
    ).eval()
    if device.startswith("cuda"):
        model = model.to(device).to(torch.bfloat16)
    return tokenizer, model


def run(input_pdf: Path, output_dir: Path, model_name: str, device: str, local_only: bool) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = pdf_to_images(input_pdf)
    tokenizer, model = load_model(model_name, device, local_only)

    page_md: list[str] = []
    for i, img in enumerate(pages, start=1):
        img_file = output_dir / f"{input_pdf.stem}_p{i:04d}.png"
        img.save(img_file)
        md = model.infer(
            tokenizer,
            prompt=PROMPT,
            image_file=str(img_file),
            output_path=str(output_dir),
            base_size=1024,
            image_size=640,
            crop_mode=True,
            save_results=False,
            test_compress=True,
        )
        page_md.append(f"\n\n<!-- page {i} -->\n{md}")

    merged = "".join(page_md).strip()
    md_path = output_dir / f"{input_pdf.stem}.md"
    json_path = output_dir / f"{input_pdf.stem}.json"
    md_path.write_text(merged, encoding="utf-8")
    json_path.write_text(json.dumps({
        "backend": "deepseek-ocr",
        "model": model_name,
        "source_pdf": str(input_pdf),
        "pages": len(pages),
        "markdown": merged,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path


def main() -> None:
    p = argparse.ArgumentParser(description="DeepSeek-OCR PDF -> Markdown + JSON")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output", default="deepseek_output")
    p.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Official DeepSeek-OCR GitHub URL")
    p.add_argument("--repo-cache-dir", default="backend/deepseek/.cache")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL)
    p.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    p.add_argument("--local-only", action="store_true")
    args = p.parse_args()

    input_pdf = Path(args.input).expanduser().resolve()
    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {input_pdf}")

    repo_dir = ensure_repo(args.repo_url, Path(args.repo_cache_dir).expanduser().resolve())
    print(f"Using DeepSeek-OCR repo at: {repo_dir}")

    md_path, json_path = run(input_pdf, Path(args.output).expanduser().resolve(), args.model, args.device, args.local_only)
    print("✅ Conversion complete")
    print(f"Markdown: {md_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
