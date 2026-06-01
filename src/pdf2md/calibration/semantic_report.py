"""Semantic cross-reference calibration report helpers.

This module reads D3 graph-export payloads from the cross-reference viewer and
summarises how often each OCR candidate source resolves semantic markers.
The functions are deliberately CLI-free so the report arithmetic can be tested
without touching the examples-only corpus on disk.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

REPORT_SCHEMA_VERSION = "1.0.0"
CROSS_REFERENCE_EDGE_KIND = "cross_reference"
UNRESOLVED_TARGET_ID = "_unresolved"


@dataclass(frozen=True)
class ResolutionCount:
    """Resolved/total counts and their derived resolution rate."""

    total: int
    resolved: int
    resolution_rate: float


@dataclass(frozen=True)
class ComboResult:
    """Resolution summary for one example, semantic backend, and OCR backend."""

    example: str
    semantic_backend: str
    ocr_backend: str
    document_id: str
    graph_path: str | None
    total: int
    resolved: int
    resolution_rate: float
    per_type: dict[str, ResolutionCount]


@dataclass(frozen=True)
class ReportData:
    """Full semantic calibration report data."""

    per_combo: list[ComboResult]
    cross_backend_matrix: dict[str, dict[str, float]]
    cross_backend_counts: dict[str, dict[str, ResolutionCount]]
    entity_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    source_graphs: list[str] = field(default_factory=list)
    adjudication_count: int = 0


@dataclass
class _MutableCount:
    total: int = 0
    resolved: int = 0

    def add(self, other: ResolutionCount | _MutableCount) -> None:
        self.total += other.total
        self.resolved += other.resolved


def load_graph(path: Path) -> dict[str, Any]:
    """Load one graph JSON payload from ``path``."""

    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"graph payload must be a JSON object: {path}")
    return payload


def resolution_matrix(graphs: list[dict[str, Any]]) -> ReportData:
    """Compute per-combination counts and the aggregated OCR-backend matrix."""

    combos: list[ComboResult] = []
    source_graphs: list[str] = []
    for graph in graphs:
        context = _graph_context(graph)
        source_path = context.get("graph_path")
        if source_path:
            source_graphs.append(source_path)

        counts: dict[str, _MutableCount] = {}
        edges = graph.get("edges", [])
        if not isinstance(edges, list):
            raise ValueError("graph edges must be a list")
        for edge in edges:
            if not isinstance(edge, dict) or not _is_cross_reference_edge(edge):
                continue
            marker_type = _edge_marker_type(edge)
            if marker_type is None:
                continue
            count = counts.setdefault(marker_type, _MutableCount())
            count.total += 1
            if _edge_resolved(edge):
                count.resolved += 1

        combos.append(_combo_result(context, counts))

    combos.sort(key=lambda c: (c.example, c.semantic_backend, c.ocr_backend, c.document_id))
    return _build_report(combos, source_graphs=sorted(source_graphs))


def apply_adjudications(report: ReportData, adj: Any) -> ReportData:
    """Return a copy of ``report`` with Plan 008_4 label corrections applied.

    ``noise`` decrements the relevant total count, while ``resolve`` increments
    the resolved count for an already-counted unresolved marker. Reclassify and
    rule-hint labels are intentionally ignored here because they require a
    richer ground-truth rewrite than this Plan 007_2 report performs.
    """

    document = _plain_adjudication_document(adj)
    if document is None:
        return report

    default_scope = _adjudication_scope(document) if isinstance(document, dict) else {}
    items = _adjudication_items(document)
    combo_counts = [_counts_from_combo(combo) for combo in report.per_combo]
    applied = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        decision = str(item.get("decision", "")).strip().lower()
        if decision not in {"noise", "resolve"}:
            continue
        marker_type = _adjudication_marker_type(item)
        if not marker_type:
            continue
        scope = {**default_scope, **_adjudication_scope(item)}
        targets = _matching_combo_indexes(report, marker_type, scope)
        for index in targets:
            count = combo_counts[index].setdefault(marker_type, _MutableCount())
            if decision == "noise":
                if count.total <= 0:
                    continue
                count.total -= 1
                if _adjudication_was_resolved(item):
                    count.resolved = max(0, count.resolved - 1)
                count.resolved = min(count.resolved, count.total)
            elif decision == "resolve":
                if count.resolved >= count.total:
                    continue
                count.resolved += 1
            applied += 1

    corrected = [
        _combo_result(
            {
                "example": combo.example,
                "semantic_backend": combo.semantic_backend,
                "ocr_backend": combo.ocr_backend,
                "document_id": combo.document_id,
                "graph_path": combo.graph_path,
            },
            counts,
        )
        for combo, counts in zip(report.per_combo, combo_counts, strict=True)
    ]
    return _build_report(
        corrected,
        entity_counts=report.entity_counts,
        source_graphs=report.source_graphs,
        adjudication_count=report.adjudication_count + applied,
    )


def render_markdown(report: ReportData) -> str:
    """Render a human-readable semantic calibration summary."""

    examples = sorted({combo.example for combo in report.per_combo})
    semantic_backends = sorted({combo.semantic_backend for combo in report.per_combo})
    ocr_backends = sorted({combo.ocr_backend for combo in report.per_combo})
    lines = [
        "# Semantic Calibration Report",
        "",
        f"- schema: pdf2md.semantic_calibration_report {REPORT_SCHEMA_VERSION}",
        f"- examples: {', '.join(examples) if examples else '(none)'}",
        f"- semantic backends: {', '.join(semantic_backends) if semantic_backends else '(none)'}",
        f"- OCR candidate sources: {', '.join(ocr_backends) if ocr_backends else '(none)'}",
        f"- source graphs: {len(report.source_graphs) or len(report.per_combo)}",
        f"- adjudication corrections applied: {report.adjudication_count}",
        "",
    ]

    if report.entity_counts:
        lines.extend(_render_entity_counts(report.entity_counts))
        lines.append("")

    lines.extend(_render_cross_backend_matrix(report.cross_backend_counts))
    lines.append("")
    lines.extend(_render_combo_table(report.per_combo))
    lines.append("")
    lines.extend(_render_type_breakdown(report.per_combo))
    lines.append("")
    return "\n".join(lines)


def render_json(report: ReportData) -> str:
    """Render ``report`` as deterministic JSON."""

    payload = {
        "schema_name": "pdf2md.semantic_calibration_report",
        "schema_version": REPORT_SCHEMA_VERSION,
        "adjudication_count": report.adjudication_count,
        "source_graphs": sorted(report.source_graphs),
        "entity_counts": _sorted_entity_counts(report.entity_counts),
        "per_combo": [_combo_to_json(combo) for combo in report.per_combo],
        "cross_backend_matrix": _sorted_nested_float_map(report.cross_backend_matrix),
        "cross_backend_counts": _counts_to_json(report.cross_backend_counts),
        "calibration_weights": _sorted_nested_float_map(report.cross_backend_matrix),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def with_entity_counts(report: ReportData, entity_counts: dict[str, dict[str, int]]) -> ReportData:
    """Attach entity-count metadata discovered by the CLI."""

    return _build_report(
        report.per_combo,
        entity_counts=entity_counts,
        source_graphs=report.source_graphs,
        adjudication_count=report.adjudication_count,
    )


def _rate(resolved: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(resolved / total, 6)


def _resolution_count(count: _MutableCount | ResolutionCount) -> ResolutionCount:
    total = max(0, count.total)
    resolved = min(max(0, count.resolved), total)
    return ResolutionCount(total=total, resolved=resolved, resolution_rate=_rate(resolved, total))


def _combo_result(context: dict[str, str | None], counts: dict[str, _MutableCount]) -> ComboResult:
    per_type = {marker_type: _resolution_count(counts[marker_type]) for marker_type in sorted(counts)}
    total = sum(count.total for count in per_type.values())
    resolved = sum(count.resolved for count in per_type.values())
    return ComboResult(
        example=context.get("example") or "unknown",
        semantic_backend=context.get("semantic_backend") or "unknown",
        ocr_backend=context.get("ocr_backend") or "unknown",
        document_id=context.get("document_id") or "unknown",
        graph_path=context.get("graph_path"),
        total=total,
        resolved=resolved,
        resolution_rate=_rate(resolved, total),
        per_type=per_type,
    )


def _build_report(
    combos: list[ComboResult],
    *,
    entity_counts: dict[str, dict[str, int]] | None = None,
    source_graphs: list[str] | None = None,
    adjudication_count: int = 0,
) -> ReportData:
    aggregate: dict[str, dict[str, _MutableCount]] = {}
    ocr_backends = sorted({combo.ocr_backend for combo in combos})
    marker_types = sorted({marker_type for combo in combos for marker_type in combo.per_type})

    for marker_type in marker_types:
        aggregate[marker_type] = {ocr_backend: _MutableCount() for ocr_backend in ocr_backends}
    for combo in combos:
        for marker_type, count in combo.per_type.items():
            aggregate[marker_type][combo.ocr_backend].add(count)

    cross_backend_counts: dict[str, dict[str, ResolutionCount]] = {}
    cross_backend_matrix: dict[str, dict[str, float]] = {}
    for marker_type in marker_types:
        count_row = {
            ocr_backend: _resolution_count(aggregate[marker_type][ocr_backend])
            for ocr_backend in ocr_backends
        }
        cross_backend_counts[marker_type] = count_row
        cross_backend_matrix[marker_type] = {
            ocr_backend: count.resolution_rate for ocr_backend, count in count_row.items()
        }

    return ReportData(
        per_combo=combos,
        cross_backend_matrix=cross_backend_matrix,
        cross_backend_counts=cross_backend_counts,
        entity_counts=_sorted_entity_counts(entity_counts or {}),
        source_graphs=sorted(source_graphs or []),
        adjudication_count=adjudication_count,
    )


def _graph_context(graph: dict[str, Any]) -> dict[str, str | None]:
    metadata = graph.get("_calibration", {})
    if not isinstance(metadata, dict):
        metadata = {}
    document_id = str(
        metadata.get("document_id")
        or graph.get("document_id")
        or graph.get("doc_hash")
        or graph.get("id")
        or "unknown"
    )
    parsed = _parse_document_id(document_id)
    return {
        "example": _str_or_none(metadata.get("example")) or parsed["example"],
        "semantic_backend": _str_or_none(metadata.get("semantic_backend")) or parsed["semantic_backend"],
        "ocr_backend": _str_or_none(metadata.get("ocr_backend")) or parsed["ocr_backend"],
        "document_id": document_id,
        "graph_path": _str_or_none(metadata.get("graph_path")),
    }


def _parse_document_id(document_id: str) -> dict[str, str]:
    example = "unknown"
    semantic_backend = "unknown"
    ocr_backend = "unknown"
    if "/" in document_id:
        example, combo = document_id.split("/", 1)
    else:
        combo = document_id
    if "+" in combo:
        semantic_backend, ocr_backend = combo.rsplit("+", 1)
    return {
        "example": example or "unknown",
        "semantic_backend": semantic_backend or "unknown",
        "ocr_backend": ocr_backend or "unknown",
    }


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_cross_reference_edge(edge: dict[str, Any]) -> bool:
    return str(edge.get("edge_kind", CROSS_REFERENCE_EDGE_KIND)) == CROSS_REFERENCE_EDGE_KIND


def _edge_marker_type(edge: dict[str, Any]) -> str | None:
    marker_type = edge.get("marker_type")
    if marker_type is None and isinstance(edge.get("marker"), dict):
        marker_type = edge["marker"].get("marker_type")
    return _str_or_none(marker_type)


def _edge_resolved(edge: dict[str, Any]) -> bool:
    if "resolved" in edge:
        return bool(edge["resolved"])
    target = edge.get("target") or edge.get("target_ref")
    return target not in {None, "", UNRESOLVED_TARGET_ID}


def _plain_adjudication_document(adj: Any) -> dict[str, Any] | list[Any] | None:
    if adj is None:
        return None
    if isinstance(adj, (dict, list)):
        return adj
    if hasattr(adj, "model_dump"):
        dumped = adj.model_dump(mode="json")
        if isinstance(dumped, (dict, list)):
            return dumped
    if is_dataclass(adj):
        dumped = asdict(adj)
        if isinstance(dumped, (dict, list)):
            return dumped
    return None


def _adjudication_items(document: dict[str, Any] | list[Any]) -> list[Any]:
    if isinstance(document, list):
        return document
    for key in ("adjudications", "labels", "items", "decisions"):
        value = document.get(key)
        if isinstance(value, list):
            return value
    return []


def _adjudication_scope(item: dict[str, Any]) -> dict[str, str]:
    scope: dict[str, str] = {}
    for key in ("document_id", "example", "semantic_backend", "ocr_backend"):
        value = _str_or_none(item.get(key))
        if value is not None:
            scope[key] = value
    semantic = _str_or_none(item.get("semantic"))
    if semantic is not None:
        scope["semantic_backend"] = semantic
    ocr = _str_or_none(item.get("ocr"))
    if ocr is not None:
        scope["ocr_backend"] = ocr
    return scope


def _adjudication_marker_type(item: dict[str, Any]) -> str | None:
    for key in ("marker_type", "ref_type", "type"):
        value = _str_or_none(item.get(key))
        if value is not None:
            return value
    for key in ("marker", "edge"):
        nested = item.get(key)
        if isinstance(nested, dict):
            value = _str_or_none(nested.get("marker_type") or nested.get("ref_type") or nested.get("type"))
            if value is not None:
                return value
    return None


def _adjudication_was_resolved(item: dict[str, Any]) -> bool:
    for key in ("resolved", "was_resolved"):
        if key in item:
            return bool(item[key])
    edge = item.get("edge")
    if isinstance(edge, dict) and "resolved" in edge:
        return bool(edge["resolved"])
    return False


def _matching_combo_indexes(report: ReportData, marker_type: str, scope: dict[str, str]) -> list[int]:
    indexes: list[int] = []
    for index, combo in enumerate(report.per_combo):
        if marker_type not in combo.per_type:
            continue
        if not _combo_matches_scope(combo, scope):
            continue
        indexes.append(index)
    return indexes


def _combo_matches_scope(combo: ComboResult, scope: dict[str, str]) -> bool:
    document_id = scope.get("document_id")
    if document_id and not (
        combo.document_id == document_id
        or combo.document_id.startswith(f"{document_id}/")
        or document_id == combo.example
    ):
        return False
    example = scope.get("example")
    if example and combo.example != example:
        return False
    semantic_backend = scope.get("semantic_backend")
    if semantic_backend and combo.semantic_backend != semantic_backend:
        return False
    ocr_backend = scope.get("ocr_backend")
    return not (ocr_backend and combo.ocr_backend != ocr_backend)


def _counts_from_combo(combo: ComboResult) -> dict[str, _MutableCount]:
    return {
        marker_type: _MutableCount(total=count.total, resolved=count.resolved)
        for marker_type, count in combo.per_type.items()
    }


def _format_rate(count: ResolutionCount) -> str:
    if count.total == 0:
        return "n/a (0/0)"
    return f"{count.resolution_rate * 100:.1f}% ({count.resolved}/{count.total})"


def _render_entity_counts(entity_counts: dict[str, dict[str, int]]) -> list[str]:
    ocr_backends = sorted({ocr for counts in entity_counts.values() for ocr in counts})
    lines = ["## Entity Counts", "", "| example | " + " | ".join(ocr_backends) + " |"]
    lines.append("|---|" + "|".join("---" for _ in ocr_backends) + "|")
    for example in sorted(entity_counts):
        row = [example]
        row.extend(str(entity_counts[example].get(ocr_backend, 0)) for ocr_backend in ocr_backends)
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _render_cross_backend_matrix(counts: dict[str, dict[str, ResolutionCount]]) -> list[str]:
    ocr_backends = sorted({ocr for row in counts.values() for ocr in row})
    lines = [
        "## Cross-Backend Matrix",
        "",
        "Resolution rates aggregate all semantic backends and examples by OCR candidate source.",
        "",
        "| marker_type | " + " | ".join(ocr_backends) + " |",
        "|---|" + "|".join("---" for _ in ocr_backends) + "|",
    ]
    for marker_type in sorted(counts):
        row = [marker_type]
        row.extend(_format_rate(counts[marker_type].get(ocr_backend, ResolutionCount(0, 0, 0.0))) for ocr_backend in ocr_backends)
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _render_combo_table(combos: list[ComboResult]) -> list[str]:
    lines = [
        "## Per-Combination Summary",
        "",
        "| example | semantic_backend | ocr_backend | resolved | total | rate |",
        "|---|---|---|---:|---:|---:|",
    ]
    for combo in combos:
        lines.append(
            f"| {combo.example} | {combo.semantic_backend} | {combo.ocr_backend} | "
            f"{combo.resolved} | {combo.total} | {combo.resolution_rate * 100:.1f}% |"
        )
    return lines


def _render_type_breakdown(combos: list[ComboResult]) -> list[str]:
    lines = [
        "## Per-Type Breakdown",
        "",
        "| example | semantic_backend | ocr_backend | marker_type | resolved | total | rate |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for combo in combos:
        for marker_type, count in combo.per_type.items():
            lines.append(
                f"| {combo.example} | {combo.semantic_backend} | {combo.ocr_backend} | "
                f"{marker_type} | {count.resolved} | {count.total} | {count.resolution_rate * 100:.1f}% |"
            )
    return lines


def _combo_to_json(combo: ComboResult) -> dict[str, Any]:
    return {
        "document_id": combo.document_id,
        "example": combo.example,
        "graph_path": combo.graph_path,
        "ocr_backend": combo.ocr_backend,
        "per_type": {key: _count_to_json(value) for key, value in sorted(combo.per_type.items())},
        "resolution_rate": combo.resolution_rate,
        "resolved": combo.resolved,
        "semantic_backend": combo.semantic_backend,
        "total": combo.total,
    }


def _count_to_json(count: ResolutionCount) -> dict[str, int | float]:
    return {
        "resolution_rate": count.resolution_rate,
        "resolved": count.resolved,
        "total": count.total,
    }


def _counts_to_json(counts: dict[str, dict[str, ResolutionCount]]) -> dict[str, dict[str, dict[str, int | float]]]:
    return {
        marker_type: {ocr: _count_to_json(count) for ocr, count in sorted(row.items())}
        for marker_type, row in sorted(counts.items())
    }


def _sorted_nested_float_map(data: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        key: {inner_key: row[inner_key] for inner_key in sorted(row)}
        for key, row in sorted(data.items())
    }


def _sorted_entity_counts(data: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return {
        example: {ocr_backend: int(counts[ocr_backend]) for ocr_backend in sorted(counts)}
        for example, counts in sorted(data.items())
    }


__all__ = [
    "ComboResult",
    "ReportData",
    "ResolutionCount",
    "apply_adjudications",
    "load_graph",
    "render_json",
    "render_markdown",
    "resolution_matrix",
    "with_entity_counts",
]
