"""Plan 16 MVP pipeline runner tests.

Tests do not execute real backends. Stage callables are injected via
``_StageOverrides`` to simulate the seven possible stage outcomes
(succeeded, skipped, failed, blocked) without touching the filesystem
beyond ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.pipeline.artifacts import (
    OneDocumentPaths,
    corpus_document_paths,
    one_document_paths,
)
from pdf2md.pipeline.runner import (
    PIPELINE_SCHEMA_VERSION,
    STAGE_ORDER,
    CorpusEvaluation,
    DocumentRecord,
    DocumentResult,
    MvpReadiness,
    PipelineManifest,
    StageName,
    StageRecord,
    StageStatus,
    _StageOverrides,
    run_corpus,
    run_one_document,
)

ROOT = Path(__file__).resolve().parents[1]
FIX_CORPUS = ROOT / "tests" / "data" / "mvp_pipeline_fixtures" / "sample_corpus"


# ---------------------------------------------------------------------------
# Stage callable mocks
# ---------------------------------------------------------------------------


def _ok_backend_smoke(**_kwargs):
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": [],
        "artefacts": {},
        "metadata": {"backends_successful": 1, "total_backends": 1},
        "raw_dirs_by_backend": {"paddleocr": Path("/fake/raw/paddleocr")},
        "selected_backends": ["paddleocr"],
    }


def _ok_connector_canonical(**_kwargs):
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": [],
        "artefacts": {},
        "canonical_dirs_by_backend": {"paddleocr": Path("/fake/canonical/paddleocr")},
    }


def _ok_connector_validation(**_kwargs):
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": [],
        "artefacts": {},
        "metadata": {"backends_validated": 1},
        "validated_backends": ["paddleocr"],
    }


def _ok_entity_validation(**_kwargs):
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": [],
        "artefacts": {},
        "metadata": {"backends_validated": 1, "backends_no_entities": 0},
    }


def _ok_consensus(**_kwargs):
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": [],
        "artefacts": {"consensus_ir": "/fake/consensus_ir.json"},
        "metadata": {"page_count": 1, "block_count": 5, "conflict_count": 0},
    }


def _ok_linking(**_kwargs):
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": [],
        "artefacts": {"linked_structure": "/fake/linked_structure.json"},
        "metadata": {"node_count": 6, "relation_count": 10, "conflict_count": 0},
    }


def _ok_export(**_kwargs):
    return {
        "status": StageStatus.SUCCEEDED.value,
        "warnings": [],
        "artefacts": {
            "docling": "/fake/out/docling/doc.docling.json",
            "rag": "/fake/out/rag/doc.rag_chunks.json",
            "markdown": "/fake/out/markdown/doc.preview.md",
            "export_report": "/fake/out/reports/export_report.json",
            "export_manifest": "/fake/out/export_manifest.json",
        },
        "metadata": {"docling_text_count": 2, "rag_chunk_count": 2, "markdown_char_count": 88},
    }


def _all_ok() -> _StageOverrides:
    return _StageOverrides(
        backend_smoke=_ok_backend_smoke,
        connector_canonical=_ok_connector_canonical,
        connector_validation=_ok_connector_validation,
        entity_validation=_ok_entity_validation,
        consensus=_ok_consensus,
        linked_structure=_ok_linking,
        export=_ok_export,
    )


def _blocked_backend_smoke(**_kwargs):
    return {
        "status": StageStatus.BLOCKED.value,
        "warnings": ["no_backend_config"],
        "artefacts": {},
        "skipped_reason": "no_successful_backend",
        "failure_class": "plan9_artifact_missing",
        "raw_dirs_by_backend": {},
        "selected_backends": [],
    }


def _failing_consensus(**_kwargs):
    return {
        "status": StageStatus.FAILED.value,
        "warnings": [],
        "failure_class": "consensus_crash",
        "failure_detail": "ValueError: forced",
    }


# ---------------------------------------------------------------------------
# Stage state + reduction tests
# ---------------------------------------------------------------------------


class TestStageReduction:
    def test_stage_order_has_seven_canonical_stages(self):
        assert STAGE_ORDER == (
            StageName.BACKEND_SMOKE,
            StageName.CONNECTOR_CANONICAL,
            StageName.CONNECTOR_VALIDATION,
            StageName.ENTITY_VALIDATION,
            StageName.CONSENSUS,
            StageName.LINKED_STRUCTURE,
            StageName.EXPORT,
        )

    def test_stage_status_enum_has_six_values(self):
        assert {s.value for s in StageStatus} == {
            "pending",
            "running",
            "succeeded",
            "skipped",
            "failed",
            "blocked",
        }

    def test_document_result_enum_has_five_values(self):
        assert {d.value for d in DocumentResult} == {
            "passed",
            "passed_with_warnings",
            "failed",
            "blocked",
            "skipped",
        }

    def test_mvp_readiness_enum_has_four_values(self):
        assert {m.value for m in MvpReadiness} == {
            "MVP_ready",
            "MVP_ready_with_warnings",
            "MVP_not_ready",
            "diagnostic_only",
        }


class TestRunOneDocument:
    def test_all_succeed_yields_passed_document_and_mvp_ready(self, tmp_path: Path):
        manifest = run_one_document(
            pdf_path=tmp_path / "fake.pdf",
            out_dir=tmp_path / "out",
            stage_overrides=_all_ok(),
        )
        assert manifest.mode == "one_document"
        assert len(manifest.documents) == 1
        doc = manifest.documents[0]
        assert doc.result == DocumentResult.PASSED.value
        assert manifest.mvp_readiness == MvpReadiness.MVP_READY.value
        assert all(s.status == StageStatus.SUCCEEDED.value for s in doc.stages)
        # final_artefacts should expose the five export paths
        for key in ("docling", "rag", "markdown", "export_report", "export_manifest"):
            assert key in doc.final_artefacts

    def test_blocked_backend_smoke_skips_downstream_and_blocks_document(self, tmp_path: Path):
        overrides = _StageOverrides(backend_smoke=_blocked_backend_smoke)
        manifest = run_one_document(
            pdf_path=tmp_path / "fake.pdf",
            out_dir=tmp_path / "out",
            stage_overrides=overrides,
        )
        doc = manifest.documents[0]
        assert doc.result == DocumentResult.BLOCKED.value
        assert doc.stages[0].status == StageStatus.BLOCKED.value
        for stage in doc.stages[1:]:
            assert stage.status == StageStatus.SKIPPED.value
            assert stage.skipped_reason == "upstream_blocked"
        assert manifest.mvp_readiness != MvpReadiness.MVP_READY.value

    def test_failing_consensus_skips_downstream_and_fails_document(self, tmp_path: Path):
        overrides = _StageOverrides(
            backend_smoke=_ok_backend_smoke,
            connector_canonical=_ok_connector_canonical,
            connector_validation=_ok_connector_validation,
            entity_validation=_ok_entity_validation,
            consensus=_failing_consensus,
        )
        manifest = run_one_document(
            pdf_path=tmp_path / "fake.pdf",
            out_dir=tmp_path / "out",
            stage_overrides=overrides,
        )
        doc = manifest.documents[0]
        assert doc.result == DocumentResult.FAILED.value
        consensus_stage = next(s for s in doc.stages if s.name == StageName.CONSENSUS.value)
        assert consensus_stage.status == StageStatus.FAILED.value
        assert consensus_stage.failure_class == "consensus_crash"
        # downstream stages skipped
        for stage in doc.stages[doc.stages.index(consensus_stage) + 1:]:
            assert stage.status == StageStatus.SKIPPED.value
        assert manifest.mvp_readiness == MvpReadiness.MVP_NOT_READY.value

    def test_pipeline_manifest_is_written(self, tmp_path: Path):
        out_dir = tmp_path / "out"
        run_one_document(
            pdf_path=tmp_path / "fake.pdf",
            out_dir=out_dir,
            stage_overrides=_all_ok(),
        )
        manifest_path = out_dir / "pipeline_manifest.json"
        summary_path = out_dir / "pipeline_summary.txt"
        stage_status_path = out_dir / "stage_status.json"
        assert manifest_path.is_file()
        assert summary_path.is_file()
        assert stage_status_path.is_file()
        payload = json.loads(manifest_path.read_text())
        assert payload["schema_name"] == "pdf2md.MvpPipelineManifest"
        assert payload["schema_version"] == PIPELINE_SCHEMA_VERSION
        assert payload["mode"] == "one_document"
        summary = summary_path.read_text()
        assert "MVP pipeline summary" in summary

    def test_work_dir_defaults_to_out_dir_work(self, tmp_path: Path):
        out_dir = tmp_path / "out"
        run_one_document(
            pdf_path=tmp_path / "fake.pdf",
            out_dir=out_dir,
            stage_overrides=_all_ok(),
        )
        assert (out_dir / "work").is_dir()


class TestRunCorpus:
    def test_corpus_discovers_documents_and_aggregates_results(self, tmp_path: Path):
        # Two docs in our fixture, neither has a PDF, so all will block at backend_smoke.
        # Inject _all_ok overrides to bypass the lack of real PDFs.
        manifest, evaluation = run_corpus(
            corpus_root=FIX_CORPUS,
            out_dir=tmp_path / "out",
            stage_overrides=_all_ok(),
        )
        assert manifest.mode == "corpus_subset"
        assert len(manifest.documents) == 2
        for d in manifest.documents:
            assert d.result == DocumentResult.PASSED.value
        assert evaluation.mvp_readiness == MvpReadiness.MVP_READY.value
        assert set(evaluation.selected_documents) == {"doc_a", "doc_b"}
        assert all(evaluation.final_export_availability.values())

    def test_corpus_respects_max_documents(self, tmp_path: Path):
        manifest, evaluation = run_corpus(
            corpus_root=FIX_CORPUS,
            out_dir=tmp_path / "out",
            max_documents=1,
            stage_overrides=_all_ok(),
        )
        assert len(manifest.documents) == 1
        assert len(evaluation.selected_documents) == 1

    def test_corpus_respects_document_list(self, tmp_path: Path):
        manifest, _ = run_corpus(
            corpus_root=FIX_CORPUS,
            out_dir=tmp_path / "out",
            document_list=["doc_b"],
            stage_overrides=_all_ok(),
        )
        assert [d.document_id for d in manifest.documents] == ["doc_b"]

    def test_corpus_with_no_pdfs_blocks_documents(self, tmp_path: Path):
        # Default real stages; corpus fixture has no PDFs.
        manifest, evaluation = run_corpus(
            corpus_root=FIX_CORPUS,
            out_dir=tmp_path / "out",
        )
        for d in manifest.documents:
            assert d.result in (DocumentResult.BLOCKED.value, DocumentResult.SKIPPED.value)
        assert evaluation.mvp_readiness != MvpReadiness.MVP_READY.value

    def test_corpus_writes_per_document_stage_status_and_aggregate(self, tmp_path: Path):
        out_dir = tmp_path / "out"
        run_corpus(
            corpus_root=FIX_CORPUS,
            out_dir=out_dir,
            stage_overrides=_all_ok(),
        )
        assert (out_dir / "pipeline_manifest.json").is_file()
        assert (out_dir / "pipeline_summary.txt").is_file()
        assert (out_dir / "mvp_corpus_evaluation.json").is_file()
        assert (out_dir / "mvp_corpus_summary.txt").is_file()
        assert (out_dir / "documents" / "doc_a" / "stage_status.json").is_file()
        assert (out_dir / "documents" / "doc_b" / "stage_status.json").is_file()

    def test_corpus_unknown_root_yields_empty_evaluation(self, tmp_path: Path):
        manifest, evaluation = run_corpus(
            corpus_root=tmp_path / "does_not_exist",
            out_dir=tmp_path / "out",
            stage_overrides=_all_ok(),
        )
        assert len(manifest.documents) == 0
        assert evaluation.selected_documents == []
        assert evaluation.mvp_readiness == MvpReadiness.DIAGNOSTIC_ONLY.value


class TestPathHelpers:
    def test_one_document_paths_defaults(self):
        p = one_document_paths(document_id="doc-x", out_dir=Path("/out"))
        assert p.work_dir == Path("/out/work")
        assert p.docling_path == Path("/out/docling/doc-x.docling.json")
        assert p.pipeline_manifest == Path("/out/pipeline_manifest.json")

    def test_corpus_document_paths_layout(self):
        p = corpus_document_paths(
            document_id="doc-y",
            corpus_out_dir=Path("/out"),
            corpus_work_dir=Path("/work"),
        )
        assert p.document_root == Path("/out/documents/doc-y")
        assert p.work_dir == Path("/work/doc-y")
        assert p.docling_path == Path("/out/documents/doc-y/docling/doc-y.docling.json")
        assert p.stage_status == Path("/out/documents/doc-y/stage_status.json")
