"""Plan 16 MVP pipeline reporting tests."""

from __future__ import annotations

from pdf2md.pipeline.reporting import (
    build_corpus_summary,
    build_pipeline_summary,
    classify_mvp_readiness,
)
from pdf2md.pipeline.runner import (
    CorpusEvaluation,
    DocumentRecord,
    DocumentResult,
    MvpReadiness,
    PipelineManifest,
    StageName,
    StageRecord,
    StageStatus,
)


def _doc(name: str, result: DocumentResult) -> DocumentRecord:
    return DocumentRecord(
        document_id=name,
        result=result,
        stages=[StageRecord(name=s, status=StageStatus.SUCCEEDED) for s in StageName],
        eligible_backends=["paddleocr"],
        final_artefacts={"docling": f"/fake/{name}.docling.json"},
    )


class TestReadinessClassification:
    def test_all_passed_yields_mvp_ready(self):
        docs = [_doc("a", DocumentResult.PASSED), _doc("b", DocumentResult.PASSED)]
        assert classify_mvp_readiness(docs) == MvpReadiness.MVP_READY

    def test_mixed_passed_and_warnings_yields_mvp_ready_with_warnings(self):
        docs = [_doc("a", DocumentResult.PASSED), _doc("b", DocumentResult.PASSED_WITH_WARNINGS)]
        assert classify_mvp_readiness(docs) == MvpReadiness.MVP_READY_WITH_WARNINGS

    def test_any_failed_yields_mvp_not_ready(self):
        docs = [_doc("a", DocumentResult.PASSED), _doc("b", DocumentResult.FAILED)]
        assert classify_mvp_readiness(docs) == MvpReadiness.MVP_NOT_READY

    def test_no_documents_is_diagnostic_only(self):
        assert classify_mvp_readiness([]) == MvpReadiness.DIAGNOSTIC_ONLY

    def test_all_blocked_is_diagnostic_only(self):
        docs = [_doc("a", DocumentResult.BLOCKED), _doc("b", DocumentResult.BLOCKED)]
        assert classify_mvp_readiness(docs) == MvpReadiness.DIAGNOSTIC_ONLY


class TestPipelineSummary:
    def test_summary_includes_mode_and_readiness_and_documents(self):
        manifest = PipelineManifest(
            generated_at="2026-05-23T00:00:00Z",
            mode="one_document",
            input_pdf="/some/x.pdf",
            out_dir="/out",
            work_dir="/out/work",
            selected_backends=["paddleocr"],
            documents=[_doc("x", DocumentResult.PASSED)],
            mvp_readiness=MvpReadiness.MVP_READY,
        )
        text = build_pipeline_summary(manifest)
        assert "MVP pipeline summary" in text
        assert "mode: one_document" in text
        assert "mvp_readiness: MVP_ready" in text
        assert "- x [passed]" in text

    def test_summary_lists_stage_statuses_in_order(self):
        manifest = PipelineManifest(
            generated_at="2026-05-23T00:00:00Z",
            mode="one_document",
            input_pdf="/some/x.pdf",
            out_dir="/out",
            work_dir="/out/work",
            documents=[_doc("x", DocumentResult.PASSED)],
            mvp_readiness=MvpReadiness.MVP_READY,
        )
        text = build_pipeline_summary(manifest)
        for stage_name in (
            "backend_smoke",
            "connector_canonical",
            "connector_validation",
            "entity_proposal_validation",
            "consensus",
            "linked_structure",
            "export",
        ):
            assert stage_name in text


class TestCorpusSummary:
    def test_corpus_summary_lists_each_document_result(self):
        evaluation = CorpusEvaluation(
            generated_at="2026-05-23T00:00:00Z",
            corpus_root="/corpus",
            out_dir="/out",
            selected_documents=["a", "b"],
            document_results={"a": "passed", "b": "failed"},
            stage_bottlenecks={"consensus": 1},
            backend_eligibility={"paddleocr": 2},
            final_export_availability={"a": True, "b": False},
            confidence_summary={"documents_with_export": 1, "documents_total": 2},
            mvp_readiness=MvpReadiness.MVP_NOT_READY,
        )
        text = build_corpus_summary(evaluation)
        assert "selected_documents (2):" in text
        assert "- a: result=passed export_present=yes" in text
        assert "- b: result=failed export_present=no" in text
        assert "consensus: 1" in text
        assert "paddleocr: 2" in text
        assert "mvp_readiness: MVP_not_ready" in text
