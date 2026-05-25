"""Connector for the DeepSeek-VL2 semantic backend.

Mirrors the OCR-backend connector convention. The vlm runtime depends
on torch + the deepseek-vl2 source package (both installed inside the
``pdf2md-deepseek-vl2`` conda env by ``setup.py``), so this connector
deliberately imports those modules at runtime, NOT at module top
level — it is intended to be invoked inside the VLM env. Loading the
connector from the main ``pdf2md`` env (e.g. via the orchestrator's
``importlib.import_module`` discovery path) is supported as long as
the caller does not invoke :func:`connect`; the discovery just inspects
``connect`` / ``BACKEND`` etc.

The Plan 006 ``VlmSemanticBackend`` adapter under
``src/pdf2md/semantic/vlm_adapter.py`` shells out to ``smoke_test.py``
via the VLM env's python — that subprocess pattern is preserved, but
the adapter now delegates to ``smoke_test.py`` which in turn calls the
in-env modules. This connector exposes the same callable surface as
the OCR connectors so the orchestrator's discovery code does not need
to special-case the semantic side.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from pdf2md.connectors.common import SemanticConnectorResult
from pdf2md.models.cross_ref import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefMarker,
    RefType,
)

# Sibling-module access; only loaded by name when connect() runs, so a
# missing torch in the caller's env doesn't break module import.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))


BACKEND = "vlm"
BACKEND_VERSION = "0.1.0"


def _hash_image(image_path: Path) -> str:
    sha = hashlib.sha256()
    with image_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


def _resolve_image(raw_dir: Path, document_id: str) -> Path | None:
    """Pick up an image from ``raw_dir`` using a deterministic lookup."""
    for candidate in (
        raw_dir / "page.png",
        raw_dir / f"{document_id}.png",
        raw_dir / "input.png",
    ):
        if candidate.is_file():
            return candidate
    pngs = sorted(raw_dir.glob("*.png")) + sorted(raw_dir.glob("*.jpg")) + sorted(raw_dir.glob("*.jpeg"))
    if len(pngs) == 1:
        return pngs[0]
    return None


def _marker_dict_to_model(raw: dict[str, Any], source_ref: str) -> RefMarker | None:
    try:
        marker_type = RefType(raw.get("marker_type", ""))
    except ValueError:
        return None
    marker_text = str(raw.get("marker_text") or "").strip()
    if not marker_text:
        return None
    raw_offset = raw.get("char_offset")
    if isinstance(raw_offset, (list, tuple)) and len(raw_offset) == 2:
        offset = (int(raw_offset[0]), int(raw_offset[1]))
    else:
        offset = (0, len(marker_text))
    confidence_raw = raw.get("confidence", 0.8)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.8
    confidence = max(0.0, min(1.0, confidence))
    return RefMarker(
        source_ref=source_ref,
        marker_text=marker_text,
        marker_type=marker_type,
        char_offset=offset,
        confidence=confidence,
        backend=BACKEND,
    )


def connect(
    raw_dir: Path,
    document_id: str,
    out_dir: Path | None = None,
    *,
    image_path: Path | None = None,
    model_id: str | None = None,
    source_ref: str = "#/document",
) -> SemanticConnectorResult:
    """Run DeepSeek-VL2 against a page image and return a graph.

    Must be invoked inside the ``pdf2md-deepseek-vl2`` conda env (the
    upstream package is the only place ``deepseek_vl_v2`` is registered
    as a transformers architecture). Calling this from another env
    raises :class:`ImportError`.

    Args:
        raw_dir: Directory containing the page image. Searched in this
            order: ``page.png``, ``<document_id>.png``, ``input.png``,
            then the single ``*.png`` / ``*.jpg`` if exactly one is
            present. Ignored when ``image_path`` is provided.
        document_id: Stable identifier embedded in marker ``source_ref``
            metadata.
        out_dir: Optional output root. When provided, the graph is
            written to ``<out_dir>/vlm/cross_references.json``.
        image_path: Explicit image path (overrides ``raw_dir`` lookup).
        model_id: Override the HuggingFace model id. Default comes from
            ``vlm_client.VlmSettings.model_id``.
        source_ref: JSON-pointer string stamped on every marker.

    Returns:
        :class:`SemanticConnectorResult`.

    Raises:
        FileNotFoundError: If the image cannot be located.
        ImportError: If called outside the ``pdf2md-deepseek-vl2`` env.
    """
    warnings: list[str] = []

    img = image_path or _resolve_image(raw_dir, document_id)
    if img is None or not img.is_file():
        raise FileNotFoundError(
            f"could not find a page image in {raw_dir} (and image_path was not provided)",
        )

    # Deferred imports — only valid inside the pdf2md-deepseek-vl2 env.
    import vlm_client  # noqa: E402 — sibling import

    kwargs: dict[str, Any] = {}
    if model_id is not None:
        kwargs["model_id"] = model_id
    settings = vlm_client.VlmSettings(**kwargs)
    model, processor = vlm_client.load_model(settings)
    out = vlm_client.extract_markers(
        img,
        model=model,
        processor=processor,
        settings=settings,
    )

    if out.get("parse_error"):
        warnings.append(f"parse_error:{out['parse_error']}")

    markers: list[RefMarker] = []
    for raw in out.get("markers", []) or []:
        if not isinstance(raw, dict):
            continue
        marker = _marker_dict_to_model(raw, source_ref)
        if marker is not None:
            markers.append(marker)

    graph = CrossReferenceGraph(
        schema_version=CROSS_REF_SCHEMA_VERSION,
        doc_hash=_hash_image(img),
        markers=markers,
        edges=[],
        entities=[],
        backend_versions={BACKEND: settings.model_id},
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
    parser.add_argument("--image", type=Path, default=None, help="Explicit image path (overrides --raw-dir lookup).")
    parser.add_argument("--model-id", default=None)
    args = parser.parse_args(argv)

    try:
        result = connect(
            args.raw_dir,
            args.document_id,
            args.out_dir,
            image_path=args.image,
            model_id=args.model_id,
        )
    except ImportError as exc:
        print(f"env_not_ready: {exc}", file=sys.stderr)
        return 3
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
        f"backend_versions={result.graph.backend_versions}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
