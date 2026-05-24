"""Audit reporting for consensus runs (Plan 13 hardening)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pdf2md.models.ir import ConsensusIR, SelectionMode

INSPECTION_STATUSES: tuple[str, ...] = (
    "appears_better_than_backends",
    "appears_equivalent_to_best_backend",
    "appears_worse_than_best_backend",
    "inconclusive",
    "diagnostic_only",
)


def _selection_value(value: SelectionMode | str) -> str:
    return value.value if isinstance(value, SelectionMode) else str(value)


_DEFAULT_BACKEND_BUCKET: dict[str, int] = {
    "accepted_blocks": 0,
    "single_source_blocks": 0,
    "fallback_blocks": 0,
    "unresolved_blocks": 0,
    "candidate_participations": 0,
    "conflict_participations": 0,
}


def _bucket_for(contributions: dict[str, dict[str, Any]], backend: str) -> dict[str, Any]:
    return contributions.setdefault(backend, dict(_DEFAULT_BACKEND_BUCKET))


def _backend_from_candidate_id(candidate_id: str) -> str:
    return candidate_id.split(":", 1)[0] if ":" in candidate_id else candidate_id


def _backend_contributions(consensus: ConsensusIR) -> dict[str, dict[str, Any]]:
    """Tally per-backend acceptance, candidate participation, and conflict participation."""

    contributions: dict[str, dict[str, Any]] = {}
    for page in consensus.pages:
        for block in page.blocks:
            source = block.selected_source
            mode = _selection_value(block.selection_mode)
            if source:
                bucket = _bucket_for(contributions, source)
                if mode == SelectionMode.AGREED.value:
                    bucket["accepted_blocks"] += 1
                elif mode == SelectionMode.SINGLE_SOURCE.value:
                    bucket["single_source_blocks"] += 1
                elif mode == SelectionMode.FALLBACK.value:
                    bucket["fallback_blocks"] += 1
                elif mode == SelectionMode.UNRESOLVED.value:
                    bucket["unresolved_blocks"] += 1
            # candidate_participations covers every backend that contributed a candidate
            # to the consensus group, including agreed/fallback backends that were not
            # the selected_source.
            for candidate_id in block.candidate_ids:
                _bucket_for(contributions, _backend_from_candidate_id(candidate_id))[
                    "candidate_participations"
                ] += 1

    for conflict in consensus.conflicts:
        for candidate_id in conflict.candidate_ids:
            _bucket_for(contributions, _backend_from_candidate_id(candidate_id))[
                "conflict_participations"
            ] += 1
    return contributions


def _confidence_summary(consensus: ConsensusIR) -> dict[str, Any]:
    scores: list[float] = []
    for page in consensus.pages:
        for block in page.blocks:
            scores.append(block.agreement_score)
    if not scores:
        return {
            "block_count": 0,
            "mean_agreement_score": None,
            "min_agreement_score": None,
            "max_agreement_score": None,
            "low_confidence_blocks": 0,
        }
    sorted_scores = sorted(scores)
    low_threshold = 0.5
    low = sum(1 for s in scores if s < low_threshold)
    return {
        "block_count": len(scores),
        "mean_agreement_score": sum(scores) / len(scores),
        "min_agreement_score": sorted_scores[0],
        "max_agreement_score": sorted_scores[-1],
        "low_confidence_threshold": low_threshold,
        "low_confidence_blocks": low,
    }


def _conflict_details(consensus: ConsensusIR) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for conflict in consensus.conflicts:
        details.append(
            {
                "id": conflict.id,
                "kind": _selection_value(conflict.kind),
                "page_no": conflict.page_no,
                "candidate_ids": list(conflict.candidate_ids),
                "description": conflict.description,
                "resolution": conflict.resolution,
                "selected_candidate_id": conflict.selected_candidate_id,
            }
        )
    return details


def _plan14_readiness(
    consensus: ConsensusIR,
    backend_summary: dict[str, dict[str, Any]],
    confidence_summary: dict[str, Any],
) -> dict[str, Any]:
    """Surface fields Plan 14 (LinkedStructure) needs as inputs."""

    priors_loaded = sorted(
        backend for backend, meta in backend_summary.items() if meta.get("prior_loaded")
    )
    return {
        "consensus_block_count": confidence_summary.get("block_count", 0),
        "consensus_page_count": consensus.page_count,
        "consensus_conflict_count": len(consensus.conflicts),
        "consensus_unresolved_conflict_count": sum(
            1 for c in consensus.conflicts if c.resolution == "unresolved"
        ),
        "backends_with_priors_loaded": priors_loaded,
        "backends_included": sorted(b.backend for b in consensus.backends),
        "low_confidence_blocks": confidence_summary.get("low_confidence_blocks", 0),
        "linkedstructure_handed_off_by": "plan_14",
    }


def build_consensus_report(
    *,
    consensus: ConsensusIR,
    warnings: list[str],
    backend_summary: dict[str, dict[str, Any]],
    inspection_status: str | None = None,
    ground_truth_ref: str | None = None,
    inspection_notes: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build the Plan 13 consensus audit report.

    Backwards compatible: pre-existing top-level fields are preserved; new
    fields (``backend_contributions``, ``confidence_summary``, ``conflict_details``,
    ``plan14_readiness``, ``inspection_status``, ``ground_truth_ref``,
    ``inspection_notes``) are added without renaming existing ones.
    """

    counts = {mode.value: 0 for mode in SelectionMode}
    for page in consensus.pages:
        for block in page.blocks:
            counts[str(block.selection_mode)] += 1

    if inspection_status is not None and inspection_status not in INSPECTION_STATUSES:
        raise ValueError(
            f"inspection_status must be one of {INSPECTION_STATUSES}; got {inspection_status!r}"
        )
    effective_inspection = inspection_status or "diagnostic_only"

    confidence_summary = _confidence_summary(consensus)
    backend_contributions = _backend_contributions(consensus)
    conflict_details = _conflict_details(consensus)
    plan14 = _plan14_readiness(consensus, backend_summary, confidence_summary)

    return {
        "schema_name": "pdf2md.ConsensusReport",
        "schema_version": "1.0.0",
        "document_id": consensus.document_id,
        "page_count": consensus.page_count,
        "backend_count": len(consensus.backends),
        "block_count": sum(len(page.blocks) for page in consensus.pages),
        "conflict_count": len(consensus.conflicts),
        "selection_counts": counts,
        "warnings": list(warnings),
        "backend_summary": backend_summary,
        "backend_contributions": backend_contributions,
        "confidence_summary": confidence_summary,
        "conflicts": [
            {
                "id": conflict.id,
                "kind": str(conflict.kind),
                "page_no": conflict.page_no,
                "candidate_ids": list(conflict.candidate_ids),
            }
            for conflict in consensus.conflicts
        ],
        "conflict_details": conflict_details,
        "inspection_status": effective_inspection,
        "inspection_notes": list(inspection_notes or []),
        "ground_truth_ref": ground_truth_ref,
        "plan14_readiness": plan14,
    }


