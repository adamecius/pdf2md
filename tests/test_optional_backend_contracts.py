"""Contract tests for optional backend stubs."""

from __future__ import annotations

import importlib.util

import pytest

from doc2md.backends.base import OptionalBackendUnavailable
from doc2md.backends.mineru_backend import MineruBackend
from doc2md.backends.paddleocr_vl_backend import PaddleOcrVlBackend
from doc2md.backends.registry import create_backend, list_backends


def _pretend_modules(monkeypatch: pytest.MonkeyPatch, present: set[str]) -> None:
    def fake_find_spec(name: str, *args, **kwargs):
        if name in present:
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def test_optional_backends_are_registered_by_install_backend_id() -> None:
    assert "mineru" in list_backends()
    assert "paddleocr_vl" in list_backends()

    assert isinstance(create_backend("mineru"), MineruBackend)
    assert isinstance(create_backend("paddleocr_vl"), PaddleOcrVlBackend)


def test_mineru_availability_matches_sandbox_smoke_test(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = MineruBackend()

    _pretend_modules(monkeypatch, {"mineru"})
    assert backend.available()

    _pretend_modules(monkeypatch, {"magic_pdf"})
    assert not backend.available()


def test_paddleocr_vl_availability_requires_paddleocr_and_paddle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = PaddleOcrVlBackend()

    _pretend_modules(monkeypatch, {"paddleocr", "paddle"})
    assert backend.available()

    _pretend_modules(monkeypatch, {"paddleocr"})
    assert not backend.available()

    _pretend_modules(monkeypatch, {"paddle"})
    assert not backend.available()


@pytest.mark.parametrize("backend", [MineruBackend(), PaddleOcrVlBackend()])
def test_optional_backends_raise_typed_unavailable_error(
    backend,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _pretend_modules(monkeypatch, set())

    with pytest.raises(OptionalBackendUnavailable) as exc_info:
        backend.extract(tmp_path / "sample.pdf")

    message = str(exc_info.value).lower()
    assert "optional" in message
    assert "offline/local experimentation" in message
