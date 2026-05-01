#!/usr/bin/env python3
"""pdf2md_paddleocr.py — Convert PDF to Markdown using PaddleOCR.

Single-file wrapper that uses the PaddleOCR Python API (PPStructureV3,
PaddleOCR-VL, or PP-OCRv5) to parse a PDF and produce Markdown output.

Usage:
  pdf2md_paddleocr.py -i paper.pdf                        # → paper.md
  pdf2md_paddleocr.py -i paper.pdf -o out.md               # explicit output
  pdf2md_paddleocr.py -i paper.pdf -p paddleocr_vl         # VLM pipeline
  pdf2md_paddleocr.py -i paper.pdf --device cpu             # CPU-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PIPELINES = [
    "pp_structurev3",   # document parsing → Markdown (default, best for pdf2md)
    "paddleocr_vl",     # VLM-based parsing (0.9B, needs ≥8 GB VRAM)
    "pp_ocrv5",         # pure OCR text recognition (no layout structure)
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert a PDF to Markdown using PaddleOCR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Default: PP-StructureV3 pipeline (layout + tables + formulas → Markdown)
  %(prog)s -i paper.pdf

  # Use PaddleOCR-VL (vision-language model, higher accuracy, more VRAM)
  %(prog)s -i paper.pdf -p paddleocr_vl

  # CPU-only inference
  %(prog)s -i paper.pdf --device cpu

  # Parse only pages 3–7
  %(prog)s -i paper.pdf --start 3 --end 7

  # Keep intermediate output (images, JSON)
  %(prog)s -i paper.pdf --keep-output --out-dir ./paddle_out
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
        help="Output Markdown path (default: <input>.md alongside the PDF).",
    )
    gio.add_argument(
        "--out-dir", metavar="DIR",
        help="Directory for PaddleOCR intermediate output (images, etc.). "
             "Default: <output_stem>_paddleocr_output/ next to the output .md.",
    )
    gio.add_argument(
        "--json-out", metavar="JSON",
        help="Write a JSON metadata sidecar to this path.",
    )

    # -- Pipeline --
    gpi = p.add_argument_group("pipeline")
    gpi.add_argument(
        "-p", "--pipeline", default="pp_structurev3", choices=PIPELINES,
        help="PaddleOCR pipeline to use (default: %(default)s). "
             "pp_structurev3 = layout-aware document parsing. "
             "paddleocr_vl  = VLM-based parsing (higher accuracy). "
             "pp_ocrv5      = pure OCR text extraction.",
    )

    # -- Inference --
    ginf = p.add_argument_group("inference options")
    ginf.add_argument(
        "--device", default="gpu:0", metavar="DEV",
        help="Inference device (default: gpu:0). "
             "Examples: gpu:0, gpu:1, cpu.",
    )
    ginf.add_argument(
        "--lang", default=None, metavar="LANG",
        help="Language hint for OCR (e.g. ch, en, korean, japan). "
             "Default: auto-detected by the pipeline.",
    )
    ginf.add_argument(
        "--start", type=int, default=None, metavar="N",
        help="Starting page number (0-based).",
    )
    ginf.add_argument(
        "--end", type=int, default=None, metavar="N",
        help="Ending page number (0-based).",
    )

    # -- Behaviour --
    gbh = p.add_argument_group("behaviour")
    gbh.add_argument(
        "--use-doc-orientation-classify", action="store_true",
        help="Enable document orientation classification (default: off).",
    )
    gbh.add_argument(
        "--use-doc-unwarping", action="store_true",
        help="Enable document unwarping (default: off).",
    )
    gbh.add_argument(
        "--keep-output", action="store_true",
        help="Keep the intermediate PaddleOCR output directory.",
    )

    return p


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------
def run_pp_structurev3(
    input_pdf: Path,
    output_md: Path,
    out_dir: Path,
    *,
    device: str,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    page_start: int | None,
    page_end: int | None,
) -> dict:
    """Run PP-StructureV3 pipeline and produce merged Markdown."""
    from paddleocr import PPStructureV3

    pipeline = PPStructureV3(
        device=device,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=False,
    )

    predict_kwargs: dict = {"input": str(input_pdf)}
    if page_start is not None:
        predict_kwargs["start_page_idx"] = page_start
    if page_end is not None:
        predict_kwargs["end_page_idx"] = page_end

    print(f"[paddleocr] Running PP-StructureV3 on {input_pdf.name} …", flush=True)
    output = pipeline.predict(**predict_kwargs)

    markdown_list = []
    markdown_images: dict = {}
    page_count = 0
    for res in output:
        page_count += 1
        md_info = res.markdown
        markdown_list.append(md_info)
        images = md_info.get("markdown_images", {})
        if images:
            markdown_images.update(images)
        # Save per-page intermediate results
        res.save_to_json(save_path=str(out_dir))
        res.save_to_markdown(save_path=str(out_dir))

    merged_md = pipeline.concatenate_markdown_pages(markdown_list)

    # Save embedded images
    for img_path, img_obj in markdown_images.items():
        full_path = out_dir / img_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        img_obj.save(str(full_path))

    return {"markdown": merged_md, "pages": page_count, "pipeline": "pp_structurev3"}


def run_paddleocr_vl(
    input_pdf: Path,
    output_md: Path,
    out_dir: Path,
    *,
    device: str,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    page_start: int | None,
    page_end: int | None,
) -> dict:
    """Run PaddleOCR-VL pipeline and produce merged Markdown."""
    from paddleocr import PaddleOCRVL

    pipeline = PaddleOCRVL(
        device=device,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
    )

    predict_kwargs: dict = {"input": str(input_pdf)}
    if page_start is not None:
        predict_kwargs["start_page_idx"] = page_start
    if page_end is not None:
        predict_kwargs["end_page_idx"] = page_end

    print(f"[paddleocr] Running PaddleOCR-VL on {input_pdf.name} …", flush=True)
    output = pipeline.predict(**predict_kwargs)

    markdown_list = []
    page_count = 0
    for res in output:
        page_count += 1
        md_info = res.markdown
        markdown_list.append(md_info)
        res.save_to_json(save_path=str(out_dir))
        res.save_to_markdown(save_path=str(out_dir))

    merged_md = pipeline.concatenate_markdown_pages(markdown_list)
    return {"markdown": merged_md, "pages": page_count, "pipeline": "paddleocr_vl"}


def run_pp_ocrv5(
    input_pdf: Path,
    output_md: Path,
    out_dir: Path,
    *,
    device: str,
    lang: str | None,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    page_start: int | None,
    page_end: int | None,
) -> dict:
    """Run PP-OCRv5 pipeline (plain text extraction, no layout structure)."""
    from paddleocr import PaddleOCR

    kwargs: dict = {
        "device": device,
        "use_doc_orientation_classify": use_doc_orientation_classify,
        "use_doc_unwarping": use_doc_unwarping,
        "use_textline_orientation": False,
    }
    if lang:
        kwargs["lang"] = lang

    ocr = PaddleOCR(**kwargs)

    predict_kwargs: dict = {"input": str(input_pdf)}
    if page_start is not None:
        predict_kwargs["start_page_idx"] = page_start
    if page_end is not None:
        predict_kwargs["end_page_idx"] = page_end

    print(f"[paddleocr] Running PP-OCRv5 on {input_pdf.name} …", flush=True)
    output = ocr.predict(**predict_kwargs)

    page_texts = []
    page_count = 0
    for res in output:
        page_count += 1
        rec_texts = res.get("res", {}).get("rec_text", [])
        if isinstance(rec_texts, list):
            page_texts.append("\n".join(rec_texts))
        elif isinstance(rec_texts, str):
            page_texts.append(rec_texts)
        else:
            # Fallback: try to extract text from the result object
            try:
                text_lines = []
                for item in res:
                    if hasattr(item, "rec_text"):
                        text_lines.append(item.rec_text)
                page_texts.append("\n".join(text_lines))
            except Exception:
                page_texts.append("")
        res.save_to_json(save_path=str(out_dir))

    merged_md = "\n\n---\n\n".join(
        f"<!-- page {i+1} -->\n{t}" for i, t in enumerate(page_texts)
    )
    return {"markdown": merged_md, "pages": page_count, "pipeline": "pp_ocrv5"}


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def validate_input(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Input file does not exist: {p}")
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a .pdf file, got: {p.suffix}")
    return p


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
) -> Path:
    """Run the selected PaddleOCR pipeline and write the output markdown."""
    import shutil

    out_dir.mkdir(parents=True, exist_ok=True)

    common_kw = dict(
        input_pdf=input_pdf,
        output_md=output_md,
        out_dir=out_dir,
        device=device,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        page_start=page_start,
        page_end=page_end,
    )

    if pipeline == "pp_structurev3":
        result = run_pp_structurev3(**common_kw)
    elif pipeline == "paddleocr_vl":
        result = run_paddleocr_vl(**common_kw)
    elif pipeline == "pp_ocrv5":
        result = run_pp_ocrv5(**common_kw, lang=lang)
    else:
        raise ValueError(f"Unknown pipeline: {pipeline}")

    # Write merged markdown
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(result["markdown"], encoding="utf-8")
    print(f"[out]   Markdown → {output_md}  ({result['pages']} pages)")

    # JSON sidecar
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
                    "device": device,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[out]   JSON    → {json_out}")

    # Cleanup
    if not keep_output and out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)

    return output_md


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    args = build_parser().parse_args()

    try:
        input_pdf = validate_input(args.input)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # Resolve output paths
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
        out = run(
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
        )
        print(str(out))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())