"""Semantic-layer integration for pdf2md.

Plan 006_0 introduced the in-tree adapters and resolver that wrap the
standalone Plan 005_0 semantic backends (``backend/semantic/``) and
emit a :class:`pdf2md.models.CrossReferenceGraph`. Plan 007_0 adds the
ground-truth generator (LaTeXML → TEI → graph) and the evaluation
harness (precision / recall / F1 + resolution accuracy). Profiler/router
CLI integration is deferred to Plan 006_1.
"""

from pdf2md.semantic.base import SemanticBackend
from pdf2md.semantic.ensemble import run_ensemble
from pdf2md.semantic.evaluation import (
    SemanticEvalResult,
    evaluate_semantic,
    result_to_csv_row,
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
    "GrobidSemanticBackend",
    "LatexMLUnavailableError",
    "RegexSemanticBackend",
    "SemanticBackend",
    "SemanticEvalResult",
    "VlmSemanticBackend",
    "evaluate_semantic",
    "generate_ground_truth",
    "resolve_markers",
    "result_to_csv_row",
    "run_ensemble",
]
