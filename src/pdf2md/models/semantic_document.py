from __future__ import annotations

import datetime as dt
from typing import Any


def new_semantic_document(
    *,
    source_pdf: str,
    source_consensus_report: str,
    source_semantic_links: str,
    source_media_manifest: str | None,
) -> dict[str, Any]:
    return {
        "schema_name": "pdf2md.semantic_document",
        "schema_version": "0.1.0",
        "source_pdf": source_pdf,
        "source_consensus_report": source_consensus_report,
        "source_semantic_links": source_semantic_links,
        "source_media_manifest": source_media_manifest,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "pages": [],
        "blocks": [],
        "relations": [],
        "anchors": [],
        "references": [],
        "conflicts": [],
        "warnings": [],
        "validation": {
            "duplicate_block_ids": [],
            "missing_anchor_targets": [],
            "unresolved_references": [],
            "blocks_missing_provenance": [],
            "media_assets_missing_files": [],
            "warnings": [],
        },
    }
