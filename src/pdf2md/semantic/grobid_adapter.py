"""In-process adapter for the standalone GROBID semantic backend.

Wraps ``backend/semantic/grobid/{grobid_client,tei_parser}.py`` and
converts the parsed TEI markers and bibliography entries into a
:class:`CrossReferenceGraph`.

Runtime preconditions (GROBID service reachable on the configured port)
are checked by :meth:`GrobidSemanticBackend.is_available`. The adapter
does not start or stop the Docker container — that is operator-managed
per Plan 005_0.
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
    SemanticEntity,
)
from pdf2md.semantic.base import SemanticBackend


BACKEND_NAME = "grobid"
BACKEND_VERSION = "0.1.0"


def _backend_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[3] / "backend" / "semantic" / "grobid"


def _load_module(filename: str, module_alias: str) -> types.ModuleType:
    path = _backend_root() / filename
    if not path.is_file():
        raise RuntimeError(
            f"GROBID backend module not found at {path}; "
            "the standalone backend/semantic/grobid/ tree was removed or moved"
        )
    spec = importlib.util.spec_from_file_location(module_alias, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_alias] = module
    spec.loader.exec_module(module)
    return module


def _safe_offset(text: str, marker_text: str) -> tuple[int, int]:
    """Return a ``(start, end)`` offset for ``marker_text`` inside ``text``.

    GROBID does not report character offsets on its TEI ``<ref>``
    elements, so we approximate by scanning the marker text. For markers
    not found in the supplied text we return ``(0, len(marker_text))`` —
    the offset is informational, not load-bearing for the schema.
    """
    if not marker_text:
        return (0, 0)
    idx = text.find(marker_text)
    if idx < 0:
        return (0, len(marker_text))
    return (idx, idx + len(marker_text))


def _hit_to_marker(hit: Any, source_ref: str, body_text: str) -> RefMarker | None:
    try:
        marker_type = RefType(hit.marker_type)
    except ValueError:
        return None
    return RefMarker(
        source_ref=source_ref,
        marker_text=hit.marker_text,
        marker_type=marker_type,
        char_offset=_safe_offset(body_text, hit.marker_text),
        confidence=1.0,
        backend=BACKEND_NAME,
    )


def _bib_entry_to_entity(entry: Any) -> SemanticEntity | None:
    label = entry.raw_text.strip() or None
    item_ref = f"#/bibliography/{entry.ref_id}" if entry.ref_id else None
    if item_ref is None:
        return None
    return SemanticEntity(
        item_ref=item_ref,
        entity_type=RefType.BIBLIOGRAPHY,
        label=label,
        confidence=1.0,
        backend=BACKEND_NAME,
    )


def _doc_hash_from_pdf(pdf_path: Path) -> str:
    sha = hashlib.sha256()
    with pdf_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


class GrobidSemanticBackend(SemanticBackend):
    """In-process GROBID backend adapter.

    Talks to a locally running GROBID service over HTTP. The Docker
    container is operator-managed; the adapter only consumes it.
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
        self._client_mod: types.ModuleType | None = None
        self._parser_mod: types.ModuleType | None = None

    def name(self) -> str:
        return BACKEND_NAME

    def version(self) -> str:
        return BACKEND_VERSION

    def is_available(self) -> bool:
        if not (_backend_root() / "grobid_client.py").is_file():
            return False
        try:
            client = self._client()
            endpoint = client.GrobidEndpoint(host=self._host, port=self._port)
            return bool(client.is_alive(endpoint))
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

        client = self._client()
        parser = self._parser()
        endpoint = client.GrobidEndpoint(host=self._host, port=self._port)
        if not client.is_alive(endpoint):
            raise RuntimeError(
                f"GROBID service at {endpoint.base_url} is not reachable"
            )

        tei_xml = client.process_fulltext_document(pdf_path, endpoint)
        parsed = parser.parse_tei(tei_xml)

        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "grobid_tei.xml").write_text(tei_xml, encoding="utf-8")

        body_text = " ".join(hit.marker_text for hit in parsed.markers)
        markers: list[RefMarker] = []
        for hit in parsed.markers:
            marker = _hit_to_marker(hit, self._source_ref, body_text)
            if marker is not None:
                markers.append(marker)

        entities: list[SemanticEntity] = []
        for entry in parsed.bib_entries:
            entity = _bib_entry_to_entity(entry)
            if entity is not None:
                entities.append(entity)

        return CrossReferenceGraph(
            schema_version=CROSS_REF_SCHEMA_VERSION,
            doc_hash=_doc_hash_from_pdf(pdf_path),
            markers=markers,
            edges=[],
            entities=entities,
            backend_versions={BACKEND_NAME: BACKEND_VERSION},
        )

    def _client(self) -> types.ModuleType:
        if self._client_mod is None:
            self._client_mod = _load_module(
                "grobid_client.py", "pdf2md._semantic_grobid_client"
            )
        return self._client_mod

    def _parser(self) -> types.ModuleType:
        if self._parser_mod is None:
            self._parser_mod = _load_module(
                "tei_parser.py", "pdf2md._semantic_grobid_tei_parser"
            )
        return self._parser_mod
