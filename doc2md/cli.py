"""CLI entry point and pipeline orchestration for doc2md."""

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc2md",
        description="Convert PDF documents to Markdown with configurable OCR and layout detection.",
    )

    # ── Required ──────────────────────────────────────────────
    parser.add_argument(
        "input",
        type=Path,
        help="Path to input PDF file.",
    )

    # ── Output ────────────────────────────────────────────────
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to <input_stem>_output/",
    )

    # ── Config ────────────────────────────────────────────────
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        help="YAML config file for batch/benchmark runs.",
    )

    # ── Model selection (CLI overrides YAML) ──────────────────
    parser.add_argument(
        "--ocr",
        type=str,
        default=None,
        help="OCR engine name (e.g. surya, paddleocr, got). Overrides config.",
    )
    parser.add_argument(
        "--layout",
        type=str,
        default=None,
        help="Layout detector name (e.g. doclayout-yolo, yolov11-obb, rt-detr). Overrides config.",
    )

    # ── Strategy override ─────────────────────────────────────
    parser.add_argument(
        "--force-strategy",
        type=str,
        choices=["deterministic", "visual", "hybrid"],
        default=None,
        help="Force a specific strategy, bypassing the router.",
    )

    # ── Profiler thresholds ───────────────────────────────────
    parser.add_argument(
        "--text-threshold",
        type=float,
        default=0.8,
        help="Text coverage ratio above which a page is routed deterministically (default: 0.8).",
    )

    # ── Verbosity ─────────────────────────────────────────────
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v info, -vv debug).",
    )

    return parser


def resolve_config(args: argparse.Namespace) -> dict:
    """Merge defaults ← YAML ← CLI into a single config dict."""

    # Defaults
    config = {
        "ocr": "surya",
        "layout": "doclayout-yolo",
        "force_strategy": None,
        "text_threshold": 0.8,
        "verbose": 0,
    }

    # YAML layer
    if args.config is not None:
        print(f"  [config] Loading YAML config from: {args.config}")
        # TODO: yaml.safe_load(args.config.read_text())
        #       merge into config dict
    else:
        print("  [config] No YAML config provided, using defaults.")

    # CLI layer (overrides)
    if args.ocr is not None:
        config["ocr"] = args.ocr
    if args.layout is not None:
        config["layout"] = args.layout
    if args.force_strategy is not None:
        config["force_strategy"] = args.force_strategy
    if args.text_threshold != 0.8:
        config["text_threshold"] = args.text_threshold
    config["verbose"] = args.verbose

    print(f"  [config] Resolved: ocr={config['ocr']}, layout={config['layout']}, "
          f"strategy={config['force_strategy'] or 'auto'}, "
          f"text_threshold={config['text_threshold']}")

    return config


def setup_output(input_path: Path, output_arg: Path | None) -> Path:
    """Create and return the output directory."""

    output_dir = output_arg or input_path.parent / f"{input_path.stem}_output"
    media_dir = output_dir / "media"

    print(f"  [output] Creating output directory: {output_dir}")
    print(f"  [output] Creating media directory:  {media_dir}")
    # TODO: output_dir.mkdir(parents=True, exist_ok=True)
    # TODO: media_dir.mkdir(parents=True, exist_ok=True)

    return output_dir


