"""Tests for deterministic backend DocIR emission."""

from __future__ import annotations

import base64

import pymupdf

from doc2md.backends.deterministic import DeterministicBackend


_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8A9d4AAAAASUVORK5CYII="
)


def _make_sample_pdf(path) -> None:
    doc = pymupdf.open()

    page0 = doc.new_page()
    page0.insert_text((72, 72), "Deterministic text page")
    page0.insert_image(pymupdf.Rect(72, 100, 140, 160), stream=_PNG_1X1)

    doc.new_page()  # blank page with no text layer -> visual route
    doc.save(path)
    doc.close()


def test_deterministic_backend_emits_docir_with_routing_and_media(tmp_path) -> None:
    input_pdf = tmp_path / "sample.pdf"
    out_dir = tmp_path / "out"
    _make_sample_pdf(input_pdf)

    backend = DeterministicBackend()
    doc_ir = backend.extract(input_pdf, output_dir=out_dir)

    assert doc_ir.schema_version == "0.1"
    assert len(doc_ir.pages) == 2
    assert [p.page_index for p in doc_ir.pages] == [0, 1]

    first_page, second_page = doc_ir.pages
    assert first_page.strategy == "deterministic"
    assert second_page.strategy == "visual"
    assert second_page.warnings

    assert doc_ir.blocks
    assert all(0 in block.page_indexes for block in doc_ir.blocks)

    assert doc_ir.media
    media_ids = {m.media_id for m in doc_ir.media}
    referenced_media = {
        media_id
        for block in doc_ir.blocks
        for media_id in block.media_refs
    }
    assert referenced_media.issubset(media_ids)

    assert doc_ir.warnings
    assert doc_ir.backend_runs[0].status == "partial"
