"""Standalone smoke test for the GROBID semantic backend.

Usage:
    # Start GROBID once (default port 8070):
    docker pull grobid/grobid:0.8.1
    docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.1
    # Wait ~30 s for the service to warm up:
    curl -s http://localhost:8070/api/isalive   # → "true"

    # Then:
    python backend/semantic/grobid/smoke_test.py \
        --pdf tests/data/<sample_article>.pdf \
        --out-dir /tmp/grobid_smoke

Acceptance (Plan 005 §5):
    exit code 0
    <out-dir>/grobid_smoke_result.json exists
    result.markers has length > 0
    result.markers contains at least one marker_type == "bibliography"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import grobid_client  # noqa: E402
import tei_parser  # noqa: E402


BACKEND_NAME = "grobid"
BACKEND_VERSION = "0.8.x"


def run_smoke(
    pdf_path: Path,
    out_dir: Path,
    *,
    host: str,
    port: int,
    timeout_s: int,
) -> dict:
    """Run the GROBID smoke test and write the result file.

    Args:
        pdf_path: Path to a readable PDF.
        out_dir: Directory to write ``grobid_smoke_result.json`` into.
        host: GROBID hostname.
        port: GROBID TCP port.
        timeout_s: Per-request timeout, in seconds.

    Returns:
        The result dict that was written to disk.

    Raises:
        grobid_client.GrobidUnavailableError: If the service is not
            reachable. Caller should report this as ``env_not_ready``.
    """
    endpoint = grobid_client.GrobidEndpoint(host=host, port=port, timeout_s=timeout_s)
    if not grobid_client.is_alive(endpoint):
        raise grobid_client.GrobidUnavailableError(
            f"GROBID is not alive at {endpoint.base_url}. "
            "Start the container with: "
            "`docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.1`."
        )

    t0 = time.perf_counter()
    tei_xml = grobid_client.process_fulltext_document(pdf_path, endpoint)
    parsed = tei_parser.parse_tei(tei_xml)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    result = {
        "backend": BACKEND_NAME,
        "backend_version": BACKEND_VERSION,
        "input_path": str(pdf_path),
        "input_bytes": pdf_path.stat().st_size,
        "endpoint": endpoint.base_url,
        "elapsed_ms": round(elapsed_ms, 3),
        "markers": [
            {
                "marker_type": m.marker_type,
                "marker_text": m.marker_text,
                "target": m.target,
            }
            for m in parsed.markers
        ],
        "bib_entries": [
            {"ref_id": e.ref_id, "raw_text": e.raw_text}
            for e in parsed.bib_entries
        ],
        "counts_by_type": tei_parser.summarise(parsed),
        "warnings": list(parsed.warnings),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "grobid_smoke_result.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GROBID semantic backend smoke test")
    parser.add_argument("--pdf", required=True, type=Path, help="Path to a PDF input")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--host", default=grobid_client.GROBID_DEFAULT_HOST)
    parser.add_argument("--port", default=grobid_client.GROBID_DEFAULT_PORT, type=int)
    parser.add_argument("--timeout-s", default=grobid_client.GROBID_DEFAULT_TIMEOUT_S, type=int)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not args.pdf.is_file():
        print(f"error: PDF not found: {args.pdf}", file=sys.stderr)
        return 2

    try:
        result = run_smoke(
            args.pdf,
            args.out_dir,
            host=args.host,
            port=args.port,
            timeout_s=args.timeout_s,
        )
    except grobid_client.GrobidUnavailableError as exc:
        # env_not_ready, not a repository defect.
        print(f"env_not_ready: {exc}", file=sys.stderr)
        return 3

    if args.verbose:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"grobid smoke: {len(result['markers'])} markers, "
            f"{len(result['bib_entries'])} bib entries, "
            f"{result['elapsed_ms']:.0f} ms, "
            f"out={args.out_dir/'grobid_smoke_result.json'}"
        )

    if not result["markers"]:
        print("error: GROBID returned no markers", file=sys.stderr)
        return 1

    has_bib = any(m["marker_type"] == "bibliography" for m in result["markers"])
    if not has_bib:
        print(
            "error: GROBID returned no bibliography markers (plan H1 requires ≥1)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
