from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pdf2md.models import Document


class Adapter(ABC):
    """Transforms backend-specific output into canonical models."""

    @abstractmethod
    def to_document(self, payload: Any, source_path: str) -> Document:
        """Convert backend payload into a Document."""
        raise NotImplementedError
