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
        merged = type(result)(consensus=result.consensus, report={**result.report, "warnings": loaded.warnings + result.warnings}, warnings=loaded.warnings + result.warnings)
        write_consensus_outputs(result=merged, out_dir=args.out_dir)
        if args.verbose:
            for warning in merged.warnings:
                print(f"warning: {warning}", file=sys.stderr)
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI converts strict failures to exit code 1
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
