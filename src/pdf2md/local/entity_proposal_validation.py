"""EntityProposalDocument validation wrapper (Plan 11).

Reads ``EntityProposalDocument`` artefacts produced by the same connector path
validated in Plan 10 and classifies each backend's output using a five-status
taxonomy. Reuses the existing ``pdf2md.connectors.common.connect_raw_dir``
entrypoint when entities must be regenerated from a raw backend directory.

Plan 11 must not reopen connector architecture, must not invent new entity
or relation types, and must not run calibration, consensus, semantic linking,
or any export stage.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from pdf2md.connectors.common import BackendConnectorConfig, ConnectorResult, connect_raw_dir
from pdf2md.models.entities import (
    EntityProposalDocument,
    EntityType,
)

ENTITY_VALIDATION_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
TOOL_NAME: Literal["validate_entity_proposals"] = "validate_entity_proposals"
DEFAULT_PREFERRED_GATE_MINIMUM = 2
DEFAULT_DOCUMENT_ID = "plan11_doc"
PLAN10_VALIDATED_STATUS = "validated"
SEMANTIC_MIN_CONFIDENCE = 0.3


class EntityValidationStatus(str, Enum):
    """The five Plan 11 entity validation statuses."""

    VALIDATED = "validated"
    NO_ENTITIES_PRODUCED = "no_entities_produced"
    SCHEMA_FAILED = "schema_failed"
    CONNECTOR_CRASH = "connector_crash"
    DEFERRED_FROM_PLAN_10 = "deferred_from_plan_10"


_NEXT_ACTIONS: dict[EntityValidationStatus, str] = {
    EntityValidationStatus.VALIDATED: (
        "EntityProposalDocument validated; Plan 12 may use these entities as input "
        "evidence for real calibration prior generation."
    ),
    EntityValidationStatus.NO_ENTITIES_PRODUCED: (
        "Backend produced a structurally valid but empty EntityProposalDocument. "
        "Record this evidence for Plan 12 calibration; it does not count toward "
        "the Plan 11 validated gate."
    ),
    EntityValidationStatus.SCHEMA_FAILED: (
        "EntityProposalDocument-like data failed schema validation; inspect "
        "validation_error_summary and either supply corrected artefacts or fix "
        "the connector defect."
    ),
    EntityValidationStatus.CONNECTOR_CRASH: (
        "Connector or validation wrapper crashed; inspect the error log."
    ),
    EntityValidationStatus.DEFERRED_FROM_PLAN_10: (
        "Backend was not validated by Plan 10 or has no Plan 10 artefact; "
        "rerun Plan 10 for this backend before retrying Plan 11."
    ),
}


class _EntityBaseModel(BaseModel):
    """Private Pydantic base for entity-validation models."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class EntityValidationResult(_EntityBaseModel):
    """Per-backend entity validation entry."""

    backend_name: str
    plan10_status: str | None = None
    page_extraction_ir_path: str | None = None
    entity_document_path: str | None = None
    connector_entrypoint: str | None = None
    status: EntityValidationStatus
    entity_count: int = 0
    entity_type_counts: dict[str, int] = Field(default_factory=dict)
    relation_count: int = 0
    relation_type_counts: dict[str, int] = Field(default_factory=dict)
    has_evidence: bool = False
    has_relations: bool = False
    has_provenance: bool = False
    has_confidence_sources: bool = False
    semantic_plausibility_passed: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    validation_error_summary: str | None = None
    entity_output_path: str | None = None
    next_action: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityValidationReport(_EntityBaseModel):
    """Plan 11 EntityProposalDocument validation report."""

    schema_name: Literal["pdf2md.EntityProposalDocumentValidationReport"] = (
        "pdf2md.EntityProposalDocumentValidationReport"
    )
    schema_version: Literal["1.0.0"] = ENTITY_VALIDATION_SCHEMA_VERSION
    generated_at: str
    tool_name: Literal["validate_entity_proposals"] = TOOL_NAME
    plan10_report_path: str | None = None
    gate_mode: Literal["preferred", "reduced"] = "preferred"
    preferred_gate_minimum: int = DEFAULT_PREFERRED_GATE_MINIMUM
    preferred_gate_passed: bool = False
    minimum_gate_passed: bool = False
    human_reduced_gate_required: bool = False
    total_backends_considered: int = 0
    backends_validated: int = 0
    backends_no_entities: int = 0
    backends_failed: int = 0
    backends_deferred: int = 0
    results: list[EntityValidationResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_counts(self) -> EntityValidationReport:
        names = [r.backend_name for r in self.results]
        if len(names) != len(set(names)):
            raise ValueError("backend names must be unique")
        validated = _count_status(self.results, EntityValidationStatus.VALIDATED)
        no_entities = _count_status(self.results, EntityValidationStatus.NO_ENTITIES_PRODUCED)
        deferred = _count_status(self.results, EntityValidationStatus.DEFERRED_FROM_PLAN_10)
        failed = sum(
            _count_status(self.results, s)
            for s in (
                EntityValidationStatus.CONNECTOR_CRASH,
                EntityValidationStatus.SCHEMA_FAILED,
            )
        )
        if self.total_backends_considered != len(self.results):
            raise ValueError("total_backends_considered must match results length")
        if self.backends_validated != validated:
            raise ValueError("backends_validated must match validated results")
        if self.backends_no_entities != no_entities:
            raise ValueError("backends_no_entities must match no_entities_produced results")
        if self.backends_failed != failed:
            raise ValueError("backends_failed must match failed results")
        if self.backends_deferred != deferred:
            raise ValueError("backends_deferred must match deferred results")
        if validated + no_entities + failed + deferred != self.total_backends_considered:
            raise ValueError(
                "validated + no_entities + failed + deferred must cover every backend"
            )
        return self


def _status_value(result: Any) -> str:
    status = result.status if hasattr(result, "status") else None
    if isinstance(status, EntityValidationStatus):
        return status.value
    return str(status)


def _count_status(results: list[Any], status: EntityValidationStatus) -> int:
    return sum(1 for r in results if _status_value(r) == status.value)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_noise_text(text: str | None) -> bool:
    if text is None:
        return True
    stripped = text.strip()
    if not stripped or len(stripped) < 3:
        return True
    if re.match(r"^(\[)?(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|TRACE)(\])?[\s:]", stripped, re.I):
        return True
    return bool(re.fullmatch(r"/(?:[A-Za-z0-9_.\-]+/?)+", stripped))


def _semantic_plausibility(document: EntityProposalDocument) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    if not document.entities:
        warnings.append("semantic_no_entities")
        return False, warnings

    typed_entities = [
        e for e in document.entities if (e.entity_type if isinstance(e.entity_type, str) else e.entity_type.value) != EntityType.UNKNOWN.value
    ]
    if not typed_entities:
        warnings.append("semantic_all_entities_unknown")

    confident = [e for e in document.entities if e.confidence >= SEMANTIC_MIN_CONFIDENCE]
    if not confident:
        warnings.append("semantic_all_entities_low_confidence")

    with_useful_text = [
        e
        for e in document.entities
        if not _is_noise_text(e.canonical_text)
        or any(not _is_noise_text(ev.text) for ev in e.evidence)
    ]
    if not with_useful_text:
        warnings.append("semantic_all_entities_noise_or_empty")

    has_evidence_refs = any(
        any(ev.source_block_id or ev.raw_ref or ev.text for ev in e.evidence)
        for e in document.entities
    )
    if not has_evidence_refs:
        warnings.append("semantic_no_evidence_references")

    plausible = bool(typed_entities) and bool(confident) and bool(with_useful_text)
    return plausible, warnings


def _entity_type_counts(document: EntityProposalDocument) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in document.entities:
        key = e.entity_type if isinstance(e.entity_type, str) else e.entity_type.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _relation_type_counts(document: EntityProposalDocument) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in document.relations:
        key = r.relation_type if isinstance(r.relation_type, str) else r.relation_type.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _has_evidence(document: EntityProposalDocument) -> bool:
    return any(e.evidence for e in document.entities)


def _has_provenance(document: EntityProposalDocument) -> bool:
    if not document.backend:
        return False
    return all(
        any(ev.source_block_id or ev.raw_ref for ev in e.evidence) or bool(e.block_ids)
        for e in document.entities
    )


def _has_confidence_sources(document: EntityProposalDocument) -> bool:
    return bool(document.entities) and all(
        bool(e.confidence_source) for e in document.entities
    )


def _write_entity_proposals_copy(
    *,
    backend_name: str,
    document: EntityProposalDocument,
    out_dir: Path,
) -> Path:
    backend_dir = out_dir / backend_name
    backend_dir.mkdir(parents=True, exist_ok=True)
    target = backend_dir / "entity_proposals.json"
    target.write_text(document.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def _result(
    *,
    backend_name: str,
    status: EntityValidationStatus,
    plan10_status: str | None = None,
    page_extraction_ir_path: str | None = None,
    entity_document_path: str | None = None,
    connector_entrypoint: str | None = None,
    entity_count: int = 0,
    entity_type_counts: dict[str, int] | None = None,
    relation_count: int = 0,
    relation_type_counts: dict[str, int] | None = None,
    has_evidence: bool = False,
    has_relations: bool = False,
    has_provenance: bool = False,
    has_confidence_sources: bool = False,
    semantic_plausibility_passed: bool = False,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    validation_error_summary: str | None = None,
    entity_output_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EntityValidationResult:
    return EntityValidationResult(
        backend_name=backend_name,
        plan10_status=plan10_status,
        page_extraction_ir_path=page_extraction_ir_path,
        entity_document_path=entity_document_path,
        connector_entrypoint=connector_entrypoint,
        status=status,
        entity_count=entity_count,
        entity_type_counts=entity_type_counts or {},
        relation_count=relation_count,
        relation_type_counts=relation_type_counts or {},
        has_evidence=has_evidence,
        has_relations=has_relations,
        has_provenance=has_provenance,
        has_confidence_sources=has_confidence_sources,
        semantic_plausibility_passed=semantic_plausibility_passed,
        warnings=warnings or [],
        errors=errors or [],
        validation_error_summary=validation_error_summary,
        entity_output_path=entity_output_path,
        next_action=_NEXT_ACTIONS[status],
        metadata=metadata or {},
    )


def _classify_document(document: EntityProposalDocument) -> tuple[EntityValidationStatus, dict[str, Any]]:
    entity_count = len(document.entities)
    relation_count = len(document.relations)
    entity_type_counts = _entity_type_counts(document)
    relation_type_counts = _relation_type_counts(document)
    has_evidence = _has_evidence(document)
    has_provenance = _has_provenance(document)
    has_confidence_sources = _has_confidence_sources(document)
    semantic_ok, semantic_warnings = _semantic_plausibility(document)

    info = {
        "entity_count": entity_count,
        "entity_type_counts": entity_type_counts,
        "relation_count": relation_count,
        "relation_type_counts": relation_type_counts,
        "has_evidence": has_evidence,
        "has_relations": relation_count > 0,
        "has_provenance": has_provenance,
        "has_confidence_sources": has_confidence_sources,
        "semantic_plausibility_passed": semantic_ok,
        "semantic_warnings": semantic_warnings,
    }
    if entity_count == 0:
        return EntityValidationStatus.NO_ENTITIES_PRODUCED, info
    return EntityValidationStatus.VALIDATED, info


def _load_entity_document_from_json(path: Path) -> tuple[EntityProposalDocument | None, str, str | None]:
    """Return (document, error_kind, error_summary).

    error_kind ∈ {"", "crash", "schema"}.
    """

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return None, "crash", f"entities_path_not_found:{exc}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, "crash", f"entities_path_unreadable:{exc}"
    try:
        document = EntityProposalDocument.model_validate(data)
    except ValidationError as exc:
        return None, "schema", str(exc)
    except Exception as exc:
        return None, "schema", f"{type(exc).__name__}: {exc}"
    return document, "", None


def validate_one_backend(
    *,
    backend_name: str,
    entities_path: Path | None = None,
    page_ir_path: Path | None = None,
    raw_dir: Path | None = None,
    plan10_status: str | None = None,
    document_id: str = DEFAULT_DOCUMENT_ID,
    connector: Callable[..., ConnectorResult] = connect_raw_dir,
    out_dir: Path | None = None,
) -> EntityValidationResult:
    """Validate one backend's EntityProposalDocument output."""

    connector_name = (
        f"{connector.__module__}.{connector.__name__}"
        if hasattr(connector, "__module__")
        else "custom_connector"
    )

    if plan10_status is not None and plan10_status != PLAN10_VALIDATED_STATUS:
        return _result(
            backend_name=backend_name,
            status=EntityValidationStatus.DEFERRED_FROM_PLAN_10,
            plan10_status=plan10_status,
            page_extraction_ir_path=str(page_ir_path) if page_ir_path else None,
            entity_document_path=str(entities_path) if entities_path else None,
            connector_entrypoint=connector_name,
            warnings=[f"plan10_status_not_validated:{plan10_status}"],
        )

    if entities_path is None and raw_dir is None:
        return _result(
            backend_name=backend_name,
            status=EntityValidationStatus.DEFERRED_FROM_PLAN_10,
            plan10_status=plan10_status,
            connector_entrypoint=connector_name,
            warnings=["no_entity_artefact_source"],
        )

    document: EntityProposalDocument | None = None
    document_source: str | None = None
    error_kind = ""
    error_summary: str | None = None
    raw_warnings: list[str] = []

    if entities_path is not None:
        document_source = str(entities_path)
        document, error_kind, error_summary = _load_entity_document_from_json(Path(entities_path))
    else:
        # entities_path not provided; invoke the connector against raw_dir
        raw_path = Path(raw_dir) if raw_dir else None
        if raw_path is None or not raw_path.exists() or not raw_path.is_dir():
            return _result(
                backend_name=backend_name,
                status=EntityValidationStatus.CONNECTOR_CRASH,
                plan10_status=plan10_status,
                page_extraction_ir_path=str(page_ir_path) if page_ir_path else None,
                connector_entrypoint=connector_name,
                errors=[f"raw_dir_missing:{raw_path}"],
            )
        config = BackendConnectorConfig(backend=backend_name, default_backend_version=None)
        try:
            connector_result = connector(
                raw_dir=raw_path,
                document_id=document_id,
                config=config,
            )
        except Exception as exc:
            return _result(
                backend_name=backend_name,
                status=EntityValidationStatus.CONNECTOR_CRASH,
                plan10_status=plan10_status,
                page_extraction_ir_path=str(page_ir_path) if page_ir_path else None,
                connector_entrypoint=connector_name,
                errors=[f"{type(exc).__name__}: {exc}"],
            )
        raw_warnings = list(getattr(connector_result, "warnings", []) or [])
        try:
            entity_obj = connector_result.entities
            if isinstance(entity_obj, EntityProposalDocument):
                document = entity_obj
            elif isinstance(entity_obj, dict):
                document = EntityProposalDocument.model_validate(entity_obj)
            else:
                document = EntityProposalDocument.model_validate(
                    json.loads(json.dumps(entity_obj, default=lambda o: getattr(o, "model_dump", lambda: o)()))
                )
        except ValidationError as exc:
            error_kind, error_summary = "schema", str(exc)
        except Exception as exc:
            error_kind, error_summary = "schema", f"{type(exc).__name__}: {exc}"

    if error_kind == "crash":
        return _result(
            backend_name=backend_name,
            status=EntityValidationStatus.CONNECTOR_CRASH,
            plan10_status=plan10_status,
            page_extraction_ir_path=str(page_ir_path) if page_ir_path else None,
            entity_document_path=document_source,
            connector_entrypoint=connector_name,
            errors=[error_summary or "connector_crash"],
            validation_error_summary=error_summary,
            warnings=raw_warnings,
        )
    if error_kind == "schema":
        return _result(
            backend_name=backend_name,
            status=EntityValidationStatus.SCHEMA_FAILED,
            plan10_status=plan10_status,
            page_extraction_ir_path=str(page_ir_path) if page_ir_path else None,
            entity_document_path=document_source,
            connector_entrypoint=connector_name,
            errors=["entity_proposal_document_model_validate_failed"],
            validation_error_summary=error_summary,
            warnings=raw_warnings,
        )
    if document is None:
        return _result(
            backend_name=backend_name,
            status=EntityValidationStatus.CONNECTOR_CRASH,
            plan10_status=plan10_status,
            page_extraction_ir_path=str(page_ir_path) if page_ir_path else None,
            entity_document_path=document_source,
            connector_entrypoint=connector_name,
            errors=["entity_proposal_document_unavailable"],
            warnings=raw_warnings,
        )

    status, info = _classify_document(document)

    entity_output_path: str | None = None
    if out_dir is not None and status in (
        EntityValidationStatus.VALIDATED,
        EntityValidationStatus.NO_ENTITIES_PRODUCED,
    ):
        target = _write_entity_proposals_copy(
            backend_name=backend_name,
            document=document,
            out_dir=out_dir,
        )
        entity_output_path = str(target)

    return _result(
        backend_name=backend_name,
        status=status,
        plan10_status=plan10_status,
        page_extraction_ir_path=str(page_ir_path) if page_ir_path else None,
        entity_document_path=document_source,
        connector_entrypoint=connector_name,
        entity_count=info["entity_count"],
        entity_type_counts=info["entity_type_counts"],
        relation_count=info["relation_count"],
        relation_type_counts=info["relation_type_counts"],
        has_evidence=info["has_evidence"],
        has_relations=info["has_relations"],
        has_provenance=info["has_provenance"],
        has_confidence_sources=info["has_confidence_sources"],
        semantic_plausibility_passed=info["semantic_plausibility_passed"],
        warnings=raw_warnings + info["semantic_warnings"],
        entity_output_path=entity_output_path,
    )


def _load_plan10_report(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    if not path.is_file():
        warnings.append(f"plan10_report_missing:{path}")
        return None, warnings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"plan10_report_unreadable:{exc}")
        return None, warnings
    if not isinstance(data, dict):
        warnings.append("plan10_report_not_object")
        return None, warnings
    return data, warnings


def _backends_from_plan10_report(
    report: dict[str, Any],
) -> list[tuple[str, str | None, Path | None, Path | None]]:
    """Return (backend_name, status, page_extraction_ir_path, raw_output_dir) tuples."""

    out: list[tuple[str, str | None, Path | None, Path | None]] = []
    results = report.get("results")
    if not isinstance(results, list):
        return out
    for entry in results:
        if not isinstance(entry, dict):
            continue
        name = entry.get("backend_name")
        if not isinstance(name, str) or not name:
            continue
        status = entry.get("status")
        status_str = status if isinstance(status, str) else None
        page_ir = entry.get("page_extraction_ir_path")
        page_ir_path = Path(page_ir) if isinstance(page_ir, str) and page_ir else None
        raw = entry.get("raw_output_dir")
        raw_path = Path(raw) if isinstance(raw, str) and raw else None
        out.append((name, status_str, page_ir_path, raw_path))
    return out


def _gates(
    results: list[EntityValidationResult],
    preferred_minimum: int,
) -> tuple[bool, bool]:
    """Compute (preferred_gate_passed, minimum_gate_passed)."""

    semantically_useful = [
        r
        for r in results
        if _status_value(r) == EntityValidationStatus.VALIDATED.value
        and r.semantic_plausibility_passed
    ]
    preferred = len(semantically_useful) >= preferred_minimum
    minimum = len(semantically_useful) >= 1
    return preferred, minimum


def build_entity_proposal_validation_report(
    *,
    backend_entities: Mapping[str, Path] | None = None,
    backend_page_ir: Mapping[str, Path] | None = None,
    backend_raw_dirs: Mapping[str, Path] | None = None,
    plan10_report_path: Path | None = None,
    preferred_gate_minimum: int = DEFAULT_PREFERRED_GATE_MINIMUM,
    allow_reduced_gate: bool = False,
    document_id: str = DEFAULT_DOCUMENT_ID,
    connector: Callable[..., ConnectorResult] = connect_raw_dir,
    out_dir: Path | None = None,
    generated_at: str | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> EntityValidationReport:
    """Validate EntityProposalDocument outputs for one or more backends.

    Sources of entity documents (priority order per backend):

    1. ``backend_entities[name]`` — explicit path to an ``entities.json`` file.
    2. ``backend_raw_dirs[name]`` — raw backend directory; the connector is
       invoked to regenerate the EntityProposalDocument.
    3. Entries derived from ``plan10_report_path`` — ``raw_output_dir`` is used
       as the connector input when entities have not been supplied explicitly.
    """

    warnings: list[str] = []
    connector_name = (
        f"{connector.__module__}.{connector.__name__}"
        if hasattr(connector, "__module__")
        else "custom_connector"
    )
    metadata: dict[str, Any] = {
        "connector_entrypoint": connector_name,
        "document_id": document_id,
        "calibration_priors_handled_by": "plan_12",
    }
    if extra_metadata:
        metadata.update(dict(extra_metadata))

    selections: dict[str, dict[str, Any]] = {}

    if plan10_report_path is not None:
        plan10_data, plan10_warnings = _load_plan10_report(Path(plan10_report_path))
        warnings.extend(plan10_warnings)
        if plan10_data is not None:
            for name, status, page_ir, raw in _backends_from_plan10_report(plan10_data):
                selections[name] = {
                    "plan10_status": status,
                    "page_ir_path": page_ir,
                    "raw_dir": raw,
                    "entities_path": None,
                }

    if backend_entities:
        for name, path in backend_entities.items():
            current = selections.get(name, {})
            current["entities_path"] = Path(path)
            current["plan10_status"] = PLAN10_VALIDATED_STATUS
            if "page_ir_path" not in current:
                current["page_ir_path"] = None
            if "raw_dir" not in current:
                current["raw_dir"] = None
            selections[name] = current

    if backend_page_ir:
        for name, path in backend_page_ir.items():
            current = selections.setdefault(name, {})
            current["page_ir_path"] = Path(path)

    if backend_raw_dirs:
        for name, path in backend_raw_dirs.items():
            current = selections.setdefault(name, {})
            current["raw_dir"] = Path(path)
            current.setdefault("plan10_status", PLAN10_VALIDATED_STATUS)
            current.setdefault("entities_path", None)
            current.setdefault("page_ir_path", None)

    if not selections:
        warnings.append(
            "no_backends_selected: provide --plan10-report and/or --backend-entities entries"
        )

    results: list[EntityValidationResult] = []
    for name in sorted(selections):
        spec = selections[name]
        result = validate_one_backend(
            backend_name=name,
            entities_path=spec.get("entities_path"),
            page_ir_path=spec.get("page_ir_path"),
            raw_dir=spec.get("raw_dir"),
            plan10_status=spec.get("plan10_status"),
            document_id=document_id,
            connector=connector,
            out_dir=out_dir,
        )
        results.append(result)

    preferred_passed, minimum_passed = _gates(results, preferred_gate_minimum)
    gate_mode: Literal["preferred", "reduced"] = "preferred"
    human_reduced_gate_required = False
    if not preferred_passed and minimum_passed and allow_reduced_gate:
        gate_mode = "reduced"
        human_reduced_gate_required = True

    validated = _count_status(results, EntityValidationStatus.VALIDATED)
    no_entities = _count_status(results, EntityValidationStatus.NO_ENTITIES_PRODUCED)
    deferred = _count_status(results, EntityValidationStatus.DEFERRED_FROM_PLAN_10)
    failed = sum(
        _count_status(results, s)
        for s in (
            EntityValidationStatus.CONNECTOR_CRASH,
            EntityValidationStatus.SCHEMA_FAILED,
        )
    )

    return EntityValidationReport(
        generated_at=generated_at or _utc_now(),
        plan10_report_path=str(plan10_report_path) if plan10_report_path else None,
        gate_mode=gate_mode,
        preferred_gate_minimum=preferred_gate_minimum,
        preferred_gate_passed=preferred_passed,
        minimum_gate_passed=minimum_passed,
        human_reduced_gate_required=human_reduced_gate_required,
        total_backends_considered=len(results),
        backends_validated=validated,
        backends_no_entities=no_entities,
        backends_failed=failed,
        backends_deferred=deferred,
        results=results,
        warnings=warnings,
        metadata=metadata,
    )


def build_entity_proposal_validation_summary(report: EntityValidationReport) -> str:
    """Render a human-readable Plan 11 summary with the Plan 12 hand-off."""

    preferred_state = "PASSED" if report.preferred_gate_passed else "FAILED"
    minimum_state = "PASSED" if report.minimum_gate_passed else "FAILED"
    lines = [
        "pdf2md EntityProposalDocument validation (Plan 11)",
        f"schema: {report.schema_name} {report.schema_version}",
        f"tool: {report.tool_name}",
        f"generated_at: {report.generated_at}",
        f"plan10_report_path: {report.plan10_report_path}",
        f"gate_mode: {report.gate_mode}",
        f"preferred_gate ({report.preferred_gate_minimum} required): {preferred_state}",
        f"minimum_gate (1 required): {minimum_state}",
        f"human_reduced_gate_required: {str(report.human_reduced_gate_required).lower()}",
        (
            f"backends: {report.total_backends_considered} considered, "
            f"{report.backends_validated} validated, "
            f"{report.backends_no_entities} no_entities, "
            f"{report.backends_failed} failed, "
            f"{report.backends_deferred} deferred"
        ),
        "",
        "validated backends:",
    ]
    validated = [r for r in report.results if _status_value(r) == EntityValidationStatus.VALIDATED.value]
    if not validated:
        lines.append("- (none)")
    for r in validated:
        sem = "yes" if r.semantic_plausibility_passed else "no"
        lines.append(
            f"- {r.backend_name}: entities={r.entity_count} relations={r.relation_count} "
            f"semantic_plausibility_passed={sem} output={r.entity_output_path}"
        )
        if r.entity_type_counts:
            lines.append(f"    entity_type_counts: {r.entity_type_counts}")
        if r.relation_type_counts:
            lines.append(f"    relation_type_counts: {r.relation_type_counts}")
        lines.append(f"    next_action: {r.next_action}")

    no_entities = [
        r for r in report.results if _status_value(r) == EntityValidationStatus.NO_ENTITIES_PRODUCED.value
    ]
    lines.extend(["", "no-entity backends (recorded for Plan 12 calibration):"])
    if not no_entities:
        lines.append("- (none)")
    for r in no_entities:
        lines.append(f"- {r.backend_name}: 0 entities, 0 relations")
        lines.append(f"    next_action: {r.next_action}")

    others = [
        r
        for r in report.results
        if _status_value(r)
        not in (
            EntityValidationStatus.VALIDATED.value,
            EntityValidationStatus.NO_ENTITIES_PRODUCED.value,
        )
    ]
    lines.extend(["", "failed or deferred backends:"])
    if not others:
        lines.append("- (none)")
    for r in others:
        detail = r.validation_error_summary or (r.errors[0] if r.errors else "")
        lines.append(f"- {r.backend_name} [{_status_value(r)}]: {detail}")
        lines.append(f"    next_action: {r.next_action}")

    if report.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in report.warnings)

    lines.extend(
        [
            "",
            "Plan 12 hand-off:",
        ]
    )
    plausible = [r for r in validated if r.semantic_plausibility_passed]
    if plausible:
        lines.append(
            "- Candidate backends for real calibration prior generation in Plan 12: "
            + ", ".join(r.backend_name for r in plausible)
        )
    else:
        lines.append("- No semantically plausible EntityProposalDocument available for Plan 12 hand-off.")
    for r in plausible:
        if r.entity_output_path:
            lines.append(f"- {r.backend_name} entity_proposals: {r.entity_output_path}")
    if no_entities:
        lines.append(
            "- No-entity backends recorded for Plan 12 calibration context: "
            + ", ".join(r.backend_name for r in no_entities)
        )
    if report.human_reduced_gate_required:
        lines.append(
            "- Reduced-gate progression requires explicit human approval recorded in the human verification report."
        )
    lines.append(
        "- Real calibration prior generation is deferred to Plan 12 and is not used for Plan 11 pass/fail."
    )

    return "\n".join(lines) + "\n"


def write_entity_proposal_validation_report(
    *,
    report: EntityValidationReport,
    out_dir: Path,
) -> Path:
    """Write the machine-readable JSON report and human-readable summary."""

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "entity_proposal_validation_report.json"
    summary_path = out_dir / "entity_proposal_validation_summary.txt"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    summary_path.write_text(build_entity_proposal_validation_summary(report), encoding="utf-8")
    return report_path


__all__ = [
    "DEFAULT_DOCUMENT_ID",
    "DEFAULT_PREFERRED_GATE_MINIMUM",
    "ENTITY_VALIDATION_SCHEMA_VERSION",
    "PLAN10_VALIDATED_STATUS",
    "SEMANTIC_MIN_CONFIDENCE",
    "TOOL_NAME",
    "EntityValidationReport",
    "EntityValidationResult",
    "EntityValidationStatus",
    "build_entity_proposal_validation_report",
    "build_entity_proposal_validation_summary",
    "validate_one_backend",
    "write_entity_proposal_validation_report",
]
