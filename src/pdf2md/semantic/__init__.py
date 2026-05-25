"""Semantic-layer integration for pdf2md.

Plan 006_0 introduced the in-tree adapters and resolver that wrap the
standalone Plan 005_0 semantic backends (``backend/semantic/``) and
emit a :class:`pdf2md.models.CrossReferenceGraph`. Plan 007_0 added the
ground-truth generator (LaTeXML → graph) and the evaluation harness.
Plan 008_0 adds the D3-compatible graph exporter that the static viewer
under ``webui/cross_ref/`` consumes.
"""

from pdf2md.semantic.base import SemanticBackend
from pdf2md.semantic.candidates import entities_to_candidates
from pdf2md.semantic.ensemble import run_ensemble
from pdf2md.semantic.evaluation import (
    SemanticEvalResult,
    evaluate_semantic,
    result_to_csv_row,
)
from pdf2md.semantic.graph_export import (
    GRAPH_EXPORT_SCHEMA_VERSION,
    GraphExport,
    export_graph,
)
from pdf2md.semantic.grobid_adapter import GrobidSemanticBackend
from pdf2md.semantic.groundtruth import (
    LatexMLUnavailableError,
    generate_ground_truth,
)
from pdf2md.semantic.regex_adapter import RegexSemanticBackend
from pdf2md.semantic.resolver import resolve_markers
from pdf2md.semantic.vlm_adapter import VlmSemanticBackend

__all__ = [
    "GRAPH_EXPORT_SCHEMA_VERSION",
    "GraphExport",
    "GrobidSemanticBackend",
    "LatexMLUnavailableError",
    "RegexSemanticBackend",
    "SemanticBackend",
    "SemanticEvalResult",
    "VlmSemanticBackend",
    "entities_to_candidates",
    "evaluate_semantic",
    "export_graph",
    "generate_ground_truth",
    "resolve_markers",
    "result_to_csv_row",
    "run_ensemble",
]
