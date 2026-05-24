"""Benchmark runner for semantic backends (Plan 007_0).

For each ``.tex`` source under ``--gt-dir`` (recursive), this CLI:

    1. Generates a ground-truth :class:`CrossReferenceGraph` via
       ``latexml`` + the Plan 007_0 LaTeXML parser.
    2. Runs each requested backend against a plain-text rendering of
       the same .tex source (a simple inline detexer; PDF rendering is
       deferred to Plan 008's worked example).
    3. Evaluates the extracted graph against the ground truth.
    4. Writes per-document graphs + a combined ``results.{json,csv}``.

Exit codes:
    0 — success
    2 — bad arguments
    3 — latexml not available (env_not_ready)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.models.cross_ref import CrossReferenceGraph  # noqa: E402
from pdf2md.semantic import (  # noqa: E402
    GrobidSemanticBackend,
    LatexMLUnavailableError,
    RegexSemanticBackend,
    SemanticBackend,
    SemanticEvalResult,
    VlmSemanticBackend,
    evaluate_semantic,
    generate_ground_truth,
    result_to_csv_row,
    run_ensemble,
)


_BACKEND_CHOICES = ("regex", "grobid", "vlm", "ensemble")


def _build_backend(name: str) -> SemanticBackend | None:
    """Return a backend adapter instance, or ``None`` for the ensemble pseudo-name."""
    if name == "regex":
        return RegexSemanticBackend()
    if name == "grobid":
        return GrobidSemanticBackend()
    if name == "vlm":
        return VlmSemanticBackend()
    if name == "ensemble":
        return None
    raise ValueError(f"unknown backend: {name}")


def _ensemble_backends() -> list[SemanticBackend]:
    return [RegexSemanticBackend(), GrobidSemanticBackend(), VlmSemanticBackend()]


# Very small detexer: stripping commands and braces produces a plain-text
# approximation of the body, sufficient for the regex backend's pattern
# detection. This is intentionally narrow — Plan 008 will swap in a real
# PDF rendering step.
_TEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?")
_TEX_GROUP_RE = re.compile(r"[{}]")
_TEX_COMMENT_RE = re.compile(r"%.*?$", re.MULTILINE)


def detex(tex_source: str) -> str:
    """Return a crude plain-text rendering of ``tex_source``."""
    s = _TEX_COMMENT_RE.sub("", tex_source)
    s = _TEX_COMMAND_RE.sub(" ", s)
    s = _TEX_GROUP_RE.sub(" ", s)
    return " ".join(s.split())


def _document_id(tex_path: Path, gt_dir: Path) -> str:
    """Return a stable, filesystem-safe identifier for ``tex_path``.

    Relative to ``gt_dir`` with separators replaced — produces something
    like ``linked_sections_figures/linked_sections_figures`` for nested
    corpus entries.
    """
    rel = tex_path.relative_to(gt_dir).with_suffix("")
    return str(rel).replace("/", "__")


def _run_one_backend(
    backend_name: str,
    tex_text: str,
    tex_path: Path,
    out_dir: Path,
) -> CrossReferenceGraph:
    if backend_name == "ensemble":
        return run_ensemble(
            backends=_ensemble_backends(),
            pdf_path=None,
            text=tex_text,
            output_dir=out_dir,
        )
    backend = _build_backend(backend_name)
    assert backend is not None
    return backend.extract(pdf_path=None, text=tex_text, output_dir=out_dir)


def _write_graph(graph: CrossReferenceGraph, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(graph.model_dump_json(indent=2), encoding="utf-8")


def _write_results(results: list[SemanticEvalResult], out_dir: Path) -> None:
    json_path = out_dir / "results.json"
    csv_path = out_dir / "results.csv"
    json_path.write_text(
        json.dumps([asdict(r) for r in results], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if not results:
        csv_path.write_text("", encoding="utf-8")
        return
    rows = [result_to_csv_row(r) for r in results]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark semantic backends against a LaTeXML ground truth"
    )
    parser.add_argument("--gt-dir", required=True, type=Path)
    parser.add_argument(
        "--backends",
        default="regex",
        help="Comma-separated list of backends; choices: " + ",".join(_BACKEND_CHOICES),
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--latexml-bin", default="latexml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not args.gt_dir.is_dir():
        print(f"error: --gt-dir not found: {args.gt_dir}", file=sys.stderr)
        return 2

    requested = [name.strip() for name in args.backends.split(",") if name.strip()]
    for name in requested:
        if name not in _BACKEND_CHOICES:
            print(
                f"error: unknown backend {name!r}; choices: {','.join(_BACKEND_CHOICES)}",
                file=sys.stderr,
            )
            return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)

    tex_files = sorted(args.gt_dir.rglob("*.tex"))
    if not tex_files:
        print(f"error: no .tex files found under {args.gt_dir}", file=sys.stderr)
        return 2

    results: list[SemanticEvalResult] = []
    for tex_path in tex_files:
        doc_id = _document_id(tex_path, args.gt_dir)
        doc_out_dir = args.out_dir / doc_id
        doc_out_dir.mkdir(parents=True, exist_ok=True)
        try:
            gt = generate_ground_truth(
                tex_path,
                doc_out_dir,
                latexml_bin=args.latexml_bin,
            )
        except LatexMLUnavailableError as exc:
            print(f"env_not_ready: {exc}", file=sys.stderr)
            return 3
        except (RuntimeError, ValueError) as exc:
            print(f"warning: ground truth failed for {tex_path}: {exc}", file=sys.stderr)
            continue
        _write_graph(gt, doc_out_dir / "gt_cross_references.json")

        tex_source = tex_path.read_text(encoding="utf-8", errors="replace")
        tex_text = detex(tex_source)

        for backend_name in requested:
            try:
                extracted = _run_one_backend(
                    backend_name,
                    tex_text,
                    tex_path,
                    doc_out_dir / backend_name,
                )
            except RuntimeError as exc:
                print(
                    f"warning: backend {backend_name!r} failed on {doc_id}: {exc}",
                    file=sys.stderr,
                )
                continue
            _write_graph(
                extracted,
                doc_out_dir / f"{backend_name}_cross_references.json",
            )
            result = evaluate_semantic(
                extracted=extracted,
                ground_truth=gt,
                document_id=doc_id,
                backend=backend_name,
            )
            results.append(result)
            if args.verbose:
                print(
                    f"  {doc_id} :: {backend_name} :: "
                    f"P={result.marker_precision:.3f} "
                    f"R={result.marker_recall:.3f} "
                    f"F1={result.marker_f1:.3f}"
                )

    _write_results(results, args.out_dir)
    print(
        f"benchmark: {len(tex_files)} document(s), "
        f"{len(requested)} backend(s), "
        f"{len(results)} (doc, backend) result(s); "
        f"out={args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
