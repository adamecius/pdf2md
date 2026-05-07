"""Pydantic contracts for backend extraction and consensus IR payloads."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"

EXTRACTION_ID_PATTERN = re.compile(r"^[a-z0-9_-]+:[A-Za-z0-9_.-]+:p\d+:b\d+$")
CONSENSUS_ID_PATTERN = re.compile(r"^con:[A-Za-z0-9_.-]+:p\d+:b\d+$")
CONFLICT_ID_PATTERN = re.compile(r"^conf:[A-Za-z0-9_.-]+:\d+$")


class CoordOrigin(str, Enum):
    """Coordinate origin conventions supported by IR bounding boxes."""

    BOTTOMLEFT = "bottomleft"
    TOPLEFT = "topleft"


class BlockKind(str, Enum):
    """Semantic block kinds shared by extraction and consensus contracts."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    FORMULA = "formula"
    FIGURE = "figure"
    TABLE = "table"
    CAPTION = "caption"
    LIST = "list"
    LIST_ITEM = "list_item"
    FOOTNOTE = "footnote"
    PAGE_NUMBER = "page_number"
    HEADER = "header"
    FOOTER = "footer"
    REFERENCE = "reference"
    BIBITEM = "bibitem"
    CODE = "code"
    UNKNOWN = "unknown"


class SelectionMode(str, Enum):
    """How a consensus block was selected from backend evidence."""

    AGREED = "agreed"
    SINGLE_SOURCE = "single_source"
    FALLBACK = "fallback"
    UNRESOLVED = "unresolved"


class ConflictKind(str, Enum):
    """Kinds of unresolved or recorded candidate conflicts."""

    TEXT_CONFLICT = "text_conflict"
    KIND_CONFLICT = "kind_conflict"
    BBOX_CONFLICT = "bbox_conflict"
    PRESENCE_CONFLICT = "presence_conflict"
    ORDER_CONFLICT = "order_conflict"


class _IRBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)


class BBox(_IRBaseModel):
    """Bounding box with explicit coordinate-origin semantics."""

    l: float
    t: float
    r: float
    b: float
    coord_origin: CoordOrigin

    @model_validator(mode="after")
    def _validate_edges(self) -> BBox:
        if self.r <= self.l:
            raise ValueError("bbox r must be greater than l")
        if self.coord_origin == CoordOrigin.BOTTOMLEFT and self.t <= self.b:
            raise ValueError("bottom-left bbox requires t > b")
        if self.coord_origin == CoordOrigin.TOPLEFT and self.b <= self.t:
            raise ValueError("top-left bbox requires b > t")
        return self


class Span(_IRBaseModel):
    """Text span inside an extraction block."""

    text: str
    bbox: BBox | None = None
    char_start: int = Field(ge=0)
    char_end: int

    @model_validator(mode="after")
    def _validate_char_range(self) -> Span:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class PageSize(_IRBaseModel):
    """Page dimensions in backend units."""

    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ExtractionBlock(_IRBaseModel):
    """One backend's evidence for one block on one page."""

    id: str
    backend: str = Field(min_length=1)
    page_no: int = Field(ge=1)
    kind: BlockKind
    bbox: BBox | None = None
    order: int = Field(ge=0)
    text: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    spans: list[Span] | None = None
    raw_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not EXTRACTION_ID_PATTERN.fullmatch(value):
            raise ValueError("ExtractionBlock.id must match <backend>:<doc>:p<page>:b<index>")
        return value


class PageExtractionIR(_IRBaseModel):
    """Per-backend, per-page extraction evidence contract."""

    schema_name: Literal["pdf2md.PageExtractionIR"] = "pdf2md.PageExtractionIR"
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    backend_version: str | None = None
    page_no: int = Field(ge=1)
    page_size: PageSize
    blocks: list[ExtractionBlock]
    raw_artifact_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_blocks(self) -> PageExtractionIR:
        block_ids: set[str] = set()
        for block in self.blocks:
            if block.page_no != self.page_no:
                raise ValueError("all blocks must share PageExtractionIR.page_no")
            if block.backend != self.backend:
                raise ValueError("all blocks must share PageExtractionIR.backend")
            if block.id in block_ids:
                raise ValueError("block ids must be unique within a page")
            block_ids.add(block.id)
        return self


