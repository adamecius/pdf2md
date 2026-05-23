import json
import subprocess
import sys
from pathlib import Path

import pytest

from pdf2md.linking.builder import build_linked_structure
from pdf2md.linking.io import load_linker_inputs, write_linker_outputs
from pdf2md.models.linked import LinkedStructure

FIX=Path('tests/data/linking_fixtures')
SCRIPT=Path('tools/build_linked_structure.py')


def test_load_linker_inputs_reads_consensus_entities_priors():
    base=FIX/'simple_document'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json',consensus_report_path=base/'consensus_report.json',entities_root=base/'entities',priors_root=base/'priors')
    assert loaded.consensus.document_id == 'linkdoc'
    assert set(loaded.entities_by_backend) == {'mineru','paddleocr'}
    assert set(loaded.priors_by_backend) == {'mineru','paddleocr'}


def test_lenient_missing_entities_prior_roots_warn():
    base=FIX/'simple_document'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json')
    assert 'entities_root_missing' in loaded.warnings
    assert 'priors_root_missing' in loaded.warnings


def test_strict_invalid_optional_input_raises(tmp_path):
    base=FIX/'simple_document'
    bad=tmp_path/'bad.json'; bad.write_text('[]')
    with pytest.raises(ValueError):
        load_linker_inputs(consensus_ir_path=base/'consensus_ir.json',consensus_report_path=bad,strict=True)


def test_write_linker_outputs_writes_both_files(tmp_path):
    base=FIX/'simple_document'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json',consensus_report_path=base/'consensus_report.json',entities_root=base/'entities',priors_root=base/'priors')
    result=build_linked_structure(consensus=loaded.consensus,entities_by_backend=loaded.entities_by_backend,priors_by_backend=loaded.priors_by_backend,consensus_report=loaded.consensus_report)
    write_linker_outputs(result=result,out_dir=tmp_path)
    assert (tmp_path/'linked_structure.json').exists()
    assert (tmp_path/'reports'/'linking_report.json').exists()


def test_cli_help_exits_zero():
    proc=subprocess.run([sys.executable,str(SCRIPT),'--help'],text=True,capture_output=True)
    assert proc.returncode == 0
    assert '--consensus-ir' in proc.stdout


def run_cli(tmp_path, fixture='simple_document', optional=True):
    base=FIX/fixture
    cmd=[sys.executable,str(SCRIPT),'--consensus-ir',str(base/'consensus_ir.json'),'--out-dir',str(tmp_path)]
    if optional:
        cmd += ['--consensus-report',str(base/'consensus_report.json'),'--entities-root',str(base/'entities'),'--priors-root',str(base/'priors')]
    return subprocess.run(cmd,text=True,capture_output=True)


def test_cli_writes_valid_linked_structure(tmp_path):
    proc=run_cli(tmp_path)
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert linked.nodes


def test_cli_unresolved_fixture_writes_conflict(tmp_path):
    proc=run_cli(tmp_path,'unresolved_ambiguity')
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert linked.conflicts


def test_cli_missing_optional_inputs_succeeds_leniently(tmp_path):
    proc=run_cli(tmp_path,optional=False)
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert 'entities_root_missing' in linked.warnings


def test_cli_strict_bad_consensus_fails(tmp_path):
    bad=tmp_path/'bad.json'; bad.write_text('{}')
    proc=subprocess.run([sys.executable,str(SCRIPT),'--consensus-ir',str(bad),'--out-dir',str(tmp_path),'--strict'],text=True,capture_output=True)
    assert proc.returncode == 1


def test_cli_report_includes_lenient_input_warnings(tmp_path):
    proc=run_cli(tmp_path,optional=False)
    assert proc.returncode == 0, proc.stderr
    report=json.loads((tmp_path/'reports'/'linking_report.json').read_text())
    assert 'entities_root_missing' in report['warnings']


def test_strict_missing_explicit_entities_root_raises(tmp_path):
    base=FIX/'simple_document'
    missing=tmp_path/'missing_entities'
    with pytest.raises(ValueError):
        load_linker_inputs(consensus_ir_path=base/'consensus_ir.json', entities_root=missing, strict=True)


def test_cli_low_confidence_threshold_option_is_applied(tmp_path):
    base=FIX/'simple_document'
    proc=subprocess.run([
        sys.executable,str(SCRIPT),'--consensus-ir',str(base/'consensus_ir.json'),'--consensus-report',str(base/'consensus_report.json'),
        '--entities-root',str(base/'entities'),'--priors-root',str(base/'priors'),'--out-dir',str(tmp_path),'--low-confidence-threshold','0.99'
    ],text=True,capture_output=True)
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert any(node.status == 'resolved_low_confidence' for node in linked.nodes[1:])


# ---------------------------------------------------------------------------
# Plan 14 hardening tests
# ---------------------------------------------------------------------------

from pdf2md.linking.reporting import (
    READINESS_STATUSES,
    build_linking_report,
    build_linking_summary,
)


