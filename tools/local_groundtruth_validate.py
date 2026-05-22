#!/usr/bin/env python
"""Validate the local LaTeX ground-truth corpus (inspect-only, Plan 8).

This CLI discovers and inspects the on-disk LaTeX ground-truth corpus and
writes a machine-readable report plus a human-readable summary. It never
compiles LaTeX, runs LaTeXML, runs generator or validator scripts, or runs any
backend.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.local.groundtruth import (
    DEFAULT_CORPUS_ROOT,
    build_validation_report,
    build_validation_summary,
    write_validation_report,
)


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(
        description="Validate the local LaTeX ground-truth corpus (inspect-only)"
    )
    parser.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        report = build_validation_report(args.corpus_root)
        report_path = write_validation_report(report=report, out_dir=args.out_dir)
        summary_path = report_path.with_name("groundtruth_validation_summary.txt")
        if args.verbose:
            print(build_validation_summary(report), end="")
            print(f"groundtruth_validation_report: {report_path}")
            print(f"groundtruth_validation_summary: {summary_path}")
            print(f"corpus_ready: {str(report.corpus_ready).lower()}")
        if args.strict and not report.corpus_ready:
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI reports invalid runtime state as exit 1
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
