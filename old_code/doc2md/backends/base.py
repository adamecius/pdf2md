"""Backend interface contracts for DocIR extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from doc2md.ir import DocumentIR


class OptionalBackendUnavailable(RuntimeError):
    """Raised when an optional backend is requested but not installed."""


@runtime_checkable
class ExtractionBackend(Protocol):
    """Contract for backends that emit DocIR from an input document."""

    name: str

    def available(self) -> bool:
        """Return True when backend dependencies are available locally."""

    def extract(
        self,
        input_path: Path,
        output_dir: Path | None = None,
        options: dict[str, Any] | None = None,
    ) -> DocumentIR:
        """Extract a document into canonical DocIR."""
