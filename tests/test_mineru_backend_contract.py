"""Focused contract tests for optional MinerU backend behavior."""

from __future__ import annotations

import pytest

from doc2md.backends.base import OptionalBackendUnavailable
from doc2md.backends.mineru_backend import MineruBackend


def test_mineru_reports_missing_dependencies_with_install_hint(tmp_path) -> None:
    backend = MineruBackend()

    with pytest.raises(OptionalBackendUnavailable) as exc_info:
        backend.extract(tmp_path / "dummy.pdf", output_dir=tmp_path)

    message = str(exc_info.value).lower()
    assert "optional" in message
    assert "missing dependencies" in message
    assert "pip install" in message
    assert "dedicated environment" in message


def test_mineru_available_false_without_runtime_modules(monkeypatch) -> None:
    backend = MineruBackend()

    monkeypatch.setattr(MineruBackend, "_missing_dependencies", classmethod(lambda cls: ["mineru"]))

    assert backend.available() is False
