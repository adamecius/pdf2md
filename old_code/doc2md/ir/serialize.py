"""DocIR serialization helpers for dict and JSON payloads."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from doc2md.ir.schema import BackendRun, BlockIR, DocumentIR, MediaRef, PageIR, Provenance


def to_dict(obj: DocumentIR) -> dict[str, Any]:
    """Convert a DocIR dataclass object into a plain dictionary."""

    if not is_dataclass(obj):
        raise TypeError("to_dict expects a dataclass instance")
    return asdict(obj)


def _provenance_from_dict(data: dict[str, Any]) -> Provenance:
    return Provenance(**data)


def _block_from_dict(data: dict[str, Any]) -> BlockIR:
    payload = dict(data)
    payload["provenance"] = [_provenance_from_dict(item) for item in payload.get("provenance", [])]
    return BlockIR(**payload)


def from_dict(data: dict[str, Any]) -> DocumentIR:
    """Build a DocumentIR object from a dict payload."""

    payload = dict(data)
    payload["pages"] = [PageIR(**item) for item in payload.get("pages", [])]
    payload["blocks"] = [_block_from_dict(item) for item in payload.get("blocks", [])]
    payload["media"] = [MediaRef(**item) for item in payload.get("media", [])]
    payload["backend_runs"] = [BackendRun(**item) for item in payload.get("backend_runs", [])]
    return DocumentIR(**payload)


def to_json(doc: DocumentIR, path: str | Path) -> None:
    """Write a DocumentIR object as pretty JSON to disk."""

    out_path = Path(path)
    out_path.write_text(json.dumps(to_dict(doc), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def from_json(path: str | Path) -> DocumentIR:
    """Load a DocumentIR JSON file from disk."""

    in_path = Path(path)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    return from_dict(data)
