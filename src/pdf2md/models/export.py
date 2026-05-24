"""Pydantic contracts for pdf2md export artefacts and RAG chunks."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EXPORT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RAG_CHUNK_ID_PATTERN = re.compile(r"^chunk:[A-Za-z0-9_.-]+:\d+$")


class ExportArtefactType(str, Enum):
    """Kinds of artefacts produced by the export stage."""

    DOCLING_JSON = "docling_json"
    RAG_CHUNKS = "rag_chunks"
    MARKDOWN_PREVIEW = "markdown_preview"
    EXPORT_REPORT = "export_report"


class ExportStatus(str, Enum):
    """Outcome status for a single export artefact."""

    WRITTEN = "written"
    WRITTEN_WITH_WARNINGS = "written_with_warnings"
    SKIPPED = "skipped"
    FAILED = "failed"


class RagChunkType(str, Enum):
    """Canonical chunk-type taxonomy for RAG-oriented exports."""

    TITLE = "title"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    EQUATION = "equation"
    FOOTNOTE = "footnote"
    REFERENCE = "reference"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class _ExportBaseModel(BaseModel):
    """Private Pydantic base for export-layer models."""

    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)


class ExportArtefact(_ExportBaseModel):
    """One artefact written by the export stage.

    Attributes:
        artefact_type: Kind of artefact (Docling JSON, RAG chunks, ...).
        path: Relative or absolute path the artefact was written to.
        status: Outcome status (written, skipped, failed, ...).
        sha256: Optional 64-char lowercase hex content hash.
        warnings: Per-artefact warnings.
        metadata: Free-form metadata bag.
    """

    artefact_type: ExportArtefactType
    path: str = Field(min_length=1)
    status: ExportStatus
    sha256: str | None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class ExportManifestDocument(_ExportBaseModel):
    """Manifest enumerating every artefact written for one document.

    Produced by the export stage as a sibling to the artefacts it
    references and consumed by downstream tooling that needs to locate
    and validate exported outputs.

    Attributes:
        schema_name: Fixed marker for the JSON schema.
        schema_version: Schema version string.
        document_id: Identifier of the source document.
        source_linked_structure: Path of the LinkedStructure input.
        source_consensus_ir: Optional path of the ConsensusIR input.
        source_pdf: Optional path of the originating PDF.
        artefacts: ExportArtefact entries with unique paths.
        warnings: Manifest-level warnings.
        metadata: Free-form metadata bag.
    """

    schema_name: Literal["pdf2md.ExportManifestDocument"] = "pdf2md.ExportManifestDocument"
    schema_version: Literal["1.0.0"] = EXPORT_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    source_linked_structure: str = Field(min_length=1)
    source_consensus_ir: str | None = None
    source_pdf: str | None = None
    artefacts: list[ExportArtefact]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_paths(self) -> ExportManifestDocument:
        paths = [artefact.path for artefact in self.artefacts]
        if len(paths) != len(set(paths)):
            raise ValueError("artefact paths must be unique")
        return self


class RagChunk(_ExportBaseModel):
    """One retrieval-oriented chunk extracted from the linked structure.

    Attributes:
        id: Canonical chunk id (`chunk:<doc>:<index>`).
        chunk_type: Chunk-type taxonomy value.
        title: Optional chunk title or heading.
        text: Concatenated chunk text (non-empty).
        node_ids: LinkedStructure node ids backing the chunk.
        relation_ids: Optional LinkedStructure relation ids backing the chunk.
        page_start: One-based first page covered by the chunk, if any.
        page_end: One-based last page covered by the chunk, if any.
        section_path: Section breadcrumbs leading to the chunk.
        breadcrumbs: Free-form breadcrumb labels.
        confidence: Aggregate confidence in [0, 1].
        metadata: Free-form metadata bag.
    """

    id: str
    chunk_type: RagChunkType
    title: str | None = None
    text: str = Field(min_length=1)
    node_ids: list[str] = Field(min_length=1)
    relation_ids: list[str] = Field(default_factory=list)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list)
    breadcrumbs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not RAG_CHUNK_ID_PATTERN.fullmatch(value):
            raise ValueError("RagChunk.id must match chunk:<doc>:<index>")
        return value

    @model_validator(mode="after")
    def _validate_page_range(self) -> RagChunk:
        if self.page_start is not None and self.page_end is not None and self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class RagChunkDocument(_ExportBaseModel):
    """Document-level bundle of RAG chunks emitted by the export stage.

    Attributes:
        schema_name: Fixed marker for the JSON schema.
        schema_version: Schema version string.
        document_id: Identifier of the source document.
        chunks: RagChunk entries with unique ids.
        warnings: Document-level warnings.
        metadata: Free-form metadata bag.
    """

    schema_name: Literal["pdf2md.RagChunkDocument"] = "pdf2md.RagChunkDocument"
    schema_version: Literal["1.0.0"] = EXPORT_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    chunks: list[RagChunk]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_chunk_ids(self) -> RagChunkDocument:
        ids = [chunk.id for chunk in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("chunk ids must be unique")
        return self


def rag_chunk_id(document_id: str, index: int) -> str:
    """Build a canonical RAG chunk id."""

    return f"chunk:{document_id}:{index}"


__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "RAG_CHUNK_ID_PATTERN",
    "SHA256_PATTERN",
    "ExportArtefact",
    "ExportArtefactType",
    "ExportManifestDocument",
    "ExportStatus",
    "RagChunk",
    "RagChunkDocument",
    "RagChunkType",
    "rag_chunk_id",
]
