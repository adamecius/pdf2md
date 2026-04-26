"""DocIR JSON import/export helpers."""

from __future__ import annotations

from pathlib import Path

from doc2md.ir.schema import DocumentIR
from doc2md.ir.serialise import from_json, to_json


def write_docir(doc: DocumentIR, path: str | Path) -> None:
    """Write a DocIR document to disk as canonical JSON."""

    to_json(doc, path)


def read_docir(path: str | Path) -> DocumentIR:
    """Read a DocIR document from a JSON file on disk."""

    return from_json(path)
