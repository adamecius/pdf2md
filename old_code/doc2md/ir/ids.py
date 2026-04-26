"""Stable identifier helpers for DocIR entities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def make_document_id(path: str) -> str:
    """Build a stable document ID from the normalized source path string."""

    normalized = Path(path).as_posix().strip()
    return f"doc_{_short_hash(normalized)}"


def make_page_id(page_index: int) -> str:
    """Build a stable page ID from a 0-based page index."""

    return f"page_{page_index:04d}"


def make_block_id(
    page_index: int,
    order: int,
    text: str | None = None,
    bbox: list[float] | tuple[float, ...] | None = None,
) -> str:
    """Build a deterministic block ID using page/order and optional content hints."""

    basis = f"p={page_index}|o={order}|t={text or ''}|b={list(bbox) if bbox is not None else ''}"
    return f"blk_{page_index:04d}_{order:04d}_{_short_hash(basis)}"


def make_media_id(page_index: int, kind: str, index: int) -> str:
    """Build a deterministic media ID from page, type, and in-page index."""

    return f"med_{page_index:04d}_{kind}_{index:04d}"
