"""DocIR schema dataclasses.

DocIR is the canonical internal representation for extracted document content.
Markdown is an exporter target, not the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MediaRef:
    """Reference to extracted media associated with a document or block."""

    media_id: str
    type: str
    path: str
    page_index: int
    bbox: list[float] | None = None
    width: int | None = None
    height: int | None = None
    dpi: int | None = None
    sha256: str | None = None


@dataclass
class Provenance:
    """Extraction provenance metadata for an IR block."""

    backend: str
    backend_version: str
    strategy: str
    page_index: int
    bbox: list[float] | None = None
    confidence: float | None = None
    raw_output_ref: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class BackendRun:
    """Execution record of a backend invocation."""

    run_id: str
    backend: str
    backend_version: str
    options: dict[str, Any] = field(default_factory=dict)
    status: str = "unknown"
    errors: list[str] = field(default_factory=list)
    raw_output_dir: str | None = None


@dataclass
class BlockIR:
    """Canonical content block in DocIR."""

    block_id: str
    type: str
    role: str | None = None
    text: str | None = None
    markdown: str | None = None
    latex: str | None = None
    html: str | None = None
    page_indexes: list[int] = field(default_factory=list)
    order: int = 0
    bbox: list[float] | None = None
    polygon: list[list[float]] | None = None
    media_refs: list[str] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    confidence: float | None = None
    normalised: bool = False
    include_in_rag: bool = True
    include_in_benchmark: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class PageIR:
    """Per-page document representation and routing metadata."""

    page_id: str
    page_index: int
    page_label: str | None = None
    width: float = 0.0
    height: float = 0.0
    rotation: int = 0
    image_ref: str | None = None
    block_ids: list[str] = field(default_factory=list)
    furniture_block_ids: list[str] = field(default_factory=list)
    strategy: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentIR:
    """Top-level canonical DocIR payload."""

    schema_version: str
    document_id: str
    source_path: str
    pages: list[PageIR] = field(default_factory=list)
    blocks: list[BlockIR] = field(default_factory=list)
    media: list[MediaRef] = field(default_factory=list)
    backend_runs: list[BackendRun] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
