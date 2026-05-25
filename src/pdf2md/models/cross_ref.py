"""Pydantic contracts for the CrossReferenceGraph semantic sidecar.

This module defines the on-disk schema used by the semantic layer
(Plan 006). A ``CrossReferenceGraph`` is persisted as
``cross_references.json`` alongside the existing DoclingDocument JSON.

The schema is intentionally backend-agnostic: the three semantic
backends (regex, GROBID, DeepSeek-VL2) all produce values of the same
shape, and the ensemble runner merges them by deduplicating on
``(source_ref, marker_text, char_offset)``.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CROSS_REF_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class RefType(str, Enum):
    """Canonical taxonomy for semantic reference types.

    Aligned with the marker_type strings emitted by the Plan 005 regex
    and GROBID backends. Adding a new type requires updating both the
    backend pattern tables and any downstream resolver heuristics.
    """

    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"
    THEOREM = "theorem"
    DEFINITION = "definition"
    PROOF = "proof"
    COROLLARY = "corollary"
    EXAMPLE = "example"
    SECTION = "section"
    CHAPTER = "chapter"
    BIBLIOGRAPHY = "bibliography"
    FOOTNOTE = "footnote"


_RESOLUTION_METHODS: frozenset[str] = frozenset(
    {"exact", "fuzzy", "grobid_tei", "unresolved"}
)


class _CrossRefBaseModel(BaseModel):
    """Private Pydantic base for cross-reference models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        use_enum_values=True,
    )


class RefMarker(_CrossRefBaseModel):
    """A single semantic reference marker detected in document text.

    Attributes:
        source_ref: JSON pointer to the originating DocItem (e.g.
            ``"#/texts/42"``). Free-form when no DoclingDocument is
            available; the resolver tolerates non-pointer strings.
        marker_text: The literal surface form (e.g. ``"Figure 3.2"``,
            ``"[15]"``).
        marker_type: Canonical RefType.
        char_offset: ``(start, end)`` indices into the source text.
        confidence: Confidence in [0, 1]. Deterministic backends use 1.0.
        backend: Backend identifier (``"regex"``, ``"grobid"``, ``"vlm"``).
    """

    source_ref: str = Field(min_length=1)
    marker_text: str = Field(min_length=1)
    marker_type: RefType
    char_offset: tuple[int, int]
    confidence: float = Field(ge=0.0, le=1.0)
    backend: str = Field(min_length=1)

    @field_validator("char_offset")
    @classmethod
    def _validate_offset(cls, value: tuple[int, int]) -> tuple[int, int]:
        start, end = value
        if start < 0 or end < 0:
            raise ValueError("char_offset values must be non-negative")
        if start > end:
            raise ValueError(f"char_offset start ({start}) > end ({end})")
        return value


class RefEdge(_CrossRefBaseModel):
    """A resolved (or unresolved) edge from a marker to a target.

    Attributes:
        marker: The originating :class:`RefMarker`.
        target_ref: JSON pointer to the resolved target, or ``None`` when
            unresolved.
        resolved: ``True`` iff a target was found.
        resolution_method: One of ``"exact"``, ``"fuzzy"``,
            ``"grobid_tei"``, or ``"unresolved"``.
    """

    marker: RefMarker
    target_ref: str | None = None
    resolved: bool
    resolution_method: str = Field(min_length=1)

    @field_validator("resolution_method")
    @classmethod
    def _validate_method(cls, value: str) -> str:
        if value not in _RESOLUTION_METHODS:
            raise ValueError(
                f"resolution_method must be one of {sorted(_RESOLUTION_METHODS)}, got {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _validate_consistency(self) -> RefEdge:
        if self.resolved and self.target_ref is None:
            raise ValueError("resolved=True requires a non-None target_ref")
        if not self.resolved and self.resolution_method != "unresolved":
            raise ValueError(
                f"resolved=False requires resolution_method='unresolved', got {self.resolution_method!r}"
            )
        return self


class SemanticEntity(_CrossRefBaseModel):
    """A semantic entity attached to a DocItem (theorem, definition, ...).

    Attributes:
        item_ref: JSON pointer to the DocItem the entity is anchored to.
        entity_type: Canonical RefType.
        label: Optional human-readable label (e.g. ``"Theorem 3.2"``).
        confidence: Confidence in [0, 1].
        backend: Backend identifier.
    """

    item_ref: str = Field(min_length=1)
    entity_type: RefType
    label: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    backend: str = Field(min_length=1)


class CrossReferenceGraph(_CrossRefBaseModel):
    """The full semantic sidecar for a document.

    Attributes:
        schema_version: Schema version string.
        doc_hash: Stable identifier for the document this graph belongs to.
            Free-form; typically a sha256 of the source PDF.
        markers: All detected reference markers.
        edges: Resolution edges (one per marker, including unresolved).
        entities: Semantic entities anchored to DocItems.
        backend_versions: Backend name → version string for each backend
            that contributed to this graph.
    """

    schema_version: Literal["1.0.0"] = CROSS_REF_SCHEMA_VERSION
    doc_hash: str = Field(min_length=1)
    markers: list[RefMarker] = Field(default_factory=list)
    edges: list[RefEdge] = Field(default_factory=list)
    entities: list[SemanticEntity] = Field(default_factory=list)
    backend_versions: dict[str, str] = Field(default_factory=dict)
