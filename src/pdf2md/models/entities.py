"""Pydantic contracts for document-level entity and relation proposals."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pdf2md.models.ir import EXTRACTION_ID_PATTERN, BBox

ENTITY_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ENTITY_ID_PATTERN = re.compile(r"^ent:[a-z0-9_-]+:[A-Za-z0-9_.-]+:[a-z_]+:\d+$")
RELATION_ID_PATTERN = re.compile(r"^rel:[a-z0-9_-]+:[A-Za-z0-9_.-]+:\d+$")


class EntityType(str, Enum):
    """Canonical entity-type taxonomy for document-level entity proposals."""

    DOCUMENT_TITLE = "document_title"
    CHAPTER = "chapter"
    SECTION = "section"
    TOC_ENTRY = "toc_entry"
    PAGE_NUMBER = "page_number"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    EQUATION = "equation"
    FIGURE = "figure"
    TABLE = "table"
    CAPTION = "caption"
    REFERENCE_SECTION = "reference_section"
    REFERENCE_ITEM = "reference_item"
    BIBLIOGRAPHY_MARKER = "bibliography_marker"
    UNKNOWN = "unknown"


class RelationType(str, Enum):
    """Canonical relation-type taxonomy for entity-to-entity proposals."""

    CAPTION_OF = "caption_of"
    FOOTNOTE_ANCHOR_FOR = "footnote_anchor_for"
    TOC_POINTS_TO = "toc_points_to"
    REFERENCE_MENTION_OF = "reference_mention_of"
    SAME_ENTITY_AS = "same_entity_as"
    NEAR = "near"
    SEQUENCE_NEXT = "sequence_next"
    CANDIDATE_FOR = "candidate_for"


class EvidenceKind(str, Enum):
    """Kinds of evidence supporting an entity or relation proposal."""

    BLOCK_TEXT = "block_text"
    BBOX = "bbox"
    REGEX = "regex"
    POSITION = "position"
    READING_ORDER = "reading_order"
    MARKDOWN_SYNTAX = "markdown_syntax"
    BACKEND_NATIVE_TYPE = "backend_native_type"
    RAW_ARTIFACT = "raw_artifact"
    DOCUMENT_CONTEXT = "document_context"


class ConfidenceSource(str, Enum):
    """Provenance of a confidence value attached to a proposal."""

    HEURISTIC = "heuristic"
    CALIBRATED = "calibrated"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class _EntityBaseModel(BaseModel):
    """Private Pydantic base for entity-proposal models."""

    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)


class EntityEvidence(_EntityBaseModel):
    """One piece of evidence backing an entity or relation proposal.

    Attributes:
        kind: Category of evidence (text, bbox, regex, position, ...).
        page_no: One-based page number the evidence comes from, if any.
        source_block_id: Extraction block id the evidence references, if any.
        raw_ref: Free-form reference to a backend-native artifact.
        text: Optional textual excerpt supporting the proposal.
        bbox: Optional bounding box localising the evidence.
        weight: Weight of this evidence in [0, 1].
        reason: Human-readable justification for the evidence.
        metadata: Free-form metadata bag.
    """

    kind: EvidenceKind
    page_no: int | None = Field(default=None, ge=1)
    source_block_id: str | None = None
    raw_ref: str | None = None
    text: str | None = None
    bbox: BBox | None = None
    weight: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_block_id")
    @classmethod
    def _validate_source_block_id(cls, value: str | None) -> str | None:
        if value is not None and not EXTRACTION_ID_PATTERN.fullmatch(value):
            raise ValueError("source_block_id must be an extraction block id")
        return value


class EntityProposal(_EntityBaseModel):
    """One backend's proposal for a document-level entity.

    Produced by entity-proposal stages from per-backend extractions and
    consumed by the linker when building the unified LinkedStructure.

    Attributes:
        id: Canonical entity id (`ent:<backend>:<doc>:<type>:<index>`).
        entity_type: Entity-type taxonomy value.
        subtype: Optional finer-grained subtype tag.
        canonical_text: Normalised textual form, if applicable.
        page_no: One-based page number, if entity is page-local.
        block_ids: Extraction block ids supporting this proposal.
        confidence: Proposal confidence in [0, 1].
        confidence_source: How the confidence was produced.
        evidence: One or more EntityEvidence items backing the proposal.
        calibration_key: Optional key used to look up calibrated priors.
        metadata: Free-form metadata bag.
    """

    id: str
    entity_type: EntityType
    subtype: str | None = None
    canonical_text: str | None = None
    page_no: int | None = Field(default=None, ge=1)
    block_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_source: ConfidenceSource
    evidence: list[EntityEvidence] = Field(min_length=1)
    calibration_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not ENTITY_ID_PATTERN.fullmatch(value):
            raise ValueError("EntityProposal.id must match ent:<backend>:<doc>:<entity_type>:<index>")
        return value

    @field_validator("block_ids")
    @classmethod
    def _validate_block_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if not EXTRACTION_ID_PATTERN.fullmatch(value):
                raise ValueError("block_ids values must be extraction ids")
        return values


class RelationProposal(_EntityBaseModel):
    """One backend's proposal for a relation between two entities.

    Attributes:
        id: Canonical relation id (`rel:<backend>:<doc>:<index>`).
        relation_type: Relation-type taxonomy value.
        source_entity_id: Entity id of the relation's source endpoint.
        target_entity_id: Entity id of the relation's target endpoint.
        confidence: Proposal confidence in [0, 1].
        confidence_source: How the confidence was produced.
        evidence: One or more EntityEvidence items backing the proposal.
        metadata: Free-form metadata bag.
    """

    id: str
    relation_type: RelationType
    source_entity_id: str
    target_entity_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_source: ConfidenceSource
    evidence: list[EntityEvidence] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not RELATION_ID_PATTERN.fullmatch(value):
            raise ValueError("RelationProposal.id must match rel:<backend>:<doc>:<index>")
        return value

    @field_validator("source_entity_id", "target_entity_id")
    @classmethod
    def _validate_entity_ids(cls, value: str) -> str:
        if not ENTITY_ID_PATTERN.fullmatch(value):
            raise ValueError("relation endpoints must be entity ids")
        return value

    @model_validator(mode="after")
    def _validate_distinct_endpoints(self) -> RelationProposal:
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("relation source and target must differ")
        return self


class EntityProposalDocument(_EntityBaseModel):
    """Per-backend, per-document bundle of entity and relation proposals.

    Produced by the entity-proposal stage for one backend over one
    document and consumed by the linker.

    Attributes:
        schema_name: Fixed marker for the JSON schema.
        schema_version: Schema version string.
        document_id: Identifier of the source document.
        backend: Backend that produced the proposals.
        backend_version: Optional backend version tag.
        page_count: Total number of pages in the document.
        entities: List of EntityProposal items with unique ids.
        relations: List of RelationProposal items with unique ids.
        warnings: Stage-level warnings.
        metadata: Free-form metadata bag.
    """

    schema_name: Literal["pdf2md.EntityProposalDocument"] = "pdf2md.EntityProposalDocument"
    schema_version: Literal["1.0.0"] = ENTITY_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    backend_version: str | None = None
    page_count: int = Field(ge=0)
    entities: list[EntityProposal] = Field(default_factory=list)
    relations: list[RelationProposal] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_document(self) -> EntityProposalDocument:
        entity_ids = [entity.id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entity ids must be unique")
        relation_ids = [relation.id for relation in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("relation ids must be unique")
        known = set(entity_ids)
        for relation in self.relations:
            if relation.source_entity_id not in known:
                raise ValueError("relation source_entity_id must exist in entities")
            if relation.target_entity_id not in known:
                raise ValueError("relation target_entity_id must exist in entities")
        return self


def entity_id(backend: str, document_id: str, entity_type: EntityType | str, index: int) -> str:
    """Build a canonical entity proposal id."""

    value = entity_type.value if isinstance(entity_type, EntityType) else str(entity_type)
    return f"ent:{backend}:{document_id}:{value}:{index}"


def relation_id(backend: str, document_id: str, index: int) -> str:
    """Build a canonical relation proposal id."""

    return f"rel:{backend}:{document_id}:{index}"


__all__ = [
    "ENTITY_ID_PATTERN",
    "ENTITY_SCHEMA_VERSION",
    "RELATION_ID_PATTERN",
    "ConfidenceSource",
    "EntityEvidence",
    "EntityProposal",
    "EntityProposalDocument",
    "EntityType",
    "EvidenceKind",
    "RelationProposal",
    "RelationType",
    "entity_id",
    "relation_id",
]
