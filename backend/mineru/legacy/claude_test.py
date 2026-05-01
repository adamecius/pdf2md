if __name__ != "__main__":
    import pytest
    pytest.skip("integration script; requires external backend dependencies", allow_module_level=True)

"""End-to-end smoke test for the MinerU pipeline backend.

Synthesizes a one-page PDF in-process (no external test fixtures), runs the
mineru pipeline on it, and asserts that valid Markdown comes out the other
side. Does NOT grade OCR accuracy — passing means the install, model load,
and parsing pipeline all run without errors.

Run after install:
    python test_smoke.py

Note: the first invocation on a fresh machine downloads ~5 GB of pipeline
models into ~/.mineru/models/. Subsequent runs are much faster.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WORKDIR = Path(__file__).parent / "smoke_test_workdir"


def make_test_pdf(path: Path) -> None:
    """Render a synthetic page with PIL and save as a 1-page PDF."""
    img = Image.new("RGB", (1240, 1754), "white")  # ~A4 at 150 dpi
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except OSError:
        # Fallback for systems without DejaVu — still produces valid input,
        # just at a smaller default font size.
        font = ImageFont.load_default()
    text = (
        "MinerU Pipeline Smoke Test\n\n"
        "This is a synthetic test document.\n"
        "If this text round-trips into Markdown,\n"
        "the pipeline backend is healthy.\n\n"
        "Equation: E = m * c^2\n"
        "Reference number: 42"
    )
    draw.multiline_text((80, 100), text, fill="black", font=font, spacing=18)
    img.save(path, "PDF", resolution=150.0)


def detect_device() -> str:
    """Return 'cuda' if torch sees a GPU, else 'cpu'."""
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def main() -> int:
    # 1. Locate mineru
    mineru = shutil.which("mineru")
    if mineru is None:
        print("FAIL: `mineru` CLI not on PATH — activate the env first",
              file=sys.stderr)
        return 1

    # 2. Set up a clean workdir
    if WORKDIR.exists():
        shutil.rmtree(WORKDIR)
    in_dir = WORKDIR / "in"
    out_dir = WORKDIR / "out"
    in_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    pdf = in_dir / "smoke.pdf"
    make_test_pdf(pdf)
    print(f"[1/3] synthesized {pdf} ({pdf.stat().st_size} bytes)")

    # 3. Run the pipeline
    device = detect_device()
    print(f"[2/3] running mineru pipeline on {device} "
          f"(first run downloads models, this can take several minutes)...")
    rc = subprocess.call([
        mineru,
        "-p", str(in_dir),
        "-o", str(out_dir),
        "-b", "pipeline",
        "-d", device,
        "-l", "en",
    ])
    if rc != 0:
        print(f"FAIL: mineru exited with code {rc}", file=sys.stderr)
        return rc

    # 4. Verify output
    md_files = list(out_dir.rglob("*.md"))
    if not md_files:
        print(f"FAIL: no Markdown output found under {out_dir}", file=sys.stderr)
        return 1
    md = md_files[0]
    size = md.stat().st_size
    if size == 0:
        print(f"FAIL: output Markdown is empty: {md}", file=sys.stderr)
        return 1

    print(f"[3/3] OK — wrote {md} ({size} bytes)")
    print("\n--- markdown preview (first 400 chars) ---")
    print(md.read_text(encoding="utf-8")[:400])
    print("------------------------------------------")
    print("\nSMOKE TEST: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
