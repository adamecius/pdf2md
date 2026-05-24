"""Pydantic contracts for document-level linked semantic structure."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pdf2md.models.entities import ENTITY_ID_PATTERN
from pdf2md.models.ir import CONFLICT_ID_PATTERN, CONSENSUS_ID_PATTERN

LINKED_SCHEMA_VERSION = "1.0.0"
LINKED_NODE_ID_PATTERN = re.compile(r"^node:[A-Za-z0-9_.-]+:\d+$")
LINKED_RELATION_ID_PATTERN = re.compile(r"^lrel:[A-Za-z0-9_.-]+:\d+$")
LINKED_CONFLICT_ID_PATTERN = re.compile(r"^lconf:[A-Za-z0-9_.-]+:\d+$")


class LinkedNodeType(str, Enum):
    """Canonical node-type taxonomy for LinkedStructure nodes."""

    DOCUMENT = "document"
    TITLE = "title"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    EQUATION = "equation"
    FOOTNOTE = "footnote"
    PAGE_NUMBER = "page_number"
    HEADER = "header"
    FOOTER = "footer"
    TOC_ENTRY = "toc_entry"
    REFERENCE_SECTION = "reference_section"
    REFERENCE_ITEM = "reference_item"
    BIBLIOGRAPHY_MARKER = "bibliography_marker"
    CODE = "code"
    UNKNOWN = "unknown"


class LinkedRelationType(str, Enum):
    """Canonical relation-type taxonomy for LinkedStructure relations."""

    CONTAINS = "contains"
    FOLLOWS = "follows"
    PARENT_OF = "parent_of"
    CAPTION_OF = "caption_of"
    FOOTNOTE_ANCHOR_FOR = "footnote_anchor_for"
    TOC_POINTS_TO = "toc_points_to"
    REFERENCES = "references"
    EQUATION_SEQUENCE_NEXT = "equation_sequence_next"
    FIGURE_SEQUENCE_NEXT = "figure_sequence_next"
    TABLE_SEQUENCE_NEXT = "table_sequence_next"
    REFERENCE_SEQUENCE_NEXT = "reference_sequence_next"
    PAGE_NUMBER_SEQUENCE_NEXT = "page_number_sequence_next"
    HEADER_REPEATS_AS = "header_repeats_as"
    FOOTER_REPEATS_AS = "footer_repeats_as"
    DERIVED_FROM_CONSENSUS = "derived_from_consensus"
    UNRESOLVED_CANDIDATE = "unresolved_candidate"


class LinkStatus(str, Enum):
    """Resolution status for a LinkedStructure node, relation, or conflict."""

    RESOLVED = "resolved"
    RESOLVED_LOW_CONFIDENCE = "resolved_low_confidence"
    UNRESOLVED = "unresolved"


class LinkEvidenceKind(str, Enum):
    """Kinds of evidence supporting a linker decision."""

    CONSENSUS_BLOCK = "consensus_block"
    ENTITY_PROPOSAL = "entity_proposal"
    RELATION_PROPOSAL = "relation_proposal"
    PRIOR = "prior"
    TEXT_PATTERN = "text_pattern"
    READING_ORDER = "reading_order"
    PAGE_SEQUENCE = "page_sequence"
    TOC_PATTERN = "toc_pattern"
    SECTION_HIERARCHY = "section_hierarchy"
    REFERENCE_PATTERN = "reference_pattern"
    CAPTION_PATTERN = "caption_pattern"
    FOOTNOTE_PATTERN = "footnote_pattern"


class _LinkedBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)


class LinkEvidence(_LinkedBaseModel):
    """One piece of evidence supporting a linker decision.

    Attributes:
        kind: Category of evidence (consensus block, entity, prior, ...).
        source_id: Optional id of the source artefact (block, entity, ...).
        page_no: One-based page number the evidence relates to, if any.
        confidence: Evidence weight in [0, 1].
        reason: Human-readable justification for the evidence.
        metadata: Free-form metadata bag.
    """

    kind: LinkEvidenceKind
    source_id: str | None = None
    page_no: int | None = Field(default=None, ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LinkedNode(_LinkedBaseModel):
    """One node in the document's linked semantic structure.

    Produced by the linker from consensus blocks and entity proposals
    and consumed by the export stage.

    Attributes:
        id: Canonical node id (`node:<doc>:<index>`).
        node_type: Node-type taxonomy value.
        text: Optional normalised text for the node.
        page_no: One-based page number for the node, if page-local.
        order: Reading-order index within the document.
        consensus_block_id: Optional backing ConsensusBlock id.
        source_backend: Optional backend the node was lifted from.
        source_entity_ids: EntityProposal ids backing the node.
        confidence: Linker confidence in [0, 1].
        status: Link-status (resolved, resolved-low-confidence, unresolved).
        evidence: One or more LinkEvidence items backing the node.
        metadata: Free-form metadata bag.
    """

    id: str
    node_type: LinkedNodeType
    text: str | None = None
    page_no: int | None = Field(default=None, ge=1)
    order: int = Field(ge=0)
    consensus_block_id: str | None = None
    source_backend: str | None = None
    source_entity_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    status: LinkStatus
    evidence: list[LinkEvidence] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not LINKED_NODE_ID_PATTERN.fullmatch(value):
            raise ValueError("LinkedNode.id must match node:<doc>:<index>")
        return value

    @field_validator("consensus_block_id")
    @classmethod
    def _validate_consensus_block_id(cls, value: str | None) -> str | None:
        if value is not None and not CONSENSUS_ID_PATTERN.fullmatch(value):
            raise ValueError("consensus_block_id must be a consensus block id")
        return value

    @field_validator("source_entity_ids")
    @classmethod
    def _validate_source_entity_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if not ENTITY_ID_PATTERN.fullmatch(value):
                raise ValueError("source_entity_ids values must be entity proposal ids")
        return values


class LinkedRelation(_LinkedBaseModel):
    """One relation between two nodes in the linked semantic structure.

    Attributes:
        id: Canonical relation id (`lrel:<doc>:<index>`).
        relation_type: Relation-type taxonomy value.
        source_node_id: Node id of the source endpoint.
        target_node_id: Node id of the target endpoint.
        confidence: Linker confidence in [0, 1].
        status: Link-status for the relation.
        evidence: One or more LinkEvidence items backing the relation.
        metadata: Free-form metadata bag.
    """

    id: str
    relation_type: LinkedRelationType
    source_node_id: str
    target_node_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: LinkStatus
    evidence: list[LinkEvidence] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not LINKED_RELATION_ID_PATTERN.fullmatch(value):
            raise ValueError("LinkedRelation.id must match lrel:<doc>:<index>")
        return value

    @field_validator("source_node_id", "target_node_id")
    @classmethod
    def _validate_endpoint(cls, value: str) -> str:
        if not LINKED_NODE_ID_PATTERN.fullmatch(value):
            raise ValueError("relation endpoints must be linked node ids")
        return value

    @model_validator(mode="after")
    def _validate_distinct_endpoints(self) -> "LinkedRelation":
        if self.source_node_id == self.target_node_id:
            raise ValueError("relation endpoints must differ")
        return self


class LinkedConflict(_LinkedBaseModel):
    """A first-class conflict recorded in the linked structure.

    Attributes:
        id: Canonical conflict id (`lconf:<doc>:<index>`).
        conflict_type: Free-form conflict-type tag.
        source_conflict_id: Optional originating consensus conflict id.
        node_ids: LinkedNode ids participating in the conflict.
        relation_ids: LinkedRelation ids participating in the conflict.
        description: Human-readable description of the conflict.
        status: Link-status (typically unresolved).
        evidence: One or more LinkEvidence items backing the conflict.
        metadata: Free-form metadata bag.
    """

    id: str
    conflict_type: str = Field(min_length=1)
    source_conflict_id: str | None = None
    node_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1)
    status: LinkStatus
    evidence: list[LinkEvidence] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not LINKED_CONFLICT_ID_PATTERN.fullmatch(value):
            raise ValueError("LinkedConflict.id must match lconf:<doc>:<index>")
        return value

    @field_validator("source_conflict_id")
    @classmethod
    def _validate_source_conflict_id(cls, value: str | None) -> str | None:
        if value is not None and not CONFLICT_ID_PATTERN.fullmatch(value):
            raise ValueError("source_conflict_id must be a consensus conflict id")
        return value

    @field_validator("node_ids")
    @classmethod
    def _validate_node_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if not LINKED_NODE_ID_PATTERN.fullmatch(value):
                raise ValueError("node_ids values must be linked node ids")
        return values

    @field_validator("relation_ids")
    @classmethod
    def _validate_relation_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if not LINKED_RELATION_ID_PATTERN.fullmatch(value):
                raise ValueError("relation_ids values must be linked relation ids")
        return values


class LinkedStructure(_LinkedBaseModel):
    """Document-level linked semantic structure.

    Produced by the linker from ConsensusIR plus EntityProposalDocuments
    and consumed by the export stage as the canonical pre-export shape.

    Attributes:
        schema_name: Fixed marker for the JSON schema.
        schema_version: Schema version string.
        document_id: Identifier of the source document.
        source_consensus_ir: Optional path of the ConsensusIR input.
        source_consensus_report: Optional path of the consensus report.
        source_entity_documents: Paths of EntityProposalDocument inputs.
        source_prior_documents: Paths of calibration prior inputs.
        nodes: LinkedNode entries with unique ids.
        relations: LinkedRelation entries with unique ids.
        conflicts: LinkedConflict entries with unique ids.
        warnings: Document-level warnings.
        metadata: Free-form metadata bag.
    """

    schema_name: Literal["pdf2md.LinkedStructure"] = "pdf2md.LinkedStructure"
    schema_version: Literal["1.0.0"] = LINKED_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    source_consensus_ir: str | None = None
    source_consensus_report: str | None = None
    source_entity_documents: list[str] = Field(default_factory=list)
    source_prior_documents: list[str] = Field(default_factory=list)
    nodes: list[LinkedNode]
    relations: list[LinkedRelation]
    conflicts: list[LinkedConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_graph(self) -> "LinkedStructure":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node ids must be unique")
        relation_ids = [relation.id for relation in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("relation ids must be unique")
        conflict_ids = [conflict.id for conflict in self.conflicts]
        if len(conflict_ids) != len(set(conflict_ids)):
            raise ValueError("conflict ids must be unique")
        known_nodes = set(node_ids)
        known_relations = set(relation_ids)
        for relation in self.relations:
            if relation.source_node_id not in known_nodes or relation.target_node_id not in known_nodes:
                raise ValueError("relation endpoints must exist in nodes")
        for conflict in self.conflicts:
            if any(node_id not in known_nodes for node_id in conflict.node_ids):
                raise ValueError("conflict node ids must exist in nodes")
            if any(relation_id not in known_relations for relation_id in conflict.relation_ids):
                raise ValueError("conflict relation ids must exist in relations")
        return self


def linked_node_id(document_id: str, index: int) -> str:
    """Build a canonical linked node id."""

    return f"node:{document_id}:{index}"


def linked_relation_id(document_id: str, index: int) -> str:
    """Build a canonical linked relation id."""

    return f"lrel:{document_id}:{index}"


def linked_conflict_id(document_id: str, index: int) -> str:
    """Build a canonical linked conflict id."""

    return f"lconf:{document_id}:{index}"


__all__ = [
    "LINKED_SCHEMA_VERSION",
    "LINKED_NODE_ID_PATTERN",
    "LINKED_RELATION_ID_PATTERN",
    "LINKED_CONFLICT_ID_PATTERN",
    "LinkedNodeType",
    "LinkedRelationType",
    "LinkStatus",
    "LinkEvidenceKind",
    "LinkEvidence",
    "LinkedNode",
    "LinkedRelation",
    "LinkedConflict",
    "LinkedStructure",
    "linked_node_id",
    "linked_relation_id",
    "linked_conflict_id",
]
