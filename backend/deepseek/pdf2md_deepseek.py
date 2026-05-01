#!/usr/bin/env python3
"""pdfmd_deepseek.py — Convert PDF to Markdown using DeepSeek-OCR (local-first).

Workflow:
  1. Look for the model locally in .local_models/ (lazy, no network).
  2. If missing, tell the user to re-run with --allow-download.
  3. --allow-download clones the official GitHub repo and pulls model
     weights via huggingface_hub.snapshot_download into .local_models/.
  4. Inference follows the official Transformers path:
       AutoModel.from_pretrained  →  model.infer()

Requirements (tested on Python 3.12 + CUDA 11.8):
  torch==2.6.0  transformers==4.46.3  tokenizers==0.20.3
  einops  addict  easydict  PyMuPDF  Pillow  huggingface_hub
  flash-attn==2.7.3 (GPU only, optional on CPU)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
# Supported model presets: repo URL + HF model id + infer() kwargs
_MODELS = {
    "deepseek-ai/DeepSeek-OCR": {
        "repo_url": "https://github.com/deepseek-ai/DeepSeek-OCR",
        "image_size": 640,
        "extra_infer": {"test_compress": True},
    },
    "deepseek-ai/DeepSeek-OCR-2": {
        "repo_url": "https://github.com/deepseek-ai/DeepSeek-OCR-2",
        "image_size": 768,
        "extra_infer": {},
    },
}

DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-OCR-2"
DEFAULT_MODELS_DIR = ".local_models/deepseek"
DEFAULT_REPO_CACHE = ".local_models/deepseek/.repos"
DEFAULT_DPI = 150
DEFAULT_BASE_SIZE = 1024
PROMPT_DOCUMENT = "<image>\n<|grounding|>Convert the document to markdown."
PROMPT_FREE_OCR = "<image>\nFree OCR."


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert a PDF to Markdown with DeepSeek-OCR (local-first).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # First-time setup: download model + clone official repo
  %(prog)s --allow-download -i paper.pdf

  # Subsequent runs (model already local)
  %(prog)s -i paper.pdf -o paper.md

  # Use OCR-1 instead of OCR-2
  %(prog)s -i paper.pdf --model-id deepseek-ai/DeepSeek-OCR

  # CPU-only inference (slow, no flash-attn needed)
  %(prog)s -i paper.pdf --device cpu

  # Custom DPI for page rasterisation
  %(prog)s -i paper.pdf --dpi 300

  # Free OCR prompt (no layout/grounding)
  %(prog)s -i paper.pdf --prompt free
""",
    )

    # -- I/O --
    gio = p.add_argument_group("input / output")
    gio.add_argument(
        "-i", "--input", required=True, metavar="PDF",
        help="Path to the input PDF file.",
    )
    gio.add_argument(
        "-o", "--output", metavar="MD",
        help="Output Markdown path.  Default: <input>.md alongside the PDF.",
    )
    gio.add_argument(
        "--out-dir", metavar="DIR",
        help="Directory for intermediate page images and results.  "
             "Default: same directory as the output Markdown file.",
    )
    gio.add_argument(
        "--json-out", metavar="JSON",
        help="Also write a JSON metadata sidecar to this path.",
    )

    # -- Model --
    gmod = p.add_argument_group("model selection")
    gmod.add_argument(
        "--model-id", default=DEFAULT_MODEL_ID, metavar="ID",
        help="HuggingFace model id (default: %(default)s).  "
             "Supported: " + ", ".join(_MODELS.keys()),
    )
    gmod.add_argument(
        "--model-path", metavar="DIR",
        help="Explicit path to a locally-stored model directory.  "
             "Overrides --models-dir lookup.",
    )
    gmod.add_argument(
        "--models-dir", default=DEFAULT_MODELS_DIR, metavar="DIR",
        help="Base directory for downloaded models (default: %(default)s).",
    )

    # -- Download / repo --
    gdl = p.add_argument_group("download & repository")
    gdl.add_argument(
        "--allow-download", action="store_true",
        help="If the model is not found locally, download it.  "
             "Clones the official GitHub repo and pulls weights via "
             "huggingface_hub.snapshot_download into --models-dir.",
    )
    gdl.add_argument(
        "--repo-cache-dir", default=DEFAULT_REPO_CACHE, metavar="DIR",
        help="Where to clone the official GitHub repo (default: %(default)s).",
    )

    # -- Inference --
    ginf = p.add_argument_group("inference")
    ginf.add_argument(
        "--device", choices=["auto", "cpu", "cuda"], default="auto",
        help="Device for inference (default: auto → cuda if available).",
    )
    ginf.add_argument(
        "--dpi", type=int, default=DEFAULT_DPI, metavar="N",
        help="DPI for PDF page rasterisation (default: %(default)s).",
    )
    ginf.add_argument(
        "--base-size", type=int, default=DEFAULT_BASE_SIZE, metavar="N",
        help="base_size passed to model.infer() (default: %(default)s).",
    )
    ginf.add_argument(
        "--prompt", choices=["document", "free"], default="document",
        help="Prompt mode: 'document' (markdown with layout) or "
             "'free' (plain OCR).  Default: document.",
    )
    ginf.add_argument(
        "--keep-images", action="store_true",
        help="Keep intermediate per-page PNG images after conversion.",
    )

    return p


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def _safe_dir_name(model_id: str) -> str:
    return model_id.replace("/", "__")


