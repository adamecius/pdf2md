#!/usr/bin/env python
"""Run the pdf2md local ground-truth preflight checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.local.preflight import PreflightSettings, build_preflight_report, write_preflight_report


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parse_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(description="Run pdf2md local ground-truth preflight checks")
    parser.add_argument("--repo-root", default=Path("."), type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--required-backends", default="mineru,paddleocr,deepseek")
    parser.add_argument("--optional-backends", default="")
    parser.add_argument("--backend-env-prefix", default="pdf2md-")
    parser.add_argument("--timeout-seconds", default=20, type=int)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        if args.timeout_seconds <= 0:
            print("error: --timeout-seconds must be greater than zero", file=sys.stderr)
            return 1
        settings = PreflightSettings(
            required_backends=_parse_list(args.required_backends),
            optional_backends=_parse_list(args.optional_backends),
            backend_env_prefix=args.backend_env_prefix,
            timeout_seconds=args.timeout_seconds,
        )
        report = build_preflight_report(settings=settings, repo_root=args.repo_root)
        report_path = write_preflight_report(report=report, out_dir=args.out_dir)
        summary_path = report_path.with_name("preflight_summary.txt")
        if args.verbose:
            print(f"preflight_report: {report_path}")
            print(f"preflight_summary: {summary_path}")
            print(f"environment_ready: {str(report.environment_ready).lower()}")
            print(f"required_failed: {report.required_failed}")
        if args.strict and not report.environment_ready:
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI reports invalid runtime state as exit 1
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