class Conflict(_IRBaseModel):
    """A first-class conflict among extraction candidates."""

    id: str
    kind: ConflictKind
    page_no: int = Field(ge=1)
    candidate_ids: list[str] = Field(min_length=2)
    description: str
    resolution: Literal["unresolved", "resolved_by_consensus", "resolved_by_linker"]
    selected_candidate_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not CONFLICT_ID_PATTERN.fullmatch(value):
            raise ValueError("Conflict.id must match conf:<doc>:<index>")
        return value

    @field_validator("candidate_ids")
    @classmethod
    def _validate_candidate_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if not EXTRACTION_ID_PATTERN.fullmatch(value):
                raise ValueError("Conflict.candidate_ids values must be extraction ids")
        return values

    @model_validator(mode="after")
    def _validate_resolution(self) -> Conflict:
        if self.resolution == "unresolved":
            return self
        if self.selected_candidate_id not in self.candidate_ids:
            raise ValueError("resolved conflicts require selected_candidate_id in candidate_ids")
        return self


class ConsensusBlock(_IRBaseModel):
    """Canonical block selected by consensus from backend candidates."""

    id: str
    kind: BlockKind
    bbox: BBox | None = None
    order: int = Field(ge=0)
    text: str
    selection_mode: SelectionMode
    selected_source: str | None = None
    agreement_score: float = Field(ge=0.0, le=1.0)
    candidate_ids: list[str]
    conflict_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not CONSENSUS_ID_PATTERN.fullmatch(value):
            raise ValueError("ConsensusBlock.id must match con:<doc>:p<page>:b<index>")
        return value

    @field_validator("candidate_ids")
    @classmethod
    def _validate_candidate_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if not EXTRACTION_ID_PATTERN.fullmatch(value):
                raise ValueError("ConsensusBlock.candidate_ids values must be extraction ids")
        return values

    @field_validator("conflict_ids")
    @classmethod
    def _validate_conflict_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if not CONFLICT_ID_PATTERN.fullmatch(value):
                raise ValueError("ConsensusBlock.conflict_ids values must be conflict ids")
        return values

    @model_validator(mode="after")
    def _validate_selection(self) -> ConsensusBlock:
        if self.selection_mode == SelectionMode.UNRESOLVED:
            if self.selected_source is not None:
                raise ValueError("unresolved consensus blocks require selected_source to be None")
            if not self.conflict_ids:
                raise ValueError("unresolved consensus blocks require at least one conflict id")
        elif self.selected_source is None:
            raise ValueError("resolved consensus blocks require selected_source")
        return self


class ConsensusPage(_IRBaseModel):
    """One page of canonical consensus blocks."""

    page_no: int = Field(ge=1)
    page_size: PageSize
    blocks: list[ConsensusBlock]


class BackendManifest(_IRBaseModel):
    """Backend provenance manifest entry for a consensus document."""

    backend: str = Field(min_length=1)
    backend_version: str | None = None
    manifest_ref: str | None = None
    prior_ref: str | None = None


class ConsensusIR(_IRBaseModel):
    """Per-document consensus resolution contract."""

    schema_name: Literal["pdf2md.ConsensusIR"] = "pdf2md.ConsensusIR"
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    page_count: int = Field(ge=0)
    pages: list[ConsensusPage]
    conflicts: list[Conflict] = Field(default_factory=list)
    backends: list[BackendManifest] = Field(default_factory=list)
    agreement_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_document(self) -> ConsensusIR:
        if self.page_count != len(self.pages):
            raise ValueError("page_count must match pages length")

        page_numbers = [page.page_no for page in self.pages]
        if self.page_count > 0 and page_numbers != list(range(1, self.page_count + 1)):
            raise ValueError("pages must be contiguous from one")

        conflict_ids = {conflict.id for conflict in self.conflicts}
        for page in self.pages:
            for block in page.blocks:
                missing = [conflict_id for conflict_id in block.conflict_ids if conflict_id not in conflict_ids]
                if missing:
                    raise ValueError("block conflict_ids must exist in top-level conflicts")
        return self


def extraction_id(backend: str, document_id: str, page_no: int, block_index: int) -> str:
    """Build a canonical extraction block id."""

    return f"{backend}:{document_id}:p{page_no}:b{block_index}"


def consensus_id(document_id: str, page_no: int, block_index: int) -> str:
    """Build a canonical consensus block id."""

    return f"con:{document_id}:p{page_no}:b{block_index}"


def conflict_id(document_id: str, index: int) -> str:
    """Build a canonical conflict id."""

    return f"conf:{document_id}:{index}"


__all__ = [
    "SCHEMA_VERSION",
    "EXTRACTION_ID_PATTERN",
    "CONSENSUS_ID_PATTERN",
    "CONFLICT_ID_PATTERN",
    "CoordOrigin",
    "BlockKind",
    "SelectionMode",
    "ConflictKind",
    "BBox",
    "Span",
    "PageSize",
    "ExtractionBlock",
    "PageExtractionIR",
    "Conflict",
    "ConsensusBlock",
    "ConsensusPage",
    "BackendManifest",
    "ConsensusIR",
    "extraction_id",
    "consensus_id",
    "conflict_id",
]
