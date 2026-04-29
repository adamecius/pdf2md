#!/usr/bin/env python3
"""DeepSeek-OCR PDF -> Markdown + JSON (standalone, minimal).

You can pass either:
- --repo-path /local/path/to/DeepSeek-OCR
- --repo-path https://github.com/deepseek-ai/DeepSeek-OCR

If a Git URL is passed, the repo is cloned into `.cache/deepseek-ocr` first.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


DEFAULT_REPO_URL = "https://github.com/deepseek-ai/DeepSeek-OCR"


def is_git_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://") or value.startswith("git@")


def ensure_repo(repo_value: str | None) -> Path:
    if not repo_value:
        env_repo = os.getenv("DEEPSEEK_OCR_REPO")
        if not env_repo:
            raise EnvironmentError("Set DEEPSEEK_OCR_REPO or pass --repo-path")
        repo_value = env_repo

    if is_git_url(repo_value):
        repo_dir = Path(".cache/deepseek-ocr").resolve()
        if not (repo_dir / ".git").exists():
            repo_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", repo_value, str(repo_dir)], check=True)
        else:
            subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only"], check=True)
        return repo_dir

    repo_path = Path(repo_value).expanduser().resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")
    return repo_path


def run_deepseek_ocr(repo_path: Path, input_pdf: Path, output_dir: Path, script_path: str | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    run_script = repo_path / (script_path or "run_deepseek_ocr.py")
    if not run_script.exists():
        raise FileNotFoundError(
            "Could not find DeepSeek-OCR entry script. "
            f"Looked for: {run_script}. Pass --script-path if needed."
        )

    cmd = ["python", str(run_script), "--input", str(input_pdf), "--output", str(output_dir)]
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
        help=(
            "Local DeepSeek-OCR path OR git URL. "
            f"Example: {DEFAULT_REPO_URL}"
        ),
    )
    parser.add_argument("--script-path", default=None, help="Entrypoint inside the repo, e.g. scripts/run_ocr.py")
    args = parser.parse_args()

    input_pdf = Path(args.input).expanduser().resolve()
    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {input_pdf}")

    repo_path = ensure_repo(args.repo_path)

    out_dir = Path(args.output).expanduser().resolve()
    run_deepseek_ocr(repo_path=repo_path, input_pdf=input_pdf, output_dir=out_dir, script_path=args.script_path)
    md_path, json_path = normalize_outputs(input_pdf=input_pdf, output_dir=out_dir)

    print("✅ Conversion complete")
    print(f"Repo: {repo_path}")
    print(f"Markdown: {md_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
