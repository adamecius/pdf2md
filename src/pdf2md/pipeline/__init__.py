"""End-to-end MVP pipeline package (Plan 16).

Public surface:

- ``run_one_document`` / ``run_corpus``: high-level orchestration entrypoints.
- ``StageStatus`` / ``DocumentResult`` / ``MvpReadiness``: typed enums.
- ``StageRecord`` / ``DocumentRecord`` / ``PipelineManifest`` / ``CorpusEvaluation``:
  Pydantic report models.

This package extends but does not replace the existing stage modules. Each
stage entry point is called at module level; backend execution still flows
through the existing backend runner.
"""

from __future__ import annotations

from pdf2md.pipeline.artifacts import (
    CorpusDocumentPaths,
    OneDocumentPaths,
    corpus_document_paths,
    one_document_paths,
)
from pdf2md.pipeline.io import (
    write_corpus_evaluation,
    write_pipeline_manifest,
    write_stage_status,
)
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
    run_corpus,
    run_one_document,
)

__all__ = [
    "CorpusDocumentPaths",
    "CorpusEvaluation",
    "DocumentRecord",
    "DocumentResult",
    "MvpReadiness",
    "OneDocumentPaths",
    "PipelineManifest",
    "StageName",
    "StageRecord",
    "StageStatus",
    "build_corpus_summary",
    "build_pipeline_summary",
    "classify_mvp_readiness",
    "corpus_document_paths",
    "one_document_paths",
    "run_corpus",
    "run_one_document",
    "write_corpus_evaluation",
    "write_pipeline_manifest",
    "write_stage_status",
]
