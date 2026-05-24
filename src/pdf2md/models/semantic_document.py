"""Builder for the legacy `semantic_document.json` representation.

Maintained for tools that still consume the pre-LinkedStructure document
shape. New code should use `pdf2md.models.linked.LinkedStructure` and
the canonical Docling export under `pdf2md.export.docling`.
"""

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
    """Build an empty legacy semantic-document payload.

    Returns the pre-LinkedStructure document shape with empty page,
    block, relation, anchor, reference, conflict, warning, and
    validation collections; populated only with the supplied source
    references and a UTC ``created_at`` timestamp.

    Args:
        source_pdf: Path of the originating PDF.
        source_consensus_report: Path of the consensus report input.
        source_semantic_links: Path of the semantic links input.
        source_media_manifest: Optional path of the media manifest.

    Returns:
        A dict matching the legacy ``pdf2md.semantic_document`` schema.
    """

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
