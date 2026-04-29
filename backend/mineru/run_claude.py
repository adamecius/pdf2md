"""pdf2md.py — convert a single PDF to Markdown using MinerU's pipeline backend.

Usage
-----
    python pdf2md.py paper.pdf                       # -> ./paper.md + ./paper_images/
    python pdf2md.py paper.pdf -o out/notes.md       # custom output path
    python pdf2md.py paper.pdf --lang es             # Spanish OCR
    python pdf2md.py paper.pdf --device cpu          # force CPU
    python pdf2md.py paper.pdf --keep-all            # also keep JSON + layout PDF

The wrapper runs mineru into a temp directory, then lifts out just the Markdown
and the images, renaming the image folder to <stem>_images/ and rewriting the
Markdown's relative paths so the references stay valid.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def detect_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def find_mineru() -> str:
    exe = shutil.which("mineru")
    if exe is None:
        sys.exit("error: `mineru` CLI not found — activate the env first "
                 "(source .venv/bin/activate  or  conda activate mineru-backend)")
    return exe


def rewrite_image_paths(md_text: str, new_dirname: str) -> str:
    """Replace mineru's `images/...` references with `<new_dirname>/...`.

    Covers Markdown image syntax `![alt](images/foo.jpg)` and the (rare) HTML
    `<img src="images/foo.jpg">` form.
    """
    md_text = re.sub(r"\]\(images/", f"]({new_dirname}/", md_text)
    md_text = re.sub(r'src="images/', f'src="{new_dirname}/', md_text)
    return md_text


def convert(pdf: Path, out_md: Path, lang: str, device: str, keep_all: bool) -> int:
    if not pdf.is_file():
        sys.exit(f"error: input is not a file: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        sys.exit(f"error: input must be a .pdf (got {pdf.suffix}): {pdf}")

    out_md = out_md.resolve()
    out_dir = out_md.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dirname = f"{out_md.stem}_images"

    mineru = find_mineru()

    with tempfile.TemporaryDirectory(prefix="mineru_") as tmp:
        tmp_out = Path(tmp)
        cmd = [
            mineru,
            "-p", str(pdf),
            "-o", str(tmp_out),
            "-b", "pipeline",
            "-d", device,
            "-l", lang,
        ]
        print(f"[1/3] running mineru on {device}…", file=sys.stderr)
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"error: mineru exited with code {rc}", file=sys.stderr)
            return rc

        # Expected layout: <tmp>/<stem>/auto/<stem>.md  (+ images/, *.json, *.pdf)
        stem = pdf.stem
        produced_dir = tmp_out / stem / "auto"
        produced_md = produced_dir / f"{stem}.md"

        # Defensive fallback for layout drift across mineru versions.
        if not produced_md.exists():
            candidates = list(tmp_out.rglob("*.md"))
            if not candidates:
                sys.exit(f"error: mineru produced no Markdown under {tmp_out}")
            produced_md = candidates[0]
            produced_dir = produced_md.parent

        print("[2/3] rewriting image paths and copying assets…", file=sys.stderr)
        md_text = produced_md.read_text(encoding="utf-8")
        out_md.write_text(rewrite_image_paths(md_text, images_dirname),
                          encoding="utf-8")

        images_src = produced_dir / "images"
        if images_src.is_dir() and any(images_src.iterdir()):
            images_dst = out_dir / images_dirname
            if images_dst.exists():
                shutil.rmtree(images_dst)
            shutil.copytree(images_src, images_dst)

        if keep_all:
            aux = out_dir / f"{out_md.stem}_aux"
            if aux.exists():
                shutil.rmtree(aux)
            shutil.copytree(produced_dir, aux)
            print(f"[+] kept full output tree at {aux}", file=sys.stderr)

    print(f"[3/3] wrote {out_md}", file=sys.stderr)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description="Convert a single PDF to Markdown via the MinerU pipeline backend.")
    p.add_argument("pdf", type=Path, help="path to the input PDF")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="output .md path (default: ./<stem>.md)")
    p.add_argument("-l", "--lang", default="en",
                   help="OCR language hint, e.g. en, ch, es (default: en)")
    p.add_argument("-d", "--device", choices=["auto", "cuda", "cpu"], default="auto",
                   help="device to run on (default: auto-detect)")
    p.add_argument("--keep-all", action="store_true",
                   help="keep mineru's full output tree (JSON, layout PDF) "
                        "in <stem>_aux/")
    args = p.parse_args()

    out = args.output or (Path.cwd() / f"{args.pdf.stem}.md")
    device = detect_device() if args.device == "auto" else args.device
    sys.exit(convert(args.pdf, out, args.lang, device, args.keep_all))


if __name__ == "__main__":
    main()
