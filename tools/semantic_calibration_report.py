#!/usr/bin/env python
"""Build the Plan 007_2 semantic calibration report from viewer graph data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.calibration.semantic_report import (  # noqa: E402
    apply_adjudications,
    load_graph,
    render_json,
    render_markdown,
    resolution_matrix,
    with_entity_counts,
)


class BadInputError(ValueError):
    """Raised when the user supplied malformed report inputs."""


class EnvironmentMissingError(RuntimeError):
    """Raised when the examples-only data surface is missing."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Return the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("webui/cross_ref/data"))
    parser.add_argument("--adjudications", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def discover_graphs(data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Discover resolved graph payloads and OCR entity counts under ``data_dir``."""

    manifest = _load_manifest(data_dir)
    graphs: list[dict[str, Any]] = []
    entity_counts: dict[str, dict[str, int]] = {}
    for example in _manifest_examples(manifest):
        example_id = example["id"]
        example_dir = data_dir / example_id
        if not example_dir.is_dir():
            raise EnvironmentMissingError(f"example directory not found: {example_dir}")
        entity_counts[example_id] = _load_entity_counts(example_dir)
        for graph_path in sorted(example_dir.glob("*__resolved_with__*.json")):
            semantic_backend, ocr_backend = _parse_resolved_graph_name(graph_path)
            try:
                graph = load_graph(graph_path)
            except ValueError as exc:
                raise BadInputError(f"malformed graph file {graph_path}: {exc}") from exc
            graph["_calibration"] = {
                "document_id": graph.get("document_id"),
                "example": example_id,
                "semantic_backend": semantic_backend,
                "ocr_backend": ocr_backend,
                "graph_path": str(graph_path),
            }
            graphs.append(graph)
    if not graphs:
        raise EnvironmentMissingError(f"no resolved graph files found under {data_dir}")
    return graphs, entity_counts


def _load_manifest(data_dir: Path) -> dict[str, Any]:
    if not data_dir.is_dir():
        raise EnvironmentMissingError(f"--data-dir not found: {data_dir}")
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        raise EnvironmentMissingError(f"manifest.json not found: {manifest_path}")
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except json.JSONDecodeError as exc:
        raise BadInputError(f"malformed manifest.json: {exc}") from exc
    if not isinstance(manifest, dict):
        raise BadInputError("manifest.json must be a JSON object")
    return manifest


def _manifest_examples(manifest: dict[str, Any]) -> list[dict[str, str]]:
    examples = manifest.get("examples")
    if not isinstance(examples, list) or not examples:
        raise BadInputError("manifest.json must contain a non-empty examples list")
    normalised: list[dict[str, str]] = []
    for item in examples:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise BadInputError("each manifest example must be an object with an id")
        normalised.append({"id": item["id"]})
    return normalised


def _parse_resolved_graph_name(path: Path) -> tuple[str, str]:
    if "__resolved_with__" not in path.stem:
        raise BadInputError(f"not a resolved graph filename: {path.name}")
    semantic_backend, ocr_backend = path.stem.split("__resolved_with__", 1)
    if not semantic_backend or not ocr_backend:
        raise BadInputError(f"resolved graph filename is missing a backend: {path.name}")
    return semantic_backend, ocr_backend


def _load_entity_counts(example_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(example_dir.glob("entities_*.json")):
        ocr_backend = path.stem.removeprefix("entities_")
        try:
            payload = load_graph(path)
        except ValueError as exc:
            raise BadInputError(f"malformed entity file {path}: {exc}") from exc
        entities = payload.get("entities", [])
        if not isinstance(entities, list):
            raise BadInputError(f"entities must be a list in {path}")
        counts[ocr_backend] = len(entities)
    return counts


def _load_adjudications(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        raise BadInputError(f"--adjudications not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise BadInputError(f"malformed adjudications JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BadInputError("--adjudications must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        graphs, entity_counts = discover_graphs(args.data_dir)
        report = with_entity_counts(resolution_matrix(graphs), entity_counts)
        adjudications = _load_adjudications(args.adjudications)
        if adjudications is not None:
            report = apply_adjudications(report, adjudications)

        args.out_dir.mkdir(parents=True, exist_ok=True)
        md_path = args.out_dir / "semantic_calibration_report.md"
        json_path = args.out_dir / "semantic_calibration_report.json"
        md_path.write_text(render_markdown(report), encoding="utf-8")
        json_path.write_text(render_json(report), encoding="utf-8")
    except BadInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except EnvironmentMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"error: environment failure: {exc}", file=sys.stderr)
        return 3

    print(
        "semantic_calibration_report: "
        f"{len(report.per_combo)} graph combinations; "
        f"markdown={md_path}; json={json_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
