"""Audit reporting helpers for linked structure builds."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pdf2md.models.linked import LinkStatus, LinkedStructure


def build_linking_report(linked: LinkedStructure) -> dict[str, Any]:
    return {
        "schema_name": "pdf2md.LinkingReport",
        "schema_version": "1.0.0",
        "document_id": linked.document_id,
        "node_count": len(linked.nodes),
        "relation_count": len(linked.relations),
        "conflict_count": len(linked.conflicts),
        "warnings": list(linked.warnings),
        "node_type_counts": dict(Counter(str(node.node_type) for node in linked.nodes)),
        "relation_type_counts": dict(Counter(str(relation.relation_type) for relation in linked.relations)),
        "unresolved": [
            {"id": conflict.id, "conflict_type": conflict.conflict_type}
            for conflict in linked.conflicts
            if conflict.status == LinkStatus.UNRESOLVED or str(conflict.status) == LinkStatus.UNRESOLVED.value
        ],
    }