def _default_model_path(model_id: str, models_dir: str) -> Path:
    return Path(models_dir).expanduser().resolve() / _safe_dir_name(model_id)


def resolve_local_model(
    model_path: str | None,
    model_id: str,
    models_dir: str,
) -> tuple[Path | None, list[str]]:
    """Lazy local lookup: return (path, searched_locations)."""
    looked: list[str] = []

    # 1. Explicit --model-path
    if model_path:
        c = Path(model_path).expanduser().resolve()
        looked.append(str(c))
        if c.is_dir():
            return c, looked

    # 2. Environment variable
    env = os.getenv("PDF2MD_DEEPSEEK_MODEL")
    if env:
        c = Path(env).expanduser().resolve()
        looked.append(str(c))
        if c.is_dir():
            return c, looked

    # 3. Convention: <models_dir>/<safe_name>
    c = _default_model_path(model_id, models_dir)
    looked.append(str(c))
    if c.is_dir():
        return c, looked

    return None, looked


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------
def _clone_or_pull_repo(repo_url: str, cache_dir: str) -> Path:
    """Clone (or update) the official GitHub repo."""
    cache = Path(cache_dir).expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    repo_dir = cache / repo_name

    if (repo_dir / ".git").is_dir():
        print(f"[repo] Updating {repo_dir} …")
        subprocess.run(
            ["git", "-C", str(repo_dir), "pull", "--ff-only"],
            check=True,
        )
    else:
        print(f"[repo] Cloning {repo_url} → {repo_dir} …")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
            check=True,
        )
    return repo_dir


def download_model(model_id: str, models_dir: str, repo_cache_dir: str) -> Path:
    """Clone the official repo and download model weights to local dir."""
    preset = _MODELS.get(model_id)
    if preset is None:
        sys.exit(
            f"error: Unknown model id '{model_id}'.  "
            f"Supported: {', '.join(_MODELS.keys())}"
        )

    # 1. Clone / update official GitHub repository
    _clone_or_pull_repo(preset["repo_url"], repo_cache_dir)

    # 2. Pull weights via huggingface_hub (the only host for model weights)
    from huggingface_hub import snapshot_download  # noqa: E402  (lazy)

    local_dir = _default_model_path(model_id, models_dir)
    local_dir.parent.mkdir(parents=True, exist_ok=True)

    print(f"[model] Downloading {model_id} → {local_dir} …")
    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
    )
    print(f"[model] Download complete: {local_dir}")
    return local_dir