def run_pipeline(input_path: Path, output_dir: Path, config: dict) -> None:
    """Orchestrate the full conversion pipeline.

    Default flow (auto):
      1. Profile: analyze PDF structure per page (pure software, no ML)
         - text layer presence, render modes, font encodings, ToUnicode cmaps
         - image coverage ratio, text area ratio
         - char sample validation (mojibake detection)
      2. Route: map each PageProfile → strategy using structural signals
      3. Execute: run assigned strategy per page
         - DETERMINISTIC: PyMuPDF text extraction (fast, no ML)
         - HYBRID: deterministic for text regions + visual for gaps
         - VISUAL: full rasterization → layout detection → OCR
      4. Assemble: merge page results → markdown + media/

    With --force-strategy: skip profiler routing, force all pages through one path.
    """

    md_output = output_dir / (input_path.stem + ".md")

    # ── Step 1: Structural profiling (pure software, no ML) ───
    print(f"\n{'='*60}")
    print(f"  [profiler] Analyzing: {input_path}")
    print(f"  [profiler] Reading PDF internal structure...")
    print(f"  [profiler]")
    print(f"  [profiler] Page 1:")
    print(f"  [profiler]   has_text_layer     = True")
    print(f"  [profiler]   text_render_mode   = 0 (visible, normal)")
    print(f"  [profiler]   has_tounicode_cmap = True")
    print(f"  [profiler]   font_encoding      = WinAnsiEncoding (standard)")
    print(f"  [profiler]   image_coverage     = 0.02")
    print(f"  [profiler]   text_area_ratio    = 0.91")
    print(f"  [profiler]   char_sample_valid  = True ('Abstract: We present a novel...')")
    print(f"  [profiler]")
    print(f"  [profiler] Page 2:")
    print(f"  [profiler]   has_text_layer     = True")
    print(f"  [profiler]   text_render_mode   = 0 (visible, normal)")
    print(f"  [profiler]   has_tounicode_cmap = True")
    print(f"  [profiler]   font_encoding      = WinAnsiEncoding (standard)")
    print(f"  [profiler]   image_coverage     = 0.45")
    print(f"  [profiler]   text_area_ratio    = 0.38")
    print(f"  [profiler]   char_sample_valid  = True ('Results show that...')")
    print(f"  [profiler]")
    print(f"  [profiler] Page 3:")
    print(f"  [profiler]   has_text_layer     = False")
    print(f"  [profiler]   text_render_mode   = n/a")
    print(f"  [profiler]   has_tounicode_cmap = n/a")
    print(f"  [profiler]   font_encoding      = n/a")
    print(f"  [profiler]   image_coverage     = 0.98")
    print(f"  [profiler]   text_area_ratio    = 0.00")
    print(f"  [profiler]   char_sample_valid  = n/a (no text to sample)")
    # TODO: profile = Profiler().analyze(input_path)

    # ── Step 2: Route (or force) ──────────────────────────────
    if config["force_strategy"]:
        print(f"\n  [router] Strategy forced via CLI: {config['force_strategy']}")
        print(f"  [router] Skipping structural routing")
        _run_forced(input_path, output_dir, config)
        return

    threshold = config["text_threshold"]
    print(f"\n  [router] Routing pages (text_threshold={threshold})...")
    print(f"  [router]")
    print(f"  [router] Page 1: has_text=✓  tounicode=✓  encoding=OK  render=0")
    print(f"  [router]          text_area=0.91 (>{threshold})  image_cov=0.02")
    print(f"  [router]          char_sample=valid")
    print(f"  [router]          → DETERMINISTIC (all signals green)")
    print(f"  [router]")
    print(f"  [router] Page 2: has_text=✓  tounicode=✓  encoding=OK  render=0")
    print(f"  [router]          text_area=0.38 (<{threshold})  image_cov=0.45")
    print(f"  [router]          char_sample=valid")
    print(f"  [router]          ⚠ text layer trustworthy but covers only 38% of page")
    print(f"  [router]          → HYBRID (good text + large visual gaps)")
    print(f"  [router]")
    print(f"  [router] Page 3: has_text=✗")
    print(f"  [router]          image_cov=0.98")
    print(f"  [router]          → VISUAL (no text layer, scanned page)")
    # TODO: page_routes = Router(threshold).route(profile)
    # Logic:
    #   if not has_text_layer OR image_coverage > 0.85:
    #       → VISUAL
    #   if not has_tounicode OR font_encoding == poor OR render_mode == 3:
    #       → VISUAL (text layer untrustworthy)
    #   if not char_sample_valid:
    #       → VISUAL (mojibake detected)
    #   if text_area_ratio >= threshold:
    #       → DETERMINISTIC
    #   else:
    #       → HYBRID

    # ── Step 3: Execute per-page strategies ───────────────────

    # 3a. Deterministic pages
    print(f"\n  [deterministic] Processing 1 page...")
    print(f"  [deterministic] Page 1: PyMuPDF text extraction")
    print(f"  [deterministic] Page 1: extracted 2847 chars")
    print(f"  [deterministic] Page 1: extracting 1 embedded image → media/img_p1_001.png")
    # TODO: result = DeterministicStrategy().process(page)

    # 3b. Hybrid pages
    print(f"\n  [hybrid] Processing 1 page...")
    print(f"  [hybrid] Page 2: PyMuPDF text extraction for trusted regions")
    print(f"  [hybrid] Page 2: extracted 412 chars from text layer")
    print(f"  [hybrid] Page 2: rasterizing page, masking known text areas")
    print(f"  [hybrid] Page 2: layout detection ({config['layout']}) on visual gaps")
    print(f"  [hybrid]   Gap 1 → detected: table  → OCR ({config['ocr']}): '| col1 | col2 |...'")
    print(f"  [hybrid]   Gap 2 → detected: figure → media/img_p2_001.png")
    print(f"  [hybrid]   Gap 3 → detected: caption → OCR ({config['ocr']}): 'Figure 1: ...'")
    print(f"  [hybrid] Page 2: merging text layer + visual results")
    # TODO: result = HybridStrategy(config).process(page, profile)

    # 3c. Visual pages
    print(f"\n  [visual] Processing 1 page...")
    print(f"  [visual] Page 3: rasterizing @ 300 DPI")
    print(f"  [visual] Page 3: layout detection ({config['layout']})")
    print(f"  [visual]   Detected: 2× text, 1× table, 1× figure")
    print(f"  [visual] Page 3: OCR ({config['ocr']}) on 3 text/table regions")
    print(f"  [visual]   Region 1 (text):   'Lorem ipsum dolor...'")
    print(f"  [visual]   Region 2 (table):  '| A | B | C |...'")
    print(f"  [visual]   Region 3 (text):   'Concluding remarks...'")
    print(f"  [visual]   Region 4 (figure): → media/img_p3_001.png")
    # TODO: result = VisualStrategy(config).process(page_image)

    # ── Step 4: Assemble ──────────────────────────────────────
    print(f"\n  [assembler] Merging results: 1 deterministic + 1 hybrid + 1 visual")
    print(f"  [assembler] Ordering by page number")
    print(f"  [assembler] Resolving media references (4 files)")
    print(f"  [assembler] Writing: {md_output}")
    print(f"  [assembler] Media dir: {output_dir / 'media/'}")
    # TODO: Assembler().assemble(all_page_results, output_dir)


