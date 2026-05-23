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
    OneDocumentPaths,
    CorpusDocumentPaths,
    one_document_paths,
    corpus_document_paths,
)
from pdf2md.pipeline.io import (
    write_pipeline_manifest,
    write_stage_status,
    write_corpus_evaluation,
)
from pdf2md.pipeline.reporting import (
    build_pipeline_summary,
    build_corpus_summary,
    classify_mvp_readiness,
)
from pdf2md.pipeline.runner import (
    DocumentRecord,
    MvpReadiness,
    PipelineManifest,
    CorpusEvaluation,
    StageRecord,
    StageStatus,
    DocumentResult,
    StageName,
    run_corpus,
    run_one_document,
)

__all__ = [
    # paths
    "OneDocumentPaths",
    "CorpusDocumentPaths",
    "one_document_paths",
    "corpus_document_paths",
    # io
    "write_pipeline_manifest",
    "write_stage_status",
    "write_corpus_evaluation",
    # reporting
    "build_pipeline_summary",
    "build_corpus_summary",
    "classify_mvp_readiness",
    # runner
    "DocumentRecord",
    "MvpReadiness",
    "PipelineManifest",
    "CorpusEvaluation",
    "StageRecord",
    "StageStatus",
    "DocumentResult",
    "StageName",
    "run_corpus",
    "run_one_document",
]
