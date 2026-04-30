"""Ready-to-run MinerU pipeline backend.

Parses every PDF / image / DOCX / PPTX / XLSX inside an input directory using
the `pipeline` backend (the CPU/GPU classical pipeline, not the VLM model) and
writes Markdown + JSON to an output directory.

Usage
-----
    python run_pipeline.py                       # uses ./data/pdfs -> ./data/output
    python run_pipeline.py -i path/to/input      # custom input dir
    python run_pipeline.py -i in -o out --lang en

The script invokes the official `mineru` CLI under the hood, which is the
most stable integration point — the Python API (`mineru.cli.common.do_parse`)
exists but its signature is not part of the stability contract across minor
versions.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_gpu() -> str:
    """Return 'cuda' if a CUDA-enabled torch sees a GPU, else 'cpu'."""
    try:
        import torch
    except ImportError:
        print("[warn] torch is not installed; falling back to CPU", file=sys.stderr)
        return "cpu"

    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        cc = torch.cuda.get_device_capability(0)
        print(f"[info] CUDA device: {name} (compute capability {cc[0]}.{cc[1]})")
        # MinerU pipeline backend works on any CUDA-capable card; the CC>=7.0
        # requirement only applies to the vllm/lmdeploy VLM backends.
        return "cuda"
    print("[info] no CUDA device found; running on CPU")
    return "cpu"


def ensure_mineru_on_path() -> str:
    """Locate the mineru CLI, raising a clear error if it is missing."""
    exe = shutil.which("mineru")
    if exe is None:
        sys.exit(
            "error: `mineru` CLI not found on PATH.\n"
            "       activate the venv/conda env first, e.g. `source .venv/bin/activate`."
        )
    return exe


def run(input_dir: Path, output_dir: Path, lang: str, device: str) -> int:
    """Invoke the mineru CLI with the pipeline backend."""
    if not input_dir.exists():
        sys.exit(f"error: input directory does not exist: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    mineru = ensure_mineru_on_path()
    cmd = [
        mineru,
        "-p", str(input_dir),
        "-o", str(output_dir),
        "-b", "pipeline",
        "-d", device,        # 'cuda' or 'cpu'
        "-l", lang,          # OCR language hint, e.g. 'en', 'ch', 'es'
    ]
    print(f"[run] {' '.join(cmd)}")
    # Stream stdout/stderr live so long parses give feedback.
    return subprocess.call(cmd, env=os.environ.copy())


def main() -> None:
    parser = argparse.ArgumentParser(description="MinerU pipeline runner")
    parser.add_argument("-i", "--input",  default="data/pdfs",   help="input dir")
    parser.add_argument("-o", "--output", default="data/output", help="output dir")
    parser.add_argument("-l", "--lang",   default="en",
                        help="OCR language hint (en, ch, es, ...)")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto",
                        help="device to run on (default: auto-detect)")
    args = parser.parse_args()

    device = check_gpu() if args.device == "auto" else args.device
    rc = run(Path(args.input), Path(args.output), args.lang, device)
    sys.exit(rc)


if __name__ == "__main__":
    main()
