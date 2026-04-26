"""Contract tests for the optional PaddleOCR-VL backend adapter."""

from __future__ import annotations

import importlib.util

import pytest

from doc2md.backends.base import OptionalBackendUnavailable
from doc2md.backends.paddleocr_vl_backend import PaddleOcrVlBackend


def _pretend_modules(monkeypatch: pytest.MonkeyPatch, present: set[str]) -> None:
    def fake_find_spec(name: str, *args, **kwargs):
        if name in present:
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def test_available_reports_false_when_dependency_missing(monkeypatch) -> None:
    backend = PaddleOcrVlBackend()

    _pretend_modules(monkeypatch, set())

    assert backend.available() is False


def test_available_requires_paddleocr_and_paddle(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = PaddleOcrVlBackend()

    _pretend_modules(monkeypatch, {"paddleocr", "paddle"})
    assert backend.available()

    _pretend_modules(monkeypatch, {"paddleocr"})
    assert not backend.available()

    _pretend_modules(monkeypatch, {"paddle"})
    assert not backend.available()


def test_extract_raises_optional_backend_unavailable_when_missing_dependency(
    tmp_path,
    monkeypatch,
) -> None:
    backend = PaddleOcrVlBackend()
    _pretend_modules(monkeypatch, set())

    with pytest.raises(OptionalBackendUnavailable) as exc_info:
        backend.extract(tmp_path / "dummy.pdf", output_dir=tmp_path)

    message = str(exc_info.value).lower()
    assert "optional" in message
    assert "offline/local experimentation" in message
    assert "paddleocr" in message
    assert "paddle" in message


def test_extract_runs_when_dependency_present(tmp_path, monkeypatch) -> None:
    backend = PaddleOcrVlBackend()

    _pretend_modules(monkeypatch, {"paddleocr", "paddle"})
    monkeypatch.setattr(backend, "_load_optional_dependencies", lambda: None)

    class _FakePaddleOCR:
        def __init__(self, **_kwargs):
            pass

        def ocr(self, _image_path: str, cls: bool = True):  # noqa: ARG002
            return [[[[[0, 0], [1, 0], [1, 1], [0, 1]], ("ok", 0.99)]]]

    import sys
    import types
    import pymupdf

    fake_module = types.SimpleNamespace(PaddleOCR=_FakePaddleOCR)
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)

    pdf_path = tmp_path / "dummy.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    doc_ir = backend.extract(pdf_path, output_dir=tmp_path)
    assert doc_ir.blocks
