#!/usr/bin/env python3
"""pdf2md_mineru.py — Convert PDF to Markdown using MinerU (CLI wrapper).

Single-file wrapper that calls the `mineru` CLI, collects the output
markdown, and copies it to the requested destination.  No Python-level
import of MinerU internals — only subprocess invocation.

Usage:
  pdf2md_mineru.py -i paper.pdf                     # → paper.md
  pdf2md_mineru.py -i paper.pdf -o out.md           # explicit output
  pdf2md_mineru.py -i paper.pdf -b pipeline         # CPU-only backend
  pdf2md_mineru.py -i paper.pdf --api-url http://…  # remote VLM server
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BACKENDS = [
    "hybrid-auto-engine",   # default in MinerU ≥3.0 (pipeline + VLM)
    "pipeline",             # CPU-friendly, no VLM needed
    "vlm-auto-engine",      # VLM-only (8 GB+ VRAM)
    "vlm-http-client",      # lightweight remote client (no local torch)
    "hybrid-http-client",   # remote VLM + local pipeline
]

LANGUAGES = [
    "ch", "ch_server", "ch_lite", "en", "korean", "japan",
    "chinese_cht", "ta", "te", "ka", "th", "el",
    "latin", "arabic", "east_slavic", "cyrillic", "devanagari",
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert a PDF to Markdown using MinerU.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # GPU-accelerated (default: hybrid-auto-engine)
  %(prog)s -i paper.pdf

  # CPU-only pipeline backend
  %(prog)s -i paper.pdf -b pipeline

  # VLM via a remote server
  %(prog)s -i paper.pdf -b vlm-http-client --api-url http://gpu:30000

  # Specify output paths
  %(prog)s -i paper.pdf -o paper.md --json-out meta.json

  # Parse only pages 5–10
  %(prog)s -i paper.pdf --start 5 --end 10
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
        help="Directory for MinerU intermediate output.  "
             "Default: <output_stem>_mineru_output/ next to the output .md.",
    )
    gio.add_argument(
        "--json-out", metavar="JSON",
        help="Write a JSON metadata sidecar to this path.",
    )

    # -- Backend --
    gbe = p.add_argument_group("backend")
    gbe.add_argument(
        "-b", "--backend", default="hybrid-auto-engine", choices=BACKENDS,
        help="MinerU parsing backend (default: %(default)s).",
    )
    gbe.add_argument(
        "--api-url", metavar="URL",
        help="MinerU API / OpenAI-compatible server URL.  "
             "Required for *-http-client backends; optional for auto-engine "
             "(if omitted, mineru starts a temporary local service).",
    )

    # -- Parsing options --
    gpo = p.add_argument_group("parsing options")
    gpo.add_argument(
        "-l", "--lang", default=None, choices=LANGUAGES, metavar="LANG",
        help="Document language hint for OCR (pipeline/hybrid backends). "
             "Default: auto-detected.",
    )
    gpo.add_argument(
        "-m", "--method", default=None, choices=["auto", "txt", "ocr"],
        help="Parsing method (pipeline/hybrid only). Default: auto.",
    )
    gpo.add_argument(
        "-s", "--start", type=int, default=None, metavar="N",
        help="Starting page number (0-based).",
    )
    gpo.add_argument(
        "-e", "--end", type=int, default=None, metavar="N",
        help="Ending page number (0-based).",
    )
    gpo.add_argument(
        "--formula", choices=["true", "false"], default=None,
        help="Enable/disable formula parsing (default: enabled).",
    )
    gpo.add_argument(
        "--table", choices=["true", "false"], default=None,
        help="Enable/disable table parsing (default: enabled).",
    )

    # -- Environment --
    genv = p.add_argument_group("environment")
    genv.add_argument(
        "--source", choices=["huggingface", "modelscope", "local"], default=None,
        help="Model source override (sets MINERU_MODEL_SOURCE for this run).",
    )
    genv.add_argument(
        "--keep-output", action="store_true",
        help="Keep the full MinerU output directory (images, content_list, "
             "etc.) after extracting the markdown.",
    )

    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def validate_input(path: str) -> Path:
    """Validate that the input is an existing PDF."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Input file does not exist: {p}")
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a .pdf file, got: {p.suffix}")
    return p


