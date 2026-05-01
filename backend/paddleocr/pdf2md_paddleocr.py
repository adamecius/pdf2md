#!/usr/bin/env python3
"""pdf2md_paddleocr_fixed.py — Convert PDF to Markdown using PaddleOCR.

Single-file wrapper around the PaddleOCR Python API.

Supported pipelines:
  - PPStructureV3: layout-aware document parsing to Markdown
  - PaddleOCR-VL: vision-language document parsing
  - PP-OCRv5: plain OCR text extraction

This version is defensive against recent PaddleOCR/PaddleX API changes where
Markdown payloads may be returned as MarkdownResult-like objects rather than
plain strings or dictionaries.

Usage:
  pdf2md_paddleocr_fixed.py -i paper.pdf
  pdf2md_paddleocr_fixed.py -i paper.pdf -o out.md
  pdf2md_paddleocr_fixed.py -i paper.pdf -p paddleocr_vl
  pdf2md_paddleocr_fixed.py -i paper.pdf --device cpu
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PIPELINES = [
    "pp_structurev3",   # document parsing -> Markdown
    "paddleocr_vl",     # VLM-based parsing
    "pp_ocrv5",         # plain OCR text extraction
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to Markdown using PaddleOCR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Default: PP-StructureV3 pipeline
  %(prog)s -i paper.pdf

  # Use PaddleOCR-VL
  %(prog)s -i paper.pdf -p paddleocr_vl

  # CPU-only inference
  %(prog)s -i paper.pdf --device cpu

  # Parse only pages 3-7, using 0-based indices
  %(prog)s -i paper.pdf --start 3 --end 7

  # Keep intermediate output
  %(prog)s -i paper.pdf --keep-output --out-dir ./paddle_out

  # Avoid PaddleX model-source connectivity checks
  PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True %(prog)s -i paper.pdf
""",
    )

    # -- I/O --
    gio = parser.add_argument_group("input / output")
    gio.add_argument(
        "-i",
        "--input",
        required=True,
        metavar="PDF",
        help="Path to the input PDF file.",
    )
    gio.add_argument(
        "-o",
        "--output",
        metavar="MD",
        help="Output Markdown path. Default: <input>.md next to the PDF.",
    )
    gio.add_argument(
        "--out-dir",
        metavar="DIR",
        help=(
            "Directory for PaddleOCR intermediate output. "
            "Default: <output_stem>_paddleocr_output next to the output .md."
        ),
    )
    gio.add_argument(
        "--json-out",
        metavar="JSON",
        help="Write a JSON metadata sidecar to this path.",
    )

    # -- Pipeline --
    gpi = parser.add_argument_group("pipeline")
    gpi.add_argument(
        "-p",
        "--pipeline",
        default="pp_structurev3",
        choices=PIPELINES,
        help=(
            "PaddleOCR pipeline to use. Default: %(default)s. "
            "pp_structurev3 = layout-aware document parsing. "
            "paddleocr_vl = VLM-based parsing. "
            "pp_ocrv5 = plain OCR text extraction."
        ),
    )

    # -- Inference --
    ginf = parser.add_argument_group("inference options")
    ginf.add_argument(
        "--device",
        default="gpu:0",
        metavar="DEV",
        help="Inference device. Examples: gpu:0, gpu:1, cpu. Default: %(default)s.",
    )
    ginf.add_argument(
        "--lang",
        default=None,
        metavar="LANG",
        help=(
            "Language hint for PP-OCRv5, for example ch, en, korean, japan. "
            "Ignored by PPStructureV3 and PaddleOCR-VL."
        ),
    )
    ginf.add_argument(
        "--start",
        type=int,
        default=None,
        metavar="N",
        help="Starting page number, 0-based and inclusive.",
    )
    ginf.add_argument(
        "--end",
        type=int,
        default=None,
        metavar="N",
        help="Ending page number, 0-based. Passed through to PaddleOCR as end_page_idx.",
    )

    # -- Behaviour --
    gbh = parser.add_argument_group("behaviour")
    gbh.add_argument(
        "--use-doc-orientation-classify",
        action="store_true",
        help="Enable document orientation classification. Default: off.",
    )
    gbh.add_argument(
        "--use-doc-unwarping",
        action="store_true",
        help="Enable document unwarping. Default: off.",
    )
    gbh.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep the intermediate PaddleOCR output directory.",
    )
    gbh.add_argument(
        "--disable-model-source-check",
        action="store_true",
        help=(
            "Set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True before importing "
            "PaddleOCR. Useful for offline or slow-network environments."
        ),
    )
    gbh.add_argument(
        "--debug-types",
        action="store_true",
        help="Print PaddleOCR result object types to stderr for debugging API changes.",
    )

    return parser


