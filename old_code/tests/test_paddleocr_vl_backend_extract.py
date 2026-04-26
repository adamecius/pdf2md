from __future__ import annotations

import sys
import types
from pathlib import Path

import pymupdf

from doc2md.backends.paddleocr_vl_backend import PaddleOcrVlBackend


class _FakePaddleOCR:
    def __init__(self, **_kwargs):
        pass

    def ocr(self, _image_path: str, cls: bool = True):  # noqa: ARG002
        return [[[[[0, 0], [1, 0], [1, 1], [0, 1]], ("hello from paddle", 0.99)]]]


def _make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello")
    doc.save(path)
    doc.close()


def test_paddleocr_vl_extract_returns_docir(tmp_path, monkeypatch) -> None:
    fake_module = types.SimpleNamespace(PaddleOCR=_FakePaddleOCR)
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)

    backend = PaddleOcrVlBackend()
    monkeypatch.setattr(backend, "_load_optional_dependencies", lambda: None)

    input_pdf = tmp_path / "sample.pdf"
    _make_pdf(input_pdf)

    doc = backend.extract(input_pdf, output_dir=tmp_path / "out")

    assert doc.pages
    assert doc.blocks
    assert "hello from paddle" in (doc.blocks[0].text or "")
