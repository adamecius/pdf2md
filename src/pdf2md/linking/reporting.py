"""Audit reporting helpers for linked structure builds (Plan 14 hardening)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from pdf2md.models.linked import LinkedStructure, LinkStatus

READINESS_STATUSES: tuple[str, ...] = (
    "ready_for_plan_15",
    "ready_with_warnings",
    "not_ready_for_plan_15",
    "diagnostic_only",
)


def _status_value(value: LinkStatus | str) -> str:
    return value.value if isinstance(value, LinkStatus) else str(value)


def _link_status_counts(linked: LinkedStructure) -> dict[str, int]:
    counts: dict[str, int] = {status.value: 0 for status in LinkStatus}
    for relation in linked.relations:
        counts[_status_value(relation.status)] = counts.get(_status_value(relation.status), 0) + 1
    return counts


def _relation_type_status_table(linked: LinkedStructure) -> dict[str, dict[str, int]]:
    """For each RelationType, tally per-LinkStatus counts."""

    table: dict[str, dict[str, int]] = {}
    for relation in linked.relations:
        rt = str(relation.relation_type)
        st = _status_value(relation.status)
        bucket = table.setdefault(rt, {status.value: 0 for status in LinkStatus})
        bucket[st] = bucket.get(st, 0) + 1
    return table


def _low_confidence_counts(
    linked: LinkedStructure, low_confidence_threshold: float
) -> dict[str, Any]:
    low_relations = 0
    low_nodes = 0
    for relation in linked.relations:
        if getattr(relation, "confidence", None) is not None and relation.confidence < low_confidence_threshold:
            low_relations += 1
    for node in linked.nodes:
        if getattr(node, "confidence", None) is not None and node.confidence < low_confidence_threshold:
            low_nodes += 1
    result: dict[str, Any] = {
        "low_confidence_relations": low_relations,
        "low_confidence_nodes": low_nodes,
        "threshold": low_confidence_threshold,
    }
    return result


def _plan15_readiness(
    linked: LinkedStructure,
    inputs_used: dict[str, Any],
    low_confidence: dict[str, int],
    unresolved_count: int,
    inspection_status: str,
) -> dict[str, Any]:
    """Surface fields Plan 15 (Docling export) needs as inputs."""

    has_reading_order = any(
        str(r.relation_type).lower() == "page_number_sequence_next"
        or str(r.relation_type).lower() == "follows"
        for r in linked.relations
    )
    return {
        "linked_node_count": len(linked.nodes),
        "linked_relation_count": len(linked.relations),
        "linked_conflict_count": len(linked.conflicts),
        "unresolved_relation_count": unresolved_count,
        "low_confidence_relation_count": low_confidence["low_confidence_relations"],
        "low_confidence_node_count": low_confidence["low_confidence_nodes"],
        "has_reading_order": has_reading_order,
        "source_consensus_ir": linked.source_consensus_ir,
        "source_consensus_report": linked.source_consensus_report,
        "source_entity_documents": list(linked.source_entity_documents or []),
        "source_prior_documents": list(linked.source_prior_documents or []),
        "entities_root_used": inputs_used.get("entities_root_used", False),
        "priors_root_used": inputs_used.get("priors_root_used", False),
        "consensus_report_used": inputs_used.get("consensus_report_used", False),
        "inspection_status": inspection_status,
        "docling_export_handled_by": "plan_15",
    }


def build_linking_report(
    linked: LinkedStructure,
    *,
    low_confidence_threshold: float = 0.60,
    inspection_status: str | None = None,
    inspection_notes: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build the Plan 14 linking audit report.

    Backwards compatible: pre-existing top-level fields (``schema_name``,
    ``schema_version``, ``document_id``, ``node_count``, ``relation_count``,
    ``conflict_count``, ``warnings``, ``node_type_counts``,
    ``relation_type_counts``, ``unresolved``) are preserved; new fields
    (``link_status_counts``, ``relation_type_status``, ``low_confidence``,
    ``inputs_used``, ``inspection_status``, ``inspection_notes``,
    ``plan15_readiness``) are added without renaming existing ones.
    """

    if inspection_status is not None and inspection_status not in READINESS_STATUSES:
        raise ValueError(
            f"inspection_status must be one of {READINESS_STATUSES}; got {inspection_status!r}"
        )
    effective_inspection = inspection_status or "diagnostic_only"

    unresolved = [
        {"id": conflict.id, "conflict_type": conflict.conflict_type}
        for conflict in linked.conflicts
        if conflict.status == LinkStatus.UNRESOLVED
        or str(conflict.status) == LinkStatus.UNRESOLVED.value
    ]

    link_status_counts = _link_status_counts(linked)
    relation_type_status = _relation_type_status_table(linked)
    low_confidence = _low_confidence_counts(linked, low_confidence_threshold)

    inputs_used = {
        "entities_root_used": bool(linked.source_entity_documents),
        "priors_root_used": bool(linked.source_prior_documents),
        "consensus_report_used": bool(linked.source_consensus_report),
    }

    plan15 = _plan15_readiness(
        linked,
        inputs_used,
        low_confidence,
        len(unresolved),
        effective_inspection,
    )

    return {
        "schema_name": "pdf2md.LinkingReport",
        "schema_version": "1.0.0",
        "document_id": linked.document_id,
        "node_count": len(linked.nodes),
        "relation_count": len(linked.relations),
        "conflict_count": len(linked.conflicts),
        "warnings": list(linked.warnings),
        "node_type_counts": dict(Counter(str(node.node_type) for node in linked.nodes)),
        "relation_type_counts": dict(
            Counter(str(relation.relation_type) for relation in linked.relations)
        ),
        "unresolved": unresolved,
        "link_status_counts": link_status_counts,
        "relation_type_status": relation_type_status,
        "low_confidence": low_confidence,
        "inputs_used": inputs_used,
        "inspection_status": effective_inspection,
        "inspection_notes": list(inspection_notes or []),
        "plan15_readiness": plan15,
    }


