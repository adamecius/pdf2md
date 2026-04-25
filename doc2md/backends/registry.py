"""Backend registry for DocIR extraction backends."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from doc2md.backends.base import ExtractionBackend
from doc2md.backends.deterministic import DeterministicBackend

BackendFactory: TypeAlias = Callable[[], ExtractionBackend]

_BACKENDS: dict[str, BackendFactory] = {}


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


register_backend("deterministic", DeterministicBackend)