def build_consensus_summary(report: dict[str, Any]) -> str:
    """Render a human-readable summary of the consensus report (Plan 13)."""

    selection_counts = report.get("selection_counts", {})
    confidence = report.get("confidence_summary", {})
    plan14 = report.get("plan14_readiness", {})
    contributions = report.get("backend_contributions", {})

    lines = [
        "pdf2md consensus run summary (Plan 13)",
        f"schema: {report.get('schema_name')} {report.get('schema_version')}",
        f"document_id: {report.get('document_id')}",
        f"page_count: {report.get('page_count')}",
        f"backend_count: {report.get('backend_count')}",
        f"block_count: {report.get('block_count')}",
        f"conflict_count: {report.get('conflict_count')}",
        f"inspection_status: {report.get('inspection_status')}",
        f"ground_truth_ref: {report.get('ground_truth_ref')}",
        "",
        "selection counts:",
    ]
    for mode, count in sorted(selection_counts.items()):
        lines.append(f"- {mode}: {count}")

    lines.extend(["", "backend contributions:"])
    if not contributions:
        lines.append("- (none)")
    for backend, detail in sorted(contributions.items()):
        lines.append(
            f"- {backend}: accepted={detail.get('accepted_blocks', 0)} "
            f"single_source={detail.get('single_source_blocks', 0)} "
            f"fallback={detail.get('fallback_blocks', 0)} "
            f"unresolved={detail.get('unresolved_blocks', 0)} "
            f"conflicts={detail.get('conflict_participations', 0)}"
        )

    lines.extend(["", "confidence summary:"])
    if confidence.get("block_count", 0) == 0:
        lines.append("- (no blocks)")
    else:
        lines.append(f"- block_count: {confidence.get('block_count')}")
        lines.append(f"- mean_agreement_score: {confidence.get('mean_agreement_score')}")
        lines.append(f"- min_agreement_score: {confidence.get('min_agreement_score')}")
        lines.append(f"- max_agreement_score: {confidence.get('max_agreement_score')}")
        lines.append(
            f"- low_confidence_blocks: {confidence.get('low_confidence_blocks')} "
            f"(threshold={confidence.get('low_confidence_threshold')})"
        )

    if report.get("conflict_count", 0) > 0:
        lines.extend(["", "conflicts (in consensus_ir.json):"])
        for detail in report.get("conflict_details", []):
            lines.append(
                f"- {detail['id']} [{detail['kind']}] page={detail['page_no']} "
                f"resolution={detail['resolution']} "
                f"selected={detail.get('selected_candidate_id')}"
            )

    inspection_notes = report.get("inspection_notes") or []
    if inspection_notes:
        lines.extend(["", "inspection notes:"])
        lines.extend(f"- {n}" for n in inspection_notes)

    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in warnings)

    lines.extend(
        [
            "",
            "Plan 14 readiness:",
            f"- consensus_block_count: {plan14.get('consensus_block_count')}",
            f"- consensus_page_count: {plan14.get('consensus_page_count')}",
            f"- consensus_conflict_count: {plan14.get('consensus_conflict_count')}",
            f"- consensus_unresolved_conflict_count: {plan14.get('consensus_unresolved_conflict_count')}",
            f"- backends_with_priors_loaded: {plan14.get('backends_with_priors_loaded')}",
            f"- backends_included: {plan14.get('backends_included')}",
            f"- low_confidence_blocks: {plan14.get('low_confidence_blocks')}",
            "- LinkedStructure cross-page semantic linking is deferred to Plan 14 and is "
            "not used for Plan 13 pass/fail.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "INSPECTION_STATUSES",
    "build_consensus_report",
    "build_consensus_summary",
]
