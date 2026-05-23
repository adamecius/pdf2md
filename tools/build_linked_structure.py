#!/usr/bin/env python
"""Build linked_structure.json and reports/linking_report.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.linking.builder import LinkerSettings, build_linked_structure
from pdf2md.linking.io import load_linker_inputs, write_linker_outputs
from pdf2md.linking.reporting import (
    READINESS_STATUSES,
    build_linking_report,
    build_linking_summary,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build pdf2md LinkedStructure from consensus IR")
    parser.add_argument("--consensus-ir", required=True, type=Path)
    parser.add_argument("--consensus-report", type=Path)
    parser.add_argument("--entities-root", type=Path)
    parser.add_argument("--priors-root", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--low-confidence-threshold", type=float, default=0.60)
    parser.add_argument(
        "--inspection-status",
        default="diagnostic_only",
        choices=list(READINESS_STATUSES),
        help=(
            "Human-supplied Plan 15 readiness verdict comparing LinkedStructure "
            "coherence against the source ConsensusIR. Defaults to diagnostic_only."
        ),
    )
    parser.add_argument(
        "--inspection-note",
        action="append",
        default=[],
        help="Optional inspection note (repeatable).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        loaded = load_linker_inputs(
            consensus_ir_path=args.consensus_ir,
            consensus_report_path=args.consensus_report,
            entities_root=args.entities_root,
            priors_root=args.priors_root,
            strict=args.strict,
        )
        result = build_linked_structure(
            consensus=loaded.consensus,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            consensus_report=loaded.consensus_report,
            source_consensus_ir=str(args.consensus_ir),
            source_consensus_report=str(args.consensus_report) if args.consensus_report else None,
            source_entity_documents=loaded.source_entity_documents,
            source_prior_documents=loaded.source_prior_documents,
            settings=LinkerSettings(strict=args.strict, low_confidence_threshold=args.low_confidence_threshold),
        )
        if loaded.warnings:
            linked = result.linked.model_copy(update={"warnings": result.linked.warnings + loaded.warnings})
        else:
            linked = result.linked
        rebuilt_report = build_linking_report(
            linked,
            low_confidence_threshold=args.low_confidence_threshold,
            inspection_status=args.inspection_status,
            inspection_notes=args.inspection_note,
        )
        merged = type(result)(
            linked=linked,
            report=rebuilt_report,
            warnings=result.warnings + loaded.warnings,
        )
        write_linker_outputs(result=merged, out_dir=args.out_dir)
        if args.verbose:
            for warning in merged.warnings:
                print(f"warning:{warning}", file=sys.stderr)
            print(build_linking_summary(rebuilt_report), end="")
            print(f"linked_structure: {args.out_dir / 'linked_structure.json'}")
            print(f"linking_report: {args.out_dir / 'reports' / 'linking_report.json'}")
            print(f"inspection_status: {rebuilt_report['inspection_status']}")
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
