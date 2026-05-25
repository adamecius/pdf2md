"""Connector for the GROBID semantic backend.

Mirrors the OCR-backend connector convention so the orchestrator can
discover it via ``importlib.import_module("backend.semantic.grobid
.connector")`` — exactly the same path it already uses for the OCR
backends. The only intentional divergence from the OCR `connect()`
signature is the return type (:class:`SemanticConnectorResult` instead
of :class:`ConnectorResult`), because the semantic layer produces a
:class:`CrossReferenceGraph` rather than per-page extraction IR.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from pdf2md.connectors.common import SemanticConnectorResult
from pdf2md.models.cross_ref import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefMarker,
    RefType,
    SemanticEntity,
)

# Sibling-module imports — `backend/` is not a python package, so we
# manipulate sys.path explicitly. Mirrors the pattern in
# `backend/semantic/grobid/smoke_test.py`.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import grobid_client   # noqa: E402 — local sibling import
import tei_parser      # noqa: E402 — local sibling import


BACKEND = "grobid"
BACKEND_VERSION = "0.1.0"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8070


def _safe_offset(text: str, marker_text: str) -> tuple[int, int]:
    """Approximate ``(start, end)`` for ``marker_text`` inside ``text``.

    GROBID does not report character offsets on ``<ref>`` elements, so
    we scan the concatenated marker text. Unfound markers fall back to
    ``(0, len(marker_text))`` — offsets are informational here, not
    load-bearing for the schema.
    """
    if not marker_text:
        return (0, 0)
    idx = text.find(marker_text)
    if idx < 0:
        return (0, len(marker_text))
    return (idx, idx + len(marker_text))


def _doc_hash_from_pdf(pdf_path: Path) -> str:
    sha = hashlib.sha256()
    with pdf_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


def _resolve_pdf(raw_dir: Path, document_id: str) -> Path | None:
    """Pick up a PDF from ``raw_dir`` using the same lookup as the OCR side.

    Checks (in order) ``input.pdf``, ``raw_dir/<document_id>.pdf``, and
    the first ``*.pdf`` if exactly one is present.
    """
    for candidate in (raw_dir / "input.pdf", raw_dir / f"{document_id}.pdf"):
        if candidate.is_file():
            return candidate
    pdfs = sorted(raw_dir.glob("*.pdf"))
    if len(pdfs) == 1:
        return pdfs[0]
    return None


def connect(
    raw_dir: Path,
    document_id: str,
    out_dir: Path | None = None,
    *,
    pdf_path: Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    source_ref: str = "#/document",
) -> SemanticConnectorResult:
    """Run GROBID against a PDF and return a :class:`CrossReferenceGraph`.

    Args:
        raw_dir: Directory containing the source PDF. Searched in this
            order: ``raw_dir/input.pdf``, ``raw_dir/<document_id>.pdf``,
            then the single ``*.pdf`` in ``raw_dir`` if exactly one is
            present. Ignored when ``pdf_path`` is provided.
        document_id: Stable identifier embedded in marker ``source_ref``
            metadata.
        out_dir: Optional output root. When provided, the TEI XML is
            written to ``<out_dir>/grobid/grobid_tei.xml`` and the
            graph to ``<out_dir>/grobid/cross_references.json``.
        pdf_path: Explicit PDF path (overrides ``raw_dir`` lookup).
        host, port: Where the locally-running GROBID service listens
            (defaults: ``localhost:8070``).
        source_ref: JSON-pointer string stamped on every marker.

    Returns:
        :class:`SemanticConnectorResult` whose ``graph`` is populated
        when GROBID is reachable. When GROBID is unreachable, returns
        an empty graph with a single ``env_not_ready:grobid`` warning.

    Raises:
        FileNotFoundError: If the PDF cannot be located in ``raw_dir``
            and ``pdf_path`` is not given.
    """
    warnings: list[str] = []

    pdf = pdf_path or _resolve_pdf(raw_dir, document_id)
    if pdf is None or not pdf.is_file():
        raise FileNotFoundError(
            f"could not find a PDF in {raw_dir} (and pdf_path was not provided)",
        )

    endpoint = grobid_client.GrobidEndpoint(host=host, port=port)
    if not grobid_client.is_alive(endpoint):
        warnings.append(f"env_not_ready:grobid:{endpoint.base_url}")
        graph = CrossReferenceGraph(
            schema_version=CROSS_REF_SCHEMA_VERSION,
            doc_hash=_doc_hash_from_pdf(pdf),
            markers=[],
            edges=[],
            entities=[],
            backend_versions={BACKEND: BACKEND_VERSION},
        )
        return SemanticConnectorResult(graph=graph, warnings=warnings)

    tei_xml = grobid_client.process_fulltext_document(pdf, endpoint)
    parsed = tei_parser.parse_tei(tei_xml)

    if out_dir is not None:
        backend_dir = out_dir / BACKEND
        backend_dir.mkdir(parents=True, exist_ok=True)
        (backend_dir / "grobid_tei.xml").write_text(tei_xml, encoding="utf-8")

    body_text = " ".join(hit.marker_text for hit in parsed.markers)
    markers: list[RefMarker] = []
    for hit in parsed.markers:
        try:
            marker_type = RefType(hit.marker_type)
        except ValueError:
            warnings.append(f"unknown_marker_type:{hit.marker_type}")
            continue
        markers.append(
            RefMarker(
                source_ref=source_ref,
                marker_text=hit.marker_text,
                marker_type=marker_type,
                char_offset=_safe_offset(body_text, hit.marker_text),
                confidence=1.0,
                backend=BACKEND,
            )
        )

    entities: list[SemanticEntity] = []
    for entry in parsed.bib_entries:
        label = entry.raw_text.strip() or None
        ref_id = entry.ref_id or f"anon-{len(entities)}"
        entities.append(
            SemanticEntity(
                item_ref=f"#/bibliography/{ref_id}",
                entity_type=RefType.BIBLIOGRAPHY,
                label=label,
                confidence=1.0,
                backend=BACKEND,
            )
        )

    graph = CrossReferenceGraph(
        schema_version=CROSS_REF_SCHEMA_VERSION,
        doc_hash=_doc_hash_from_pdf(pdf),
        markers=markers,
        edges=[],
        entities=entities,
        backend_versions={BACKEND: BACKEND_VERSION},
    )

    if out_dir is not None:
        backend_dir = out_dir / BACKEND
        backend_dir.mkdir(parents=True, exist_ok=True)
        (backend_dir / "cross_references.json").write_text(
            graph.model_dump_json(indent=2),
            encoding="utf-8",
        )

    return SemanticConnectorResult(graph=graph, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Connect {BACKEND} semantic backend output to a CrossReferenceGraph")
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--pdf", type=Path, default=None, help="Explicit PDF path (overrides --raw-dir lookup).")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    try:
        result = connect(
            args.raw_dir,
            args.document_id,
            args.out_dir,
            pdf_path=args.pdf,
            host=args.host,
            port=args.port,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — connector top-level guard
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(
        f"{BACKEND} connector: {len(result.graph.markers)} markers, "
        f"{len(result.graph.entities)} entities, "
        f"backend_versions={result.graph.backend_versions}"
    )
    if any(w.startswith("env_not_ready:") for w in result.warnings):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
