"""Human adjudication labels for unresolved cross-reference markers.

The models in this module describe the downloadable/re-importable JSON
teaching signal produced by the static cross-reference viewer's Adjudicate tab.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pdf2md.models.cross_ref import RefType

SCHEMA_NAME: Literal["pdf2md.MarkerAdjudication"] = "pdf2md.MarkerAdjudication"
SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
VIEWER_VERSION: Literal["008_4"] = "008_4"

Decision = Literal["resolve", "reclassify", "noise", "rule_hint"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _AdjudicationBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


class AdjudicationImportHistory(_AdjudicationBaseModel):
    """One import/merge operation recorded in document metadata."""

    at: datetime
    merged_from: str = Field(min_length=1)
    added: int = Field(ge=0)
    overwritten: int = Field(ge=0)

    @field_validator("at")
    @classmethod
    def _require_iso_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value


class AdjudicationMetadata(_AdjudicationBaseModel):
    """Metadata carried by an adjudication label file."""

    graph_schema_version: str = Field(min_length=1)
    viewer_version: Literal["008_4"] = VIEWER_VERSION
    import_history: list[AdjudicationImportHistory] = Field(default_factory=list)


class MarkerAdjudication(_AdjudicationBaseModel):
    """One human decision about an unresolved reference marker."""

    marker_id: str = Field(min_length=1)
    marker_type: RefType
    label: str
    source_ref: str = Field(min_length=1)
    char_offset: tuple[int, int]
    page_no: int | None = None
    backend: str = Field(min_length=1)
    decision: Decision
    target_entity_id: str | None = None
    corrected_type: RefType | None = None
    rule_hint: str | None = None
    decided_at: datetime

    @field_validator("char_offset")
    @classmethod
    def _validate_offset(cls, value: tuple[int, int]) -> tuple[int, int]:
        start, end = value
        if start < 0 or end < 0:
            raise ValueError("char_offset values must be non-negative")
        if start > end:
            raise ValueError("char_offset start must be <= end")
        return value

    @field_validator("decided_at")
    @classmethod
    def _require_decided_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("decided_at must include a timezone")
        return value

    @model_validator(mode="after")
    def _validate_decision_payload(self) -> MarkerAdjudication:
        payloads = {
            "target_entity_id": self.target_entity_id,
            "corrected_type": self.corrected_type,
            "rule_hint": self.rule_hint,
        }
        populated = [name for name, value in payloads.items() if value not in (None, "")]
        expected = {
            "resolve": "target_entity_id",
            "reclassify": "corrected_type",
            "rule_hint": "rule_hint",
            "noise": None,
        }[self.decision]
        if expected is None:
            if populated:
                raise ValueError("decision='noise' must not populate a payload field")
        elif populated != [expected]:
            raise ValueError(
                f"decision={self.decision!r} requires exactly one payload field: {expected}"
            )
        return self


class AdjudicationDocument(_AdjudicationBaseModel):
    """Versioned label file exported by the marker adjudication viewer."""

    schema_name: Literal["pdf2md.MarkerAdjudication"] = SCHEMA_NAME
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    generated_at: datetime
    document_id: str = Field(min_length=1)
    adjudicator: str = ""
    adjudications: list[MarkerAdjudication] = Field(default_factory=list)
    metadata: AdjudicationMetadata

    @field_validator("generated_at")
    @classmethod
    def _require_generated_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must include a timezone")
        return value


def _latest_by_marker(
    adjudications: Iterable[MarkerAdjudication],
) -> dict[str, MarkerAdjudication]:
    latest: dict[str, MarkerAdjudication] = {}
    for item in adjudications:
        current = latest.get(item.marker_id)
        if current is None or item.decided_at >= current.decided_at:
            latest[item.marker_id] = item
    return latest


def merge_documents(
    a: AdjudicationDocument,
    b: AdjudicationDocument,
    *,
    merged_from: str = "(memory)",
) -> AdjudicationDocument:
    """Merge two same-document adjudication files.

    The most recent ``decided_at`` per ``marker_id`` wins. A history entry is
    appended describing how many markers from ``b`` were added or overwrote a
    decision from ``a``.
    """

    if a.document_id != b.document_id:
        raise ValueError(
            f"document_id mismatch: {a.document_id!r} != {b.document_id!r}"
        )

    merged = _latest_by_marker(a.adjudications)
    added = 0
    overwritten = 0
    for incoming in _latest_by_marker(b.adjudications).values():
        current = merged.get(incoming.marker_id)
        if current is None:
            merged[incoming.marker_id] = incoming
            added += 1
        elif incoming.decided_at >= current.decided_at:
            merged[incoming.marker_id] = incoming
            overwritten += 1

    adjudications = sorted(merged.values(), key=lambda item: item.marker_id)
    metadata = AdjudicationMetadata(
        graph_schema_version=a.metadata.graph_schema_version,
        viewer_version=VIEWER_VERSION,
        import_history=[
            *a.metadata.import_history,
            *b.metadata.import_history,
            AdjudicationImportHistory(
                at=_utc_now(),
                merged_from=merged_from,
                added=added,
                overwritten=overwritten,
            ),
        ],
    )
    generated_at = max(a.generated_at, b.generated_at, _utc_now())
    return AdjudicationDocument(
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        generated_at=generated_at,
        document_id=a.document_id,
        adjudicator=a.adjudicator or b.adjudicator,
        adjudications=adjudications,
        metadata=metadata,
    )