class TestPlan14ReportHardening:
    def _result(self, name: str = "simple_document"):
        base = FIX / name
        loaded = load_linker_inputs(
            consensus_ir_path=base / "consensus_ir.json",
            consensus_report_path=base / "consensus_report.json",
            entities_root=base / "entities",
            priors_root=base / "priors",
        )
        result = build_linked_structure(
            consensus=loaded.consensus,
            entities_by_backend=loaded.entities_by_backend,
            priors_by_backend=loaded.priors_by_backend,
            consensus_report=loaded.consensus_report,
            source_consensus_ir=str(base / "consensus_ir.json"),
            source_consensus_report=str(base / "consensus_report.json"),
            source_entity_documents=loaded.source_entity_documents,
            source_prior_documents=loaded.source_prior_documents,
        )
        return result.linked, loaded

    def test_report_contains_plan15_readiness(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(linked)
        for field in (
            "linked_node_count",
            "linked_relation_count",
            "linked_conflict_count",
            "unresolved_relation_count",
            "low_confidence_relation_count",
            "low_confidence_node_count",
            "has_reading_order",
            "source_consensus_ir",
            "source_consensus_report",
            "source_entity_documents",
            "source_prior_documents",
            "entities_root_used",
            "priors_root_used",
            "consensus_report_used",
            "inspection_status",
            "docling_export_handled_by",
        ):
            assert field in report["plan15_readiness"], field
        assert report["plan15_readiness"]["docling_export_handled_by"] == "plan_15"

    def test_report_contains_link_status_counts(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(linked)
        counts = report["link_status_counts"]
        assert "resolved" in counts
        assert "resolved_low_confidence" in counts
        assert "unresolved" in counts
        assert sum(counts.values()) == report["relation_count"]

    def test_report_contains_relation_type_status_table(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(linked)
        table = report["relation_type_status"]
        assert isinstance(table, dict)
        for relation_type, status_counts in table.items():
            for status in ("resolved", "resolved_low_confidence", "unresolved"):
                assert status in status_counts

    def test_report_contains_low_confidence_block(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(linked, low_confidence_threshold=0.50)
        low = report["low_confidence"]
        assert low["threshold"] == 0.50
        assert "low_confidence_relations" in low
        assert "low_confidence_nodes" in low

    def test_report_contains_inputs_used_block(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(linked)
        assert report["inputs_used"]["entities_root_used"] is True
        assert report["inputs_used"]["priors_root_used"] is True
        assert report["inputs_used"]["consensus_report_used"] is True

    def test_default_inspection_status_is_diagnostic_only(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(linked)
        assert report["inspection_status"] == "diagnostic_only"
        assert report["inspection_notes"] == []

    def test_report_accepts_all_readiness_statuses(self):
        linked, _ = self._result("simple_document")
        for status in READINESS_STATUSES:
            report = build_linking_report(linked, inspection_status=status)
            assert report["inspection_status"] == status

    def test_report_rejects_unknown_inspection_status(self):
        linked, _ = self._result("simple_document")
        with pytest.raises(ValueError):
            build_linking_report(linked, inspection_status="totally_made_up")

    def test_report_records_inspection_notes(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(
            linked,
            inspection_status="ready_with_warnings",
            inspection_notes=["unresolved TOC link investigated"],
        )
        assert "unresolved TOC link investigated" in report["inspection_notes"]

    def test_build_linking_summary_renders_plan15_block(self):
        linked, _ = self._result("simple_document")
        report = build_linking_report(linked, inspection_status="ready_for_plan_15")
        text = build_linking_summary(report)
        assert "Plan 14" in text
        assert "Plan 15 readiness" in text
        assert "Docling export is deferred to Plan 15" in text


class TestPlan14CLI:
    def test_cli_default_inspection_status_is_diagnostic_only(self, tmp_path):
        base = FIX / "simple_document"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--consensus-ir",
                str(base / "consensus_ir.json"),
                "--consensus-report",
                str(base / "consensus_report.json"),
                "--entities-root",
                str(base / "entities"),
                "--priors-root",
                str(base / "priors"),
                "--out-dir",
                str(tmp_path),
            ],
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr
        report = json.loads((tmp_path / "reports" / "linking_report.json").read_text())
        assert report["inspection_status"] == "diagnostic_only"
        # Plan 14 explicitly forbids linking_summary.txt as a disk output.
        assert not (tmp_path / "linking_summary.txt").exists()
        assert not (tmp_path / "linked_structure_summary.txt").exists()
        assert not (tmp_path / "linked_structure_report.json").exists()

    def test_cli_accepts_inspection_status_and_notes(self, tmp_path):
        base = FIX / "simple_document"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--consensus-ir",
                str(base / "consensus_ir.json"),
                "--consensus-report",
                str(base / "consensus_report.json"),
                "--entities-root",
                str(base / "entities"),
                "--priors-root",
                str(base / "priors"),
                "--out-dir",
                str(tmp_path),
                "--inspection-status",
                "ready_for_plan_15",
                "--inspection-note",
                "synthetic run; all relations resolved",
            ],
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr
        report = json.loads((tmp_path / "reports" / "linking_report.json").read_text())
        assert report["inspection_status"] == "ready_for_plan_15"
        assert "synthetic run; all relations resolved" in report["inspection_notes"]

    def test_cli_rejects_unknown_inspection_status(self, tmp_path):
        base = FIX / "simple_document"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--consensus-ir",
                str(base / "consensus_ir.json"),
                "--out-dir",
                str(tmp_path),
                "--inspection-status",
                "totally_made_up",
            ],
            text=True,
            capture_output=True,
        )
        assert proc.returncode != 0

    def test_cli_verbose_prints_summary_but_does_not_write_summary_file(self, tmp_path):
        base = FIX / "simple_document"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--consensus-ir",
                str(base / "consensus_ir.json"),
                "--consensus-report",
                str(base / "consensus_report.json"),
                "--entities-root",
                str(base / "entities"),
                "--priors-root",
                str(base / "priors"),
                "--out-dir",
                str(tmp_path),
                "--verbose",
            ],
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Plan 15 readiness" in proc.stdout
        assert "Docling export is deferred to Plan 15" in proc.stdout
        # Disk: only the two allowed artefacts.
        assert (tmp_path / "linked_structure.json").is_file()
        assert (tmp_path / "reports" / "linking_report.json").is_file()
        assert not (tmp_path / "linking_summary.txt").exists()
