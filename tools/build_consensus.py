#!/usr/bin/env python
"""Build consensus IR from backend connector output directories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.consensus.factory import ConsensusFactorySettings, build_consensus_ir
from pdf2md.consensus.io import load_consensus_inputs, write_consensus_outputs
from pdf2md.consensus.reporting import INSPECTION_STATUSES, build_consensus_report
from pdf2md.consensus.scoring import ConsensusScoringSettings


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(description="Build pdf2md consensus IR")
    parser.add_argument("--connector-root", required=True, type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--priors-root", type=Path)
    parser.add_argument("--backends")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--min-agreement-score", default=0.50, type=float)
    parser.add_argument("--unresolved-margin", default=0.05, type=float)
    parser.add_argument(
        "--inspection-status",
        default="diagnostic_only",
        choices=list(INSPECTION_STATUSES),
        help=(
            "Human-supplied quality verdict comparing ConsensusIR against backends "
            "and ground truth. Defaults to diagnostic_only."
        ),
    )
    parser.add_argument(
        "--ground-truth",
        default=None,
        type=Path,
        help=(
            "Optional ground-truth artefact reference recorded in the report. "
            "No automated comparison is performed in Plan 13."
        ),
    )
    parser.add_argument(
        "--inspection-note",
        action="append",
        default=[],
        help="Optional inspection note (repeatable).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    backends = [item.strip() for item in args.backends.split(",") if item.strip()] if args.backends else None
    try:
        loaded = load_consensus_inputs(
            connector_root=args.connector_root,
            document_id=args.document_id,
            backends=backends,
            priors_root=args.priors_root,
            strict=args.strict,
        )
        settings = ConsensusFactorySettings(
            scoring=ConsensusScoringSettings(
                min_agreement_score=args.min_agreement_score,
                unresolved_margin=args.unresolved_margin,
            ),
            strict=args.strict,
        )
        result = build_consensus_ir(
            document_id=args.document_id,
            pages_by_backend=loaded.pages_by_backend,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            settings=settings,
        )
        all_warnings = loaded.warnings + result.warnings
        rebuilt_report = build_consensus_report(
            consensus=result.consensus,
            warnings=all_warnings,
            backend_summary=result.report.get("backend_summary", {}),
            inspection_status=args.inspection_status,
            ground_truth_ref=str(args.ground_truth) if args.ground_truth else None,
            inspection_notes=args.inspection_note,
        )
        merged = type(result)(
            consensus=result.consensus,
            report=rebuilt_report,
            warnings=all_warnings,
        )
        write_consensus_outputs(result=merged, out_dir=args.out_dir)
        if args.verbose:
            for warning in merged.warnings:
                print(f"warning: {warning}", file=sys.stderr)
            print(f"consensus_ir: {args.out_dir / 'consensus_ir.json'}")
            print(f"consensus_report: {args.out_dir / 'reports' / 'consensus_report.json'}")
            print(f"consensus_summary: {args.out_dir / 'consensus_summary.txt'}")
            print(f"inspection_status: {rebuilt_report['inspection_status']}")
            print(f"plan14_readiness: {rebuilt_report['plan14_readiness']}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI converts strict failures to exit code 1
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
