"""Validate, merge, and summarize marker adjudication label files.

Exit codes:
    0 — success
    2 — bad input (missing file, malformed JSON/schema, document mismatch)
    3 — reserved for valid inputs with warnings/errors in future checks
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pydantic import ValidationError  # noqa: E402

from pdf2md.diagnostics.adjudication import (  # noqa: E402
    AdjudicationDocument,
    merge_documents,
)


def _load_raw(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_document(path: Path) -> AdjudicationDocument:
    if not path.is_file():
        raise ValueError(f"file not found: {path}")
    try:
        return AdjudicationDocument.model_validate(_load_raw(path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc}") from exc
    except ValidationError as exc:
        raise ValueError(f"schema validation failed: {exc}") from exc


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        doc = _load_document(args.path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"valid: {args.path} document_id={doc.document_id} "
        f"adjudications={len(doc.adjudications)}"
    )
    return 0


def _cmd_merge(args: argparse.Namespace) -> int:
    try:
        docs = [_load_document(path) for path in args.inputs]
        merged = docs[0]
        for path, doc in zip(args.inputs[1:], docs[1:], strict=True):
            merged = merge_documents(merged, doc, merged_from=path.name)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        merged.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(
        f"merged: {args.output} document_id={merged.document_id} "
        f"adjudications={len(merged.adjudications)}"
    )
    return 0


def _duplicate_counts(raw: dict) -> Counter[str]:
    marker_ids = [item.get("marker_id", "") for item in raw.get("adjudications", [])]
    return Counter(marker_id for marker_id in marker_ids if marker_id)


def _cmd_summary(args: argparse.Namespace) -> int:
    try:
        raw = _load_raw(args.path)
        doc = AdjudicationDocument.model_validate(raw)
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: malformed JSON: {exc}", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print(f"error: schema validation failed: {exc}", file=sys.stderr)
        return 2

    decisions = Counter(item.decision for item in doc.adjudications)
    duplicates = {k: v for k, v in _duplicate_counts(raw).items() if v > 1}
    print(f"document_id: {doc.document_id}")
    print(f"marker_id count: {len({item.marker_id for item in doc.adjudications})}")
    print(f"adjudication count: {len(doc.adjudications)}")
    print("decision breakdown:")
    for decision in ("resolve", "reclassify", "noise", "rule_hint"):
        print(f"  {decision}: {decisions.get(decision, 0)}")
    if duplicates:
        print("duplicate-marker_id warnings:")
        for marker_id, count in sorted(duplicates.items()):
            print(f"  {marker_id}: {count}")
    else:
        print("duplicate-marker_id warnings: none")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage pdf2md marker adjudication files")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate one adjudication file")
    validate.add_argument("path", type=Path)
    validate.set_defaults(func=_cmd_validate)

    merge = sub.add_parser("merge", help="Merge same-document adjudication files")
    merge.add_argument("output", type=Path)
    merge.add_argument("inputs", nargs="+", type=Path)
    merge.set_defaults(func=_cmd_merge)

    summary = sub.add_parser("summary", help="Summarize one adjudication file")
    summary.add_argument("path", type=Path)
    summary.set_defaults(func=_cmd_summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