def _run_forced(input_path: Path, output_dir: Path, config: dict) -> None:
    """Execute a single forced strategy on all pages (debug/benchmark mode)."""

    strategy = config["force_strategy"]
    md_output = output_dir / (input_path.stem + ".md")

    print(f"\n  [forced:{strategy}] Running {strategy} on all pages...")

    if strategy == "deterministic":
        print(f"  [forced:deterministic] PyMuPDF text extraction on all pages")
        print(f"  [forced:deterministic] Extracting embedded media → media/")

    elif strategy == "visual":
        print(f"  [forced:visual] Rasterizing all pages @ 300 DPI")
        print(f"  [forced:visual] Layout detection ({config['layout']}) on all pages")
        print(f"  [forced:visual] OCR ({config['ocr']}) on all detected regions")

    elif strategy == "hybrid":
        print(f"  [forced:hybrid] Deterministic extraction first")
        print(f"  [forced:hybrid] Rasterizing all gap regions")
        print(f"  [forced:hybrid] Layout + OCR on gap regions")

    print(f"\n  [assembler] Writing: {md_output}")
    print(f"  [assembler] Media dir: {output_dir / 'media/'}")
    # TODO: implement forced execution paths


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    # ── Validate input ────────────────────────────────────────
    print(f"\ndoc2md - Document to Markdown Pipeline")
    print(f"{'='*60}")

    if not args.input.suffix.lower() == ".pdf":
        print(f"  [error] Input must be a PDF file, got: {args.input.suffix}")
        sys.exit(1)

    # For now, skip existence check so we can test the flow
    print(f"  [input] File: {args.input}")

    # ── Resolve config ────────────────────────────────────────
    config = resolve_config(args)

    # ── Setup output ──────────────────────────────────────────
    output_dir = setup_output(args.input, args.output)

    # ── Run ────────────────────────────────────────────────────
    run_pipeline(args.input, output_dir, config)

    # ── Done ──────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  [done] Pipeline complete.")
    print(f"{'='*60}\n")
