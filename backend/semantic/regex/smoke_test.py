"""Standalone smoke test for the regex semantic backend.

Usage:
    python backend/semantic/regex/smoke_test.py \
        --text tests/data/semantic_fixtures/sample_text.txt \
        --out-dir /tmp/regex_smoke

Acceptance (Plan 005 §5):
    exit code 0
    <out-dir>/regex_smoke_result.json exists
    result.markers contains ≥3 distinct marker_type values
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Make this script runnable without installing anything: add this file's
# parent directory to sys.path so `import patterns` resolves locally.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import patterns  # noqa: E402 — intentional local import


BACKEND_NAME = "regex"
BACKEND_VERSION = "0.1.0"


def run_smoke(text_path: Path, out_dir: Path) -> dict:
    """Run the regex backend against ``text_path`` and write a result file.

    Args:
        text_path: Path to a UTF-8 plain-text file.
        out_dir: Directory to write ``regex_smoke_result.json`` into.
            Created if missing.

    Returns:
        The result dict that was written to disk.
    """
    text = text_path.read_text(encoding="utf-8")
    t0 = time.perf_counter()
    hits = patterns.find_markers(text)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    result = {
        "backend": BACKEND_NAME,
        "backend_version": BACKEND_VERSION,
        "input_path": str(text_path),
        "input_chars": len(text),
        "elapsed_ms": round(elapsed_ms, 3),
        "markers": [
            {
                "marker_type": h.marker_type,
                "marker_text": h.marker_text,
                "char_offset": list(h.char_offset),
            }
            for h in hits
        ],
        "counts_by_type": patterns.summarise_by_type(hits),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "regex_smoke_result.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regex semantic backend smoke test")
    parser.add_argument("--text", required=True, type=Path, help="Path to plain-text input")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not args.text.is_file():
        print(f"error: text file not found: {args.text}", file=sys.stderr)
        return 2

    result = run_smoke(args.text, args.out_dir)

    distinct_types = len(result["counts_by_type"])
    if args.verbose:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"regex smoke: {len(result['markers'])} markers, "
            f"{distinct_types} distinct types, "
            f"{result['elapsed_ms']:.2f} ms, "
            f"out={args.out_dir/'regex_smoke_result.json'}"
        )

    if distinct_types < 3:
        print(
            f"error: regex backend detected only {distinct_types} distinct marker types "
            f"(plan requires ≥3)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