# ---------------------------------------------------------------------------
# PDF → page images
# ---------------------------------------------------------------------------
def pdf_to_images(pdf_path: Path, dpi: int = 150):
    """Rasterise every page of a PDF to a PIL Image list."""
    import fitz  # PyMuPDF
    from PIL import Image

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    images = []
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            images.append(
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            )
    finally:
        doc.close()
    return images


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
def load_model(model_dir: str, device: str):
    """Load tokenizer + model from a local directory."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    attn_impl = "flash_attention_2" if device.startswith("cuda") else "eager"

    tokenizer = AutoTokenizer.from_pretrained(
        model_dir, trust_remote_code=True, local_files_only=True,
    )
    model = AutoModel.from_pretrained(
        model_dir,
        trust_remote_code=True,
        use_safetensors=True,
        _attn_implementation=attn_impl,
        local_files_only=True,
    ).eval()

    if device.startswith("cuda"):
        model = model.to(device).to(torch.bfloat16)

    return tokenizer, model


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def run_inference(
    *,
    input_pdf: Path,
    output_md: Path,
    out_dir: Path,
    model_dir: str,
    device: str,
    model_id: str,
    dpi: int,
    base_size: int,
    prompt_mode: str,
    keep_images: bool,
    json_out: Path | None,
) -> int:
    """Full pipeline: rasterise → infer per page → merge → write."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve model-specific parameters
    preset = _MODELS.get(model_id, _MODELS[DEFAULT_MODEL_ID])
    image_size = preset["image_size"]
    extra_infer = preset.get("extra_infer", {})

    prompt = PROMPT_DOCUMENT if prompt_mode == "document" else PROMPT_FREE_OCR

    print(f"[pdf]   Rasterising {input_pdf.name} at {dpi} dpi …")
    pages = pdf_to_images(input_pdf, dpi=dpi)
    print(f"[pdf]   {len(pages)} page(s)")

    print(f"[model] Loading from {model_dir} on {device} …")
    tokenizer, model = load_model(model_dir, device)

    page_md: list[str] = []
    img_files: list[Path] = []
    for i, img in enumerate(pages, start=1):
        img_file = out_dir / f"{input_pdf.stem}_p{i:04d}.png"
        img.save(img_file)
        img_files.append(img_file)

        print(f"[ocr]   Page {i}/{len(pages)} …", end=" ", flush=True)
        md = model.infer(
            tokenizer,
            prompt=prompt,
            image_file=str(img_file),
            output_path=str(out_dir),
            base_size=base_size,
            image_size=image_size,
            crop_mode=True,
            save_results=False,
            **extra_infer,
        )
        page_md.append(f"\n\n<!-- page {i} -->\n{md}")
        print("done")

    merged = "".join(page_md).strip()

    # Write outputs
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(merged, encoding="utf-8")
    print(f"[out]   Markdown → {output_md}")

    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(
                {
                    "backend": "deepseek-ocr",
                    "model": model_id,
                    "model_path": model_dir,
                    "source_pdf": str(input_pdf),
                    "pages": len(pages),
                    "dpi": dpi,
                    "prompt": prompt,
                    "markdown": merged,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[out]   JSON    → {json_out}")

    # Cleanup
    if not keep_images:
        for f in img_files:
            f.unlink(missing_ok=True)

    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    args = build_parser().parse_args()

    # -- Validate input --
    input_pdf = Path(args.input).expanduser().resolve()
    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        print(f"error: Input must be an existing PDF file: {input_pdf}", file=sys.stderr)
        return 1

    # -- Resolve device --
    if args.device == "auto":
        try:
            import torch
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    else:
        device = args.device if args.device != "cuda" else "cuda:0"

    # -- Resolve model path (lazy, no network) --
    model_dir, looked = resolve_local_model(
        args.model_path, args.model_id, args.models_dir,
    )

    if model_dir is None:
        if not args.allow_download:
            looked_fmt = "\n".join(f"  • {p}" for p in looked)
            print(
                f"error: DeepSeek model not found locally.\n"
                f"Searched:\n{looked_fmt}\n\n"
                f"Options:\n"
                f"  1. Re-run with --allow-download to clone the official repo\n"
                f"     and download model weights (~6 GB for OCR-2).\n"
                f"  2. Point to an existing checkout with --model-path /path/to/model\n"
                f"  3. Set the env var PDF2MD_DEEPSEEK_MODEL=/path/to/model",
                file=sys.stderr,
            )
            return 1

        try:
            model_dir = download_model(
                args.model_id, args.models_dir, args.repo_cache_dir,
            )
        except Exception as e:
            print(f"error: Download failed: {e}", file=sys.stderr)
            return 1

    # -- Resolve output paths --
    output_md = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_pdf.with_suffix(".md")
    )
    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else output_md.parent
    )
    json_out = Path(args.json_out).expanduser().resolve() if args.json_out else None

    # -- Run --
    try:
        return run_inference(
            input_pdf=input_pdf,
            output_md=output_md,
            out_dir=out_dir,
            model_dir=str(model_dir),
            device=device,
            model_id=args.model_id,
            dpi=args.dpi,
            base_size=args.base_size,
            prompt_mode=args.prompt,
            keep_images=args.keep_images,
            json_out=json_out,
        )
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
