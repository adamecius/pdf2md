"""Pydantic contracts for pdf2md export artefacts and RAG chunks."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EXPORT_SCHEMA_VERSION = "1.0.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RAG_CHUNK_ID_PATTERN = re.compile(r"^chunk:[A-Za-z0-9_.-]+:\d+$")


class ExportArtefactType(str, Enum):
    DOCLING_JSON = "docling_json"
    RAG_CHUNKS = "rag_chunks"
    MARKDOWN_PREVIEW = "markdown_preview"
    EXPORT_REPORT = "export_report"


class ExportStatus(str, Enum):
    WRITTEN = "written"
    WRITTEN_WITH_WARNINGS = "written_with_warnings"
    SKIPPED = "skipped"
    FAILED = "failed"


class RagChunkType(str, Enum):
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
    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)


class ExportArtefact(_ExportBaseModel):
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
    def _validate_unique_paths(self) -> "ExportManifestDocument":
        paths = [artefact.path for artefact in self.artefacts]
        if len(paths) != len(set(paths)):
            raise ValueError("artefact paths must be unique")
        return self


class RagChunk(_ExportBaseModel):
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
    def _validate_page_range(self) -> "RagChunk":
        if self.page_start is not None and self.page_end is not None and self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class RagChunkDocument(_ExportBaseModel):
    schema_name: Literal["pdf2md.RagChunkDocument"] = "pdf2md.RagChunkDocument"
    schema_version: Literal["1.0.0"] = EXPORT_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    chunks: list[RagChunk]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_chunk_ids(self) -> "RagChunkDocument":
        ids = [chunk.id for chunk in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("chunk ids must be unique")
        return self


def rag_chunk_id(document_id: str, index: int) -> str:
    """Build a canonical RAG chunk id."""

    return f"chunk:{document_id}:{index}"


__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "SHA256_PATTERN",
    "RAG_CHUNK_ID_PATTERN",
    "ExportArtefactType",
    "ExportStatus",
    "RagChunkType",
    "ExportArtefact",
    "ExportManifestDocument",
    "RagChunk",
    "RagChunkDocument",
    "rag_chunk_id",
]
