#!/usr/bin/env python
"""Plan 10 connector PageExtractionIR validation CLI.

Drives ``pdf2md.local.connector_validation`` to validate raw backend outputs
(typically Plan 9 successful backends) by reusing the existing connector
entrypoint and emitting a machine-readable report plus a human-readable
summary. EntityProposalDocument validation is deferred to Plan 11 and is not
used for Plan 10 pass/fail.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.local.connector_validation import (
    DEFAULT_PREFERRED_GATE_MINIMUM,
    build_connector_validation_report,
    build_connector_validation_summary,
    write_connector_validation_report,
)


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parse_backend_output(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"--backend-output must be in the form <backend_name>=<raw_output_dir>; got {raw!r}"
        )
    name, _, value = raw.partition("=")
    name = name.strip()
    value = value.strip()
    if not name or not value:
        raise argparse.ArgumentTypeError(
            f"--backend-output requires non-empty backend name and path; got {raw!r}"
        )
    return name, Path(value)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(
        description=(
            "Validate that raw backend outputs convert via the existing connector "
            "path into structurally and semantically valid PageExtractionIR (Plan 10)."
        )
    )
    parser.add_argument(
        "--plan9-report",
        default=None,
        type=Path,
        help="Path to the Plan 9 backend smoke report JSON.",
    )
    parser.add_argument(
        "--backend-output",
        action="append",
        default=[],
        metavar="BACKEND_NAME=RAW_OUTPUT_DIR",
        help="Explicit backend output (repeatable).",
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--preferred-gate-minimum",
        default=DEFAULT_PREFERRED_GATE_MINIMUM,
        type=int,
    )
    parser.add_argument("--allow-reduced-gate", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        if args.preferred_gate_minimum < 1:
            print("error: --preferred-gate-minimum must be 1 or greater", file=sys.stderr)
            return 1
        if args.plan9_report is None and not args.backend_output:
            print(
                "error: provide --plan9-report and/or at least one --backend-output entry",
                file=sys.stderr,
            )
            return 1

        backend_outputs: dict[str, Path] = {}
        for raw in args.backend_output:
            try:
                name, path = _parse_backend_output(raw)
            except argparse.ArgumentTypeError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            backend_outputs[name] = path

        report = build_connector_validation_report(
            backend_outputs=backend_outputs or None,
            plan9_report_path=args.plan9_report,
            preferred_gate_minimum=args.preferred_gate_minimum,
            allow_reduced_gate=args.allow_reduced_gate,
            out_dir=args.out_dir,
        )
        report_path = write_connector_validation_report(report=report, out_dir=args.out_dir)
        summary_path = report_path.with_name("connector_validation_summary.txt")

        if args.verbose:
            print(build_connector_validation_summary(report), end="")
            print(f"connector_validation_report: {report_path}")
            print(f"connector_validation_summary: {summary_path}")
            print(f"preferred_gate_passed: {str(report.preferred_gate_passed).lower()}")
            print(f"minimum_gate_passed: {str(report.minimum_gate_passed).lower()}")
            print(
                f"human_reduced_gate_required: {str(report.human_reduced_gate_required).lower()}"
            )

        if report.preferred_gate_passed:
            return 0
        if args.allow_reduced_gate and report.minimum_gate_passed:
            return 0
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI reports invalid runtime state as exit 1
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
