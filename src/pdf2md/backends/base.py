from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Backend(ABC):
    """Base class for OCR/parser backends."""

    name: str

    @abstractmethod
    def run(self, pdf_path: str) -> Any:
        """Execute backend and return backend-native/raw result."""
        raise NotImplementedError
