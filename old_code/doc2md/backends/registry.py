"""Backend registry for DocIR extraction backends."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import TypeAlias

from doc2md.backends.base import ExtractionBackend
from doc2md.backends.deterministic import DeterministicBackend

BackendFactory: TypeAlias = Callable[[], ExtractionBackend]

_BACKENDS: dict[str, BackendFactory] = {}


def lazy_backend_factory(module_path: str, class_name: str) -> BackendFactory:
    """Return a backend factory that imports its adapter class lazily."""

    def _factory() -> ExtractionBackend:
        module = import_module(module_path)
        backend_cls = getattr(module, class_name)
        return backend_cls()

    return _factory


def register_backend(name: str, backend_cls: BackendFactory) -> None:
    """Register a backend constructor under a unique name."""

    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("backend name must not be empty")
    if normalized in _BACKENDS:
        raise ValueError(f"backend '{normalized}' is already registered")
    _BACKENDS[normalized] = backend_cls


def get_backend(name: str) -> BackendFactory:
    """Return a backend constructor by name."""

    normalized = name.strip().lower()
    try:
        return _BACKENDS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_BACKENDS)) or "none"
        raise KeyError(f"unknown backend '{normalized}'. Available: {available}") from exc


def list_backends() -> list[str]:
    """List registered backend names."""

    return sorted(_BACKENDS)


def create_backend(name: str) -> ExtractionBackend:
    """Instantiate a backend by name."""

    factory = get_backend(name)
    return factory()


def _create_mineru_backend() -> ExtractionBackend:
    """Create MinerU backend via local lazy import."""

    from doc2md.backends.mineru_backend import MineruBackend

    return MineruBackend()


register_backend("deterministic", DeterministicBackend)
register_backend("mineru", _create_mineru_backend)
register_backend(
    "paddleocr_vl",
    lazy_backend_factory("doc2md.backends.paddleocr_vl_backend", "PaddleOcrVlBackend"),
)
