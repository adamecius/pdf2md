"""Thin connector CLI for mineru raw backend outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pdf2md.connectors.common import BackendConnectorConfig, ConnectorResult, connect_raw_dir

BACKEND = "mineru"
BACKEND_VERSION = None


def connect(raw_dir: Path, document_id: str, out_dir: Path | None = None) -> ConnectorResult:
    """Connect a raw mineru output directory to page IR and entity proposals."""

    config = BackendConnectorConfig(
        backend=BACKEND,
        default_backend_version=BACKEND_VERSION,
        markdown_file_candidates=("output.md", "output.mmd", "result.md", "result.mmd"),
        manifest_file_candidates=("manifest.json", "status.json", "command.json"),
    )
    return connect_raw_dir(raw_dir=Path(raw_dir), document_id=document_id, config=config, out_dir=out_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Connect {BACKEND} raw output to pdf2md IR")
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        result = connect(args.raw_dir, args.document_id, args.out_dir)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
