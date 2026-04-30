from __future__ import annotations

from pdf2md.adapters.base import Adapter
from pdf2md.backends.base import Backend
from pdf2md.models import Document


def convert_pdf(pdf_path: str, backend: Backend, adapter: Adapter) -> Document:
    """Placeholder conversion pipeline.

    Future versions will orchestrate multiple backends, adapters,
    and consensus-based fault detection.
    """
    raw_result = backend.run(pdf_path)
    return adapter.to_document(raw_result, source_path=pdf_path)
