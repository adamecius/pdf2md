"""Standalone smoke test for the DeepSeek-VL2 semantic backend.

Usage:
    # One-time setup:
    conda env create -f backend/semantic/deepseek_vl2/env.yaml
    # Model download (~5.6 GB) happens on first run via Hugging Face.

    # Smoke test:
    conda run -n pdf2md-deepseek-vl2 python backend/semantic/deepseek_vl2/smoke_test.py \
        --image tests/data/<a_sample_page>.png \
        --out-dir /tmp/vlm_smoke

Acceptance (Plan 005 §5):
    exit code 0
    <out-dir>/vlm_smoke_result.json exists
    result.markers has length >= 1
    result.backend_version contains the model id
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


BACKEND_NAME = "deepseek-vl2"


def _env_check() -> str | None:
    """Return ``None`` if the env has the deps; an error string otherwise."""
    try:
        import torch  # noqa: F401 — presence check
        import transformers  # noqa: F401
        import PIL  # noqa: F401
    except ImportError as exc:
        return (
            f"missing dependency: {exc}. "
            "Create the env with: conda env create -f backend/semantic/deepseek_vl2/env.yaml"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeepSeek-VL2 semantic backend smoke test")
    parser.add_argument("--image", required=True, type=Path, help="Path to a page image (PNG/JPEG)")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--model-id", default=None, help="HF model id; default deepseek-vl2-small")
    parser.add_argument("--device", default=None, help="cuda or cpu (default: cuda if available)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not args.image.is_file():
        print(f"error: image not found: {args.image}", file=sys.stderr)
        return 2

    env_err = _env_check()
    if env_err is not None:
        print(f"env_not_ready: {env_err}", file=sys.stderr)
        return 3

    # Deferred import — only valid inside the pdf2md-deepseek-vl2 env.
    import vlm_client  # noqa: E402

    settings_kwargs: dict = {}
    if args.model_id:
        settings_kwargs["model_id"] = args.model_id
    if args.device:
        settings_kwargs["device"] = args.device
    settings = vlm_client.VlmSettings(**settings_kwargs)

    t0 = time.perf_counter()
    try:
        model, processor = vlm_client.load_model(settings)
    except Exception as exc:  # noqa: BLE001 — model load can fail many ways
        print(f"env_not_ready: model load failed: {exc}", file=sys.stderr)
        return 3
    load_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    out = vlm_client.extract_markers(
        args.image,
        model=model,
        processor=processor,
        settings=settings,
    )
    infer_ms = (time.perf_counter() - t1) * 1000.0

    result = {
        "backend": BACKEND_NAME,
        "backend_version": settings.model_id,
        "device": settings.device,
        "input_path": str(args.image),
        "load_ms": round(load_ms, 1),
        "inference_ms": round(infer_ms, 1),
        "markers": out["markers"],
        "raw_text": out["raw_text"],
        "parse_error": out["parse_error"],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "vlm_smoke_result.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    if args.verbose:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"deepseek-vl2 smoke: {len(result['markers'])} markers, "
            f"load={result['load_ms']:.0f} ms, infer={result['inference_ms']:.0f} ms, "
            f"out={out_path}"
        )

    if result["parse_error"]:
        print(f"warning: {result['parse_error']}", file=sys.stderr)

    if len(result["markers"]) < 1:
        print("error: DeepSeek-VL2 returned no markers", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
