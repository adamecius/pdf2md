from __future__ import annotations

from abc import ABC, abstractmethod

from pdf2md.models import Document


class Backend(ABC):
    """Base class for OCR/parser backends."""

    name: str

    @abstractmethod
    def run(self, pdf_path: str) -> Document:
        """Parse a PDF and return a Document model."""
        raise NotImplementedError
