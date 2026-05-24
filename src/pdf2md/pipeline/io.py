"""Manifest, status and corpus-eval writers (Plan 16)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf2md.pipeline.runner import CorpusEvaluation, DocumentRecord, PipelineManifest


def write_pipeline_manifest(*, manifest: PipelineManifest, target: Path, summary_target: Path | None = None) -> Path:
    """Write the pipeline manifest JSON and the human-readable summary."""

    from pdf2md.pipeline.reporting import build_pipeline_summary

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if summary_target is not None:
        summary_target = Path(summary_target)
        summary_target.parent.mkdir(parents=True, exist_ok=True)
        summary_target.write_text(build_pipeline_summary(manifest), encoding="utf-8")
    return target


def write_stage_status(*, document: DocumentRecord, target: Path) -> Path:
    """Write the per-document stage status JSON."""

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def write_corpus_evaluation(
    *,
    evaluation: CorpusEvaluation,
    target: Path,
    summary_target: Path | None = None,
) -> Path:
    """Write the corpus evaluation JSON and the human-readable summary."""

    from pdf2md.pipeline.reporting import build_corpus_summary

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(evaluation.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if summary_target is not None:
        summary_target = Path(summary_target)
        summary_target.parent.mkdir(parents=True, exist_ok=True)
        summary_target.write_text(build_corpus_summary(evaluation), encoding="utf-8")
    return target


__all__ = [
    "write_corpus_evaluation",
    "write_pipeline_manifest",
    "write_stage_status",
]
