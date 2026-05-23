#!/usr/bin/env python
"""Plan 16 end-to-end MVP pipeline runner.

Two modes:

- one-document: ``--pdf <input.pdf> --out-dir <out>``
- corpus subset: ``--corpus-root <dir> --out-dir <out>`` plus optional
  ``--max-documents`` and ``--document-list``.

The runner reuses the existing per-stage entry points at the module level
(except backend execution, which flows through the existing backend runner
because of conda environment isolation). It does NOT modify the public
Typer CLI in ``src/pdf2md/cli/main.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.pipeline.runner import run_corpus, run_one_document


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parse_backends(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ExitCodeOneParser(
        description=(
            "Run the pdf2md MVP pipeline end-to-end (Plan 16). "
            "Pick exactly one of --pdf (one-document mode) or --corpus-root "
            "(corpus subset mode)."
        )
    )
    # Mode selection
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pdf", default=None, type=Path, help="Input PDF for one-document mode.")
    mode.add_argument(
        "--corpus-root",
        default=None,
        type=Path,
        help="Corpus root directory for corpus/subset mode.",
    )

    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--work-dir",
        default=None,
        type=Path,
        help="Working directory for stage outputs. Defaults to <out-dir>/work.",
    )
    parser.add_argument(
        "--backends",
        default=None,
        help="Comma-separated backend allowlist (e.g. paddleocr,mineru).",
    )
    parser.add_argument(
        "--max-documents",
        default=None,
        type=int,
        help="Cap on selected corpus documents. Ignored in one-document mode.",
    )
    parser.add_argument(
        "--document-list",
        default=None,
        type=Path,
        help="Optional text file with one document id per line. Ignored in one-document mode.",
    )
    parser.add_argument(
        "--timeout-seconds",
        default=1500,
        type=int,
        help="Per-backend smoke timeout in seconds. Default: 1500.",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def _read_document_list(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    if not Path(path).is_file():
        raise SystemExit(f"document_list_not_found: {path}")
    raw = Path(path).read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out or None


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    try:
        backends = _parse_backends(args.backends)

        if args.pdf is not None:
            manifest = run_one_document(
                pdf_path=args.pdf,
                out_dir=args.out_dir,
                work_dir=args.work_dir,
                backends=backends,
                timeout_seconds=args.timeout_seconds,
                strict=args.strict,
            )
            if args.verbose:
                doc = manifest.documents[0]
                result_value = doc.result if isinstance(doc.result, str) else doc.result.value
                readiness_value = (
                    manifest.mvp_readiness
                    if isinstance(manifest.mvp_readiness, str)
                    else manifest.mvp_readiness.value
                )
                print(f"document: {doc.document_id} result: {result_value}")
                print(f"mvp_readiness: {readiness_value}")
                for stage in doc.stages:
                    status_value = stage.status if isinstance(stage.status, str) else stage.status.value
                    print(f"  {stage.name if isinstance(stage.name, str) else stage.name.value}: {status_value}")
            failed = any(
                (d.result if isinstance(d.result, str) else d.result.value) == "failed"
                for d in manifest.documents
            )
            if args.strict and failed:
                return 1
            return 0

        # corpus mode
        document_list = _read_document_list(args.document_list)
        manifest, evaluation = run_corpus(
            corpus_root=args.corpus_root,
            out_dir=args.out_dir,
            work_dir=args.work_dir,
            backends=backends,
            max_documents=args.max_documents,
            document_list=document_list,
            timeout_seconds=args.timeout_seconds,
            strict=args.strict,
        )
        if args.verbose:
            readiness_value = (
                manifest.mvp_readiness
                if isinstance(manifest.mvp_readiness, str)
                else manifest.mvp_readiness.value
            )
            print(f"selected: {len(manifest.documents)}")
            print(f"mvp_readiness: {readiness_value}")
            for d in manifest.documents:
                result_value = d.result if isinstance(d.result, str) else d.result.value
                print(f"  {d.document_id}: {result_value}")
        return 0
    except SystemExit as exc:
        if exc.code is not None and not isinstance(exc.code, int):
            print(f"error: {exc.code}", file=sys.stderr)
        return int(exc.code) if isinstance(exc.code, int) else 1
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
