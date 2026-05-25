"""Connector for the regex semantic backend.

Mirrors the OCR-backend connector convention so the orchestrator can
discover it via the same ``importlib.import_module(f"backend.semantic.
{name}.connector")`` path it already uses for the OCR backends.

The semantic layer's return type is a :class:`CrossReferenceGraph`
rather than per-page extraction IR — that's the only intentional
divergence from the OCR `connect()` signature. The function name,
positional arguments, and CLI entry point match the OCR side exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from pdf2md.connectors.common import SemanticConnectorResult
from pdf2md.models.cross_ref import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefMarker,
    RefType,
)

# Patterns module lives next to this connector; the loader uses
# importlib because `backend/` is intentionally NOT a python package.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import patterns  # noqa: E402 — local sibling import


BACKEND = "regex"
BACKEND_VERSION = "0.1.0"


def _doc_hash_from_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def connect(
    raw_dir: Path,
    document_id: str,
    out_dir: Path | None = None,
    *,
    text: str | None = None,
    source_ref: str = "#/document",
) -> SemanticConnectorResult:
    """Run the regex semantic backend against raw text.

    Args:
        raw_dir: Directory containing the text input. Looked up in this
            order: ``raw_dir/text.txt``, ``raw_dir/output.txt``,
            ``raw_dir/<document_id>.txt``. Ignored when ``text`` is
            provided directly.
        document_id: Stable identifier embedded in marker ``source_ref``
            when the default (``"#/document"``) is not overridden.
        out_dir: Optional output root; when provided, the graph is
            written to ``<out_dir>/regex/cross_references.json``.
        text: Pre-extracted plain text. When provided, ``raw_dir`` is
            not consulted.
        source_ref: JSON-pointer string stamped on every emitted marker.

    Returns:
        :class:`SemanticConnectorResult` whose ``graph`` is a populated
        :class:`CrossReferenceGraph` with one marker per detected
        pattern hit.
    """
    warnings: list[str] = []

    body = text
    if body is None:
        for candidate in (
            raw_dir / "text.txt",
            raw_dir / "output.txt",
            raw_dir / f"{document_id}.txt",
        ):
            if candidate.is_file():
                body = candidate.read_text(encoding="utf-8")
                break
    if body is None:
        warnings.append("no_text_found")
        body = ""

    hits = patterns.find_markers(body)

    markers: list[RefMarker] = []
    for hit in hits:
        try:
            marker_type = RefType(hit.marker_type)
        except ValueError:
            warnings.append(f"unknown_marker_type:{hit.marker_type}")
            continue
        markers.append(
            RefMarker(
                source_ref=source_ref,
                marker_text=hit.marker_text,
                marker_type=marker_type,
                char_offset=tuple(hit.char_offset),
                confidence=1.0,
                backend=BACKEND,
            )
        )

    graph = CrossReferenceGraph(
        schema_version=CROSS_REF_SCHEMA_VERSION,
        doc_hash=_doc_hash_from_text(body),
        markers=markers,
        edges=[],
        entities=[],
        backend_versions={BACKEND: BACKEND_VERSION},
    )

    if out_dir is not None:
        backend_dir = out_dir / BACKEND
        backend_dir.mkdir(parents=True, exist_ok=True)
        (backend_dir / "cross_references.json").write_text(
            graph.model_dump_json(indent=2),
            encoding="utf-8",
        )

    return SemanticConnectorResult(graph=graph, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Connect {BACKEND} semantic backend output to a CrossReferenceGraph")
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument(
        "--text",
        type=Path,
        default=None,
        help="Optional pre-extracted plain-text file (overrides --raw-dir lookup).",
    )
    args = parser.parse_args(argv)

    text_payload: str | None = None
    if args.text is not None:
        if not args.text.is_file():
            print(f"error: --text not found: {args.text}", file=sys.stderr)
            return 1
        text_payload = args.text.read_text(encoding="utf-8")

    try:
        result = connect(args.raw_dir, args.document_id, args.out_dir, text=text_payload)
    except Exception as exc:  # noqa: BLE001 — connector top-level guard
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(
        f"{BACKEND} connector: {len(result.graph.markers)} markers, "
        f"backend_versions={result.graph.backend_versions}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
