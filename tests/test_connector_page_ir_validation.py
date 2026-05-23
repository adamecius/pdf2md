"""Plan 10 connector PageExtractionIR validation tests.

These tests do not run real backends. They exercise the validation module and
CLI using fixtures plus custom in-process connector functions for the failure
classes that cannot be reproduced from raw markdown alone (connector_crash and
schema_failed).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from pdf2md.connectors.common import ConnectorResult
from pdf2md.local.connector_validation import (
    ConnectorValidationStatus,
    build_connector_validation_report,
    build_connector_validation_summary,
    validate_one_backend,
    write_connector_validation_report,
)
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import (
    BlockKind,
    ExtractionBlock,
    PageExtractionIR,
    PageSize,
    extraction_id,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "data" / "connector_validation_fixtures"
MINIMAL_BACKEND_DIR = FIXTURES / "minimal_markdown_backend"
MISSING_BACKEND_DIR = FIXTURES / "missing_output_backend"
SCHEMA_FAILURE_BACKEND_DIR = FIXTURES / "schema_failure_backend"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location(
        "validate_connectors_page_ir_cli",
        ROOT / "tools" / "validate_connectors_page_ir.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_connectors_page_ir_cli"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_plan9_report(
    path: Path,
    *,
    entries: list[dict[str, Any]],
    gate_minimum: int = 2,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    successful = sum(1 for e in entries if e.get("status") == "success")
    failed_statuses = {"backend_crash", "output_missing", "timeout"}
    deferred_statuses = {
        "env_not_ready",
        "model_missing",
        "dependency_missing",
        "not_configured",
    }
    failed = sum(1 for e in entries if e.get("status") in failed_statuses)
    deferred = sum(1 for e in entries if e.get("status") in deferred_statuses)
    payload = {
        "schema_name": "pdf2md.BackendSmokeReport",
        "schema_version": "1.0.0",
        "generated_at": "2026-01-01T00:00:00Z",
        "tool_name": "backend_smoke",
        "repo_root": str(ROOT),
        "corpus_root": None,
        "input_pdf": None,
        "gate_minimum": gate_minimum,
        "gate_passed": successful >= gate_minimum,
        "total_backends": len(entries),
        "backends_successful": successful,
        "backends_failed": failed,
        "backends_deferred": deferred,
        "results": entries,
        "warnings": [],
        "metadata": {},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _plan9_entry(
    name: str,
    *,
    status: str,
    output_dir: str | None,
) -> dict[str, Any]:
    return {
        "backend_name": name,
        "configured": True,
        "enabled": True,
        "environment_name": None,
        "command": None,
        "input_pdf": None,
        "output_dir": output_dir,
        "exit_code": 0 if status == "success" else 1,
        "duration_seconds": 0.1,
        "status": status,
        "expected_output_patterns": ["output.md", "manifest.json"],
        "output_files_found": ["output.md"] if status == "success" else [],
        "missing_output_patterns": [] if status == "success" else ["output.md"],
        "stdout_snippet": "",
        "stderr_snippet": "",
        "failure_reason": None if status == "success" else "deferred for test",
        "next_action": "test stub",
        "metadata": {},
    }


def _make_page(
    *,
    backend: str = "test_backend",
    document_id: str = "doc",
    page_no: int = 1,
    block_texts: list[str] | None = None,
    raw_ref: str | None = "output.md",
) -> PageExtractionIR:
    block_texts = block_texts or ["This is a meaningful paragraph of document text."]
    blocks = [
        ExtractionBlock(
            id=extraction_id(backend, document_id, page_no, order),
            backend=backend,
            page_no=page_no,
            kind=BlockKind.PARAGRAPH,
            order=order,
            text=text,
            raw_ref=raw_ref,
        )
        for order, text in enumerate(block_texts)
    ]
    return PageExtractionIR(
        document_id=document_id,
        backend=backend,
        backend_version=None,
        page_no=page_no,
        page_size=PageSize(width=1.0, height=1.0),
        blocks=blocks,
        raw_artifact_ref=raw_ref,
    )


def _empty_entities(backend: str = "test_backend", document_id: str = "doc") -> EntityProposalDocument:
    return EntityProposalDocument(
        document_id=document_id,
        backend=backend,
        backend_version=None,
        page_count=0,
        entities=[],
        relations=[],
        warnings=[],
        metadata={},
    )


def _crashing_connector(**_kwargs: Any) -> ConnectorResult:
    raise RuntimeError("simulated backend connector failure")


class _SchemaFailingPage:
    """Page-like stub whose model_dump returns dict invalid for PageExtractionIR."""

    def model_dump(self) -> dict[str, Any]:
        return {
            "schema_name": "pdf2md.PageExtractionIR",
            "schema_version": "1.0.0",
            "document_id": "",  # min_length=1 violation
            "backend": "",
            "page_no": 0,  # ge=1 violation
            "page_size": {"width": 0.0, "height": 0.0},  # gt=0 violation
            "blocks": [],
            "metadata": {},
        }


def _schema_failing_connector(**_kwargs: Any) -> ConnectorResult:
    return ConnectorResult(
        pages=[_SchemaFailingPage()],  # type: ignore[list-item]
        entities=_empty_entities(),
        warnings=[],
    )


def _noise_connector(**_kwargs: Any) -> ConnectorResult:
    pages = [
        _make_page(
            block_texts=[
                "INFO: log line",
                "/var/log/backend.log",
                "ERROR  another log",
            ],
        )
    ]
    return ConnectorResult(
        pages=pages,
        entities=_empty_entities(),
        warnings=[],
    )


def _entities_corrupted_connector(**_kwargs: Any) -> ConnectorResult:
    """Returns valid pages but an obviously broken entities payload.

    The Plan 10 validator must ignore entities entirely, so this still
    yields ``validated`` status when the pages are valid.
    """

    return ConnectorResult(
        pages=[_make_page()],
        entities="not-an-entity-document",  # type: ignore[arg-type]
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Required tests
# ---------------------------------------------------------------------------


def test_reuses_existing_connector_entrypoint() -> None:
    """The validation module must default to pdf2md.connectors.common.connect_raw_dir."""

    import inspect

    from pdf2md.connectors.common import connect_raw_dir
    from pdf2md.local import connector_validation as cv

    sig = inspect.signature(cv.validate_one_backend)
    assert sig.parameters["connector"].default is connect_raw_dir

    sig2 = inspect.signature(cv.build_connector_validation_report)
    assert sig2.parameters["connector"].default is connect_raw_dir

    result = cv.validate_one_backend(
        backend_name="minimal",
        raw_dir=MINIMAL_BACKEND_DIR,
        plan9_status="success",
    )
    assert result.connector_entrypoint == "pdf2md.connectors.common.connect_raw_dir"


def test_valid_backend_output_produces_page_extraction_ir(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"minimal": MINIMAL_BACKEND_DIR},
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == ConnectorValidationStatus.VALIDATED.value
    assert result.page_count >= 1
    assert result.block_count >= 1
    assert result.has_text is True
    assert result.has_provenance is True
    assert result.semantic_quality_passed is True
    assert result.raw_artefact_references
    assert result.page_extraction_ir_path
    written = Path(result.page_extraction_ir_path)
    assert written.is_file()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["backend"] == "minimal"
    assert payload["page_count"] >= 1


def test_missing_required_output_classification(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"missing": MISSING_BACKEND_DIR},
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == ConnectorValidationStatus.MISSING_REQUIRED_OUTPUT.value
    assert result.semantic_quality_passed is False
    assert any("raw_text_missing" in w or "no_pages_produced" in w for w in result.warnings + result.errors)


def test_connector_crash_classification(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"crash": MINIMAL_BACKEND_DIR},
        connector=_crashing_connector,
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == ConnectorValidationStatus.CONNECTOR_CRASH.value
    assert any("simulated backend connector failure" in e for e in result.errors)
    assert result.semantic_quality_passed is False


def test_schema_failed_classification(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"schema_failed": SCHEMA_FAILURE_BACKEND_DIR},
        connector=_schema_failing_connector,
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == ConnectorValidationStatus.SCHEMA_FAILED.value
    assert result.validation_error_summary is not None
    assert result.semantic_quality_passed is False


def test_deferred_from_plan9_classification(tmp_path: Path) -> None:
    plan9_path = tmp_path / "plan9_report.json"
    _write_plan9_report(
        plan9_path,
        entries=[
            _plan9_entry("deferred_backend", status="env_not_ready", output_dir=None),
        ],
        gate_minimum=1,
    )
    report = build_connector_validation_report(
        plan9_report_path=plan9_path,
        out_dir=tmp_path / "out",
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == ConnectorValidationStatus.DEFERRED_FROM_PLAN_9.value
    assert result.plan9_status == "env_not_ready"
    assert result.semantic_quality_passed is False


def test_preferred_gate_passes_with_two_validated_backends(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={
            "backend_one": MINIMAL_BACKEND_DIR,
            "backend_two": MINIMAL_BACKEND_DIR,
        },
        out_dir=tmp_path,
    )
    assert report.backends_validated == 2
    assert report.preferred_gate_passed is True
    assert report.minimum_gate_passed is True
    assert report.gate_mode == "preferred"
    assert report.human_reduced_gate_required is False


def test_preferred_gate_fails_with_one_validated_backend(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"single": MINIMAL_BACKEND_DIR},
        out_dir=tmp_path,
    )
    assert report.backends_validated == 1
    assert report.preferred_gate_passed is False
    assert report.gate_mode == "preferred"
    assert report.human_reduced_gate_required is False


def test_minimum_gate_passes_with_one_validated_backend(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"single": MINIMAL_BACKEND_DIR},
        out_dir=tmp_path,
    )
    assert report.minimum_gate_passed is True


def test_allow_reduced_gate_sets_human_required_flag(tmp_path: Path) -> None:
    cli = _load_cli_module()
    out_dir = tmp_path / "out"
    exit_code = cli.main(
        [
            "--backend-output",
            f"single={MINIMAL_BACKEND_DIR}",
            "--out-dir",
            str(out_dir),
            "--allow-reduced-gate",
        ]
    )
    assert exit_code == 0
    report_path = out_dir / "connector_validation_report.json"
    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["minimum_gate_passed"] is True
    assert payload["preferred_gate_passed"] is False
    assert payload["human_reduced_gate_required"] is True
    assert payload["gate_mode"] == "reduced"

    # And without --allow-reduced-gate, the CLI exits 1 on the same input.
    out_dir2 = tmp_path / "out2"
    exit_code2 = cli.main(
        [
            "--backend-output",
            f"single={MINIMAL_BACKEND_DIR}",
            "--out-dir",
            str(out_dir2),
        ]
    )
    assert exit_code2 == 1
    payload2 = json.loads((out_dir2 / "connector_validation_report.json").read_text(encoding="utf-8"))
    assert payload2["human_reduced_gate_required"] is False


def test_semantic_quality_passes_for_nonempty_document_text(tmp_path: Path) -> None:
    result = validate_one_backend(
        backend_name="minimal",
        raw_dir=MINIMAL_BACKEND_DIR,
        plan9_status="success",
        out_dir=tmp_path,
    )
    assert result.status == ConnectorValidationStatus.VALIDATED.value
    assert result.semantic_quality_passed is True
    assert result.has_text is True


def test_semantic_quality_fails_for_empty_or_noise_ir(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"noisy": MINIMAL_BACKEND_DIR},
        connector=_noise_connector,
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == ConnectorValidationStatus.VALIDATED.value
    assert result.semantic_quality_passed is False
    assert any("semantic_" in w for w in result.warnings)
    # Gates depend on semantic quality, so a single noisy backend cannot pass either gate.
    assert report.preferred_gate_passed is False
    assert report.minimum_gate_passed is False


def test_entity_proposals_are_ignored_for_plan10_acceptance(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"entities_corrupted": MINIMAL_BACKEND_DIR},
        connector=_entities_corrupted_connector,
        out_dir=tmp_path,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == ConnectorValidationStatus.VALIDATED.value
    assert result.semantic_quality_passed is True
    payload = json.loads(result.model_dump_json())
    # Pass/fail must not surface EntityProposalDocument-derived fields.
    for forbidden in ("entity_count", "entities", "entity_proposal_status"):
        assert forbidden not in payload
    summary = build_connector_validation_summary(report)
    assert "EntityProposalDocument validation is deferred to Plan 11" in summary


def test_report_json_contract(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"minimal": MINIMAL_BACKEND_DIR},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    payload = json.loads(report.model_dump_json())
    required_top = {
        "schema_name",
        "schema_version",
        "generated_at",
        "tool_name",
        "plan9_report_path",
        "gate_mode",
        "preferred_gate_minimum",
        "preferred_gate_passed",
        "minimum_gate_passed",
        "human_reduced_gate_required",
        "total_backends_considered",
        "backends_validated",
        "backends_failed",
        "backends_deferred",
        "results",
        "warnings",
        "metadata",
    }
    assert required_top.issubset(payload.keys())
    assert payload["schema_name"] == "pdf2md.ConnectorPageExtractionIRValidationReport"
    assert payload["schema_version"] == "1.0.0"
    assert payload["tool_name"] == "validate_connectors_page_ir"

    required_entry = {
        "backend_name",
        "plan9_status",
        "raw_output_dir",
        "connector_entrypoint",
        "status",
        "page_count",
        "block_count",
        "block_kind_counts",
        "has_text",
        "has_bboxes",
        "has_provenance",
        "raw_artefact_references",
        "semantic_quality_passed",
        "warnings",
        "errors",
        "validation_error_summary",
        "next_action",
        "metadata",
    }
    assert payload["results"], "report should include backend results"
    for entry in payload["results"]:
        assert required_entry.issubset(entry.keys())
        assert entry["status"] in {s.value for s in ConnectorValidationStatus}


def test_summary_is_written(tmp_path: Path) -> None:
    report = build_connector_validation_report(
        backend_outputs={"minimal": MINIMAL_BACKEND_DIR},
        preferred_gate_minimum=1,
        out_dir=tmp_path,
    )
    write_connector_validation_report(report=report, out_dir=tmp_path)
    summary_path = tmp_path / "connector_validation_summary.txt"
    report_path = tmp_path / "connector_validation_report.json"
    assert summary_path.is_file()
    assert report_path.is_file()
    text = summary_path.read_text(encoding="utf-8")
    assert "Plan 10" in text
    assert "validated backends" in text
    assert "Plan 11 hand-off" in text
    assert "EntityProposalDocument validation is deferred to Plan 11" in text
