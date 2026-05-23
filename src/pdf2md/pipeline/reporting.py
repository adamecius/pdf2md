"""Human-readable summaries and MVP readiness classification (Plan 16)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf2md.pipeline.runner import (
        CorpusEvaluation,
        DocumentRecord,
        MvpReadiness,
        PipelineManifest,
    )


def _status_value(value) -> str:
    return value if isinstance(value, str) else getattr(value, "value", str(value))


def build_pipeline_summary(manifest: "PipelineManifest") -> str:
    """Render a human-readable summary of a one-document or corpus manifest."""

    mode = _status_value(manifest.mode)
    readiness = _status_value(manifest.mvp_readiness)
    lines = [
        "pdf2md MVP pipeline summary (Plan 16)",
        f"schema: {manifest.schema_name} {manifest.schema_version}",
        f"generated_at: {manifest.generated_at}",
        f"mode: {mode}",
        f"input_pdf: {manifest.input_pdf}",
        f"corpus_root: {manifest.corpus_root}",
        f"out_dir: {manifest.out_dir}",
        f"work_dir: {manifest.work_dir}",
        f"selected_backends: {list(manifest.selected_backends)}",
        f"mvp_readiness: {readiness}",
        "",
        "documents:",
    ]
    if not manifest.documents:
        lines.append("- (none)")
    for d in manifest.documents:
        lines.append(
            f"- {d.document_id} [{_status_value(d.result)}] eligible_backends={d.eligible_backends}"
        )
        for stage in d.stages:
            stage_name = _status_value(stage.name)
            stage_status = _status_value(stage.status)
            suffix = ""
            if stage.skipped_reason:
                suffix = f" reason={stage.skipped_reason}"
            elif stage.failure_class:
                suffix = f" failure_class={stage.failure_class}"
            duration = f" ({stage.duration_seconds}s)" if stage.duration_seconds is not None else ""
            lines.append(f"    {stage_name}: {stage_status}{duration}{suffix}")
        if d.final_artefacts:
            lines.append(f"    final_artefacts: {sorted(d.final_artefacts.keys())}")

    if manifest.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in manifest.warnings)
    if manifest.errors:
        lines.extend(["", "errors:"])
        lines.extend(f"- {e}" for e in manifest.errors)

    lines.extend(
        [
            "",
            "Plan 17+ (post-MVP) is not in scope for Plan 16; MVP means a local, "
            "auditable, reproducible end-to-end run.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_corpus_summary(evaluation: "CorpusEvaluation") -> str:
    """Render a human-readable summary of a corpus MVP evaluation."""

    readiness = _status_value(evaluation.mvp_readiness)
    lines = [
        "pdf2md MVP corpus evaluation summary (Plan 16)",
        f"schema: {evaluation.schema_name} {evaluation.schema_version}",
        f"generated_at: {evaluation.generated_at}",
        f"corpus_root: {evaluation.corpus_root}",
        f"out_dir: {evaluation.out_dir}",
        f"mvp_readiness: {readiness}",
        "",
        f"selected_documents ({len(evaluation.selected_documents)}):",
    ]
    for doc_id in evaluation.selected_documents:
        result = evaluation.document_results.get(doc_id, "unknown")
        export = "yes" if evaluation.final_export_availability.get(doc_id) else "no"
        lines.append(f"- {doc_id}: result={result} export_present={export}")
    lines.extend(["", "stage bottlenecks (failure counts):"])
    for stage, count in evaluation.stage_bottlenecks.items():
        lines.append(f"- {stage}: {count}")
    lines.extend(["", "backend eligibility (documents per backend):"])
    if not evaluation.backend_eligibility:
        lines.append("- (none)")
    for backend, count in sorted(evaluation.backend_eligibility.items()):
        lines.append(f"- {backend}: {count}")
    lines.extend(
        [
            "",
            "confidence summary:",
            f"- documents_with_export: {evaluation.confidence_summary.get('documents_with_export')}",
            f"- documents_total: {evaluation.confidence_summary.get('documents_total')}",
        ]
    )
    if evaluation.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in evaluation.warnings)
    return "\n".join(lines) + "\n"


def classify_mvp_readiness(documents: list["DocumentRecord"]) -> "MvpReadiness":
    """Expose the runner's classification helper publicly for tests."""

    from pdf2md.pipeline.runner import _mvp_readiness  # noqa: WPS437 - intentional reuse

    return _mvp_readiness(documents)


def build_orchestrator_pipeline_summary(manifest: dict) -> str:
    """Render a Plan 18 ``pipeline_manifest.json`` dict as plain text.

    Distinct from :func:`build_pipeline_summary` which renders the Plan 16
    ``PipelineManifest`` pydantic model. The orchestrator stores its manifest
    as a plain dict, so we accept that shape directly.
    """

    lines = [
        "Pipeline Summary",
        "================",
        f"Document: {manifest.get('document_id', '')}",
        f"Input: {manifest.get('input_pdf', '')}",
        f"Overall: {manifest.get('overall_status', '')}",
        "",
        f"Backends requested: {list(manifest.get('backends_requested', []))}",
        f"Backends succeeded: {list(manifest.get('backends_succeeded', []))}",
        "",
        "Stages:",
    ]
    for stage in manifest.get("stages", []):
        name = stage.get("name", "")
        status = stage.get("status", "")
        duration = stage.get("duration_seconds")
        duration_str = f"{duration:.2f}s" if isinstance(duration, (int, float)) else "-"
        lines.append(f"  {name:<22} [{status}]    {duration_str}")
        if stage.get("error"):
            lines.append(f"    error: {stage['error']}")
        for warning in stage.get("warnings", []) or []:
            lines.append(f"    warning: {warning}")

    warnings = manifest.get("warnings", []) or []
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines) + "\n"


__all__ = [
    "build_pipeline_summary",
    "build_orchestrator_pipeline_summary",
    "build_corpus_summary",
    "classify_mvp_readiness",
]
