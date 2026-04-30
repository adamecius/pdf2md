#!/usr/bin/env python3
"""DeepSeek-OCR-2 PDF -> Markdown + JSON using the vLLM backend.

This runner is designed for the corrected DeepSeek-OCR-2 environment:

- Model: deepseek-ai/DeepSeek-OCR-2
- Repo:  https://github.com/deepseek-ai/DeepSeek-OCR-2
- Backend: vLLM, using the OCR-2 repository model plugin
- Expected environment: CUDA 11.8 + Torch 2.6.0 + vLLM 0.8.5+cu118

Unlike the official OCR-2 vLLM scripts, this script does not require editing
DeepSeek-OCR2-vllm/config.py. It exposes the important settings as CLI flags.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageDraw, ImageFont


DEFAULT_REPO_URL = "https://github.com/deepseek-ai/DeepSeek-OCR-2"
DEFAULT_REPO_DIRNAME = "DeepSeek-OCR-2"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-OCR-2"

PROMPT_MARKDOWN = "<image>\n<|grounding|>Convert the document to markdown. "
PROMPT_FREE_OCR = "<image>\nFree OCR. "
EOS_TOKEN = "<｜end▁of▁sentence｜>"


@dataclass(frozen=True)
class RunConfig:
    backend: str
    model: str
    repo_url: str
    repo_dir: str
    vllm_dir: str
    source_pdf: str
    output_dir: str
    prompt: str
    dpi: int
    crop_mode: bool
    max_tokens: int
    max_model_len: int
    max_concurrency: int
    num_workers: int
    tensor_parallel_size: int
    gpu_memory_utilization: float
    ngram_size: int
    ngram_window_size: int
    skip_repeat: bool
    pages_total: int
    pages_written: int


def run_checked(cmd: list[str], cwd: Path | None = None) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def ensure_repo(repo_url: str, repo_cache_dir: Path, repo_dirname: str = DEFAULT_REPO_DIRNAME, update: bool = False) -> Path:
    """Clone DeepSeek-OCR-2 if missing.

    Updating is optional because a reproducible OCR pipeline should not
    silently change repository code on every run.
    """
    repo_cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = repo_cache_dir / repo_dirname

    if not (repo_dir / ".git").exists():
        run_checked(["git", "clone", repo_url, str(repo_dir)])
    elif update:
        run_checked(["git", "-C", str(repo_dir), "pull", "--ff-only"])

    return repo_dir


def find_vllm_dir(repo_dir: Path) -> Path:
    vllm_dir = repo_dir / "DeepSeek-OCR2-master" / "DeepSeek-OCR2-vllm"
    if not vllm_dir.exists():
        raise FileNotFoundError(
            f"Could not find OCR-2 vLLM directory: {vllm_dir}. "
            "Check that the repository is DeepSeek-OCR-2."
        )
    return vllm_dir


def configure_cuda_and_vllm_runtime(cuda_visible_devices: str | None, ptxas_path: str | None) -> None:
    """Configure runtime variables before importing vLLM.

    The official OCR-2 vLLM scripts hard-code /usr/local/cuda-11.8/bin/ptxas.
    In the corrected Conda setup, CUDA 11.8 usually lives inside CONDA_PREFIX,
    so we prefer $CUDA_HOME/bin/ptxas or $CONDA_PREFIX/bin/ptxas.
    """
    os.environ.setdefault("VLLM_USE_V1", "0")

    if cuda_visible_devices is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices

    candidate_ptxas: list[Path] = []

    if ptxas_path:
        candidate_ptxas.append(Path(ptxas_path).expanduser())

    cuda_home = os.environ.get("CUDA_HOME")
    if cuda_home:
        candidate_ptxas.append(Path(cuda_home) / "bin" / "ptxas")

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidate_ptxas.append(Path(conda_prefix) / "bin" / "ptxas")

    candidate_ptxas.append(Path("/usr/local/cuda-11.8/bin/ptxas"))

    for candidate in candidate_ptxas:
        if candidate.exists():
            os.environ["TRITON_PTXAS_PATH"] = str(candidate)
            break


def import_vllm_stack(vllm_dir: Path) -> dict[str, Any]:
    """Import vLLM and OCR-2 repository plugin modules after sys.path setup."""
    sys.path.insert(0, str(vllm_dir))

    import torch
    from vllm import LLM, SamplingParams
    from vllm.model_executor.models.registry import ModelRegistry

    from deepseek_ocr2 import DeepseekOCR2ForCausalLM
    from process.image_process import DeepseekOCR2Processor
    from process.ngram_norepeat import NoRepeatNGramLogitsProcessor

    try:
        ModelRegistry.register_model("DeepseekOCR2ForCausalLM", DeepseekOCR2ForCausalLM)
    except Exception:
        # Registration can fail if the model was already registered in the same process.
        pass

    return {
        "torch": torch,
        "LLM": LLM,
        "SamplingParams": SamplingParams,
        "DeepseekOCR2Processor": DeepseekOCR2Processor,
        "NoRepeatNGramLogitsProcessor": NoRepeatNGramLogitsProcessor,
    }


def validate_environment(torch_module: Any) -> None:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Torch: {torch_module.__version__}")
    print(f"Torch CUDA build: {torch_module.version.cuda}")
    print(f"CUDA available: {torch_module.cuda.is_available()}")
    print(f"CUDA_HOME: {os.environ.get('CUDA_HOME')}")
    print(f"TRITON_PTXAS_PATH: {os.environ.get('TRITON_PTXAS_PATH')}")
    print(f"VLLM_USE_V1: {os.environ.get('VLLM_USE_V1')}")

    if not torch_module.cuda.is_available():
        raise RuntimeError("vLLM OCR requires CUDA, but torch.cuda.is_available() is False.")


def pdf_to_images_high_quality(pdf_path: Path, dpi: int = 144) -> list[Image.Image]:
    """Render a PDF into RGB PIL images."""
    images: list[Image.Image] = []
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    try:
        for page_index in range(doc.page_count):
            page = doc[page_index]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            images.append(image)
    finally:
        doc.close()

    return images


def tqdm_or_plain(iterable: Any, total: int | None = None, desc: str | None = None) -> Any:
    try:
        from tqdm import tqdm

        return tqdm(iterable, total=total, desc=desc)
    except Exception:
        return iterable


def build_batch_inputs(
    images: list[Image.Image],
    prompt: str,
    crop_mode: bool,
    num_workers: int,
    processor_cls: Any,
) -> list[dict[str, Any]]:
    def process_one(image: Image.Image) -> dict[str, Any]:
        processor = processor_cls()
        image_features = processor.tokenize_with_images(
            images=[image],
            bos=True,
            eos=True,
            cropping=crop_mode,
        )
        return {
            "prompt": prompt,
            "multi_modal_data": {"image": image_features},
        }

    workers = max(1, int(num_workers))
    if workers == 1:
        return [process_one(image) for image in tqdm_or_plain(images, total=len(images), desc="Pre-processing pages")]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(
            tqdm_or_plain(
                executor.map(process_one, images),
                total=len(images),
                desc="Pre-processing pages",
            )
        )


def make_llm(
    LLM: Any,
    model_name: str,
    max_model_len: int,
    max_concurrency: int,
    tensor_parallel_size: int,
    gpu_memory_utilization: float,
    swap_space: int,
    enforce_eager: bool,
) -> Any:
    return LLM(
        model=model_name,
        hf_overrides={"architectures": ["DeepseekOCR2ForCausalLM"]},
        block_size=256,
        enforce_eager=enforce_eager,
        trust_remote_code=True,
        max_model_len=max_model_len,
        swap_space=swap_space,
        max_num_seqs=max_concurrency,
        tensor_parallel_size=tensor_parallel_size,
        gpu_memory_utilization=gpu_memory_utilization,
        disable_mm_preprocessor_cache=True,
    )


def make_sampling_params(
    SamplingParams: Any,
    NoRepeatNGramLogitsProcessor: Any,
    max_tokens: int,
    ngram_size: int,
    ngram_window_size: int,
) -> Any:
    logits_processors = [
        NoRepeatNGramLogitsProcessor(
            ngram_size=ngram_size,
            window_size=ngram_window_size,
            whitelist_token_ids={128821, 128822},
        )
    ]

    return SamplingParams(
        temperature=0.0,
        max_tokens=max_tokens,
        logits_processors=logits_processors,
        skip_special_tokens=False,
        include_stop_str_in_output=True,
    )


def parse_refs(text: str) -> tuple[list[tuple[str, str, str]], list[str], list[str]]:
    pattern = r"(<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>)"
    matches = re.findall(pattern, text, re.DOTALL)
    image_refs: list[str] = []
    other_refs: list[str] = []

    for full_match, label, _coords in matches:
        if label == "image":
            image_refs.append(full_match)
        else:
            other_refs.append(full_match)

    return matches, image_refs, other_refs


def parse_ref_coordinates(match: tuple[str, str, str]) -> tuple[str, list[list[int]]] | None:
    _full_match, label, coords_text = match
    try:
        coords = ast.literal_eval(coords_text)
    except Exception:
        return None

    if not isinstance(coords, list):
        return None

    return label, coords


def crop_image_refs(
    page_image: Image.Image,
    matches: list[tuple[str, str, str]],
    page_index: int,
    images_dir: Path,
) -> dict[str, str]:
    replacements: dict[str, str] = {}
    width, height = page_image.size
    image_idx = 0

    for match in matches:
        full_match, label, _coords_text = match
        if label != "image":
            continue

        parsed = parse_ref_coordinates(match)
        if parsed is None:
            continue

        _label, boxes = parsed
        for box in boxes:
            if not isinstance(box, list) or len(box) != 4:
                continue

            x1, y1, x2, y2 = box
            left = int(x1 / 999 * width)
            top = int(y1 / 999 * height)
            right = int(x2 / 999 * width)
            bottom = int(y2 / 999 * height)

            left = max(0, min(left, width))
            right = max(0, min(right, width))
            top = max(0, min(top, height))
            bottom = max(0, min(bottom, height))

            if right <= left or bottom <= top:
                continue

            crop_path = images_dir / f"{page_index}_{image_idx}.jpg"
            page_image.crop((left, top, right, bottom)).save(crop_path)
            replacements[full_match] = f"![](images/{crop_path.name})\n"
            image_idx += 1

    return replacements


def clean_output_text(
    raw_text: str,
    page_image: Image.Image,
    page_index: int,
    images_dir: Path,
    extract_images: bool,
) -> tuple[str, dict[str, Any]]:
    matches, image_refs, other_refs = parse_refs(raw_text)
    cleaned = raw_text

    if extract_images:
        replacements = crop_image_refs(
            page_image=page_image,
            matches=matches,
            page_index=page_index,
            images_dir=images_dir,
        )
        for full_match, replacement in replacements.items():
            cleaned = cleaned.replace(full_match, replacement)
    else:
        for full_match in image_refs:
            cleaned = cleaned.replace(full_match, "")

    for full_match in other_refs:
        cleaned = cleaned.replace(full_match, "")

    cleaned = (
        cleaned.replace("\\coloneqq", ":=")
        .replace("\\eqqcolon", "=:")
        .replace("\n\n\n\n", "\n\n")
        .replace("\n\n\n", "\n\n")
        .strip()
    )

    return cleaned, {
        "ref_count": len(matches),
        "image_ref_count": len(image_refs),
        "other_ref_count": len(other_refs),
    }


def draw_layout_boxes(page_image: Image.Image, matches: list[tuple[str, str, str]]) -> Image.Image:
    width, height = page_image.size
    img = page_image.copy()
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    palette = [
        "red",
        "blue",
        "green",
        "purple",
        "orange",
        "brown",
        "magenta",
        "cyan",
    ]

    for idx, match in enumerate(matches):
        parsed = parse_ref_coordinates(match)
        if parsed is None:
            continue

        label, boxes = parsed
        colour = palette[idx % len(palette)]

        for box in boxes:
            if not isinstance(box, list) or len(box) != 4:
                continue

            x1, y1, x2, y2 = box
            left = int(x1 / 999 * width)
            top = int(y1 / 999 * height)
            right = int(x2 / 999 * width)
            bottom = int(y2 / 999 * height)

            draw.rectangle([left, top, right, bottom], outline=colour, width=2)
            draw.text((left, max(0, top - 12)), label, fill=colour, font=font)

    return img


def save_layout_pdf(layout_images: list[Image.Image], output_path: Path) -> None:
    if not layout_images:
        return

    try:
        import img2pdf

        image_bytes: list[bytes] = []
        import io

        for image in layout_images:
            if image.mode != "RGB":
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=95)
            image_bytes.append(buffer.getvalue())

        output_path.write_bytes(img2pdf.convert(image_bytes))
    except Exception:
        # Fall back to PIL's PDF writer.
        rgb_images = [img.convert("RGB") for img in layout_images]
        first, rest = rgb_images[0], rgb_images[1:]
        first.save(output_path, save_all=True, append_images=rest)


def run(
    input_pdf: Path,
    output_dir: Path,
    model_name: str,
    repo_url: str,
    repo_cache_dir: Path,
    update_repo: bool,
    cuda_visible_devices: str | None,
    ptxas_path: str | None,
    dpi: int,
    crop_mode: bool,
    prompt: str,
    max_tokens: int,
    max_model_len: int,
    max_concurrency: int,
    num_workers: int,
    tensor_parallel_size: int,
    gpu_memory_utilization: float,
    swap_space: int,
    enforce_eager: bool,
    ngram_size: int,
    ngram_window_size: int,
    skip_repeat: bool,
    extract_images: bool,
    annotate_layouts: bool,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    if extract_images:
        images_dir.mkdir(parents=True, exist_ok=True)

    repo_dir = ensure_repo(
        repo_url=repo_url,
        repo_cache_dir=repo_cache_dir,
        repo_dirname=DEFAULT_REPO_DIRNAME,
        update=update_repo,
    )
    vllm_dir = find_vllm_dir(repo_dir)

    configure_cuda_and_vllm_runtime(
        cuda_visible_devices=cuda_visible_devices,
        ptxas_path=ptxas_path,
    )

    stack = import_vllm_stack(vllm_dir)
    validate_environment(stack["torch"])

    print(f"Using DeepSeek-OCR-2 repo at: {repo_dir}")
    print(f"Using OCR-2 vLLM plugin dir: {vllm_dir}")

    print("Loading PDF pages...")
    images = pdf_to_images_high_quality(input_pdf, dpi=dpi)
    if not images:
        raise RuntimeError(f"No pages rendered from PDF: {input_pdf}")

    print(f"Rendered pages: {len(images)}")

    print("Pre-processing pages for OCR-2 vLLM...")
    batch_inputs = build_batch_inputs(
        images=images,
        prompt=prompt,
        crop_mode=crop_mode,
        num_workers=num_workers,
        processor_cls=stack["DeepseekOCR2Processor"],
    )

    print("Loading vLLM model...")
    llm = make_llm(
        LLM=stack["LLM"],
        model_name=model_name,
        max_model_len=max_model_len,
        max_concurrency=max_concurrency,
        tensor_parallel_size=tensor_parallel_size,
        gpu_memory_utilization=gpu_memory_utilization,
        swap_space=swap_space,
        enforce_eager=enforce_eager,
    )

    sampling_params = make_sampling_params(
        SamplingParams=stack["SamplingParams"],
        NoRepeatNGramLogitsProcessor=stack["NoRepeatNGramLogitsProcessor"],
        max_tokens=max_tokens,
        ngram_size=ngram_size,
        ngram_window_size=ngram_window_size,
    )

    print("Running vLLM batch generation...")
    outputs = llm.generate(batch_inputs, sampling_params=sampling_params)

    raw_parts: list[str] = []
    clean_parts: list[str] = []
    page_records: list[dict[str, Any]] = []
    layout_images: list[Image.Image] = []

    written_pages = 0

    for page_index, (output, page_image) in enumerate(zip(outputs, images), start=1):
        raw_text = output.outputs[0].text

        finished_with_eos = EOS_TOKEN in raw_text
        if finished_with_eos:
            raw_text = raw_text.replace(EOS_TOKEN, "")
        elif skip_repeat:
            page_records.append(
                {
                    "page": page_index,
                    "status": "skipped_no_eos",
                    "raw_markdown": raw_text,
                    "markdown": "",
                }
            )
            continue

        matches, _image_refs, _other_refs = parse_refs(raw_text)
        cleaned, ref_stats = clean_output_text(
            raw_text=raw_text,
            page_image=page_image,
            page_index=page_index,
            images_dir=images_dir,
            extract_images=extract_images,
        )

        page_separator = "\n<--- Page Split --->\n"
        raw_parts.append(f"<!-- page {page_index} -->\n{raw_text}\n{page_separator}")
        clean_parts.append(f"<!-- page {page_index} -->\n{cleaned}\n{page_separator}")

        if annotate_layouts:
            layout_images.append(draw_layout_boxes(page_image, matches))

        page_records.append(
            {
                "page": page_index,
                "status": "ok",
                "finished_with_eos": finished_with_eos,
                "raw_markdown": raw_text,
                "markdown": cleaned,
                **ref_stats,
            }
        )
        written_pages += 1

    raw_merged = "\n".join(raw_parts).strip()
    clean_merged = "\n".join(clean_parts).strip()

    md_path = output_dir / f"{input_pdf.stem}.md"
    det_path = output_dir / f"{input_pdf.stem}_det.mmd"
    json_path = output_dir / f"{input_pdf.stem}.json"
    layouts_pdf_path = output_dir / f"{input_pdf.stem}_layouts.pdf"

    md_path.write_text(clean_merged + "\n", encoding="utf-8")
    det_path.write_text(raw_merged + "\n", encoding="utf-8")

    if annotate_layouts:
        save_layout_pdf(layout_images, layouts_pdf_path)

    config = RunConfig(
        backend="deepseek-ocr-2-vllm",
        model=model_name,
        repo_url=repo_url,
        repo_dir=str(repo_dir),
        vllm_dir=str(vllm_dir),
        source_pdf=str(input_pdf),
        output_dir=str(output_dir),
        prompt=prompt,
        dpi=dpi,
        crop_mode=crop_mode,
        max_tokens=max_tokens,
        max_model_len=max_model_len,
        max_concurrency=max_concurrency,
        num_workers=num_workers,
        tensor_parallel_size=tensor_parallel_size,
        gpu_memory_utilization=gpu_memory_utilization,
        ngram_size=ngram_size,
        ngram_window_size=ngram_window_size,
        skip_repeat=skip_repeat,
        pages_total=len(images),
        pages_written=written_pages,
    )

    json_path.write_text(
        json.dumps(
            {
                "config": asdict(config),
                "markdown": clean_merged,
                "raw_markdown": raw_merged,
                "page_records": page_records,
                "outputs": {
                    "markdown": str(md_path),
                    "raw_detections": str(det_path),
                    "layouts_pdf": str(layouts_pdf_path) if annotate_layouts else None,
                    "images_dir": str(images_dir) if extract_images else None,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return md_path, det_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DeepSeek-OCR-2 PDF -> Markdown + JSON using vLLM batch inference"
    )

    parser.add_argument("-i", "--input", required=True, help="Input PDF path")
    parser.add_argument("-o", "--output", default="deepseek_ocr2_vllm_output", help="Output directory")

    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="DeepSeek-OCR-2 GitHub URL")
    parser.add_argument("--repo-cache-dir", default="backend/deepseek/.cache", help="Repository cache directory")
    parser.add_argument("--update-repo", action="store_true", help="Run git pull --ff-only if the repo already exists")

    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help="HF model name or local model path")

    parser.add_argument("--cuda-visible-devices", default="0", help="Value for CUDA_VISIBLE_DEVICES. Use '' to leave unchanged.")
    parser.add_argument("--ptxas-path", default=None, help="Explicit path to CUDA 11.8 ptxas")

    parser.add_argument("--dpi", type=int, default=144, help="PDF render DPI")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--max-model-len", type=int, default=8192)
    parser.add_argument("--max-concurrency", type=int, default=100)
    parser.add_argument("--num-workers", type=int, default=64)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--swap-space", type=int, default=0)

    parser.add_argument("--ngram-size", type=int, default=20)
    parser.add_argument("--ngram-window-size", type=int, default=50)

    crop_group = parser.add_mutually_exclusive_group()
    crop_group.add_argument("--crop-mode", dest="crop_mode", action="store_true", default=True)
    crop_group.add_argument("--no-crop-mode", dest="crop_mode", action="store_false")

    repeat_group = parser.add_mutually_exclusive_group()
    repeat_group.add_argument("--skip-repeat", dest="skip_repeat", action="store_true", default=True)
    repeat_group.add_argument("--no-skip-repeat", dest="skip_repeat", action="store_false")

    parser.add_argument("--enforce-eager", action="store_true", help="Pass enforce_eager=True to vLLM")

    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--markdown-prompt", dest="prompt_mode", action="store_const", const="markdown", default="markdown")
    prompt_group.add_argument("--free-ocr-prompt", dest="prompt_mode", action="store_const", const="free_ocr")
    parser.add_argument("--prompt", default=None, help="Override prompt completely")

    parser.add_argument("--extract-images", action="store_true", help="Crop detected image regions into output/images")
    parser.add_argument("--annotate-layouts", action="store_true", help="Save a PDF with layout boxes")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_pdf = Path(args.input).expanduser().resolve()
    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {input_pdf}")

    if args.prompt is not None:
        prompt = args.prompt
    elif args.prompt_mode == "free_ocr":
        prompt = PROMPT_FREE_OCR
    else:
        prompt = PROMPT_MARKDOWN

    cuda_visible_devices: str | None
    if args.cuda_visible_devices == "":
        cuda_visible_devices = None
    else:
        cuda_visible_devices = args.cuda_visible_devices

    md_path, det_path, json_path = run(
        input_pdf=input_pdf,
        output_dir=Path(args.output).expanduser().resolve(),
        model_name=args.model,
        repo_url=args.repo_url,
        repo_cache_dir=Path(args.repo_cache_dir).expanduser().resolve(),
        update_repo=args.update_repo,
        cuda_visible_devices=cuda_visible_devices,
        ptxas_path=args.ptxas_path,
        dpi=args.dpi,
        crop_mode=args.crop_mode,
        prompt=prompt,
        max_tokens=args.max_tokens,
        max_model_len=args.max_model_len,
        max_concurrency=args.max_concurrency,
        num_workers=args.num_workers,
        tensor_parallel_size=args.tensor_parallel_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        swap_space=args.swap_space,
        enforce_eager=args.enforce_eager,
        ngram_size=args.ngram_size,
        ngram_window_size=args.ngram_window_size,
        skip_repeat=args.skip_repeat,
        extract_images=args.extract_images,
        annotate_layouts=args.annotate_layouts,
    )

    print("Conversion complete")
    print(f"Markdown: {md_path}")
    print(f"Raw detections: {det_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
