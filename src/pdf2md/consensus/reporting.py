"""Audit reporting for consensus runs."""

from __future__ import annotations

from typing import Any

from pdf2md.models.ir import ConsensusIR, SelectionMode


def build_consensus_report(
    *,
    consensus: ConsensusIR,
    warnings: list[str],
    backend_summary: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    counts = {mode.value: 0 for mode in SelectionMode}
    for page in consensus.pages:
        for block in page.blocks:
            counts[str(block.selection_mode)] += 1
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
        "conflicts": [
            {
                "id": conflict.id,
                "kind": str(conflict.kind),
                "page_no": conflict.page_no,
                "candidate_ids": list(conflict.candidate_ids),
            }
            for conflict in consensus.conflicts
        ],
    }
