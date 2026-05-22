from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from pdf2md.local.groundtruth import (
    DocumentStatus,
    GroundtruthValidationReport,
    build_validation_report,
    discover_corpus_documents,
    inspect_document,
)

CLI = Path("tools/local_groundtruth_validate.py")
FIXTURES = Path("tests/data/local_groundtruth_fixtures")
MINIMAL = FIXTURES / "minimal_valid_corpus"
PARTIAL = FIXTURES / "partial_corpus"
EMPTY = FIXTURES / "empty_corpus"
FIXED_TIMESTAMP = "2026-01-01T00:00:00Z"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("local_groundtruth_validate_test", CLI)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discover_finds_all_documents() -> None:
    assert [path.name for path in discover_corpus_documents(MINIMAL)] == ["simple_doc"]
    assert [path.name for path in discover_corpus_documents(PARTIAL)] == ["incomplete_doc"]
    assert discover_corpus_documents(EMPTY) == []


def test_inspect_ready_document() -> None:
    entry = inspect_document(MINIMAL / "simple_doc")
    assert entry.status == DocumentStatus.READY
    assert entry.required_missing == []
    assert set(entry.required_present) == {"tex", "meta_toml", "docling_json"}


def test_inspect_partial_document() -> None:
    entry = inspect_document(PARTIAL / "incomplete_doc")
    assert entry.status == DocumentStatus.PARTIAL
    assert "docling_json" in entry.required_missing
    assert "tex" in entry.required_present


def test_empty_corpus_is_not_ready() -> None:
    report = build_validation_report(EMPTY, generated_at=FIXED_TIMESTAMP)
    assert report.total_documents == 0
    assert report.corpus_ready is False


def test_report_schema_validates() -> None:
    report = build_validation_report(MINIMAL, generated_at=FIXED_TIMESTAMP)
    restored = GroundtruthValidationReport.model_validate_json(report.model_dump_json())
    assert restored == report
    assert report.schema_name == "pdf2md.LocalGroundtruthValidationReport"
    assert report.corpus_ready is True


def test_report_is_deterministic() -> None:
    first = build_validation_report(MINIMAL, generated_at=FIXED_TIMESTAMP)
    second = build_validation_report(MINIMAL, generated_at=FIXED_TIMESTAMP)
    assert first.model_dump() == second.model_dump()


def test_meta_toml_parsed() -> None:
    entry = inspect_document(MINIMAL / "simple_doc")
    assert entry.metadata["expected_features"] == ["equations", "sections"]
    assert entry.metadata["expected_counts"]["equations"] == 1


def test_optional_artefacts_are_reported() -> None:
    entry = inspect_document(MINIMAL / "simple_doc")
    assert "pdf" in entry.optional_present
    assert "latexml_xml" in entry.optional_present
    assert "docling_groundtruth_meta" in entry.optional_present
    assert "tagged_pdf" in entry.optional_missing
    assert set(entry.optional_present) | set(entry.optional_missing) == {
        "pdf",
        "tagged_pdf",
        "latexml_xml",
        "docling_groundtruth_meta",
    }


def test_cli_nonstrict_exits_zero_on_partial(tmp_path: Path) -> None:
    cli = _load_cli_module()
    rc = cli.main(["--corpus-root", str(PARTIAL), "--out-dir", str(tmp_path / "out")])
    assert rc == 0


def test_cli_strict_exits_one_on_partial(tmp_path: Path) -> None:
    cli = _load_cli_module()
    rc = cli.main(["--corpus-root", str(PARTIAL), "--out-dir", str(tmp_path / "out"), "--strict"])
    assert rc == 1
    assert (tmp_path / "out/groundtruth_validation_report.json").exists()


def test_cli_nonstrict_exits_zero_on_empty(tmp_path: Path) -> None:
    cli = _load_cli_module()
    rc = cli.main(["--corpus-root", str(EMPTY), "--out-dir", str(tmp_path / "out")])
    assert rc == 0


def test_cli_strict_exits_one_on_empty(tmp_path: Path) -> None:
    cli = _load_cli_module()
    rc = cli.main(["--corpus-root", str(EMPTY), "--out-dir", str(tmp_path / "out"), "--strict"])
    assert rc == 1
    assert (tmp_path / "out/groundtruth_validation_report.json").exists()


def test_cli_writes_report_and_summary(tmp_path: Path) -> None:
    cli = _load_cli_module()
    out = tmp_path / "out"
    rc = cli.main(["--corpus-root", str(MINIMAL), "--out-dir", str(out)])
    assert rc == 0
    report_path = out / "groundtruth_validation_report.json"
    summary_path = out / "groundtruth_validation_summary.txt"
    assert report_path.exists()
    assert summary_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "pdf2md.LocalGroundtruthValidationReport"
    assert payload["corpus_ready"] is True


def test_report_json_contract() -> None:
    report = build_validation_report(MINIMAL, generated_at=FIXED_TIMESTAMP)
    payload = json.loads(report.model_dump_json())
    for key in (
        "schema_name",
        "schema_version",
        "generated_at",
        "tool_name",
        "corpus_root",
        "corpus_ready",
        "total_documents",
        "documents_ready",
        "documents_partial",
        "documents_missing_critical",
        "documents",
        "warnings",
        "metadata",
    ):
        assert key in payload
    assert payload["tool_name"] == "local_groundtruth_validate"
    document = payload["documents"][0]
    for key in (
        "document_id",
        "document_path",
        "status",
        "artefacts",
        "required_present",
        "required_missing",
        "optional_present",
        "optional_missing",
        "warnings",
        "metadata",
    ):
        assert key in document
