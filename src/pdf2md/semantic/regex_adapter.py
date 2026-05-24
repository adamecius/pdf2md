"""In-process adapter for the standalone regex semantic backend.

Wraps ``backend/semantic/regex/patterns.py`` and converts its
``PatternHit`` output into a :class:`CrossReferenceGraph`.

The standalone backend module is imported dynamically by path because
``backend/`` is not a Python package on ``sys.path``. This keeps the
isolation pattern: the standalone backend remains importable on its own
(per Plan 005_0), and the adapter is the only place the two trees touch.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

from pdf2md.models.cross_ref import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefMarker,
    RefType,
)
from pdf2md.semantic.base import SemanticBackend


BACKEND_NAME = "regex"
BACKEND_VERSION = "0.1.0"


def _backend_root() -> Path:
    """Return the absolute path to ``backend/semantic/regex/``."""
    here = Path(__file__).resolve()
    # src/pdf2md/semantic/regex_adapter.py → up 4 → repo root → backend/semantic/regex
    return here.parents[3] / "backend" / "semantic" / "regex"


def _load_patterns_module() -> types.ModuleType:
    """Load ``patterns.py`` from the standalone backend by path."""
    patterns_path = _backend_root() / "patterns.py"
    if not patterns_path.is_file():
        raise RuntimeError(
            f"regex backend not found at {patterns_path}; "
            "the standalone backend/semantic/regex/ tree was removed or moved"
        )
    spec = importlib.util.spec_from_file_location(
        "pdf2md._semantic_regex_patterns", patterns_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not build import spec for {patterns_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hit_to_marker(hit: Any, source_ref: str) -> RefMarker | None:
    """Convert a backend ``PatternHit`` into a :class:`RefMarker`.

    Skips hits whose ``marker_type`` is not part of the canonical
    :class:`RefType` taxonomy (defensive: protects against backend
    additions landing before the schema is updated).
    """
    try:
        marker_type = RefType(hit.marker_type)
    except ValueError:
        return None
    return RefMarker(
        source_ref=source_ref,
        marker_text=hit.marker_text,
        marker_type=marker_type,
        char_offset=tuple(hit.char_offset),
        confidence=1.0,
        backend=BACKEND_NAME,
    )


def _doc_hash_from_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class RegexSemanticBackend(SemanticBackend):
    """In-process regex backend adapter.

    Operates on raw text. When ``text`` is ``None`` but a ``pdf_path``
    pointing to a UTF-8 ``.txt`` file is given, reads that file as a
    convenience for the proof-of-life CLI. PDF parsing is out of scope —
    the GROBID and VLM backends handle PDFs directly.
    """

    def __init__(self, source_ref: str = "#/document") -> None:
        """Initialise the adapter.

        Args:
            source_ref: JSON pointer string used as the ``source_ref`` on
                every emitted :class:`RefMarker`. Callers that have a
                DoclingDocument should pass the pointer to the text item
                they extracted ``text`` from; bulk-text callers can leave
                this at the default.
        """
        self._source_ref = source_ref
        self._patterns_module: types.ModuleType | None = None

    def name(self) -> str:
        return BACKEND_NAME

    def version(self) -> str:
        return BACKEND_VERSION

    def is_available(self) -> bool:
        return (_backend_root() / "patterns.py").is_file()

    def extract(
        self,
        pdf_path: Path | None,
        text: str | None,
        output_dir: Path,
    ) -> CrossReferenceGraph:
        del output_dir  # the regex adapter writes nothing transient

        body = self._resolve_text(pdf_path, text)
        if self._patterns_module is None:
            self._patterns_module = _load_patterns_module()
        hits = self._patterns_module.find_markers(body)

        markers: list[RefMarker] = []
        for hit in hits:
            marker = _hit_to_marker(hit, self._source_ref)
            if marker is not None:
                markers.append(marker)

        return CrossReferenceGraph(
            schema_version=CROSS_REF_SCHEMA_VERSION,
            doc_hash=_doc_hash_from_text(body),
            markers=markers,
            edges=[],
            entities=[],
            backend_versions={BACKEND_NAME: BACKEND_VERSION},
        )

    @staticmethod
    def _resolve_text(pdf_path: Path | None, text: str | None) -> str:
        if text is not None:
            return text
        if pdf_path is not None and pdf_path.suffix.lower() == ".txt":
            return pdf_path.read_text(encoding="utf-8")
        raise ValueError(
            "RegexSemanticBackend.extract requires either text= or a .txt path; "
            "PDF parsing is out of scope for the regex adapter"
        )
