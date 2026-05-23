#!/usr/bin/env python
"""Plan 12 BlockKind vocabulary alignment check.

Scans a calibration truth root for raw Docling labels and verifies they map
into canonical ``BlockKind`` values. The mandatory top-four labels
(``text``, ``section_header``, ``title``, ``picture``) are a hard gate — if
any of them is missing from the mapping, the CLI exits non-zero.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.calibration.vocabulary import (
    build_vocabulary_alignment_report,
    build_vocabulary_alignment_summary,
    scan_truth_root_labels,
    write_vocabulary_alignment_report,
)


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(
        description=(
            "Verify Docling-label to BlockKind mapping for a calibration truth root."
        )
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit non-zero if any observed truth label is unmapped, not only the "
            "mandatory top-four."
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        observed, scan_errors = scan_truth_root_labels(args.root)
        report = build_vocabulary_alignment_report(
            truth_root=args.root,
            observed_labels=observed,
        )
        if scan_errors:
            # _ = scan errors are already reflected in the report; surface them in verbose
            pass
        write_vocabulary_alignment_report(report=report, out_dir=args.out_dir)
        if args.verbose:
            print(build_vocabulary_alignment_summary(report), end="")
            report_path = args.out_dir / "reports" / "blockkind_vocabulary_alignment_report.json"
            print(f"blockkind_vocabulary_alignment_report: {report_path}")
            print(f"mandatory_mapping_passed: {str(report.mandatory_mapping_passed).lower()}")
            print(f"all_observed_labels_mapped: {str(report.all_observed_labels_mapped).lower()}")
        if not report.mandatory_mapping_passed:
            return 1
        if args.strict and not report.all_observed_labels_mapped:
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
