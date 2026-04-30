from __future__ import annotations

from pdf2md.backends.base import Backend
from pdf2md.models import Document


def convert_pdf(pdf_path: str, backend: Backend) -> Document:
    """Placeholder conversion pipeline.

    Future versions will orchestrate multiple backends, adapters,
    and consensus-based fault detection.
    """
    return backend.run(pdf_path)