# ---------------------------------------------------------------------------
# Markdown extraction helpers
# ---------------------------------------------------------------------------
def object_to_dict(obj: Any) -> dict[str, Any]:
    """Best-effort conversion of PaddleOCR/PaddleX result-like objects to a dict."""
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    # Some PaddleX result objects behave like mappings.
    try:
        converted = dict(obj)
        if isinstance(converted, dict):
            return converted
    except Exception:
        pass

    # Pydantic-like or dataclass-like APIs.
    for attr in ("model_dump", "dict", "to_dict", "as_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                converted = fn()
                if isinstance(converted, dict):
                    return converted
            except Exception:
                pass

    # Last resort: inspect public attributes only.
    data: dict[str, Any] = {}
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            continue
        data[name] = value
    return data


def first_str_value(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return the first string value found for the provided keys."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            return value
    return None


def first_dict_value(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """Return the first dictionary value found for the provided keys."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def extract_markdown_payload(payload: Any) -> tuple[str, dict[str, Any]]:
    """Extract Markdown text and image objects from PaddleOCR markdown payloads.

    PaddleOCR/PaddleX versions differ here:
      - older examples imply a plain string is returned by concatenate_markdown_pages
      - local page results are usually dict-like with markdown_texts/markdown_images
      - newer builds may return a MarkdownResult-like object

    This helper normalises those shapes into:
      (markdown_text, markdown_images)
    """
    if isinstance(payload, str):
        return payload, {}

    data = object_to_dict(payload)

    text = first_str_value(
        data,
        (
            "markdown_texts",
            "markdown_text",
            "markdown",
            "text",
            "content",
        ),
    )

    images = first_dict_value(
        data,
        (
            "markdown_images",
            "images",
            "imgs",
        ),
    )

    if text is None:
        # Sometimes the interesting payload is nested one level down.
        for nested_key in ("res", "result", "data", "output"):
            nested = data.get(nested_key)
            if nested is None:
                continue
            nested_text, nested_images = extract_markdown_payload(nested)
            if nested_text:
                merged_images = dict(images)
                merged_images.update(nested_images)
                return nested_text, merged_images

    if text is None:
        available_keys = sorted(data.keys()) if isinstance(data, dict) else []
        raise TypeError(
            f"Could not extract Markdown text from {type(payload).__name__}. "
            f"Available keys/attributes: {available_keys}"
        )

    return text, images


def save_markdown_images(markdown_images: dict[str, Any], out_dir: Path) -> int:
    """Save image objects referenced by PaddleOCR Markdown results."""
    saved = 0
    for relative_path, image_obj in markdown_images.items():
        if not relative_path:
            continue

        full_path = out_dir / str(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Typical case: PIL Image-like object.
        save_fn = getattr(image_obj, "save", None)
        if callable(save_fn):
            save_fn(str(full_path))
            saved += 1
            continue

        # Bytes-like fallback.
        if isinstance(image_obj, bytes):
            full_path.write_bytes(image_obj)
            saved += 1
            continue

        # Path-like fallback. Avoid silently failing if the object is actually
        # a source path emitted by the library.
        try:
            source = Path(str(image_obj)).expanduser()
            if source.is_file():
                full_path.write_bytes(source.read_bytes())
                saved += 1
        except Exception:
            pass

    return saved


def safe_save_result(result: Any, out_dir: Path, *, save_markdown: bool = True) -> None:
    """Save PaddleOCR intermediate result files when the object supports it."""
    out_dir.mkdir(parents=True, exist_ok=True)

    save_to_json = getattr(result, "save_to_json", None)
    if callable(save_to_json):
        try:
            save_to_json(save_path=str(out_dir))
        except Exception as exc:
            print(f"[warn] could not save JSON intermediate: {exc}", file=sys.stderr)

    if save_markdown:
        save_to_markdown = getattr(result, "save_to_markdown", None)
        if callable(save_to_markdown):
            try:
                save_to_markdown(save_path=str(out_dir))
            except Exception as exc:
                print(f"[warn] could not save Markdown intermediate: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------
def validate_input(path: str) -> Path:
    pdf = Path(path).expanduser().resolve()
    if not pdf.is_file():
        raise FileNotFoundError(f"Input file does not exist: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a .pdf file, got: {pdf.suffix}")
    return pdf


def validate_page_range(start: int | None, end: int | None) -> None:
    if start is not None and start < 0:
        raise ValueError("--start must be >= 0")
    if end is not None and end < 0:
        raise ValueError("--end must be >= 0")
    if start is not None and end is not None and end < start:
        raise ValueError("--end must be greater than or equal to --start")


def debug_type(label: str, obj: Any, enabled: bool) -> None:
    if not enabled:
        return
    print(f"[debug] {label}: {type(obj)!r}", file=sys.stderr)
    data = object_to_dict(obj)
    if data:
        print(f"[debug] {label} keys: {sorted(data.keys())}", file=sys.stderr)


def build_predict_kwargs(
    input_pdf: Path,
    page_start: int | None,
    page_end: int | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"input": str(input_pdf)}
    if page_start is not None:
        kwargs["start_page_idx"] = page_start
    if page_end is not None:
        kwargs["end_page_idx"] = page_end
    return kwargs


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------
def run_pp_structurev3(
    input_pdf: Path,
    out_dir: Path,
    *,
    device: str,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    page_start: int | None,
    page_end: int | None,
    debug_types: bool,
) -> dict[str, Any]:
    """Run PP-StructureV3 and produce merged Markdown."""
    from paddleocr import PPStructureV3

    pipeline = PPStructureV3(
        device=device,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=False,
    )

    predict_kwargs = build_predict_kwargs(input_pdf, page_start, page_end)

    print(f"[paddleocr] Running PP-StructureV3 on {input_pdf.name} ...", flush=True)
    output = pipeline.predict(**predict_kwargs)

    markdown_list: list[Any] = []
    markdown_images: dict[str, Any] = {}
    page_count = 0

    for res in output:
        page_count += 1
        debug_type(f"pp_structurev3 page result {page_count}", res, debug_types)

        md_payload = getattr(res, "markdown", None)
        debug_type(f"pp_structurev3 page markdown {page_count}", md_payload, debug_types)

        if md_payload is None:
            raise TypeError(f"Page result {page_count} has no .markdown payload")

        markdown_list.append(md_payload)

        _, page_images = extract_markdown_payload(md_payload)
        markdown_images.update(page_images)

        safe_save_result(res, out_dir, save_markdown=True)

    if page_count == 0:
        raise RuntimeError("PaddleOCR returned no pages")

    merged_payload = pipeline.concatenate_markdown_pages(markdown_list)
    debug_type("pp_structurev3 merged markdown", merged_payload, debug_types)

    merged_md, merged_images = extract_markdown_payload(merged_payload)
    markdown_images.update(merged_images)

    images_saved = save_markdown_images(markdown_images, out_dir)

    return {
        "markdown": merged_md,
        "pages": page_count,
        "pipeline": "pp_structurev3",
        "images_saved": images_saved,
    }


def run_paddleocr_vl(
    input_pdf: Path,
    out_dir: Path,
    *,
    device: str,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    page_start: int | None,
    page_end: int | None,
    debug_types: bool,
) -> dict[str, Any]:
    """Run PaddleOCR-VL and produce merged Markdown.

    Recent PaddleOCR-VL examples use restructure_pages for multi-page PDFs.
    This function prefers that path and falls back to direct concatenation if
    the local build exposes a different API.
    """
    from paddleocr import PaddleOCRVL

    pipeline = PaddleOCRVL(
        device=device,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
    )

    predict_kwargs = build_predict_kwargs(input_pdf, page_start, page_end)

    print(f"[paddleocr] Running PaddleOCR-VL on {input_pdf.name} ...", flush=True)
    page_results = list(pipeline.predict(**predict_kwargs))
    page_count = len(page_results)

    if page_count == 0:
        raise RuntimeError("PaddleOCR-VL returned no pages")

    for idx, res in enumerate(page_results, start=1):
        debug_type(f"paddleocr_vl raw page result {idx}", res, debug_types)

    restructured_results: list[Any]
    restructure_pages = getattr(pipeline, "restructure_pages", None)

    if callable(restructure_pages):
        try:
            restructured = restructure_pages(
                page_results,
                merge_tables=True,
                relevel_titles=True,
                concatenate_pages=True,
            )
        except TypeError:
            # Compatibility with local builds that accept fewer parameters.
            restructured = restructure_pages(page_results)

        if isinstance(restructured, list):
            restructured_results = restructured
        else:
            restructured_results = list(restructured)
    else:
        restructured_results = page_results

    markdown_parts: list[str] = []
    markdown_images: dict[str, Any] = {}

    for idx, res in enumerate(restructured_results, start=1):
        debug_type(f"paddleocr_vl result {idx}", res, debug_types)

        md_payload = getattr(res, "markdown", None)
        debug_type(f"paddleocr_vl markdown {idx}", md_payload, debug_types)

        if md_payload is None:
            raise TypeError(f"PaddleOCR-VL result {idx} has no .markdown payload")

        md_text, md_images = extract_markdown_payload(md_payload)
        markdown_parts.append(md_text)
        markdown_images.update(md_images)

        safe_save_result(res, out_dir, save_markdown=True)

    images_saved = save_markdown_images(markdown_images, out_dir)
    merged_md = "\n\n---\n\n".join(part for part in markdown_parts if part.strip())

    return {
        "markdown": merged_md,
        "pages": page_count,
        "pipeline": "paddleocr_vl",
        "images_saved": images_saved,
    }


def extract_pp_ocrv5_text(result: Any) -> str:
    """Best-effort text extraction from PaddleOCR PP-OCRv5 result objects."""
    data = object_to_dict(result)

    # Common shape: {"res": {"rec_texts": [...]}} or similar.
    containers = [data]
    for key in ("res", "result", "data", "output"):
        value = data.get(key)
        if isinstance(value, dict):
            containers.append(value)

    text_keys = (
        "rec_texts",
        "rec_text",
        "texts",
        "text",
        "ocr_text",
    )

    for container in containers:
        for key in text_keys:
            value = container.get(key)
            if isinstance(value, list):
                return "\n".join(str(item) for item in value if item is not None)
            if isinstance(value, str):
                return value

    # Iterable fallback for older structures.
    try:
        lines: list[str] = []
        for item in result:
            item_data = object_to_dict(item)
            text = first_str_value(item_data, ("rec_text", "text", "ocr_text"))
            if text:
                lines.append(text)
        if lines:
            return "\n".join(lines)
    except Exception:
        pass

    return ""


def run_pp_ocrv5(
    input_pdf: Path,
    out_dir: Path,
    *,
    device: str,
    lang: str | None,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    page_start: int | None,
    page_end: int | None,
    debug_types: bool,
) -> dict[str, Any]:
    """Run PP-OCRv5 for plain text extraction."""
    from paddleocr import PaddleOCR

    kwargs: dict[str, Any] = {
        "device": device,
        "use_doc_orientation_classify": use_doc_orientation_classify,
        "use_doc_unwarping": use_doc_unwarping,
        "use_textline_orientation": False,
    }
    if lang:
        kwargs["lang"] = lang

    ocr = PaddleOCR(**kwargs)
    predict_kwargs = build_predict_kwargs(input_pdf, page_start, page_end)

    print(f"[paddleocr] Running PP-OCRv5 on {input_pdf.name} ...", flush=True)
    output = ocr.predict(**predict_kwargs)

    page_texts: list[str] = []
    page_count = 0

    for res in output:
        page_count += 1
        debug_type(f"pp_ocrv5 page result {page_count}", res, debug_types)
        page_texts.append(extract_pp_ocrv5_text(res))
        safe_save_result(res, out_dir, save_markdown=False)

    if page_count == 0:
        raise RuntimeError("PP-OCRv5 returned no pages")

    merged_md = "\n\n---\n\n".join(
        f"<!-- page {idx} -->\n{text}" for idx, text in enumerate(page_texts, start=1)
    )

    return {
        "markdown": merged_md,
        "pages": page_count,
        "pipeline": "pp_ocrv5",
        "images_saved": 0,
    }


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def run(
    *,
    input_pdf: Path,
    output_md: Path,
    out_dir: Path,
    pipeline: str,
    device: str,
    lang: str | None,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    page_start: int | None,
    page_end: int | None,
    keep_output: bool,
    json_out: Path | None,
    debug_types: bool,
) -> Path:
    """Run the selected PaddleOCR pipeline and write Markdown output."""
    import shutil

    validate_page_range(page_start, page_end)
    out_dir.mkdir(parents=True, exist_ok=True)

    common_kw = dict(
        input_pdf=input_pdf,
        out_dir=out_dir,
        device=device,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        page_start=page_start,
        page_end=page_end,
        debug_types=debug_types,
    )

    if pipeline == "pp_structurev3":
        result = run_pp_structurev3(**common_kw)
    elif pipeline == "paddleocr_vl":
        result = run_paddleocr_vl(**common_kw)
    elif pipeline == "pp_ocrv5":
        result = run_pp_ocrv5(**common_kw, lang=lang)
    else:
        raise ValueError(f"Unknown pipeline: {pipeline}")

    markdown = result.get("markdown")
    if not isinstance(markdown, str):
        raise TypeError(f"Internal error: expected Markdown str, got {type(markdown).__name__}")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(markdown, encoding="utf-8")
    print(f"[out]   Markdown -> {output_md} ({result['pages']} pages)")

    if result.get("images_saved"):
        print(f"[out]   Images   -> {out_dir} ({result['images_saved']} files)")

    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(
                {
                    "backend": "paddleocr",
                    "pipeline": result["pipeline"],
                    "input": str(input_pdf),
                    "output_md": str(output_md),
                    "paddleocr_output_dir": str(out_dir),
                    "pages": result["pages"],
                    "images_saved": result.get("images_saved", 0),
                    "device": device,
                    "lang": lang,
                    "page_start": page_start,
                    "page_end": page_end,
                    "use_doc_orientation_classify": use_doc_orientation_classify,
                    "use_doc_unwarping": use_doc_unwarping,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[out]   JSON     -> {json_out}")

    if not keep_output and out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)

    return output_md


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    args = build_parser().parse_args()

    if args.disable_model_source_check:
        # Must be set before importing PaddleOCR, which happens inside runner functions.
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    try:
        input_pdf = validate_input(args.input)
        validate_page_range(args.start, args.end)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_md = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_pdf.with_suffix(".md")
    )

    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else output_md.parent / f"{output_md.stem}_paddleocr_output"
    )

    json_out = Path(args.json_out).expanduser().resolve() if args.json_out else None

    try:
        output_path = run(
            input_pdf=input_pdf,
            output_md=output_md,
            out_dir=out_dir,
            pipeline=args.pipeline,
            device=args.device,
            lang=args.lang,
            use_doc_orientation_classify=args.use_doc_orientation_classify,
            use_doc_unwarping=args.use_doc_unwarping,
            page_start=args.start,
            page_end=args.end,
            keep_output=args.keep_output,
            json_out=json_out,
            debug_types=args.debug_types,
        )
        print(str(output_path))
        return 0
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        if args.debug_types:
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
