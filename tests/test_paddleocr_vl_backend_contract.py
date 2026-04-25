"""Contract tests for the optional PaddleOCR-VL backend adapter."""

from __future__ import annotations

import pytest

from doc2md.backends.base import OptionalBackendUnavailable
from doc2md.backends.paddleocr_vl_backend import PaddleOcrVlBackend


def test_available_reports_false_when_dependency_missing(monkeypatch) -> None:
    backend = PaddleOcrVlBackend()

    monkeypatch.setattr("importlib.util.find_spec", lambda _: None)

    assert backend.available() is False


def test_extract_raises_optional_backend_unavailable_when_missing_dependency(
    tmp_path,
    monkeypatch,
) -> None:
    backend = PaddleOcrVlBackend()
    monkeypatch.setattr("importlib.util.find_spec", lambda _: None)

    with pytest.raises(OptionalBackendUnavailable) as exc_info:
        backend.extract(tmp_path / "dummy.pdf", output_dir=tmp_path)

    message = str(exc_info.value).lower()
    assert "optional" in message
    assert "offline/local experimentation" in message
    assert "paddleocr" in message


def test_extract_still_reports_stub_when_dependency_present(tmp_path, monkeypatch) -> None:
    backend = PaddleOcrVlBackend()

    monkeypatch.setattr("importlib.util.find_spec", lambda _: object())
    monkeypatch.setattr("builtins.__import__", lambda *args, **kwargs: object())

    with pytest.raises(RuntimeError) as exc_info:
        backend.extract(tmp_path / "dummy.pdf", output_dir=tmp_path)

    assert "not implemented" in str(exc_info.value).lower()
