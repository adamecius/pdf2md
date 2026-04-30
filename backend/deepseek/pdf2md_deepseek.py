#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-OCR-2"
DEFAULT_MODELS_DIR = ".local_models/deepseek"


def parser():
    p = argparse.ArgumentParser(description="Convert PDF to Markdown with DeepSeek OCR (local first).")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--json-out")
    p.add_argument("--out-dir")
    p.add_argument("--lang", default="en")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--model-path")
    p.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    p.add_argument("--models-dir", default=DEFAULT_MODELS_DIR)
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("--api", action="store_true")
    return p


def safe_model_dir_name(model_id: str) -> str:
    return model_id.replace("/", "__")


def default_model_path(model_id: str, models_dir: str) -> Path:
    return Path(models_dir).expanduser().resolve() / safe_model_dir_name(model_id)


def resolve_local_model_path(model_path: str | None, model_id: str, models_dir: str) -> tuple[Path | None, list[str]]:
    looked: list[str] = []
    if model_path:
        candidate = Path(model_path).expanduser().resolve()
        looked.append(str(candidate))
        if candidate.exists():
            return candidate, looked

    env_path = os.getenv("PDF2MD_DEEPSEEK_MODEL")
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        looked.append(str(candidate))
        if candidate.exists():
            return candidate, looked

    candidate = default_model_path(model_id=model_id, models_dir=models_dir)
    looked.append(str(candidate))
    if candidate.exists():
        return candidate, looked

    return None, looked


def explicit_download_model(*, model_id: str, models_dir: str) -> Path:
    from huggingface_hub import snapshot_download

    local_dir = default_model_path(model_id=model_id, models_dir=models_dir)
    local_dir.parent.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=model_id, local_dir=str(local_dir), local_dir_use_symlinks=False)
    return local_dir


def _missing_model_message(looked: list[str]) -> str:
    looked_lines = "\n".join(f"  - {p}" for p in looked)
    return (
        "error: Missing local DeepSeek model.\n"
        f"Looked in:\n{looked_lines}\n"
        "Provide an explicit local model path with --model-path /path/to/model\n"
        "or set PDF2MD_DEEPSEEK_MODEL=/path/to/model.\n"
        "To explicitly download once into .local_models, pass --allow-download."
    )


def main():
    a = parser().parse_args()
    ip = Path(a.input).expanduser().resolve()
    if not ip.exists() or ip.suffix.lower() != ".pdf":
        print(f"error: Input must be an existing PDF file: {ip}", file=sys.stderr)
        return 1

    if a.api:
        print(
            "error: API mode exists only if separately implemented; this wrapper requires explicit local model path.",
            file=sys.stderr,
        )
        return 1

    model_dir, looked = resolve_local_model_path(a.model_path, a.model_id, a.models_dir)
    if model_dir is None and not a.allow_download:
        print(_missing_model_message(looked), file=sys.stderr)
        return 1

    if model_dir is None and a.allow_download:
        try:
            model_dir = explicit_download_model(model_id=a.model_id, models_dir=a.models_dir)
        except Exception as e:
            print(f"error: Failed explicit model download: {e}", file=sys.stderr)
            return 1

    try:
        from pdf_to_md_json import run
    except Exception as e:
        print(f"error: Failed to import local deepseek backend dependency: {e}", file=sys.stderr)
        return 1

    out_md = Path(a.output).expanduser().resolve() if a.output else ip.with_suffix(".md")
    out_dir = Path(a.out_dir).expanduser().resolve() if a.out_dir else out_md.parent
    dev = "cpu" if a.device == "auto" else a.device
    try:
        md, _ = run(ip, out_dir, str(model_dir), dev, local_only=True)
        out_md.write_text(md.read_text(encoding="utf-8"), encoding="utf-8")
        if a.json_out:
            Path(a.json_out).write_text(
                json.dumps({"backend": "deepseek", "input": str(ip), "model_path": str(model_dir)}), encoding="utf-8"
            )
        print(str(out_md))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
