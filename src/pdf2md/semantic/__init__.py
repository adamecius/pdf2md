"""Semantic-layer integration for pdf2md.

Plan 006_0 introduces the in-tree adapters and resolver that wrap the
standalone Plan 005_0 semantic backends (``backend/semantic/``) and
emit a :class:`pdf2md.models.CrossReferenceGraph`. Profiler/router/CLI
integration is deferred to Plan 006_1.
"""

from pdf2md.semantic.base import SemanticBackend
from pdf2md.semantic.ensemble import run_ensemble
from pdf2md.semantic.grobid_adapter import GrobidSemanticBackend
from pdf2md.semantic.regex_adapter import RegexSemanticBackend
from pdf2md.semantic.resolver import resolve_markers
from pdf2md.semantic.vlm_adapter import VlmSemanticBackend

__all__ = [
    "GrobidSemanticBackend",
    "RegexSemanticBackend",
    "SemanticBackend",
    "VlmSemanticBackend",
    "resolve_markers",
    "run_ensemble",
]
