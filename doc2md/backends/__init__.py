"""Public backend interfaces and registry helpers."""

from doc2md.backends.base import ExtractionBackend, OptionalBackendUnavailable
from doc2md.backends.deterministic import DeterministicBackend
from doc2md.backends.registry import create_backend, get_backend, list_backends, register_backend

__all__ = [
    "ExtractionBackend",
    "OptionalBackendUnavailable",
    "DeterministicBackend",
    "register_backend",
    "get_backend",
    "list_backends",
    "create_backend",
]
