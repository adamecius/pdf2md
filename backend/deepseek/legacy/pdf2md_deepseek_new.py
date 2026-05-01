#!/usr/bin/env python3
"""pdfmd_deepseek.py

DeepSeek-OCR-2 PDF -> Markdown + JSON, local-model-first.

This is the main script. It does not call another pdf_to_md_json.py.

Model resolution order:
1. --model-path
2. PDF2MD_DEEPSEEK_MODEL
3. .local_models/deepseek/deepseek-ai__DeepSeek-OCR-2

If the model is missing, the script exits lazily and tells the user to call
with --allow-download.

Download mode:
- Uses git + git-lfs.
- Does not import huggingface_hub.
- Downloads from the official DeepSeek-OCR-2 model repository URL configured by
  --model-git-url.

Important:
The official GitHub repository contains the code and examples.
The official model repository contains the weights. DeepSeek's own README links
to the model repository for model download.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz
import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer


DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-OCR-2"
DEFAULT_MODELS_DIR = ".local_models/deepseek"

DEFAULT_REPO_URL = "https://github.com/deepseek-ai/DeepSeek-OCR-2.git"
DEFAULT_REPO_CACHE_DIR = "backend/deepseek/.cache"
DEFAULT_REPO_DIRNAME = "DeepSeek-OCR-2"

# This is the official model repository URL for the model weights.
# It is not using the huggingface_hub Python package.
DEFAULT_MODEL_GIT_URL = "https://huggingface.co/deepseek-ai/DeepSeek-OCR-2"

PROMPT_MARKDOWN = "<image>\n<|grounding|>Convert the document to markdown. "
PROMPT_FREE_OCR = "<image>\nFree OCR. "


@dataclass(frozen=True)
class RunConfig:
    backend: str
    model_path: str
    model_id: str
    model_git_url: str
    repo_url: str
    repo_dir: str | None
    source_pdf: str
    output_dir: str
    output_markdown: str
    output_json: str
    lang: str
    device: str
    dtype: str
    prompt: str
    dpi: int
    base_size: int
    image_size: int
    crop_mode: bool
    pages: int


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Convert PDF to Markdown with DeepSeek-OCR-2. "
            "Local model first; optional git-lfs download into .local_models."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Original pdfmd_deepseek.py interface.
    p.add_argument("-i", "--input", required=True, help="Input PDF path.")
    p.add_argument("-o", "--output", help="Final Markdown output path. Defaults to <input>.md.")
    p.add_argument("--json-out", help="Final JSON output path. Defaults to Markdown path with .json suffix.")
    p.add_argument("--out-dir", help="Working/output directory. Defaults to Markdown output parent.")
    p.add_argument("--lang", default="en", help="Language metadata. DeepSeek prompt itself is language agnostic.")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--model-path", help="Explicit local model directory.")
    p.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    p.add_argument("--models-dir", default=DEFAULT_MODELS_DIR)
    p.add_argument(
        "--allow-download",
        action="store_true",
        help="Download the model once with git/git-lfs into --models-dir if no local model is found.",
    )
    p.add_argument(
        "--api",
        action="store_true",
        help="Reserved for compatibility with the old wrapper. Not implemented in this local runner.",
    )

    # Official repository/code options.
    p.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Official DeepSeek-OCR-2 GitHub code repository.")
    p.add_argument("--repo-cache-dir", default=DEFAULT_REPO_CACHE_DIR)
    p.add_argument("--skip-repo", action="store_true", help="Do not clone/update the GitHub code repository.")
    p.add_argument("--update-repo", action="store_true", help="git pull --ff-only if the code repository exists.")

    # Model repository options.
    p.add_argument(
        "--model-git-url",
        default=DEFAULT_MODEL_GIT_URL,
        help="Official model repository URL used by git-lfs download.",
    )
    p.add_argument("--update-model", action="store_true", help="git pull and git lfs pull if local model repo exists.")

    # OCR/inference options.
    p.add_argument("--dpi", type=int, default=150, help="PDF rendering DPI.")
    p.add_argument("--base-size", type=int, default=1024)
    p.add_argument("--image-size", type=int, default=768)
    p.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="auto")

    crop_group = p.add_mutually_exclusive_group()
    crop_group.add_argument("--crop-mode", dest="crop_mode", action="store_true", default=True)
    crop_group.add_argument("--no-crop-mode", dest="crop_mode", action="store_false")

    prompt_group = p.add_mutually_exclusive_group()
    prompt_group.add_argument("--markdown-prompt", dest="prompt_mode", action="store_const", const="markdown", default="markdown")
    prompt_group.add_argument("--free-ocr-prompt", dest="prompt_mode", action="store_const", const="free_ocr")
    p.add_argument("--prompt", help="Override the prompt completely.")

    p.add_argument("--save-page-images", action="store_true", help="Keep rendered page PNG files.")
    p.add_argument("--save-model-results", action="store_true", help="Let model.infer save its own artefacts.")
    p.add_argument(
        "--no-require-flash-attn",
        dest="require_flash_attn",
        action="store_false",
        default=True,
        help="Skip flash-attn import check. Useful only for CPU/eager debugging.",
    )

    return p


def run_checked(cmd: list[str], cwd: Path | None = None) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def run_capture(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd), flush=True)
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd, output=completed.stdout)
    return completed


def safe_model_dir_name(model_id: str) -> str:
    return model_id.replace("/", "__")


def default_model_path(model_id: str, models_dir: str) -> Path:
    return Path(models_dir).expanduser().resolve() / safe_model_dir_name(model_id)


def looks_like_model_dir(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False

    has_config = (path / "config.json").exists()
    has_tokenizer = (
        (path / "tokenizer.json").exists()
        or (path / "tokenizer_config.json").exists()
    )
    has_weights = (
        (path / "model.safetensors.index.json").exists()
        or any(path.glob("*.safetensors"))
        or any(path.glob("pytorch_model*.bin"))
    )

    return has_config and has_tokenizer and has_weights


def resolve_local_model_path(
    model_path: str | None,
    model_id: str,
    models_dir: str,
) -> tuple[Path | None, list[str]]:
    looked: list[str] = []

    if model_path:
        candidate = Path(model_path).expanduser().resolve()
        looked.append(str(candidate))
        if looks_like_model_dir(candidate):
            return candidate, looked

    env_path = os.getenv("PDF2MD_DEEPSEEK_MODEL")
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        looked.append(str(candidate))
        if looks_like_model_dir(candidate):
            return candidate, looked

    candidate = default_model_path(model_id=model_id, models_dir=models_dir)
    looked.append(str(candidate))
    if looks_like_model_dir(candidate):
        return candidate, looked

    return None, looked


def _missing_model_message(looked: list[str]) -> str:
    looked_lines = "\n".join(f"  - {p}" for p in looked)
    return (
        "error: Missing local DeepSeek-OCR-2 model.\n"
        f"Looked in:\n{looked_lines}\n"
        "Provide an explicit local model path with:\n"
        "  --model-path /path/to/model\n"
        "or set:\n"
        "  PDF2MD_DEEPSEEK_MODEL=/path/to/model\n\n"
        "To download once into .local_models with git/git-lfs, call again with:\n"
        "  --allow-download\n"
    )


def explicit_download_model_with_git(
    *,
    model_id: str,
    models_dir: str,
    model_git_url: str,
    update: bool,
) -> Path:
    """Download model with git-lfs, not huggingface_hub."""
    if shutil.which("git") is None:
        raise RuntimeError("git is required for --allow-download.")

    if shutil.which("git-lfs") is None and shutil.which("git-lfs.exe") is None:
        raise RuntimeError(
            "git-lfs is required for --allow-download because the model weights are large files. "
            "Install git-lfs, then run: git lfs install"
        )

    local_dir = default_model_path(model_id=model_id, models_dir=models_dir)
    local_dir.parent.mkdir(parents=True, exist_ok=True)

    if not (local_dir / ".git").exists():
        run_checked(["git", "lfs", "install"])
        run_checked(["git", "clone", model_git_url, str(local_dir)])
    else:
        if update:
            run_checked(["git", "-C", str(local_dir), "pull", "--ff-only"])
            run_checked(["git", "-C", str(local_dir), "lfs", "pull"])

    if not looks_like_model_dir(local_dir):
        raise RuntimeError(
            f"Downloaded model directory does not look complete: {local_dir}. "
            "Most likely git-lfs did not pull the safetensors weights."
        )

    return local_dir


def ensure_repo(
    repo_url: str,
    repo_cache_dir: Path,
    update: bool,
    skip: bool,
) -> Path | None:
    """Clone the official GitHub code repository.

    This is code/reference only. The weights are resolved through model_path.
    """
    if skip:
        return None

    if shutil.which("git") is None:
        raise RuntimeError("git is required to clone the official GitHub repository.")

    repo_cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = repo_cache_dir / DEFAULT_REPO_DIRNAME

    if not (repo_dir / ".git").exists():
        run_checked(["git", "clone", repo_url, str(repo_dir)])
    elif update:
        run_checked(["git", "-C", str(repo_dir), "pull", "--ff-only"])

    return repo_dir


def pdf_to_images(pdf_path: Path, dpi: int = 150) -> list[Image.Image]:
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    images: list[Image.Image] = []

    try:
        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    finally:
        doc.close()

    return images


def select_device(device_arg: str) -> str:
    if device_arg == "auto":
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    if device_arg == "cuda":
        return "cuda:0"
    return "cpu"


def select_torch_dtype(device: str, dtype_arg: str) -> torch.dtype:
    if dtype_arg == "auto":
        return torch.bfloat16 if device.startswith("cuda") else torch.float32
    if dtype_arg == "bf16":
        return torch.bfloat16
    if dtype_arg == "fp16":
        return torch.float16
    if dtype_arg == "fp32":
        return torch.float32
    raise ValueError(f"Unsupported dtype: {dtype_arg}")


def validate_runtime(device: str, require_flash_attn: bool) -> None:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Torch: {torch.__version__}")
    print(f"Torch CUDA build: {torch.version.cuda}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested, but torch.cuda.is_available() is False.")
        print(f"CUDA device: {torch.cuda.get_device_name(torch.device(device).index or 0)}")

        if require_flash_attn:
            try:
                import flash_attn  # noqa: F401
            except Exception as exc:
                raise RuntimeError(
                    "flash-attn is required for CUDA + flash_attention_2 inference. "
                    "Install the corrected DeepSeek-OCR-2 environment first, or pass "
                    "--no-require-flash-attn only for CPU/debugging."
                ) from exc


def load_model(
    model_path: Path,
    device: str,
    dtype_arg: str,
) -> tuple[Any, Any, torch.dtype]:
    attn_impl = "flash_attention_2" if device.startswith("cuda") else "eager"
    torch_dtype = select_torch_dtype(device, dtype_arg)

    tokenizer = AutoTokenizer.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        local_files_only=True,
    )

    model = AutoModel.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        use_safetensors=True,
        _attn_implementation=attn_impl,
        local_files_only=True,
    ).eval()

    if device.startswith("cuda"):
        model = model.to(device).to(torch_dtype)
    else:
        model = model.to(device)

    return tokenizer, model, torch_dtype


def infer_page(
    model: Any,
    tokenizer: Any,
    image_file: Path,
    output_dir: Path,
    prompt: str,
    base_size: int,
    image_size: int,
    crop_mode: bool,
    save_model_results: bool,
) -> str:
    result = model.infer(
        tokenizer,
        prompt=prompt,
        image_file=str(image_file),
        output_path=str(output_dir),
        base_size=base_size,
        image_size=image_size,
        crop_mode=crop_mode,
        save_results=save_model_results,
    )
    return str(result)


def run(
    input_pdf: Path,
    output_dir: Path,
    model_path: Path,
    model_id: str,
    model_git_url: str,
    repo_url: str,
    repo_dir: Path | None,
    lang: str,
    device: str,
    dtype_arg: str,
    prompt: str,
    dpi: int,
    base_size: int,
    image_size: int,
    crop_mode: bool,
    save_page_images: bool,
    save_model_results: bool,
    require_flash_attn: bool,
    final_md_path: Path,
    final_json_path: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = output_dir / f"{input_pdf.stem}_pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    validate_runtime(device=device, require_flash_attn=require_flash_attn)

    pages = pdf_to_images(input_pdf, dpi=dpi)
    if not pages:
        raise RuntimeError(f"No pages rendered from PDF: {input_pdf}")

    tokenizer, model, torch_dtype = load_model(
        model_path=model_path,
        device=device,
        dtype_arg=dtype_arg,
    )

    page_md: list[str] = []
    page_records: list[dict[str, Any]] = []

    for i, img in enumerate(pages, start=1):
        img_file = pages_dir / f"{input_pdf.stem}_p{i:04d}.png"
        img.save(img_file)

        print(f"[{i}/{len(pages)}] OCR page: {img_file}", flush=True)

        md = infer_page(
            model=model,
            tokenizer=tokenizer,
            image_file=img_file,
            output_dir=output_dir,
            prompt=prompt,
            base_size=base_size,
            image_size=image_size,
            crop_mode=crop_mode,
            save_model_results=save_model_results,
        )

        page_md.append(f"\n\n<!-- page {i} -->\n{md}")
        page_records.append(
            {
                "page": i,
                "image_file": str(img_file),
                "markdown": md,
            }
        )

        if not save_page_images:
            try:
                img_file.unlink()
            except OSError:
                pass

    if not save_page_images:
        try:
            pages_dir.rmdir()
        except OSError:
            pass

    merged = "".join(page_md).strip()

    config = RunConfig(
        backend="deepseek-ocr-2-transformers-local",
        model_path=str(model_path),
        model_id=model_id,
        model_git_url=model_git_url,
        repo_url=repo_url,
        repo_dir=str(repo_dir) if repo_dir else None,
        source_pdf=str(input_pdf),
        output_dir=str(output_dir),
        output_markdown=str(final_md_path),
        output_json=str(final_json_path),
        lang=lang,
        device=device,
        dtype=str(torch_dtype).replace("torch.", ""),
        prompt=prompt,
        dpi=dpi,
        base_size=base_size,
        image_size=image_size,
        crop_mode=crop_mode,
        pages=len(pages),
    )

    final_md_path.parent.mkdir(parents=True, exist_ok=True)
    final_json_path.parent.mkdir(parents=True, exist_ok=True)

    final_md_path.write_text(merged + "\n", encoding="utf-8")
    final_json_path.write_text(
        json.dumps(
            {
                "config": asdict(config),
                "markdown": merged,
                "page_records": page_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return final_md_path, final_json_path


def main() -> int:
    a = parser().parse_args()

    ip = Path(a.input).expanduser().resolve()
    if not ip.exists() or ip.suffix.lower() != ".pdf":
        print(f"error: Input must be an existing PDF file: {ip}", file=sys.stderr)
        return 1

    if a.api:
        print(
            "error: API mode is reserved for compatibility and is not implemented in this local runner.",
            file=sys.stderr,
        )
        return 1

    model_dir, looked = resolve_local_model_path(
        model_path=a.model_path,
        model_id=a.model_id,
        models_dir=a.models_dir,
    )

    if model_dir is None and not a.allow_download:
        print(_missing_model_message(looked), file=sys.stderr)
        return 1

    if model_dir is None and a.allow_download:
        try:
            model_dir = explicit_download_model_with_git(
                model_id=a.model_id,
                models_dir=a.models_dir,
                model_git_url=a.model_git_url,
                update=a.update_model,
            )
        except Exception as exc:
            print(f"error: Failed explicit model download: {exc}", file=sys.stderr)
            return 1

    assert model_dir is not None

    try:
        repo_dir = ensure_repo(
            repo_url=a.repo_url,
            repo_cache_dir=Path(a.repo_cache_dir).expanduser().resolve(),
            update=a.update_repo,
            skip=a.skip_repo,
        )
        if repo_dir:
            print(f"Using DeepSeek-OCR-2 GitHub repo at: {repo_dir}")
    except Exception as exc:
        print(f"warning: Could not prepare official GitHub repo: {exc}", file=sys.stderr)
        repo_dir = None

    out_md = Path(a.output).expanduser().resolve() if a.output else ip.with_suffix(".md")
    out_json = Path(a.json_out).expanduser().resolve() if a.json_out else out_md.with_suffix(".json")
    out_dir = Path(a.out_dir).expanduser().resolve() if a.out_dir else out_md.parent

    device = select_device(a.device)

    if a.prompt is not None:
        prompt = a.prompt
    elif a.prompt_mode == "free_ocr":
        prompt = PROMPT_FREE_OCR
    else:
        prompt = PROMPT_MARKDOWN

    try:
        md_path, json_path = run(
            input_pdf=ip,
            output_dir=out_dir,
            model_path=model_dir,
            model_id=a.model_id,
            model_git_url=a.model_git_url,
            repo_url=a.repo_url,
            repo_dir=repo_dir,
            lang=a.lang,
            device=device,
            dtype_arg=a.dtype,
            prompt=prompt,
            dpi=a.dpi,
            base_size=a.base_size,
            image_size=a.image_size,
            crop_mode=a.crop_mode,
            save_page_images=a.save_page_images,
            save_model_results=a.save_model_results,
            require_flash_attn=a.require_flash_attn,
            final_md_path=out_md,
            final_json_path=out_json,
        )

        print("Conversion complete")
        print(f"Markdown: {md_path}")
        print(f"JSON: {json_path}")
        return 0

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
