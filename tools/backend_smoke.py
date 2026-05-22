#!/usr/bin/env python
"""Backend smoke-readiness CLI (Plan 9).

Attempts configured backends on a real PDF through the existing repository
backend runner, classifies each backend, and writes a machine-readable report
plus a human-readable summary. It does not install environments or models and
does not run connector, calibration, consensus, linking or export stages.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.local.backend_smoke import (
    DEFAULT_CORPUS_ROOT,
    DEFAULT_GATE_MINIMUM,
    DEFAULT_TIMEOUT_SECONDS,
    build_backend_smoke_report,
    build_backend_smoke_summary,
    write_backend_smoke_report,
)


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _select_corpus_pdf(corpus_root: Path) -> Path | None:
    """Return the first real ``*.pdf`` under the corpus, ignoring placeholders."""

    if not corpus_root.is_dir():
        return None
    pdfs = sorted(path for path in corpus_root.rglob("*.pdf") if path.is_file())
    return pdfs[0] if pdfs else None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(
        description="Attempt configured backends on a real PDF and report smoke readiness"
    )
    parser.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT, type=Path)
    parser.add_argument("--input-pdf", default=None, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--gate-minimum", default=DEFAULT_GATE_MINIMUM, type=int)
    parser.add_argument("--strict-gate", action="store_true")
    parser.add_argument("--timeout-seconds", default=DEFAULT_TIMEOUT_SECONDS, type=int)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        if args.gate_minimum < 0:
            print("error: --gate-minimum must be zero or greater", file=sys.stderr)
            return 1
        if args.timeout_seconds <= 0:
            print("error: --timeout-seconds must be greater than zero", file=sys.stderr)
            return 1
        input_pdf = args.input_pdf
        if input_pdf is None:
            input_pdf = _select_corpus_pdf(args.corpus_root)
        report = build_backend_smoke_report(
            repo_root=ROOT,
            input_pdf=input_pdf,
            work_dir=args.out_dir / "backend_runs",
            gate_minimum=args.gate_minimum,
            timeout_seconds=args.timeout_seconds,
            corpus_root=args.corpus_root,
        )
        report_path = write_backend_smoke_report(report=report, out_dir=args.out_dir)
        summary_path = report_path.with_name("backend_smoke_summary.txt")
        if args.verbose:
            print(build_backend_smoke_summary(report), end="")
            print(f"backend_smoke_report: {report_path}")
            print(f"backend_smoke_summary: {summary_path}")
            print(f"gate_passed: {str(report.gate_passed).lower()}")
        if args.strict_gate and not report.gate_passed:
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI reports invalid runtime state as exit 1
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