def build_linking_summary(report: dict[str, Any]) -> str:
    """Render a human-readable summary of the linking report (Plan 14)."""

    plan15 = report.get("plan15_readiness", {})
    low_confidence = report.get("low_confidence", {})
    link_status = report.get("link_status_counts", {})

    lines = [
        "pdf2md linked structure summary (Plan 14)",
        f"schema: {report.get('schema_name')} {report.get('schema_version')}",
        f"document_id: {report.get('document_id')}",
        f"node_count: {report.get('node_count')}",
        f"relation_count: {report.get('relation_count')}",
        f"conflict_count: {report.get('conflict_count')}",
        f"inspection_status: {report.get('inspection_status')}",
        "",
        "link status counts:",
    ]
    for status, count in sorted(link_status.items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "node type counts:"])
    node_counts = report.get("node_type_counts", {})
    if not node_counts:
        lines.append("- (none)")
    for kind, count in sorted(node_counts.items()):
        lines.append(f"- {kind}: {count}")

    lines.extend(["", "relation type counts:"])
    relation_counts = report.get("relation_type_counts", {})
    if not relation_counts:
        lines.append("- (none)")
    for rt, count in sorted(relation_counts.items()):
        lines.append(f"- {rt}: {count}")

    lines.extend(
        [
            "",
            "low confidence:",
            f"- low_confidence_relations: {low_confidence.get('low_confidence_relations', 0)}",
            f"- low_confidence_nodes: {low_confidence.get('low_confidence_nodes', 0)}",
            f"- threshold: {low_confidence.get('threshold')}",
        ]
    )

    unresolved = report.get("unresolved", [])
    if unresolved:
        lines.extend(["", "unresolved candidates:"])
        for entry in unresolved:
            lines.append(f"- {entry['id']} [{entry['conflict_type']}]")

    inputs = report.get("inputs_used", {})
    lines.extend(
        [
            "",
            "inputs used:",
            f"- entities_root_used: {inputs.get('entities_root_used')}",
            f"- priors_root_used: {inputs.get('priors_root_used')}",
            f"- consensus_report_used: {inputs.get('consensus_report_used')}",
        ]
    )

    notes = report.get("inspection_notes") or []
    if notes:
        lines.extend(["", "inspection notes:"])
        lines.extend(f"- {n}" for n in notes)

    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in warnings)

    lines.extend(
        [
            "",
            "Plan 15 readiness:",
            f"- linked_node_count: {plan15.get('linked_node_count')}",
            f"- linked_relation_count: {plan15.get('linked_relation_count')}",
            f"- linked_conflict_count: {plan15.get('linked_conflict_count')}",
            f"- unresolved_relation_count: {plan15.get('unresolved_relation_count')}",
            f"- low_confidence_relation_count: {plan15.get('low_confidence_relation_count')}",
            f"- has_reading_order: {plan15.get('has_reading_order')}",
            f"- entities_root_used: {plan15.get('entities_root_used')}",
            f"- priors_root_used: {plan15.get('priors_root_used')}",
            f"- source_consensus_ir: {plan15.get('source_consensus_ir')}",
            f"- inspection_status: {plan15.get('inspection_status')}",
            "- Docling export is deferred to Plan 15 and is not used for Plan 14 pass/fail.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "READINESS_STATUSES",
    "build_linking_report",
    "build_linking_summary",
]
