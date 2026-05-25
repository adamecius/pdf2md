"""In-process adapter for the standalone regex semantic backend.

Thin wrapper around ``backend/semantic/regex/connector.py``. The
connector is the single source of truth — this adapter exists only to
adapt the connector's :class:`SemanticConnectorResult` to the
:class:`SemanticBackend` ABC the Plan 006 ensemble runner expects.

The standalone backend module is loaded dynamically by path because
``backend/`` is not a Python package on ``sys.path``. This preserves
the isolation pattern from Plan 005: the standalone backend is still
importable on its own, the connector mirrors the OCR-backend
convention exactly, and this adapter is the only place the two trees
touch from inside ``src/pdf2md/``.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from pdf2md.models.cross_ref import CrossReferenceGraph
from pdf2md.semantic.base import SemanticBackend


BACKEND_NAME = "regex"
BACKEND_VERSION = "0.1.0"


def _backend_root() -> Path:
    """Return the absolute path to ``backend/semantic/regex/``."""
    here = Path(__file__).resolve()
    # src/pdf2md/semantic/regex_adapter.py → up 4 → repo root → backend/semantic/regex
    return here.parents[3] / "backend" / "semantic" / "regex"


def _load_connector_module() -> types.ModuleType:
    """Load ``backend/semantic/regex/connector.py`` by file path."""
    connector_path = _backend_root() / "connector.py"
    if not connector_path.is_file():
        raise RuntimeError(
            f"regex connector not found at {connector_path}; "
            "the standalone backend/semantic/regex/ tree was removed or moved"
        )
    spec = importlib.util.spec_from_file_location(
        "pdf2md._semantic_regex_connector", connector_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not build import spec for {connector_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RegexSemanticBackend(SemanticBackend):
    """In-process regex backend adapter.

    Delegates to ``backend/semantic/regex/connector.py::connect`` —
    that connector follows the same convention as the OCR backends
    (``backend/<name>/connector.py``).
    """

    def __init__(self, source_ref: str = "#/document") -> None:
        """Initialise the adapter.

        Args:
            source_ref: JSON pointer string used as the ``source_ref``
                on every emitted :class:`RefMarker`.
        """
        self._source_ref = source_ref
        self._connector_mod: types.ModuleType | None = None

    def name(self) -> str:
        return BACKEND_NAME

    def version(self) -> str:
        return BACKEND_VERSION

    def is_available(self) -> bool:
        return (_backend_root() / "connector.py").is_file()

    def extract(
        self,
        pdf_path: Path | None,
        text: str | None,
        output_dir: Path,
    ) -> CrossReferenceGraph:
        body = self._resolve_text(pdf_path, text)
        if self._connector_mod is None:
            self._connector_mod = _load_connector_module()
        # The connector's connect() takes raw_dir + document_id but we
        # have the text already; pass it via the optional `text` kwarg
        # so the connector skips the raw_dir lookup entirely.
        result = self._connector_mod.connect(
            raw_dir=output_dir,
            document_id="adapter",
            out_dir=None,
            text=body,
            source_ref=self._source_ref,
        )
        return result.graph

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
