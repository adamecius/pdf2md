
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
    """Orchestrate the full conversion pipeline."""

    # ── Step 1: Profile ───────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  [profiler] Analyzing: {input_path}")
    print(f"  [profiler] Extracting metadata (page count, fonts, text layers)...")
    print(f"  [profiler] Classifying each page → PageProfile")
    print(f"  [profiler] Result: DocumentProfile with N page profiles")
    # TODO: profile = Profiler(config).analyze(input_path)

    # ── Step 2: Route ─────────────────────────────────────────
    if config["force_strategy"]:
        print(f"\n  [router] Strategy forced: {config['force_strategy']} (skipping classification)")
    else:
        print(f"\n  [router] Routing each page based on text_ratio (threshold={config['text_threshold']})")
        print(f"  [router]   Page 1: text_ratio=0.95 → deterministic")
        print(f"  [router]   Page 2: text_ratio=0.40 → hybrid")
        print(f"  [router]   Page 3: text_ratio=0.02 → visual")
    # TODO: page_strategies = Router(config).route(profile)

    # ── Step 3: Execute strategies per page ────────────────────
    print(f"\n  [strategy] Processing pages...")

    # Deterministic path
    print(f"  [strategy:deterministic] Page 1 → PyMuPDF text extraction")
    print(f"  [strategy:deterministic] Extracting embedded images → media/")
    # TODO: result = DeterministicStrategy(config).process(page)

    # Hybrid path
    print(f"  [strategy:hybrid] Page 2 → Extracting text layer with PyMuPDF")
    print(f"  [strategy:hybrid] Page 2 → Rasterizing non-text regions")
    print(f"  [strategy:hybrid] Page 2 → Sending rasterized regions to visual pipeline")
    # TODO: result = HybridStrategy(config).process(page)

    # Visual path
    print(f"  [strategy:visual] Page 3 → Rasterizing full page")
    print(f"  [strategy:visual] Page 3 → Layout detection with {config['layout']}")
    print(f"  [strategy:visual]   Detected: 2 text blocks, 1 table, 1 figure")
    print(f"  [strategy:visual] Page 3 → OCR with {config['ocr']}")
    print(f"  [strategy:visual]   Region 1 (text):  'Lorem ipsum...'")
    print(f"  [strategy:visual]   Region 2 (table): '| col1 | col2 |...'")
    print(f"  [strategy:visual]   Region 3 (text):  'Dolor sit amet...'")
    print(f"  [strategy:visual]   Region 4 (figure): → media/img_p3_001.png")
    # TODO: result = VisualStrategy(config).process(page)

    # ── Step 4: Assemble ──────────────────────────────────────
    print(f"\n  [assembler] Collecting PageResults...")
    print(f"  [assembler] Ordering by page number")
    print(f"  [assembler] Resolving media references")
    print(f"  [assembler] Writing: {output_dir / (input_path.stem + '.md')}")
    print(f"  [assembler] Media files: {output_dir / 'media/'}")
    # TODO: Assembler(config).assemble(page_results, output_dir)


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