def build_mineru_cmd(
    *,
    input_pdf: Path,
    output_dir: Path,
    backend: str,
    lang: str | None,
    method: str | None,
    api_url: str | None,
    start: int | None,
    end: int | None,
    formula: str | None,
    table: str | None,
) -> list[str]:
    """Build the `mineru` CLI command list."""
    cmd = ["mineru", "-p", str(input_pdf), "-o", str(output_dir)]
    cmd.extend(["-b", backend])

    if lang:
        cmd.extend(["-l", lang])
    if method:
        cmd.extend(["-m", method])
    if api_url:
        cmd.extend(["--api-url", api_url])
    if start is not None:
        cmd.extend(["-s", str(start)])
    if end is not None:
        cmd.extend(["-e", str(end)])
    if formula is not None:
        cmd.extend(["-f", formula])
    if table is not None:
        cmd.extend(["-t", table])

    return cmd


def find_output_markdown(output_dir: Path, input_stem: str) -> Path:
    """Locate the generated markdown file inside MinerU's output tree.

    MinerU typically writes  <output_dir>/<stem>/<stem>.md  or similar.
    We search by stem match first, then fall back to any single .md file.
    """
    # Exact stem match (may be nested)
    by_stem = sorted(output_dir.rglob(f"{input_stem}.md"))
    if len(by_stem) == 1:
        return by_stem[0]
    if len(by_stem) > 1:
        # Prefer the shortest (shallowest) path
        return min(by_stem, key=lambda p: len(p.parts))

    # Fallback: any .md
    all_md = sorted(output_dir.rglob("*.md"))
    if len(all_md) == 1:
        return all_md[0]
    if not all_md:
        raise FileNotFoundError(
            f"MinerU completed but no .md file found under: {output_dir}"
        )
    # Multiple .md files, none matching stem — pick shallowest
    return min(all_md, key=lambda p: len(p.parts))


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def run(
    *,
    input_pdf: Path,
    output_md: Path,
    mineru_out: Path,
    backend: str,
    lang: str | None,
    method: str | None,
    api_url: str | None,
    start: int | None,
    end: int | None,
    formula: str | None,
    table: str | None,
    source: str | None,
    keep_output: bool,
    json_out: Path | None,
) -> Path:
    """Run MinerU and collect the output markdown."""
    mineru_out.mkdir(parents=True, exist_ok=True)

    cmd = build_mineru_cmd(
        input_pdf=input_pdf,
        output_dir=mineru_out,
        backend=backend,
        lang=lang,
        method=method,
        api_url=api_url,
        start=start,
        end=end,
        formula=formula,
        table=table,
    )

    env = os.environ.copy()
    if source:
        env["MINERU_MODEL_SOURCE"] = source

    print(f"[mineru] Running: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"mineru exited with code {result.returncode}:\n{stderr}"
        )

    # Locate and copy the markdown
    selected = find_output_markdown(mineru_out, input_pdf.stem)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(selected, output_md)
    print(f"[out]   Markdown → {output_md}")

    # JSON sidecar
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(
                {
                    "backend": "mineru",
                    "mineru_backend": backend,
                    "input": str(input_pdf),
                    "output_md": str(output_md),
                    "mineru_output_dir": str(mineru_out),
                    "selected_markdown": str(selected),
                    "command": cmd,
                    "returncode": result.returncode,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[out]   JSON    → {json_out}")

    # Cleanup intermediate output
    if not keep_output and mineru_out.exists():
        shutil.rmtree(mineru_out, ignore_errors=True)

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

    # Validate http-client backends need --api-url
    if "http-client" in args.backend and not args.api_url:
        print(
            f"error: Backend '{args.backend}' requires --api-url.",
            file=sys.stderr,
        )
        return 1

    # Resolve output paths
    output_md = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_pdf.with_suffix(".md")
    )
    mineru_out = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else output_md.parent / f"{output_md.stem}_mineru_output"
    )
    json_out = Path(args.json_out).expanduser().resolve() if args.json_out else None

    try:
        out = run(
            input_pdf=input_pdf,
            output_md=output_md,
            mineru_out=mineru_out,
            backend=args.backend,
            lang=args.lang,
            method=args.method,
            api_url=args.api_url,
            start=args.start,
            end=args.end,
            formula=args.formula,
            table=args.table,
            source=args.source,
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