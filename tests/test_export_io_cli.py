from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pdf2md.export.docling import DoclingExportSettings, validate_docling_like_document
from pdf2md.export.io import build_export_run, load_export_inputs, write_export_outputs
from pdf2md.export.markdown import MarkdownExportSettings
from pdf2md.export.rag import RagExportSettings
from pdf2md.models.export import ExportManifestDocument, RagChunkDocument

FIX = Path("tests/data/export_fixtures/simple_document")


def test_load_export_inputs_reads_both_and_missing_consensus_warns():
    loaded = load_export_inputs(linked_structure_path=FIX / "linked_structure.json", consensus_ir_path=FIX / "consensus_ir.json")
    assert loaded.linked.document_id == "doc-simple"
    assert loaded.consensus is not None
    missing = load_export_inputs(linked_structure_path=FIX / "linked_structure.json")
    assert missing.consensus is None
    assert missing.warnings == ["consensus_ir_missing"]


def test_strict_invalid_consensus_raises(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    with pytest.raises(Exception):
        load_export_inputs(linked_structure_path=FIX / "linked_structure.json", consensus_ir_path=bad, strict=True)
    loaded = load_export_inputs(linked_structure_path=FIX / "linked_structure.json", consensus_ir_path=bad, strict=False)
    assert loaded.warnings == ["invalid_consensus_ir"]


def test_write_export_outputs_writes_valid_files(tmp_path: Path):
    loaded = load_export_inputs(linked_structure_path=FIX / "linked_structure.json", consensus_ir_path=FIX / "consensus_ir.json")
    result = build_export_run(linked=loaded.linked, consensus=loaded.consensus, source_linked_structure=str(FIX / "linked_structure.json"), source_consensus_ir=str(FIX / "consensus_ir.json"), source_pdf=None, docling_settings=DoclingExportSettings(), rag_settings=RagExportSettings(), markdown_settings=MarkdownExportSettings())
    write_export_outputs(result=result, out_dir=tmp_path)
    manifest = ExportManifestDocument.model_validate_json((tmp_path / "export_manifest.json").read_text())
    rag = RagChunkDocument.model_validate_json(next((tmp_path / "rag").glob("*.rag_chunks.json")).read_text())
    doc = json.loads(next((tmp_path / "docling").glob("*.docling.json")).read_text())
    assert manifest.artefacts[0].sha256
    assert rag.chunks
    assert validate_docling_like_document(doc) == []
    report = json.loads((tmp_path / "reports" / "export_report.json").read_text())
    assert report["docling"]["text_count"] > 0


def test_cli_help_and_smoke(tmp_path: Path):
    help_result = subprocess.run([sys.executable, "tools/export_linked_docling.py", "--help"], text=True, capture_output=True)
    assert help_result.returncode == 0
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, "tools/export_linked_docling.py", "--linked-structure", str(FIX / "linked_structure.json"), "--consensus-ir", str(FIX / "consensus_ir.json"), "--out-dir", str(out)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert next((out / "docling").glob("*.docling.json")).exists()
    assert next((out / "rag").glob("*.rag_chunks.json")).exists()
    assert next((out / "markdown").glob("*.preview.md")).exists()
    ExportManifestDocument.model_validate_json((out / "export_manifest.json").read_text())


def test_cli_no_rag_no_markdown_and_strict_failure(tmp_path: Path):
    out = tmp_path / "skip"
    result = subprocess.run([sys.executable, "tools/export_linked_docling.py", "--linked-structure", str(FIX / "linked_structure.json"), "--consensus-ir", str(FIX / "consensus_ir.json"), "--out-dir", str(out), "--no-rag", "--no-markdown"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert not (out / "rag" / "doc-simple.rag_chunks.json").exists()
    assert not (out / "markdown" / "doc-simple.preview.md").exists()
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    strict = subprocess.run([sys.executable, "tools/export_linked_docling.py", "--linked-structure", str(FIX / "linked_structure.json"), "--consensus-ir", str(bad), "--out-dir", str(tmp_path / "badout"), "--strict"], text=True, capture_output=True)
    assert strict.returncode == 1

@pytest.mark.parametrize("artefact_name", [
    "docling/doc-simple.docling.json",
    "rag/doc-simple.rag_chunks.json",
    "markdown/doc-simple.preview.md",
    "reports/export_report.json",
])
def test_manifest_lists_expected_artefacts(tmp_path: Path, artefact_name: str):
    loaded = load_export_inputs(linked_structure_path=FIX / "linked_structure.json", consensus_ir_path=FIX / "consensus_ir.json")
    result = build_export_run(linked=loaded.linked, consensus=loaded.consensus, source_linked_structure=str(FIX / "linked_structure.json"), source_consensus_ir=str(FIX / "consensus_ir.json"), source_pdf=None, docling_settings=DoclingExportSettings(), rag_settings=RagExportSettings(), markdown_settings=MarkdownExportSettings())
    write_export_outputs(result=result, out_dir=tmp_path)
    manifest = ExportManifestDocument.model_validate_json((tmp_path / "export_manifest.json").read_text())
    assert artefact_name in [a.path for a in manifest.artefacts]


@pytest.mark.parametrize("args", [
    ["--no-rag"],
    ["--no-markdown"],
    ["--verbose"],
    ["--max-chars", "100"],
    ["--include-unresolved"],
    ["--source-pdf", "sample.pdf"],
    [],
])
def test_cli_option_variants_succeed(tmp_path: Path, args: list[str]):
    out = tmp_path / ("out" + str(len(args)) + "_" + "_".join(a.strip('-') for a in args))
    result = subprocess.run([sys.executable, "tools/export_linked_docling.py", "--linked-structure", str(FIX / "linked_structure.json"), "--consensus-ir", str(FIX / "consensus_ir.json"), "--out-dir", str(out), *args], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    ExportManifestDocument.model_validate_json((out / "export_manifest.json").read_text())


# ---------------------------------------------------------------------------
# Plan 15 hardening tests
# ---------------------------------------------------------------------------

from pdf2md.export.reporting import (
    INSPECTION_STATUSES,
    build_export_report,
)


def _build_run(name: str = "simple_document"):
    fix = Path("tests/data/export_fixtures") / name
    loaded = load_export_inputs(
        linked_structure_path=fix / "linked_structure.json",
        consensus_ir_path=fix / "consensus_ir.json",
    )
    result = build_export_run(
        linked=loaded.linked,
        consensus=loaded.consensus,
        source_linked_structure=str(fix / "linked_structure.json"),
        source_consensus_ir=str(fix / "consensus_ir.json"),
        source_pdf=None,
        docling_settings=DoclingExportSettings(),
        rag_settings=RagExportSettings(),
        markdown_settings=MarkdownExportSettings(),
    )
    return result, loaded


class TestPlan15ReportHardening:
    def test_report_contains_plan16_readiness(self):
        result, loaded = _build_run("simple_document")
        report = build_export_report(
            document_id=loaded.linked.document_id,
            docling=result.docling,
            rag_chunks=result.rag_chunks,
            markdown=result.markdown,
            warnings=list(result.warnings),
        )
        for field in (
            "document_id",
            "docling_text_count",
            "docling_table_count",
            "docling_picture_count",
            "docling_group_count",
            "docling_page_count",
            "docling_warning_count",
            "rag_chunk_count",
            "markdown_char_count",
            "consensus_report_used",
            "source_pdf_supplied",
            "ground_truth_supplied",
            "docling_core_validation_available",
            "warning_count",
            "inspection_status",
            "end_to_end_orchestration_handed_off_by",
        ):
            assert field in report["plan16_readiness"], field
        assert report["plan16_readiness"]["end_to_end_orchestration_handed_off_by"] == "plan_16"

    def test_default_inspection_status_is_diagnostic_only(self):
        result, loaded = _build_run("simple_document")
        report = build_export_report(
            document_id=loaded.linked.document_id,
            docling=result.docling,
            rag_chunks=result.rag_chunks,
            markdown=result.markdown,
            warnings=list(result.warnings),
        )
        assert report["inspection_status"] == "diagnostic_only"
        assert report["inspection_notes"] == []
        assert report["ground_truth_ref"] is None

    def test_report_accepts_all_inspection_statuses(self):
        result, loaded = _build_run("simple_document")
        for status in INSPECTION_STATUSES:
            report = build_export_report(
                document_id=loaded.linked.document_id,
                docling=result.docling,
                rag_chunks=result.rag_chunks,
                markdown=result.markdown,
                warnings=list(result.warnings),
                inspection_status=status,
            )
            assert report["inspection_status"] == status

    def test_report_rejects_unknown_inspection_status(self):
        result, loaded = _build_run("simple_document")
        with pytest.raises(ValueError):
            build_export_report(
                document_id=loaded.linked.document_id,
                docling=result.docling,
                rag_chunks=result.rag_chunks,
                markdown=result.markdown,
                warnings=list(result.warnings),
                inspection_status="totally_made_up",
            )

    def test_report_records_ground_truth_and_notes(self):
        result, loaded = _build_run("simple_document")
        report = build_export_report(
            document_id=loaded.linked.document_id,
            docling=result.docling,
            rag_chunks=result.rag_chunks,
            markdown=result.markdown,
            warnings=list(result.warnings),
            inspection_status="ready_with_warnings",
            inspection_notes=["docling_core unavailable on this host"],
            source_pdf="/path/to/some.pdf",
            ground_truth_ref="groundtruth/corpus/latex/doc/expected.docling.json",
        )
        assert report["ground_truth_ref"].endswith("expected.docling.json")
        assert "docling_core unavailable on this host" in report["inspection_notes"]
        assert report["plan16_readiness"]["source_pdf_supplied"] is True
        assert report["plan16_readiness"]["ground_truth_supplied"] is True

    def test_report_detects_docling_core_unavailable_in_warnings(self):
        result, loaded = _build_run("simple_document")
        warnings = list(result.warnings) + ["docling_core_unavailable"]
        report = build_export_report(
            document_id=loaded.linked.document_id,
            docling=result.docling,
            rag_chunks=result.rag_chunks,
            markdown=result.markdown,
            warnings=warnings,
        )
        assert report["plan16_readiness"]["docling_core_validation_available"] is False


class TestPlan15CLI:
    SCRIPT = "tools/export_linked_docling.py"
    FIX = Path("tests/data/export_fixtures/simple_document")

    def _run(self, tmp_path: Path, extra: list[str] | None = None):
        out = tmp_path / "out"
        return subprocess.run(
            [
                sys.executable,
                self.SCRIPT,
                "--linked-structure",
                str(self.FIX / "linked_structure.json"),
                "--consensus-ir",
                str(self.FIX / "consensus_ir.json"),
                "--out-dir",
                str(out),
                *(extra or []),
            ],
            text=True,
            capture_output=True,
        ), out

    def test_cli_default_inspection_status_is_diagnostic_only(self, tmp_path: Path):
        proc, out = self._run(tmp_path)
        assert proc.returncode == 0, proc.stderr
        report = json.loads((out / "reports" / "export_report.json").read_text())
        assert report["inspection_status"] == "diagnostic_only"
        assert report["ground_truth_ref"] is None

    def test_cli_accepts_inspection_status_and_notes(self, tmp_path: Path):
        proc, out = self._run(
            tmp_path,
            extra=[
                "--inspection-status",
                "ready_for_plan_16",
                "--inspection-note",
                "synthetic; clean export",
                "--ground-truth",
                "groundtruth/corpus/latex/x.docling.json",
            ],
        )
        assert proc.returncode == 0, proc.stderr
        report = json.loads((out / "reports" / "export_report.json").read_text())
        assert report["inspection_status"] == "ready_for_plan_16"
        assert "synthetic; clean export" in report["inspection_notes"]
        assert report["ground_truth_ref"].endswith("x.docling.json")
        assert report["plan16_readiness"]["ground_truth_supplied"] is True

    def test_cli_rejects_unknown_inspection_status(self, tmp_path: Path):
        proc, _ = self._run(tmp_path, extra=["--inspection-status", "totally_made_up"])
        assert proc.returncode != 0

    def test_cli_verbose_prints_plan16_readiness_summary(self, tmp_path: Path):
        proc, _ = self._run(tmp_path, extra=["--verbose"])
        assert proc.returncode == 0, proc.stderr
        assert "end_to_end_orchestration_handed_off_by: plan_16" in proc.stdout
