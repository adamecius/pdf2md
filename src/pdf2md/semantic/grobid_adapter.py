"""In-process adapter for the GROBID semantic backend.

Thin wrapper around ``backend/semantic/grobid/connector.py``. The
connector is the single source of truth and follows the same
convention as the OCR backends (``backend/<name>/connector.py``):

    BACKEND, BACKEND_VERSION constants,
    connect(raw_dir, document_id, out_dir=None, *, …) -> SemanticConnectorResult,
    main(argv=None) -> int.

This adapter does the minimum needed to expose that surface as the
:class:`SemanticBackend` ABC the Plan 006 ensemble runner expects.
The Docker container is operator-managed; the adapter only consumes
it via HTTP, exactly like the standalone smoke test.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from pdf2md.models.cross_ref import CrossReferenceGraph
from pdf2md.semantic.base import SemanticBackend


BACKEND_NAME = "grobid"
BACKEND_VERSION = "0.1.0"


def _backend_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[3] / "backend" / "semantic" / "grobid"


def _load_connector_module() -> types.ModuleType:
    """Load ``backend/semantic/grobid/connector.py`` by file path."""
    connector_path = _backend_root() / "connector.py"
    if not connector_path.is_file():
        raise RuntimeError(
            f"GROBID connector not found at {connector_path}; "
            "the standalone backend/semantic/grobid/ tree was removed or moved"
        )
    spec = importlib.util.spec_from_file_location(
        "pdf2md._semantic_grobid_connector", connector_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not build import spec for {connector_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GrobidSemanticBackend(SemanticBackend):
    """In-process GROBID backend adapter.

    Delegates to ``backend/semantic/grobid/connector.py::connect``.
    The connector itself talks to a locally-running GROBID service
    over HTTP; the Docker container (or any other host of the GROBID
    service) is operator-managed.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8070,
        source_ref: str = "#/document",
    ) -> None:
        """Initialise the adapter.

        Args:
            host: GROBID hostname; defaults to ``localhost``.
            port: GROBID port; defaults to ``8070`` (the GROBID default).
            source_ref: JSON pointer stamped on every emitted marker.
        """
        self._host = host
        self._port = port
        self._source_ref = source_ref
        self._connector_mod: types.ModuleType | None = None

    def name(self) -> str:
        return BACKEND_NAME

    def version(self) -> str:
        return BACKEND_VERSION

    def is_available(self) -> bool:
        if not (_backend_root() / "connector.py").is_file():
            return False
        try:
            connector = self._connector()
            endpoint = connector.grobid_client.GrobidEndpoint(
                host=self._host, port=self._port
            )
            return bool(connector.grobid_client.is_alive(endpoint))
        except Exception:
            return False

    def extract(
        self,
        pdf_path: Path | None,
        text: str | None,
        output_dir: Path,
    ) -> CrossReferenceGraph:
        del text  # the GROBID backend works on the PDF directly
        if pdf_path is None or not pdf_path.is_file():
            raise ValueError(
                "GrobidSemanticBackend.extract requires an existing pdf_path"
            )

        connector = self._connector()
        result = connector.connect(
            raw_dir=pdf_path.parent,
            document_id=pdf_path.stem,
            out_dir=output_dir,
            pdf_path=pdf_path,
            host=self._host,
            port=self._port,
            source_ref=self._source_ref,
        )
        # The connector returns an empty graph + env_not_ready warning
        # when GROBID is unreachable; bubble that up as RuntimeError to
        # match the prior adapter contract.
        for warning in result.warnings:
            if warning.startswith("env_not_ready:"):
                raise RuntimeError(warning)
        return result.graph

    def _connector(self) -> types.ModuleType:
        if self._connector_mod is None:
            self._connector_mod = _load_connector_module()
        return self._connector_mod
