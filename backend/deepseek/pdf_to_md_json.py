#!/usr/bin/env python3
"""DeepSeek-OCR PDF -> Markdown + JSON (standalone, minimal).

This wrapper runs the official DeepSeek-OCR repository code, then normalizes
outputs to:
- <name>.md
- <name>.json

Requirements:
- Clone https://github.com/deepseek-ai/DeepSeek-OCR
- Set DEEPSEEK_OCR_REPO to that local path (or pass --repo-path)
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run_deepseek_ocr(repo_path: Path, input_pdf: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Typical inference entrypoint in the official repo.
    run_script = repo_path / "run_deepseek_ocr.py"
    if not run_script.exists():
        raise FileNotFoundError(
            f"Could not find {run_script}. Pass --script-path if your clone uses a different entrypoint."
        )

    cmd = [
        "python",
        str(run_script),
        "--input",
        str(input_pdf),
        "--output",
        str(output_dir),
    ]
    subprocess.run(cmd, check=True, cwd=repo_path)
    return output_dir


def normalize_outputs(input_pdf: Path, output_dir: Path) -> tuple[Path, Path]:
    stem = input_pdf.stem

    md_candidates = sorted(output_dir.glob(f"{stem}*.md")) + sorted(output_dir.glob("*.md"))
    if not md_candidates:
        raise FileNotFoundError(f"No markdown output found in {output_dir}")

    md_path = output_dir / f"{stem}.md"
    md_text = md_candidates[0].read_text(encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")

    json_path = output_dir / f"{stem}.json"
    payload = {
        "backend": "deepseek-ocr",
        "source_pdf": str(input_pdf),
        "markdown_file": str(md_path),
        "markdown": md_text,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek-OCR PDF -> Markdown + JSON")
    parser.add_argument("-i", "--input", required=True, help="Input PDF path")
    parser.add_argument("-o", "--output", default="deepseek_output", help="Output directory")
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Local clone of deepseek-ai/DeepSeek-OCR (required if DEEPSEEK_OCR_REPO not set)",
    )
    args = parser.parse_args()

    input_pdf = Path(args.input).expanduser().resolve()
    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {input_pdf}")

    if args.repo_path:
        repo_path = Path(args.repo_path).expanduser().resolve()
    else:
        import os

        env_repo = os.getenv("DEEPSEEK_OCR_REPO")
        if not env_repo:
            raise EnvironmentError("Set DEEPSEEK_OCR_REPO or pass --repo-path")
        repo_path = Path(env_repo).expanduser().resolve()

    out_dir = Path(args.output).expanduser().resolve()
    run_deepseek_ocr(repo_path=repo_path, input_pdf=input_pdf, output_dir=out_dir)
    md_path, json_path = normalize_outputs(input_pdf=input_pdf, output_dir=out_dir)

    print("✅ Conversion complete")
    print(f"Markdown: {md_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
