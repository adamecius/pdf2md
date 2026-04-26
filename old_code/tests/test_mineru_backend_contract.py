"""Focused contract tests for optional MinerU backend behavior."""

from __future__ import annotations

import importlib.util

import pytest

from doc2md.backends.base import OptionalBackendUnavailable
from doc2md.backends.mineru_backend import MineruBackend


def _pretend_modules(monkeypatch: pytest.MonkeyPatch, present: set[str]) -> None:
    def fake_find_spec(name: str, *args, **kwargs):
        if name in present:
            return object()
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def test_mineru_reports_missing_dependencies_with_install_hint(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = MineruBackend()
    _pretend_modules(monkeypatch, set())

    with pytest.raises(OptionalBackendUnavailable) as exc_info:
        backend.extract(tmp_path / "dummy.pdf", output_dir=tmp_path)

    message = str(exc_info.value).lower()
    assert "optional" in message
    assert "missing dependencies" in message
    assert "pip install" in message
    assert "dedicated environment" in message


def test_mineru_available_false_without_runtime_modules(monkeypatch) -> None:
    backend = MineruBackend()

    _pretend_modules(monkeypatch, set())

    assert backend.available() is False


def test_mineru_availability_matches_sandbox_smoke_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = MineruBackend()

    _pretend_modules(monkeypatch, {"mineru"})
    assert backend.available()

    _pretend_modules(monkeypatch, {"magic_pdf"})
    assert not backend.available()
