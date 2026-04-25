"""CLI entry point and pipeline orchestration for doc2md."""

import argparse
import sys
from pathlib import Path

from doc2md.assembler import Assembler
from doc2md.backends.deterministic import DeterministicBackend
from doc2md.exporters.chunks_jsonl import write_chunks_jsonl
from doc2md.exporters.json_ir import write_docir
from doc2md.models import Strategy
from doc2md.profiler import profile_document
from doc2md.router import route_document
from doc2md.strategies.deterministic import DeterministicStrategy

import pymupdf


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
        help="Output directory. Defaults to .data/<input_stem>_output/",
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
        help="Layout detector name (e.g. doclayout_yolo, yolov11-obb, rt-detr). Overrides config.",
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

    parser.add_argument(
        "--emit-docir",
        action="store_true",
        help="Also emit canonical DocIR JSON at <output>/<input_stem>.docir.json.",
    )
    parser.add_argument(
        "--emit-chunks",
        action="store_true",
        help="Also emit chunked JSONL at <output>/<input_stem>.blocks.jsonl.",
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
    """Merge defaults <- YAML <- CLI into a single config dict."""

    config = {
        "ocr": "surya",
        "layout": "doclayout_yolo",
        "force_strategy": None,
        "text_threshold": 0.8,
        "verbose": 0,
        "emit_docir": False,
        "emit_chunks": False,
    }

    if args.config is not None:
        print(f"  [config] Loading YAML config from: {args.config}")
        # TODO: yaml.safe_load(args.config.read_text()) -> merge
    else:
        print("  [config] No YAML provided, using defaults.")

    if args.ocr is not None:
        config["ocr"] = args.ocr
    if args.layout is not None:
        config["layout"] = args.layout
    if args.force_strategy is not None:
        config["force_strategy"] = args.force_strategy
    if args.text_threshold != 0.8:
        config["text_threshold"] = args.text_threshold
    config["verbose"] = args.verbose
    config["emit_docir"] = args.emit_docir
    config["emit_chunks"] = args.emit_chunks

    print(f"  [config] Resolved: ocr={config['ocr']}, layout={config['layout']}, "
          f"strategy={config['force_strategy'] or 'auto'}, "
          f"text_threshold={config['text_threshold']}, "
          f"emit_docir={config['emit_docir']}, emit_chunks={config['emit_chunks']}")

    return config


def setup_output(input_path: Path, output_arg: Path | None) -> Path:
    """Create and return the output directory."""

    output_dir = output_arg or Path(".data") / f"{input_path.stem}_output"
    media_dir = output_dir / "media"

    output_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [output] Output directory: {output_dir}")
    return output_dir


# ── Display helpers ───────────────────────────────────────────

def _print_page_profile(p, verbose: int = 0) -> None:
    """Print a single page profile."""

    render_str = {0: "visible", 3: "invisible (OCR layer)", None: "n/a"}
    rm_display = render_str.get(p.text_render_mode, f"mode {p.text_render_mode}")

    print(f"  [profiler] Page {p.page_number + 1}  ({p.width:.0f}x{p.height:.0f} pts)")
    print(f"  [profiler]   text_layer={p.has_text_layer}  "
          f"render_mode={rm_display}  "
          f"chars={p.char_count}")
    print(f"  [profiler]   text_area_ratio={p.text_area_ratio:.2f}  "
          f"image_coverage={p.image_coverage:.2f}  "
          f"images={p.image_count}")
    print(f"  [profiler]   tounicode={p.has_tounicode_cmap}  "
          f"encoding={p.font_encoding_quality.name}  "
          f"fonts={len(p.fonts)}")
    print(f"  [profiler]   sample_valid={p.char_sample_valid}", end="")
    if p.char_sample:
        preview = p.char_sample[:60].replace("\n", " ")
        print(f"  ('{preview}...')")
    else:
        print(f"  (no text)")

    if verbose >= 2 and p.fonts:
        for f in p.fonts:
            print(f"  [profiler]     font: {f.name}  enc={f.encoding}  "
                  f"tu={f.has_tounicode}  emb={f.is_embedded}  q={f.quality.name}")


def _print_route_decision(p) -> None:
    """Print routing decision for a page."""

    symbol = {"DETERMINISTIC": "DET", "HYBRID": "HYB", "VISUAL": "VIS"}
    strategy_name = p.strategy.name if p.strategy else "NONE"
    tag = symbol.get(strategy_name, strategy_name)

    warn = " !!" if strategy_name == "HYBRID" else ""
    print(f"  [router] Page {p.page_number + 1}: -> {tag}{warn}  "
          f"(text={p.text_area_ratio:.2f}, img={p.image_coverage:.2f}, "
          f"chars={p.char_count})")


# ── Pipeline ──────────────────────────────────────────────────

def run_pipeline(input_path: Path, output_dir: Path, config: dict) -> None:
    """Orchestrate the full conversion pipeline."""

    md_output = output_dir / (input_path.stem + ".md")
    verbose = config["verbose"]

    # ── Step 1: Profile (real PyMuPDF analysis) ───────────────
    print(f"\n{'='*60}")
    print(f"  [profiler] Analyzing: {input_path}")

    profile = profile_document(input_path)

    print(f"  [profiler] PDF: {profile.pdf_version}  "
          f"Pages: {profile.page_count}  "
          f"Size: {profile.file_size_bytes / 1024:.1f} KB  "
          f"Encrypted: {profile.is_encrypted}  "
          f"Forms: {profile.has_forms}")
    print()

    for p in profile.pages:
        _print_page_profile(p, verbose)

    # ── Step 2: Route ─────────────────────────────────────────
    if config["force_strategy"]:
        forced = Strategy[config["force_strategy"].upper()]
        print(f"\n  [router] Strategy forced: {forced.name}")
        for p in profile.pages:
            p.strategy = forced
    else:
        route_document(profile, text_threshold=config["text_threshold"])
        print(f"\n  [router] Routing (text_threshold={config['text_threshold']}):")
        for p in profile.pages:
            _print_route_decision(p)

    # ── Step 3: Execute per-page strategies ───────────────────
    det_pages = profile.deterministic_pages
    hyb_pages = profile.hybrid_pages
    vis_pages = profile.visual_pages

    page_results = []

    if det_pages:
        print(f"\n  [deterministic] {len(det_pages)} page(s)")
        strategy = DeterministicStrategy(output_dir=output_dir)
        with pymupdf.open(str(input_path)) as doc:
            for p in det_pages:
                print(f"  [deterministic] Page {p.page_number + 1}: "
                      f"PyMuPDF extraction ({p.char_count} chars)")
                result = strategy.process_page(doc[p.page_number], p.page_number)
                page_results.append(result)
                if result.error:
                    print(f"  [deterministic][warn] Page {p.page_number + 1}: {result.error}")

    if hyb_pages:
        print(f"\n  [hybrid] {len(hyb_pages)} page(s) (not yet implemented)")
        for p in hyb_pages:
            print(f"  [hybrid] Page {p.page_number + 1}: "
                  f"text={p.text_area_ratio:.2f} img={p.image_coverage:.2f}")

    if vis_pages:
        print(f"\n  [visual] {len(vis_pages)} page(s) (not yet implemented)")
        for p in vis_pages:
            reason = "no text layer" if not p.has_text_layer else \
                     "scanned" if p.image_coverage > 0.85 else \
                     "invisible text" if p.text_render_mode == 3 else \
                     "bad encoding" if not p.char_sample_valid else \
                     "visual"
            print(f"  [visual] Page {p.page_number + 1}: {reason}")

    # ── Step 4: Assemble (stub) ───────────────────────────────
    print(f"\n  [assembler] {len(det_pages)} det + "
          f"{len(hyb_pages)} hyb + {len(vis_pages)} vis")

    if page_results:
        assembler = Assembler(output_dir=output_dir, stem=input_path.stem)
        assembled_path, stats = assembler.assemble(page_results)
        print(f"  [assembler] -> {assembled_path}")
        print(f"  [assembler] pages={stats['pages']} chars={stats['chars']} media={stats['media']}")
    else:
        print(f"  [assembler] No deterministic pages to assemble.")
        print(f"  [assembler] -> {md_output}")

    if config["emit_docir"] or config["emit_chunks"]:
        print("\n  [docir] Building DocIR from deterministic backend")
        backend = DeterministicBackend()
        doc_ir = backend.extract(
            input_path,
            output_dir=output_dir,
            options={"text_threshold": config["text_threshold"]},
        )

        if config["emit_docir"]:
            docir_output = output_dir / f"{input_path.stem}.docir.json"
            write_docir(doc_ir, docir_output)
            print(f"  [docir] -> {docir_output}")

        if config["emit_chunks"]:
            chunks_output = output_dir / f"{input_path.stem}.blocks.jsonl"
            write_chunks_jsonl(doc_ir, chunks_output)
            print(f"  [chunks] -> {chunks_output}")


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    print(f"\ndoc2md - Document to Markdown Pipeline")
    print(f"{'='*60}")

    if not args.input.suffix.lower() == ".pdf":
        print(f"  [error] Input must be a PDF file, got: {args.input.suffix}")
        sys.exit(1)

    if not args.input.exists():
        print(f"  [error] File not found: {args.input}")
        sys.exit(1)

    print(f"  [input] File: {args.input}")

    config = resolve_config(args)
    output_dir = setup_output(args.input, args.output)
    run_pipeline(args.input, output_dir, config)

    print(f"\n{'='*60}")
    print(f"  [done] Pipeline complete.")
    print(f"{'='*60}\n")
