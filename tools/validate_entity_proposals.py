#!/usr/bin/env python
"""Plan 11 EntityProposalDocument validation CLI.

Drives ``pdf2md.local.entity_proposal_validation`` to validate the
EntityProposalDocument outputs produced by the same connector path validated
in Plan 10. Real calibration prior generation is deferred to Plan 12 and is
not used for Plan 11 pass/fail.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.local.entity_proposal_validation import (
    DEFAULT_PREFERRED_GATE_MINIMUM,
    build_entity_proposal_validation_report,
    build_entity_proposal_validation_summary,
    write_entity_proposal_validation_report,
)


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parse_pair(raw: str, flag: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"{flag} must be in the form <backend_name>=<path>; got {raw!r}"
        )
    name, _, value = raw.partition("=")
    name = name.strip()
    value = value.strip()
    if not name or not value:
        raise argparse.ArgumentTypeError(
            f"{flag} requires non-empty backend name and path; got {raw!r}"
        )
    return name, Path(value)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(
        description=(
            "Validate EntityProposalDocument outputs produced by the existing "
            "connector path (Plan 11)."
        )
    )
    parser.add_argument(
        "--plan10-report",
        default=None,
        type=Path,
        help="Path to the Plan 10 connector validation report JSON.",
    )
    parser.add_argument(
        "--backend-entities",
        action="append",
        default=[],
        metavar="BACKEND_NAME=ENTITY_DOCUMENT_PATH",
        help="Explicit entities.json override (repeatable).",
    )
    parser.add_argument(
        "--page-ir",
        action="append",
        default=[],
        metavar="BACKEND_NAME=PAGE_EXTRACTION_IR_PATH",
        help="Optional PageExtractionIR path for evidence cross-checking (repeatable).",
    )
    parser.add_argument(
        "--backend-raw-dir",
        action="append",
        default=[],
        metavar="BACKEND_NAME=RAW_OUTPUT_DIR",
        help=(
            "Raw backend output directory; the existing connector is invoked to "
            "regenerate the EntityProposalDocument (repeatable)."
        ),
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


def _collect_pairs(values: list[str], flag: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for raw in values:
        name, path = _parse_pair(raw, flag)
        out[name] = path
    return out


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        if args.preferred_gate_minimum < 1:
            print("error: --preferred-gate-minimum must be 1 or greater", file=sys.stderr)
            return 1
        if (
            args.plan10_report is None
            and not args.backend_entities
            and not args.backend_raw_dir
        ):
            print(
                "error: provide --plan10-report and/or at least one --backend-entities or --backend-raw-dir entry",
                file=sys.stderr,
            )
            return 1

        try:
            backend_entities = _collect_pairs(args.backend_entities, "--backend-entities")
            backend_page_ir = _collect_pairs(args.page_ir, "--page-ir")
            backend_raw_dirs = _collect_pairs(args.backend_raw_dir, "--backend-raw-dir")
        except argparse.ArgumentTypeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        report = build_entity_proposal_validation_report(
            backend_entities=backend_entities or None,
            backend_page_ir=backend_page_ir or None,
            backend_raw_dirs=backend_raw_dirs or None,
            plan10_report_path=args.plan10_report,
            preferred_gate_minimum=args.preferred_gate_minimum,
            allow_reduced_gate=args.allow_reduced_gate,
            out_dir=args.out_dir,
        )
        report_path = write_entity_proposal_validation_report(report=report, out_dir=args.out_dir)
        summary_path = report_path.with_name("entity_proposal_validation_summary.txt")

        if args.verbose:
            print(build_entity_proposal_validation_summary(report), end="")
            print(f"entity_proposal_validation_report: {report_path}")
            print(f"entity_proposal_validation_summary: {summary_path}")
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
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
