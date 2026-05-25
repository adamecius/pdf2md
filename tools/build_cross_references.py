"""Proof-of-life CLI for the semantic layer (Plan 006_0).

Runs one or more semantic backends against a PDF (or a text file when
the regex backend is selected) and writes a merged
``cross_references.json`` to ``--out-dir``.

Usage:
    python tools/build_cross_references.py \\
        --backend regex \\
        --text tests/data/semantic_fixtures/sample_text.txt \\
        --out-dir /tmp/cross_ref_smoke

    python tools/build_cross_references.py \\
        --backend grobid \\
        --pdf tests/data/<a_sample_article>.pdf \\
        --out-dir /tmp/cross_ref_grobid

    python tools/build_cross_references.py \\
        --backend ensemble \\
        --pdf tests/data/<a_sample_article>.pdf \\
        --text tests/data/semantic_fixtures/sample_text.txt \\
        --out-dir /tmp/cross_ref_ensemble

Exit codes:
    0 — success
    2 — bad input (missing file, contradictory arguments)
    3 — backend not available (no GROBID running, no conda env)
    1 — backend ran but produced no markers
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.models.cross_ref import CrossReferenceGraph  # noqa: E402
from pdf2md.models.entities import EntityProposalDocument  # noqa: E402
from pdf2md.semantic import (  # noqa: E402
    GrobidSemanticBackend,
    RegexSemanticBackend,
    SemanticBackend,
    VlmSemanticBackend,
    entities_to_candidates,
    resolve_markers,
    run_ensemble,
)


_BACKEND_CHOICES = ("regex", "grobid", "vlm", "ensemble")


def _build_backends(name: str) -> list[SemanticBackend]:
    if name == "regex":
        return [RegexSemanticBackend()]
    if name == "grobid":
        return [GrobidSemanticBackend()]
    if name == "vlm":
        return [VlmSemanticBackend()]
    if name == "ensemble":
        return [RegexSemanticBackend(), GrobidSemanticBackend(), VlmSemanticBackend()]
    raise ValueError(f"unknown backend: {name}")


def _write_graph(graph: CrossReferenceGraph, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cross_references.json"
    out_path.write_text(
        graph.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return out_path


def _summarise(graph: CrossReferenceGraph, out_path: Path) -> str:
    counts: dict[str, int] = {}
    for marker in graph.markers:
        key = str(marker.marker_type)
        counts[key] = counts.get(key, 0) + 1
    counts_str = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    backends = ", ".join(sorted(graph.backend_versions))
    return (
        f"cross_references: {len(graph.markers)} markers ({counts_str}); "
        f"{len(graph.entities)} entities; backends=[{backends}]; out={out_path}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a CrossReferenceGraph from one or more semantic backends",
    )
    parser.add_argument(
        "--backend",
        required=True,
        choices=_BACKEND_CHOICES,
        help="Which semantic backend(s) to run",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Source PDF (required for grobid/vlm; optional for regex/ensemble)",
    )
    parser.add_argument(
        "--text",
        type=Path,
        default=None,
        help="Pre-extracted plain-text file (required for regex unless --pdf is .txt)",
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--ocr-entities",
        type=Path,
        default=None,
        help=(
            "Optional path to an EntityProposalDocument JSON (the "
            "`entities.json` written by an OCR connector). When given, "
            "the markers detected by the semantic backend(s) are "
            "resolved against the OCR-detected entities and the "
            "resulting RefEdges are attached to the output graph."
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.pdf is not None and not args.pdf.exists():
        print(f"error: --pdf not found: {args.pdf}", file=sys.stderr)
        return 2
    if args.text is not None and not args.text.is_file():
        print(f"error: --text not found: {args.text}", file=sys.stderr)
        return 2
    if args.ocr_entities is not None and not args.ocr_entities.is_file():
        print(f"error: --ocr-entities not found: {args.ocr_entities}", file=sys.stderr)
        return 2

    text_payload: str | None = None
    if args.text is not None:
        text_payload = args.text.read_text(encoding="utf-8")

    backends = _build_backends(args.backend)

    if args.backend == "regex":
        if text_payload is None and args.pdf is None:
            print(
                "error: regex backend requires --text or a .txt --pdf path",
                file=sys.stderr,
            )
            return 2
    elif args.backend in {"grobid", "vlm"}:
        if args.pdf is None:
            print(
                f"error: --pdf is required for the {args.backend} backend",
                file=sys.stderr,
            )
            return 2
        single = backends[0]
        if not single.is_available():
            print(
                f"env_not_ready: backend {single.name()!r} is not available on this host",
                file=sys.stderr,
            )
            return 3

    if args.backend == "ensemble":
        graph = run_ensemble(
            backends=backends,
            pdf_path=args.pdf,
            text=text_payload,
            output_dir=args.out_dir,
        )
    else:
        single = backends[0]
        graph = single.extract(
            pdf_path=args.pdf,
            text=text_payload,
            output_dir=args.out_dir,
        )

    if args.ocr_entities is not None:
        proposals = EntityProposalDocument.model_validate_json(
            args.ocr_entities.read_text(encoding="utf-8"),
        )
        candidates = entities_to_candidates(proposals)
        edges = resolve_markers(graph.markers, candidates)
        graph = graph.model_copy(update={"edges": list(graph.edges) + edges})
        resolved = sum(1 for e in edges if e.resolved)
        print(
            f"resolver: {len(edges)} marker(s) attempted, {resolved} resolved "
            f"against {len(candidates)} OCR candidate(s)",
            file=sys.stderr,
        )

    out_path = _write_graph(graph, args.out_dir)
    if args.verbose:
        print(json.dumps(json.loads(graph.model_dump_json()), indent=2, sort_keys=True))
    else:
        print(_summarise(graph, out_path))

    if not graph.markers and args.backend != "ensemble":
        # An ensemble run with no available backends legitimately returns
        # an empty graph; a single-backend run with no markers is a soft
        # failure surfaced to the caller.
        print(
            f"warning: backend {args.backend!r} produced no markers",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
