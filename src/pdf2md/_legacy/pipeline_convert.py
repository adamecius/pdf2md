from __future__ import annotations

from pdf2md._legacy.adapters_base import Adapter
from pdf2md._legacy.backends_base import Backend
from pdf2md._legacy.models_document import Document


def convert_pdf(pdf_path: str, backend: Backend, adapter: Adapter) -> Document:
    """Placeholder conversion pipeline.

    Future versions will orchestrate multiple backends, adapters,
    and consensus-based fault detection.
    """
    raw_result = backend.run(pdf_path)
    return adapter.to_document(raw_result, source_path=pdf_path)
