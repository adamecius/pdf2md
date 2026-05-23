"""Plan 11 EntityProposalDocument validation tests.

These tests do not run real backends. They exercise the validation module
and CLI using fixture JSON files plus a small custom-connector helper for the
connector_crash class.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from pdf2md.connectors.common import ConnectorResult
from pdf2md.local.entity_proposal_validation import (
    EntityValidationStatus,
    build_entity_proposal_validation_report,
    build_entity_proposal_validation_summary,
    validate_one_backend,
    write_entity_proposal_validation_report,
)
from pdf2md.models.entities import (
    ConfidenceSource,
    EntityEvidence,
    EntityProposal,
    EntityProposalDocument,
    EntityType,
    EvidenceKind,
    RelationProposal,
    RelationType,
    entity_id,
    relation_id,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "data" / "entity_proposal_validation_fixtures"
VALID = FIXTURES / "valid_entities"
NO_ENTITIES = FIXTURES / "no_entities"
SCHEMA_FAILURE = FIXTURES / "schema_failure"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location(
        "validate_entity_proposals_cli",
        ROOT / "tools" / "validate_entity_proposals.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_entity_proposals_cli"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_plan10_report(
    path: Path,
    *,
    entries: list[dict[str, Any]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    validated = sum(1 for e in entries if e.get("status") == "validated")
    deferred = sum(1 for e in entries if e.get("status") == "deferred_from_plan_9")
    failed = sum(
        1
        for e in entries
        if e.get("status") in {"connector_crash", "schema_failed", "missing_required_output"}
    )
    payload = {
        "schema_name": "pdf2md.ConnectorPageExtractionIRValidationReport",
        "schema_version": "1.0.0",
        "generated_at": "2026-01-01T00:00:00Z",
        "tool_name": "validate_connectors_page_ir",
        "plan9_report_path": None,
        "gate_mode": "preferred",
        "preferred_gate_minimum": 2,
        "preferred_gate_passed": validated >= 2,
        "minimum_gate_passed": validated >= 1,
        "human_reduced_gate_required": False,
        "total_backends_considered": len(entries),
        "backends_validated": validated,
        "backends_failed": failed,
        "backends_deferred": deferred,
        "results": entries,
        "warnings": [],
        "metadata": {},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _plan10_entry(
    name: str,
    *,
    status: str,
    page_ir: str | None = None,
    raw_dir: str | None = None,
) -> dict[str, Any]:
    return {
        "backend_name": name,
        "plan9_status": "success" if status == "validated" else None,
        "raw_output_dir": raw_dir,
        "connector_entrypoint": "pdf2md.connectors.common.connect_raw_dir",
        "status": status,
        "page_count": 2 if status == "validated" else 0,
        "block_count": 4 if status == "validated" else 0,
        "block_kind_counts": {"paragraph": 4} if status == "validated" else {},
        "has_text": status == "validated",
        "has_bboxes": False,
        "has_provenance": status == "validated",
        "raw_artefact_references": ["output.md"] if status == "validated" else [],
        "semantic_quality_passed": status == "validated",
        "warnings": [],
        "errors": [],
        "validation_error_summary": None,
        "page_extraction_ir_path": page_ir,
        "next_action": "test stub",
        "metadata": {},
    }


def _make_entity(
    *,
    backend: str = "backend_a",
    document_id: str = "doc",
    entity_type: EntityType = EntityType.SECTION,
    index: int = 1,
    canonical_text: str = "Section heading",
    page_no: int = 1,
    confidence: float = 0.7,
) -> EntityProposal:
    block_id = f"{backend}:{document_id}:p{page_no}:b0"
    return EntityProposal(
        id=entity_id(backend, document_id, entity_type, index),
        entity_type=entity_type,
        canonical_text=canonical_text,
        page_no=page_no,
        block_ids=[block_id],
        confidence=confidence,
        confidence_source=ConfidenceSource.HEURISTIC,
        evidence=[
            EntityEvidence(
                kind=EvidenceKind.BLOCK_TEXT,
                page_no=page_no,
                source_block_id=block_id,
                raw_ref="output.md",
                text=canonical_text,
                weight=1.0,
                reason="heading_section_detector",
            )
        ],
        calibration_key=f"{backend}:section:heading_section_detector",
    )


def _make_relation(
    *,
    backend: str = "backend_a",
    document_id: str = "doc",
    source: EntityProposal,
    target: EntityProposal,
    index: int = 1,
    relation_type: RelationType = RelationType.SEQUENCE_NEXT,
) -> RelationProposal:
    return RelationProposal(
        id=relation_id(backend, document_id, index),
        relation_type=relation_type,
        source_entity_id=source.id,
        target_entity_id=target.id,
        confidence=0.55,
        confidence_source=ConfidenceSource.HEURISTIC,
        evidence=[
            EntityEvidence(
                kind=EvidenceKind.DOCUMENT_CONTEXT,
                page_no=source.page_no,
                source_block_id=source.block_ids[0] if source.block_ids else None,
                weight=1.0,
                reason="adjacent sections",
            )
        ],
    )


def _document(
    *,
    backend: str = "backend_a",
    document_id: str = "doc",
    entities: list[EntityProposal] | None = None,
    relations: list[RelationProposal] | None = None,
    page_count: int = 2,
) -> EntityProposalDocument:
    if entities is None:
        e1 = _make_entity(backend=backend, document_id=document_id, index=1, canonical_text="Introduction")
        e2 = _make_entity(
            backend=backend, document_id=document_id, index=2, canonical_text="Methods", page_no=2
        )
        entities = [e1, e2]
        if relations is None:
            relations = [
                _make_relation(
                    backend=backend, document_id=document_id, source=e1, target=e2, index=1
                )
            ]
    return EntityProposalDocument(
        document_id=document_id,
        backend=backend,
        backend_version=None,
        page_count=page_count,
        entities=entities,
        relations=relations or [],
        warnings=[],
        metadata={"connector": "markdown_fallback"},
    )


def _crashing_connector(**_kwargs: Any) -> ConnectorResult:
    raise RuntimeError("simulated entity connector failure")


def _empty_entity_document_connector(backend: str, document_id: str) -> Any:
    def _connector(**_kwargs: Any) -> ConnectorResult:
        from pdf2md.models.ir import PageExtractionIR, PageSize

        page = PageExtractionIR(
            document_id=document_id,
            backend=backend,
            backend_version=None,
            page_no=1,
            page_size=PageSize(width=1.0, height=1.0),
            blocks=[],
            raw_artifact_ref="output.md",
        )
        empty_doc = EntityProposalDocument(
            document_id=document_id,
            backend=backend,
            backend_version=None,
            page_count=1,
            entities=[],
            relations=[],
        )
        return ConnectorResult(pages=[page], entities=empty_doc, warnings=[])

    return _connector


# ---------------------------------------------------------------------------
# Required tests
# ---------------------------------------------------------------------------


def test_valid_entity_document_classifies_validated(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"minimal": VALID / "entities.json"},
        backend_page_ir={"minimal": VALID / "page_extraction_ir.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == EntityValidationStatus.VALIDATED.value
    assert result.entity_count == 2
    assert result.relation_count == 1
    assert result.has_evidence is True
    assert result.has_relations is True
    assert result.has_provenance is True
    assert result.has_confidence_sources is True
    assert result.semantic_plausibility_passed is True
    assert result.entity_output_path
    written = Path(result.entity_output_path)
    assert written.is_file()


def test_empty_entity_document_classifies_no_entities_produced(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"empty_backend": NO_ENTITIES / "entities.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == EntityValidationStatus.NO_ENTITIES_PRODUCED.value
    assert result.entity_count == 0
    assert result.relation_count == 0
    assert result.semantic_plausibility_passed is False
    assert report.backends_no_entities == 1
    assert report.backends_validated == 0


def test_invalid_entity_document_classifies_schema_failed(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"broken_backend": SCHEMA_FAILURE / "entities.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == EntityValidationStatus.SCHEMA_FAILED.value
    assert result.validation_error_summary is not None
    assert "target_entity_id" in result.validation_error_summary or "relation" in (
        result.validation_error_summary or ""
    )
    assert result.semantic_plausibility_passed is False


def test_connector_crash_classification(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "output.md").write_text("# heading\n\nbody\n", encoding="utf-8")
    report = build_entity_proposal_validation_report(
        backend_raw_dirs={"crash_backend": raw_dir},
        connector=_crashing_connector,
        preferred_gate_minimum=1,
        out_dir=tmp_path / "out",
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == EntityValidationStatus.CONNECTOR_CRASH.value
    assert any("simulated entity connector failure" in e for e in result.errors)
    assert result.semantic_plausibility_passed is False


def test_deferred_from_plan10_classification(tmp_path: Path) -> None:
    plan10_path = tmp_path / "plan10_report.json"
    _write_plan10_report(
        plan10_path,
        entries=[
            _plan10_entry("deferred_backend", status="deferred_from_plan_9"),
        ],
    )
    report = build_entity_proposal_validation_report(
        plan10_report_path=plan10_path,
        preferred_gate_minimum=1,
        out_dir=tmp_path / "out",
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == EntityValidationStatus.DEFERRED_FROM_PLAN_10.value
    assert result.plan10_status == "deferred_from_plan_9"
    assert result.semantic_plausibility_passed is False
    assert report.backends_deferred == 1


def test_entity_type_counts_are_reported(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"minimal": VALID / "entities.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    result = report.results[0]
    assert result.entity_type_counts.get("section") == 2


def test_relation_type_counts_are_reported(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"minimal": VALID / "entities.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    result = report.results[0]
    assert result.relation_type_counts.get("sequence_next") == 1


def test_relation_endpoints_are_validated_by_schema(tmp_path: Path) -> None:
    # The schema_failure fixture has a relation pointing at a non-existent target.
    # The validator must classify this as schema_failed via the document-level validator.
    report = build_entity_proposal_validation_report(
        backend_entities={"broken_backend": SCHEMA_FAILURE / "entities.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    result = report.results[0]
    assert result.status == EntityValidationStatus.SCHEMA_FAILED.value
    summary = result.validation_error_summary or ""
    assert "target_entity_id" in summary or "exist in entities" in summary


def test_evidence_references_are_validated_by_schema(tmp_path: Path) -> None:
    # Build an in-memory entities.json whose evidence references an invalid block id.
    payload = json.loads((VALID / "entities.json").read_text(encoding="utf-8"))
    payload["entities"][0]["evidence"][0]["source_block_id"] = "not-a-valid-block-id"
    target = tmp_path / "entities.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    report = build_entity_proposal_validation_report(
        backend_entities={"minimal": target},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    result = report.results[0]
    assert result.status == EntityValidationStatus.SCHEMA_FAILED.value
    summary = result.validation_error_summary or ""
    assert "source_block_id" in summary or "extraction block id" in summary


def test_preferred_gate_passes_with_two_validated_backends(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={
            "backend_one": VALID / "entities.json",
            "backend_two": VALID / "entities.json",
        },
        out_dir=tmp_path,
    )
    assert report.backends_validated == 2
    assert report.preferred_gate_passed is True
    assert report.minimum_gate_passed is True
    assert report.gate_mode == "preferred"
    assert report.human_reduced_gate_required is False


def test_preferred_gate_fails_with_one_validated_backend(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"single": VALID / "entities.json"},
        out_dir=tmp_path,
    )
    assert report.backends_validated == 1
    assert report.preferred_gate_passed is False
    assert report.gate_mode == "preferred"


def test_minimum_gate_passes_with_one_validated_backend(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"single": VALID / "entities.json"},
        out_dir=tmp_path,
    )
    assert report.minimum_gate_passed is True


def test_no_entities_produced_does_not_count_toward_validated_gate(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={
            "empty_one": NO_ENTITIES / "entities.json",
            "empty_two": NO_ENTITIES / "entities.json",
        },
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    assert report.backends_no_entities == 2
    assert report.backends_validated == 0
    assert report.preferred_gate_passed is False
    assert report.minimum_gate_passed is False


def test_allow_reduced_gate_sets_human_required_flag(tmp_path: Path) -> None:
    cli = _load_cli_module()
    out_dir = tmp_path / "out"
    exit_code = cli.main(
        [
            "--backend-entities",
            f"single={VALID / 'entities.json'}",
            "--out-dir",
            str(out_dir),
            "--allow-reduced-gate",
        ]
    )
    assert exit_code == 0
    payload = json.loads((out_dir / "entity_proposal_validation_report.json").read_text(encoding="utf-8"))
    assert payload["minimum_gate_passed"] is True
    assert payload["preferred_gate_passed"] is False
    assert payload["human_reduced_gate_required"] is True
    assert payload["gate_mode"] == "reduced"

    out_dir2 = tmp_path / "out2"
    exit_code2 = cli.main(
        [
            "--backend-entities",
            f"single={VALID / 'entities.json'}",
            "--out-dir",
            str(out_dir2),
        ]
    )
    assert exit_code2 == 1


def test_semantic_plausibility_passes_for_plausible_entities(tmp_path: Path) -> None:
    result = validate_one_backend(
        backend_name="minimal",
        entities_path=VALID / "entities.json",
        plan10_status="validated",
        out_dir=tmp_path,
    )
    assert result.status == EntityValidationStatus.VALIDATED.value
    assert result.semantic_plausibility_passed is True


def test_semantic_plausibility_fails_for_noise_or_empty_entities(tmp_path: Path) -> None:
    # Build an entities document where every entity is UNKNOWN with low confidence and noise text.
    backend = "noisy"
    document_id = "doc"
    noisy_entities: list[EntityProposal] = []
    for i in range(1, 3):
        block_id = f"{backend}:{document_id}:p1:b{i - 1}"
        noisy_entities.append(
            EntityProposal(
                id=entity_id(backend, document_id, EntityType.UNKNOWN, i),
                entity_type=EntityType.UNKNOWN,
                canonical_text="INFO:",
                page_no=1,
                block_ids=[block_id],
                confidence=0.05,
                confidence_source=ConfidenceSource.HEURISTIC,
                evidence=[
                    EntityEvidence(
                        kind=EvidenceKind.BLOCK_TEXT,
                        page_no=1,
                        source_block_id=block_id,
                        text="INFO:",
                        weight=1.0,
                        reason="noisy_detector",
                    )
                ],
            )
        )
    document = EntityProposalDocument(
        document_id=document_id,
        backend=backend,
        backend_version=None,
        page_count=1,
        entities=noisy_entities,
        relations=[],
    )
    entities_path = tmp_path / "entities.json"
    entities_path.write_text(document.model_dump_json(), encoding="utf-8")
    result = validate_one_backend(
        backend_name=backend,
        entities_path=entities_path,
        plan10_status="validated",
        out_dir=tmp_path / "out",
    )
    assert result.status == EntityValidationStatus.VALIDATED.value
    assert result.semantic_plausibility_passed is False
    assert any("semantic_" in w for w in result.warnings)


def test_report_json_contract(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"minimal": VALID / "entities.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    payload = json.loads(report.model_dump_json())
    required_top = {
        "schema_name",
        "schema_version",
        "generated_at",
        "tool_name",
        "plan10_report_path",
        "gate_mode",
        "preferred_gate_minimum",
        "preferred_gate_passed",
        "minimum_gate_passed",
        "human_reduced_gate_required",
        "total_backends_considered",
        "backends_validated",
        "backends_no_entities",
        "backends_failed",
        "backends_deferred",
        "results",
        "warnings",
        "metadata",
    }
    assert required_top.issubset(payload.keys())
    assert payload["schema_name"] == "pdf2md.EntityProposalDocumentValidationReport"
    assert payload["schema_version"] == "1.0.0"
    assert payload["tool_name"] == "validate_entity_proposals"

    required_entry = {
        "backend_name",
        "plan10_status",
        "page_extraction_ir_path",
        "entity_document_path",
        "connector_entrypoint",
        "status",
        "entity_count",
        "entity_type_counts",
        "relation_count",
        "relation_type_counts",
        "has_evidence",
        "has_relations",
        "has_provenance",
        "has_confidence_sources",
        "semantic_plausibility_passed",
        "warnings",
        "errors",
        "validation_error_summary",
        "next_action",
        "metadata",
    }
    assert payload["results"]
    for entry in payload["results"]:
        assert required_entry.issubset(entry.keys())
        assert entry["status"] in {s.value for s in EntityValidationStatus}


def test_summary_is_written(tmp_path: Path) -> None:
    report = build_entity_proposal_validation_report(
        backend_entities={"minimal": VALID / "entities.json"},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    write_entity_proposal_validation_report(report=report, out_dir=tmp_path)
    summary_path = tmp_path / "entity_proposal_validation_summary.txt"
    report_path = tmp_path / "entity_proposal_validation_report.json"
    assert summary_path.is_file()
    assert report_path.is_file()
    text = summary_path.read_text(encoding="utf-8")
    assert "Plan 11" in text
    assert "Plan 12 hand-off" in text
    assert "Real calibration prior generation is deferred to Plan 12" in text
