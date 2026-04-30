#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


TEXT_KEYS = {"rec_text", "text", "transcription", "label"}


def parser():
    p = argparse.ArgumentParser(description="Convert PDF to Markdown via PaddleOCR CLI (local).")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--json-out")
    p.add_argument("--out-dir")
    p.add_argument("--lang", default="en")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--model-path")
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("--api", action="store_true")
    return p


def validate_input_pdf(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file() or p.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {p}")
    return p


def plan_paddleocr_command(input_pdf: Path, out_dir: Path, lang: str, device: str) -> list[str]:
    cmd = ["paddleocr", "ocr", "-i", str(input_pdf), "--save_path", str(out_dir), "--lang", lang,
           "--use_doc_orientation_classify", "False", "--use_doc_unwarping", "False", "--use_textline_orientation", "False"]
    if device == "cpu":
        cmd.extend(["--device", "cpu"])
    elif device == "cuda":
        cmd.extend(["--device", "gpu:0"])
    return cmd


def _extract_text(node, out: list[str]) -> None:
    if isinstance(node, str):
        if node.strip():
            out.append(node.strip())
        return
    if isinstance(node, dict):
        for k, v in node.items():
            if k in TEXT_KEYS and isinstance(v, str) and v.strip():
                out.append(v.strip())
            else:
                _extract_text(v, out)
        return
    if isinstance(node, list):
        for item in node:
            _extract_text(item, out)


def extract_text_from_json_files(out_dir: Path) -> list[str]:
    lines: list[str] = []
    for j in sorted(out_dir.rglob("*.json")):
        try:
            payload = json.loads(j.read_text(encoding="utf-8"))
        except Exception:
            continue
        _extract_text(payload, lines)
    return lines


def main() -> int:
    a = parser().parse_args()
    try:
        ip = validate_input_pdf(a.input)
        if a.api:
            raise RuntimeError("API mode is not implemented for PaddleOCR wrapper.")
        if a.allow_download:
            raise RuntimeError("--allow-download is not implemented for PaddleOCR wrapper. PaddleOCR may manage its own model cache depending on installation.")

        out_md = Path(a.output).expanduser().resolve() if a.output else ip.with_suffix(".md")
        out_dir = Path(a.out_dir).expanduser().resolve() if a.out_dir else (out_md.parent / f"{out_md.stem}_paddleocr")
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = plan_paddleocr_command(ip, out_dir, a.lang, a.device)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"paddleocr failed with code {result.returncode}")

        lines = extract_text_from_json_files(out_dir)
        if not lines:
            raise RuntimeError("PaddleOCR completed but no recognised text could be extracted from generated JSON files.")

        out_md.write_text("\n\n".join(lines).strip() + "\n", encoding="utf-8")
        if a.json_out:
            Path(a.json_out).write_text(json.dumps({"backend": "paddleocr", "input": str(ip), "output_md": str(out_md), "paddleocr_output_dir": str(out_dir), "command": cmd, "returncode": result.returncode}, indent=2), encoding="utf-8")
        print(str(out_md))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
