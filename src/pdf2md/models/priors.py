"""Calibration prior and truth contracts."""

from __future__ import annotations

import json
from enum import Enum
from importlib import resources
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pdf2md.models.entities import EntityType, RelationType
from pdf2md.models.ir import BlockKind

PRIOR_SCHEMA_VERSION = "1.0.0"


class CalibrationTarget(str, Enum):
    """Targets that calibration metrics can be computed against."""

    BLOCK_KIND = "block_kind"
    ENTITY_TYPE = "entity_type"
    RELATION_TYPE = "relation_type"
    CALIBRATION_KEY = "calibration_key"


class CalibrationStatus(str, Enum):
    """Per-metric calibration status."""

    CALIBRATED = "calibrated"
    UNDERPOWERED = "underpowered"
    NO_SAMPLES = "no_samples"
    UNINFORMATIVE = "uninformative"


class MatchOutcome(str, Enum):
    """Outcome of matching a backend prediction against truth."""

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"


class _PriorBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)


class CalibrationCounts(_PriorBaseModel):
    """Match-outcome counts underlying a calibration metric.

    Attributes:
        true_positive: Number of true-positive matches.
        false_positive: Number of false-positive matches.
        false_negative: Number of false-negative matches.
    """

    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)


class CalibrationMetric(_PriorBaseModel):
    """One calibrated metric for a (target, key) pair.

    Attributes:
        target: Calibration target the metric applies to.
        key: Key identifying the slice within the target (e.g. block kind name).
        counts: Underlying true/false-positive/negative counts.
        precision: Precision in [0, 1].
        recall: Recall in [0, 1].
        f1: F1 score in [0, 1].
        support: Total number of samples (sum of counts).
        calibrated_confidence: Smoothed confidence in [0, 1].
        status: Calibration status (calibrated, uninformative, ...).
        metadata: Free-form metadata bag.
    """

    target: CalibrationTarget
    key: str = Field(min_length=1)
    counts: CalibrationCounts
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)
    support: int = Field(ge=0)
    calibrated_confidence: float = Field(ge=0.0, le=1.0)
    status: CalibrationStatus
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_support_and_status(self) -> "CalibrationMetric":
        expected_support = self.counts.true_positive + self.counts.false_positive + self.counts.false_negative
        if self.support != expected_support:
            raise ValueError("support must equal true_positive + false_positive + false_negative")
        if self.status == CalibrationStatus.NO_SAMPLES and self.support != 0:
            raise ValueError("no_samples status requires zero support")
        # TODO: If a future metric schema carries min_samples, validate the exact
        # underpowered/calibrated boundary here instead of only checking positivity.
        if self.status == CalibrationStatus.UNDERPOWERED and self.support <= 0:
            raise ValueError("underpowered status requires positive support")
        if self.status == CalibrationStatus.CALIBRATED and self.support <= 0:
            raise ValueError("calibrated status requires positive support")
        if self.status == CalibrationStatus.UNINFORMATIVE and self.support != 0:
            raise ValueError("uninformative status requires zero support")
        return self


