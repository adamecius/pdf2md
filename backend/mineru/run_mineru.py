from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def validate_pdf(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file() or p.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {p}")
    return p


def build_mineru_command(*, input_pdf: Path, output_dir: Path, lang: str, backend: str, api_url: str | None) -> list[str]:
    cmd = ["mineru", "-p", str(input_pdf), "-o", str(output_dir)]
    if backend:
        cmd.extend(["-b", backend])
    if lang:
        cmd.extend(["-l", lang])
    if api_url:
        cmd.extend(["--api-url", api_url])
    return cmd


def select_markdown(output_dir: Path, input_stem: str) -> Path:
    by_stem = sorted(output_dir.rglob(f"{input_stem}.md"))
    if len(by_stem) == 1:
        return by_stem[0]
    if len(by_stem) > 1:
        raise RuntimeError(f"MinerU generated multiple markdown files matching stem '{input_stem}' under: {output_dir}")
    all_md = sorted(output_dir.rglob("*.md"))
    if len(all_md) == 1:
        return all_md[0]
    if not all_md:
        raise RuntimeError(f"MinerU completed but no markdown found under: {output_dir}")
    raise RuntimeError(f"MinerU generated multiple markdown files under {output_dir}; unable to choose safely.")


def run_mineru_cli(*, input_path: str | Path, output_path: str | Path | None, out_dir: str | Path | None, json_out: str | Path | None, lang: str, device: str, model_path: str | None, allow_download: bool, api: bool, backend: str, api_url: str | None) -> Path:
    input_pdf = validate_pdf(input_path)
    if allow_download:
        raise RuntimeError("--allow-download is not implemented for MinerU wrapper. Configure MinerU model source/cache explicitly.")
    if api and not api_url:
        raise RuntimeError("API mode requires --api-url explicitly.")
    if device in {"cpu", "cuda"}:
        print("warning: MinerU device selection is controlled by MinerU/backend runtime (e.g., CUDA_VISIBLE_DEVICES).", flush=True)

    out_md = Path(output_path).expanduser().resolve() if output_path else input_pdf.with_suffix(".md")
    mineru_out = Path(out_dir).expanduser().resolve() if out_dir else (out_md.parent / f"{out_md.stem}_mineru_output")
    mineru_out.mkdir(parents=True, exist_ok=True)

    cmd = build_mineru_command(input_pdf=input_pdf, output_dir=mineru_out, lang=lang, backend=backend, api_url=api_url)
    env = os.environ.copy()
    if model_path:
        env["MINERU_MODEL_PATH"] = model_path

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"mineru failed with code {result.returncode}")

    selected = select_markdown(mineru_out, input_pdf.stem)
    shutil.copyfile(selected, out_md)

    if json_out:
        Path(json_out).write_text(json.dumps({"backend": "mineru", "input": str(input_pdf), "output_md": str(out_md), "mineru_output_dir": str(mineru_out), "selected_markdown": str(selected), "command": cmd, "returncode": result.returncode}, indent=2), encoding="utf-8")
    return out_md
