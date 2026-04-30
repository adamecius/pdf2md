from __future__ import annotations

import json
import subprocess
from pathlib import Path

TEXT_KEYS = {"rec_text", "text", "transcription", "label"}


def validate_pdf(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file() or p.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be an existing PDF file: {p}")
    return p


def build_paddleocr_command(*, input_pdf: Path, output_dir: Path, lang: str, device: str) -> list[str]:
    cmd = ["paddleocr", "ocr", "-i", str(input_pdf), "--save_path", str(output_dir), "--lang", lang,
           "--use_doc_orientation_classify", "False", "--use_doc_unwarping", "False", "--use_textline_orientation", "False"]
    if device == "cpu":
        cmd.extend(["--device", "cpu"])
    elif device == "cuda":
        cmd.extend(["--device", "gpu:0"])
    return cmd


def _extract(node, out: list[str]) -> None:
    if isinstance(node, str):
        t = node.strip()
        if t:
            out.append(t)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in TEXT_KEYS and isinstance(v, str) and v.strip():
                out.append(v.strip())
            else:
                _extract(v, out)
    elif isinstance(node, list):
        for item in node:
            _extract(item, out)


def extract_text_from_json(output_dir: Path) -> list[str]:
    lines: list[str] = []
    for p in sorted(output_dir.rglob("*.json")):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        _extract(payload, lines)
    return lines


def run_paddleocr_cli(*, input_path: str | Path, output_path: str | Path | None, out_dir: str | Path | None, json_out: str | Path | None, lang: str, device: str, model_path: str | None, allow_download: bool, api: bool) -> Path:
    _ = model_path
    ip = validate_pdf(input_path)
    if api:
        raise RuntimeError("API mode is not implemented for PaddleOCR wrapper.")
    if allow_download:
        raise RuntimeError("--allow-download is not implemented for PaddleOCR wrapper. PaddleOCR may manage its own cache depending on installation.")

    out_md = Path(output_path).expanduser().resolve() if output_path else ip.with_suffix(".md")
    pod = Path(out_dir).expanduser().resolve() if out_dir else (out_md.parent / f"{out_md.stem}_paddleocr_output")
    pod.mkdir(parents=True, exist_ok=True)

    cmd = build_paddleocr_command(input_pdf=ip, output_dir=pod, lang=lang, device=device)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip() or f"paddleocr failed with code {r.returncode}")

    lines = extract_text_from_json(pod)
    if not lines:
        raise RuntimeError("PaddleOCR completed but no recognised text could be extracted from generated JSON files.")
    out_md.write_text("\n\n".join(lines).strip() + "\n", encoding="utf-8")
    if json_out:
        Path(json_out).write_text(json.dumps({"backend": "paddleocr", "input": str(ip), "output_md": str(out_md), "paddleocr_output_dir": str(pod), "command": cmd, "returncode": r.returncode}, indent=2), encoding="utf-8")
    return out_md