class CalibrationPriorDocument(_PriorBaseModel):
    """Calibrated per-backend confidence priors.

    Produced by the calibration stage from CalibrationTruthDocuments and
    backend extractions; consumed by the consensus scorer and the linker
    to weight backend evidence.

    Attributes:
        schema_name: Fixed marker for the JSON schema.
        schema_version: Schema version string.
        backend: Backend identifier the priors apply to.
        backend_version: Optional backend version tag.
        generated_from: Source artefact paths the priors were derived from.
        min_samples: Minimum support required to mark a metric calibrated.
        smoothing_alpha: Beta-distribution alpha smoothing prior.
        smoothing_beta: Beta-distribution beta smoothing prior.
        default_confidence: Fallback confidence when no metric applies.
        block_kind_priors: Per-BlockKind metrics.
        entity_type_priors: Per-EntityType metrics.
        relation_type_priors: Per-RelationType metrics.
        calibration_key_priors: Per-calibration-key metrics.
        warnings: Calibration-stage warnings.
        metadata: Free-form metadata bag.
    """

    schema_name: Literal["pdf2md.CalibrationPriorDocument"] = "pdf2md.CalibrationPriorDocument"
    schema_version: Literal["1.0.0"] = PRIOR_SCHEMA_VERSION
    backend: str = Field(min_length=1)
    backend_version: str | None = None
    generated_from: list[str] = Field(default_factory=list)
    min_samples: int = Field(ge=1)
    smoothing_alpha: float = Field(gt=0)
    smoothing_beta: float = Field(gt=0)
    default_confidence: float = Field(ge=0.0, le=1.0)
    block_kind_priors: list[CalibrationMetric] = Field(default_factory=list)
    entity_type_priors: list[CalibrationMetric] = Field(default_factory=list)
    relation_type_priors: list[CalibrationMetric] = Field(default_factory=list)
    calibration_key_priors: list[CalibrationMetric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_metric_lists(self) -> "CalibrationPriorDocument":
        for metrics in (
            self.block_kind_priors,
            self.entity_type_priors,
            self.relation_type_priors,
            self.calibration_key_priors,
        ):
            keys = [metric.key for metric in metrics]
            if len(keys) != len(set(keys)):
                raise ValueError("metric keys must be unique within each prior list")
        return self


class TruthEntity(_PriorBaseModel):
    """One ground-truth entity used to calibrate backend priors.

    Attributes:
        id: Stable truth-entity identifier.
        entity_type: Entity-type taxonomy value.
        canonical_text: Optional canonical textual form.
        page_no: One-based page number, if page-local.
        metadata: Free-form metadata bag.
    """

    id: str = Field(min_length=1)
    entity_type: EntityType
    canonical_text: str | None = None
    page_no: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TruthRelation(_PriorBaseModel):
    """One ground-truth relation between two truth entities.

    Attributes:
        id: Stable truth-relation identifier.
        relation_type: Relation-type taxonomy value.
        source_truth_id: TruthEntity id of the source endpoint.
        target_truth_id: TruthEntity id of the target endpoint.
        metadata: Free-form metadata bag.
    """

    id: str = Field(min_length=1)
    relation_type: RelationType
    source_truth_id: str = Field(min_length=1)
    target_truth_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TruthBlock(_PriorBaseModel):
    """One ground-truth block used to calibrate backend priors.

    Attributes:
        id: Stable truth-block identifier.
        block_kind: BlockKind taxonomy value.
        text: Optional canonical block text.
        page_no: One-based page number the block belongs to.
        metadata: Free-form metadata bag.
    """

    id: str = Field(min_length=1)
    block_kind: BlockKind
    text: str | None = None
    page_no: int = Field(ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalibrationTruthDocument(_PriorBaseModel):
    """Per-document bundle of ground-truth blocks, entities, and relations.

    Consumed by the calibration stage as the reference against which
    backend extractions are scored.

    Attributes:
        schema_name: Fixed marker for the JSON schema.
        schema_version: Schema version string.
        document_id: Identifier of the source document.
        blocks: TruthBlock entries with unique ids.
        entities: TruthEntity entries with unique ids.
        relations: TruthRelation entries with unique ids.
        metadata: Free-form metadata bag.
    """

    schema_name: Literal["pdf2md.CalibrationTruthDocument"] = "pdf2md.CalibrationTruthDocument"
    schema_version: Literal["1.0.0"] = PRIOR_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    blocks: list[TruthBlock] = Field(default_factory=list)
    entities: list[TruthEntity] = Field(default_factory=list)
    relations: list[TruthRelation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_truth_document(self) -> "CalibrationTruthDocument":
        block_ids = [block.id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("truth block ids must be unique")
        entity_ids = [entity.id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("truth entity ids must be unique")
        relation_ids = [relation.id for relation in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("truth relation ids must be unique")
        known = set(entity_ids)
        for relation in self.relations:
            if relation.source_truth_id not in known or relation.target_truth_id not in known:
                raise ValueError("truth relation endpoints must exist in truth entities")
            if relation.source_truth_id == relation.target_truth_id:
                raise ValueError("truth relation endpoints must differ")
        return self


def _target_value(target: CalibrationTarget | str) -> str:
    return target.value if isinstance(target, CalibrationTarget) else str(target)


def prior_key(target: CalibrationTarget | str, key: str) -> str:
    """Build the canonical `<target>:<key>` lookup string for a prior."""

    return f"{_target_value(target)}:{key}"


def _metrics_for_target(prior: CalibrationPriorDocument, target: CalibrationTarget | str) -> list[CalibrationMetric]:
    value = _target_value(target)
    if value == CalibrationTarget.BLOCK_KIND.value:
        return prior.block_kind_priors
    if value == CalibrationTarget.ENTITY_TYPE.value:
        return prior.entity_type_priors
    if value == CalibrationTarget.RELATION_TYPE.value:
        return prior.relation_type_priors
    if value == CalibrationTarget.CALIBRATION_KEY.value:
        return prior.calibration_key_priors
    return []


def lookup_prior(
    prior: CalibrationPriorDocument, target: CalibrationTarget | str, key: str
) -> CalibrationMetric | None:
    """Return the calibration metric for `(target, key)`, or None if absent.

    Args:
        prior: Calibration prior document to search.
        target: Calibration target selecting which metric list to scan.
        key: Slice key within the target.

    Returns:
        The matching CalibrationMetric, or None if no metric is registered
        for the given target/key pair.
    """

    for metric in _metrics_for_target(prior, target):
        if metric.key == key:
            return metric
    return None


def lookup_confidence(prior: CalibrationPriorDocument, target: CalibrationTarget | str, key: str) -> float:
    """Return the calibrated confidence for `(target, key)`.

    Falls back to ``prior.default_confidence`` when no metric is registered
    for the given target/key pair.

    Args:
        prior: Calibration prior document to query.
        target: Calibration target selecting which metric list to scan.
        key: Slice key within the target.

    Returns:
        The metric's ``calibrated_confidence``, or the document's default
        confidence if no metric matches.
    """

    metric = lookup_prior(prior, target, key)
    if metric is None:
        return prior.default_confidence
    return metric.calibrated_confidence


# ---------------------------------------------------------------------------
# Plan 19 — three-level prior hierarchy (uninformative -> factory -> user)
# ---------------------------------------------------------------------------


_UNINFORMATIVE_WARNING = "uninformative_prior:no_calibration_data"


def build_uninformative_prior(
    backend: str,
    *,
    default_confidence: float = 0.50,
    min_samples: int = 5,
    smoothing_alpha: float = 1.0,
    smoothing_beta: float = 1.0,
) -> CalibrationPriorDocument:
    """Return a uniform prior with one UNINFORMATIVE metric per BlockKind.

    The document carries zero support, ``calibrated_confidence`` set to
    ``default_confidence`` for every block kind, and a single warning
    flagging that no calibration data was consumed. ``lookup_confidence``
    returns ``default_confidence`` for any key — known or unknown — so
    downstream scoring is identical to the pre-Plan-19 "no priors"
    fallback path.
    """

    metrics: list[CalibrationMetric] = []
    for block_kind in BlockKind:
        metrics.append(
            CalibrationMetric(
                target=CalibrationTarget.BLOCK_KIND,
                key=block_kind.value,
                counts=CalibrationCounts(true_positive=0, false_positive=0, false_negative=0),
                precision=0.0,
                recall=0.0,
                f1=0.0,
                support=0,
                calibrated_confidence=default_confidence,
                status=CalibrationStatus.UNINFORMATIVE,
                metadata={},
            )
        )
    return CalibrationPriorDocument(
        backend=backend,
        backend_version=None,
        generated_from=[],
        min_samples=min_samples,
        smoothing_alpha=smoothing_alpha,
        smoothing_beta=smoothing_beta,
        default_confidence=default_confidence,
        block_kind_priors=metrics,
        entity_type_priors=[],
        relation_type_priors=[],
        calibration_key_priors=[],
        warnings=[_UNINFORMATIVE_WARNING],
        metadata={"prior_type": "uninformative"},
    )


def load_factory_prior(backend: str) -> CalibrationPriorDocument | None:
    """Load a factory prior shipped under ``pdf2md/data/factory_priors/``.

    Returns ``None`` when the file is missing, unreadable, or fails
    schema validation. The lookup uses ``importlib.resources`` so the
    file resolves both from an editable checkout (``src/pdf2md/data/``)
    and from an installed wheel.
    """

    try:
        ref = resources.files("pdf2md.data.factory_priors").joinpath(f"{backend}.json")
    except (ModuleNotFoundError, FileNotFoundError):
        return None
    try:
        text = ref.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, AttributeError):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        return CalibrationPriorDocument.model_validate(payload)
    except Exception:  # noqa: BLE001
        return None


__all__ = [
    "PRIOR_SCHEMA_VERSION",
    "CalibrationTarget",
    "CalibrationStatus",
    "MatchOutcome",
    "CalibrationCounts",
    "CalibrationMetric",
    "CalibrationPriorDocument",
    "TruthEntity",
    "TruthRelation",
    "TruthBlock",
    "CalibrationTruthDocument",
    "prior_key",
    "lookup_prior",
    "lookup_confidence",
    "build_uninformative_prior",
    "load_factory_prior",
]
