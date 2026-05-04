#!/usr/bin/env python3
"""pdf2ir_deeepseek.py - DeepSeek-OCR-2 PDF to page-first extraction IR.

This script is an adapter, not a Markdown converter. It writes our extraction
IR under:

  .current/extraction_ir/<pdf_stem>/
    manifest.json
    pages/page_0000.json
    page_images/page_0000.png
    raw_pages/page_0000.det.mmd
    raw_pages/page_0000.clean.mmd
    raw_pages/page_0000.capture.json
    official_results/page_0000/
    media/

Markdown/text produced by DeepSeek-OCR-2 is preserved as evidence inside the IR.
Final Markdown export should be handled by a separate renderer after consensus
or semantic document compilation.
"""

from __future__ import annotations
from pathlib import Path
ADAPTER_DIR = Path(__file__).resolve().parent
DEFAULT_LOCAL_MODEL_ROOT = ADAPTER_DIR / ".local_models" / "deepseek"

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


_MODELS = {
    "deepseek-ai/DeepSeek-OCR-2": {
        "repo_url": "https://github.com/deepseek-ai/DeepSeek-OCR-2",
        "image_size": 768,
        "extra_infer": {},
    },
}

DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-OCR-2"
#DEFAULT_MODELS_DIR = ".local_models/deepseek"
#DEFAULT_REPO_CACHE = ".local_models/deepseek/.repos"
DEFAULT_MODELS_DIR = str(DEFAULT_LOCAL_MODEL_ROOT)
DEFAULT_REPO_CACHE = str(DEFAULT_LOCAL_MODEL_ROOT / ".repos")

DEFAULT_DPI = 144
DEFAULT_BASE_SIZE = 1024
DEFAULT_CURRENT_DIR = ".current"
DEFAULT_BACKEND_ID = "deepseek_ocr_2"
DEFAULT_BACKEND_NAME = "deepseek_ocr_2"
DEFAULT_ADAPTER_NAME = "deepseek_ocr_2_adapter"
DEFAULT_ADAPTER_VERSION = "0.5.0"

PROMPT_DOCUMENT = "<image>\n<|grounding|>Convert the document to markdown. "
PROMPT_FREE_OCR = "<image>\nFree OCR. "

REF_DET_RE = re.compile(
    r"<\|ref\|>(.*?)<\|/ref\|>\s*<\|det\|>(.*?)<\|/det\|>",
    re.DOTALL,
)
TAG_RE = re.compile(
    r"<\|ref\|>.*?<\|/ref\|>\s*<\|det\|>.*?<\|/det\|>",
    re.DOTALL,
)
TEXT_OUTPUT_SUFFIXES = {".mmd", ".md", ".markdown", ".txt"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_run_id() -> str:
    return f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def clean_ocr2_markdown(raw_text: str) -> str:
    cleaned = TAG_RE.sub("", raw_text or "")
    cleaned = cleaned.replace("<--- Page Split --->", "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def snapshot_text_outputs(root: Path) -> dict[str, tuple[int, int]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_OUTPUT_SUFFIXES:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        snapshot[str(path)] = (int(st.st_mtime_ns), int(st.st_size))
    return snapshot


def read_new_text_output(root: Path, before: dict[str, tuple[int, int]]) -> tuple[str, Path | None]:
    if not root.exists():
        return "", None

    candidates: list[tuple[int, int, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_OUTPUT_SUFFIXES:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        current = (int(st.st_mtime_ns), int(st.st_size))
        if before.get(str(path)) == current:
            continue
        if st.st_size <= 0:
            continue
        candidates.append((int(st.st_mtime_ns), int(st.st_size), path))

    if not candidates:
        return "", None

    candidates.sort(reverse=True)
    chosen = candidates[0][2]
    try:
        return chosen.read_text(encoding="utf-8"), chosen
    except UnicodeDecodeError:
        return chosen.read_text(encoding="utf-8", errors="replace"), chosen


def coerce_infer_markdown(
    result: Any,
    official_output_dir: Path,
    before: dict[str, tuple[int, int]],
) -> tuple[str, str, Path | None]:
    """Capture OCR text from return value or official saved output file."""
    if isinstance(result, str):
        if result.strip() and result.strip() != "None":
            return result, "return_value", None
    elif result is not None:
        text = str(result)
        if text.strip() and text.strip() != "None":
            return text, "return_value_coerced", None

    saved_text, saved_path = read_new_text_output(official_output_dir, before)
    if saved_text.strip():
        return saved_text, "official_saved_file", saved_path

    return "", "empty", None


def bbox_999_to_1000(coords: list[float]) -> list[float]:
    if len(coords) != 4:
        raise ValueError(f"Expected four bbox values, got {coords!r}")
    x0, y0, x1, y1 = [float(v) for v in coords]
    scale = 1000.0 / 999.0
    box = [clamp(v * scale, 0.0, 1000.0) for v in (x0, y0, x1, y1)]
    if box[2] < box[0]:
        box[0], box[2] = box[2], box[0]
    if box[3] < box[1]:
        box[1], box[3] = box[3], box[1]
    return [round(v, 3) for v in box]


def bbox_999_to_pixels(
    coords: list[float],
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = [float(v) for v in coords]
    left = int(clamp(round(x0 / 999.0 * image_width), 0, image_width))
    top = int(clamp(round(y0 / 999.0 * image_height), 0, image_height))
    right = int(clamp(round(x1 / 999.0 * image_width), 0, image_width))
    bottom = int(clamp(round(y1 / 999.0 * image_height), 0, image_height))
    if right < left:
        left, right = right, left
    if bottom < top:
        top, bottom = bottom, top
    return left, top, right, bottom


def classify_ocr2_label(label: str) -> tuple[str, str | None, str, str]:
    native = normalise_text(label).replace(" ", "_") or "unknown"
    mapping: dict[str, tuple[str, str | None, str, str]] = {
        "title": ("title", None, "title", "title"),
        "doc_title": ("title", "doc_title", "title", "title"),
        "section_header": ("section_header", None, "section_header", "section_header"),
        "heading": ("section_header", "heading", "section_header", "section_header"),
        "text": ("paragraph", None, "body_text", "text"),
        "paragraph": ("paragraph", None, "body_text", "text"),
        "body_text": ("paragraph", "body_text", "body_text", "text"),
        "list": ("list_item", "list", "list_item", "list_item"),
        "list_item": ("list_item", None, "list_item", "list_item"),
        "table": ("table", None, "table", "table"),
        "formula": ("formula", None, "formula", "formula"),
        "equation": ("formula", "equation", "formula", "formula"),
        "math": ("formula", "math", "formula", "formula"),
        "image": ("picture", "image", "picture", "picture"),
        "picture": ("picture", None, "picture", "picture"),
        "figure": ("picture", "figure", "picture", "picture"),
        "chart": ("chart", None, "chart", "picture"),
        "caption": ("caption", None, "caption", "caption"),
        "header": ("page_header", None, "page_header", "page_header"),
        "footer": ("page_footer", None, "page_footer", "page_footer"),
        "page_number": ("page_number", None, "page_number", "page_number"),
        "footnote": ("footnote", None, "footnote", "footnote"),
        "code": ("code", None, "code", "code"),
        "algorithm": ("algorithm", None, "algorithm", "code"),
        "seal": ("seal", None, "seal", "picture"),
    }
    return mapping.get(native, ("unknown", f"ocr2_{native}", native, "text"))


def parse_ocr2_ref_det(raw_text: str) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    last_end = 0

    for match_index, match in enumerate(REF_DET_RE.finditer(raw_text or "")):
        label = (match.group(1) or "unknown").strip()
        coords_raw = (match.group(2) or "").strip()
        preceding_fragment = clean_ocr2_markdown((raw_text or "")[last_end:match.start()])
        last_end = match.end()

        try:
            parsed = ast.literal_eval(coords_raw)
        except Exception:
            continue
        if not isinstance(parsed, list):
            continue

        boxes = parsed if parsed and isinstance(parsed[0], list) else [parsed]
        for box_index, box in enumerate(boxes):
            if not isinstance(box, list) or len(box) != 4:
                continue
            try:
                native_bbox = [float(v) for v in box]
                norm_bbox = bbox_999_to_1000(native_bbox)
            except Exception:
                continue

            block_type, subtype, semantic_role, docling_hint = classify_ocr2_label(label)
            regions.append(
                {
                    "match_index": match_index,
                    "box_index": box_index,
                    "label": label,
                    "native_label": normalise_text(label).replace(" ", "_") or "unknown",
                    "native_bbox": native_bbox,
                    "bbox": norm_bbox,
                    "fragment": preceding_fragment,
                    "type": block_type,
                    "subtype": subtype,
                    "semantic_role": semantic_role,
                    "docling_label_hint": docling_hint,
                }
            )
    return regions


# ---------------------------------------------------------------------------
# Markdown-to-provisional-IR enrichment
# ---------------------------------------------------------------------------
# DeepSeek-OCR-2 often writes useful Markdown/HTML but no ref/det geometry. For
# Docling compilation we still want semantic page items, even if geometry is
# absent. These helpers parse the generated page text into provisional blocks.

HTML_TABLE_RE = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
DISPLAY_FORMULA_RE = re.compile(r"^\s*\\\[(.*?)\\\]\s*$", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_ITEM_RE = re.compile(r"^\s*(?:\d+\.|[-*])\s+.+", re.DOTALL)
CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.|Table)\s+\d+(?:\.\d+)?\b", re.IGNORECASE)


def strip_html_tags(html: str) -> str:
    text = HTML_TAG_RE.sub(" ", html or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class SimpleHTMLTableParser:
    """Tiny forgiving table parser for OCR-generated <table> fragments."""

    def __init__(self) -> None:
        from html.parser import HTMLParser

        class _Parser(HTMLParser):
            def __init__(self, outer: "SimpleHTMLTableParser") -> None:
                super().__init__()
                self.outer = outer
                self.in_cell = False
                self.current_cell: list[str] = []
                self.current_row: list[dict[str, Any]] = []
                self.current_tag = "td"

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                tag_l = tag.lower()
                if tag_l == "tr":
                    self.current_row = []
                elif tag_l in {"td", "th"}:
                    self.in_cell = True
                    self.current_cell = []
                    self.current_tag = tag_l

            def handle_data(self, data: str) -> None:
                if self.in_cell:
                    self.current_cell.append(data)

            def handle_endtag(self, tag: str) -> None:
                tag_l = tag.lower()
                if tag_l in {"td", "th"} and self.in_cell:
                    txt = re.sub(r"\s+", " ", "".join(self.current_cell)).strip()
                    self.current_row.append({"text": txt, "is_header": self.current_tag == "th"})
                    self.in_cell = False
                    self.current_cell = []
                elif tag_l == "tr":
                    if self.current_row:
                        self.outer.rows.append(self.current_row)
                    self.current_row = []

        self.rows: list[list[dict[str, Any]]] = []
        self.parser = _Parser(self)

    def feed(self, html: str) -> None:
        try:
            self.parser.feed(html)
            self.parser.close()
        except Exception:
            pass


def table_cells_from_html(html: str, table_id: str) -> tuple[list[dict[str, Any]], int | None, int | None]:
    parser = SimpleHTMLTableParser()
    parser.feed(html)
    cells: list[dict[str, Any]] = []
    max_cols = 0
    for r, row in enumerate(parser.rows):
        max_cols = max(max_cols, len(row))
        for c, cell in enumerate(row):
            text = cell.get("text", "")
            cells.append(
                {
                    "cell_id": f"{table_id}_r{r:04d}_c{c:04d}",
                    "row_index": r,
                    "col_index": c,
                    "row_span": 1,
                    "col_span": 1,
                    "is_header": bool(cell.get("is_header")) or r == 0,
                    "text": text,
                    "normalised_text": normalise_text(text),
                    "html": None,
                    "geometry": None,
                    "confidence": {"text": None, "structure": None},
                }
            )
    return cells, (len(parser.rows) if parser.rows else None), (max_cols or None)


def markdown_source_ref(
    *,
    source_ref_id: str,
    backend_id: str,
    backend_name: str,
    raw_file: Path,
    clean_file: Path,
    raw_id: str,
    native_type: str,
    char_start: int | None,
    char_end: int | None,
) -> dict[str, Any]:
    ref = source_ref(
        source_ref_id=source_ref_id,
        backend_id=backend_id,
        backend_name=backend_name,
        raw_file=raw_file,
        clean_file=clean_file,
        raw_id=raw_id,
        native_type=native_type,
    )
    ref.update(
        {
            "clean_char_start": char_start,
            "clean_char_end": char_end,
            "native_coordinate_space": None,
            "native_bbox": None,
        }
    )
    return ref


def classify_markdown_chunk(chunk: str) -> tuple[str, str | None, str, str, int | None, str]:
    stripped = chunk.strip()
    heading = HEADING_RE.match(stripped)
    if heading:
        level = len(heading.group(1))
        text = heading.group(2).strip()
        block_type = "title" if level == 1 else "section_header"
        return block_type, f"markdown_h{level}", block_type, block_type, level, text

    if DISPLAY_FORMULA_RE.match(stripped):
        latex = DISPLAY_FORMULA_RE.match(stripped).group(1).strip()
        return "formula", "display", "formula", "formula", None, latex

    img = MD_IMAGE_RE.fullmatch(stripped)
    if img:
        return "picture", "markdown_image_reference", "picture", "picture", None, stripped

    if CAPTION_RE.match(stripped):
        return "caption", None, "caption", "caption", None, stripped

    if LIST_ITEM_RE.match(stripped):
        return "list_item", None, "list_item", "list_item", None, stripped

    return "paragraph", None, "body_text", "text", None, stripped


def make_markdown_enriched_block(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    order: int,
    block_index: int,
    block_type: str,
    subtype: str | None,
    semantic_role: str,
    docling_hint: str,
    heading_level: int | None,
    text: str,
    raw_markdown: str,
    raw_det_path: Path,
    clean_path: Path,
    char_start: int | None,
    char_end: int | None,
) -> dict[str, Any]:
    block_id = f"{page_id}_m{block_index:04d}"
    normalised = normalise_text(text)
    refs = base_refs()
    table_obj = None
    formula_obj = None
    media_obj = None
    content_html = None
    content_latex = None

    if block_type == "table":
        table_id = f"{block_id}_table"
        cells, rows, cols = table_cells_from_html(raw_markdown, table_id)
        table_obj = {
            "table_id": table_id,
            "representation": "html_from_generated_markdown",
            "html": raw_markdown,
            "markdown": raw_markdown,
            "caption_block_ids": [],
            "footnote_block_ids": [],
            "rows": rows,
            "cols": cols,
            "cells": cells,
            "confidence": {"overall": None, "structure": None, "text": None},
        }
        refs["table_ref"] = table_id
        content_html = raw_markdown

    if block_type == "formula":
        formula_id = f"{block_id}_formula"
        formula_obj = {
            "formula_id": formula_id,
            "kind": "display",
            "latex": text,
            "text": text,
            "mathml": None,
            "image_ref": None,
            "confidence": {"overall": None, "recognition": None},
        }
        refs["formula_ref"] = formula_id
        content_latex = text

    if block_type == "picture":
        m = MD_IMAGE_RE.search(raw_markdown)
        href = m.group(1) if m else None
        media_obj = {
            "media_id": f"{block_id}_media",
            "kind": "image_reference",
            "path": href,
            "mime_type": None,
            "caption_block_ids": [],
            "alt_text": None,
            "geometry": None,
            "sha256": None,
        }
        refs["media_ref"] = media_obj["media_id"]

    return {
        "block_id": block_id,
        "page_id": page_id,
        "document_id": source_id,
        "backend_id": backend_id,
        "page_index": page_index,
        "page_number": page_number,
        "order": order,
        "type": block_type,
        "subtype": subtype,
        "semantic_role": semantic_role,
        "docling_label_hint": docling_hint,
        "docling": {
            "label_hint": docling_hint,
            "level_hint": heading_level,
            "provenance_ready": True,
            "excluded_from_docling": False,
            "notes": ["Provisional semantic block parsed from DeepSeek-OCR-2 generated Markdown; geometry is unavailable."],
        },
        "geometry": None,
        "content": {
            "text": text,
            "normalised_text": normalised,
            "markdown": raw_markdown,
            "html": content_html,
            "latex": content_latex,
            "language": None,
            "char_span": {"start": char_start, "end": char_end},
        },
        "structure": {
            "heading_level": heading_level,
            "list": None,
            "caption_for": None,
            "footnote_marker": None,
            "parent_block_id": f"{page_id}_b0000",
            "child_block_ids": [],
        },
        "refs": refs,
        "lines": [],
        "spans": [],
        "table": table_obj,
        "formula": formula_obj,
        "media": media_obj,
        "confidence": {
            "overall": None,
            "layout": None,
            "text": None,
            "reading_order": 0.65,
            "structure": 0.55,
        },
        "comparison": {
            "compare_as": "semantic_markdown_block",
            "text_hash": sha256_text(normalised),
            "geometry_hash": None,
            "candidate_group_id": None,
            "match_keys": ["page_index", "type", "normalised_text"],
        },
        "source_refs": [
            markdown_source_ref(
                source_ref_id=f"{block_id}_src0",
                backend_id=backend_id,
                backend_name=backend_name,
                raw_file=raw_det_path,
                clean_file=clean_path,
                raw_id=f"page_{page_index}_markdown_block_{block_index}",
                native_type=f"markdown_enrichment:{block_type}",
                char_start=char_start,
                char_end=char_end,
            )
        ],
        "flags": [
            {
                "code": "geometry_missing",
                "severity": "medium",
                "message": "Block was parsed from generated Markdown and has no backend geometry.",
            }
        ],
    }


def iter_markdown_segments(markdown: str) -> list[dict[str, Any]]:
    """Split Markdown into text and table segments, preserving character spans."""
    segments: list[dict[str, Any]] = []
    pos = 0
    for table_match in HTML_TABLE_RE.finditer(markdown or ""):
        if table_match.start() > pos:
            segments.append({"kind": "text", "text": markdown[pos:table_match.start()], "start": pos, "end": table_match.start()})
        segments.append({"kind": "table", "text": table_match.group(0), "start": table_match.start(), "end": table_match.end()})
        pos = table_match.end()
    if pos < len(markdown or ""):
        segments.append({"kind": "text", "text": markdown[pos:], "start": pos, "end": len(markdown)})
    return segments


def split_text_segment_into_chunks(segment: dict[str, Any]) -> list[dict[str, Any]]:
    text = segment["text"]
    base = int(segment["start"])
    chunks: list[dict[str, Any]] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, re.DOTALL):
        chunk = match.group(0).strip()
        if not chunk:
            continue
        start = base + match.start()
        end = base + match.end()
        chunks.append({"kind": "text", "text": chunk, "start": start, "end": end})
    return chunks


def create_markdown_semantic_blocks(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    clean_markdown: str,
    raw_det_path: Path,
    clean_path: Path,
    start_order: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    blocks: list[dict[str, Any]] = []
    stats = {
        "semantic_block_count": 0,
        "table_block_count": 0,
        "formula_block_count": 0,
        "heading_block_count": 0,
        "picture_reference_count": 0,
        "caption_block_count": 0,
        "list_item_block_count": 0,
        "paragraph_block_count": 0,
    }

    next_index = 0
    next_order = start_order
    for segment in iter_markdown_segments(clean_markdown):
        if segment["kind"] == "table":
            text = strip_html_tags(segment["text"])
            block = make_markdown_enriched_block(
                page_id=page_id,
                source_id=source_id,
                backend_id=backend_id,
                backend_name=backend_name,
                page_index=page_index,
                page_number=page_number,
                order=next_order,
                block_index=next_index,
                block_type="table",
                subtype="html_from_markdown",
                semantic_role="table",
                docling_hint="table",
                heading_level=None,
                text=text,
                raw_markdown=segment["text"],
                raw_det_path=raw_det_path,
                clean_path=clean_path,
                char_start=segment["start"],
                char_end=segment["end"],
            )
            blocks.append(block)
            stats["table_block_count"] += 1
            next_index += 1
            next_order += 1
            continue

        for chunk in split_text_segment_into_chunks(segment):
            chunk_text = chunk["text"].strip()
            if not chunk_text:
                continue
            block_type, subtype, semantic_role, docling_hint, heading_level, content_text = classify_markdown_chunk(chunk_text)
            block = make_markdown_enriched_block(
                page_id=page_id,
                source_id=source_id,
                backend_id=backend_id,
                backend_name=backend_name,
                page_index=page_index,
                page_number=page_number,
                order=next_order,
                block_index=next_index,
                block_type=block_type,
                subtype=subtype,
                semantic_role=semantic_role,
                docling_hint=docling_hint,
                heading_level=heading_level,
                text=content_text,
                raw_markdown=chunk_text,
                raw_det_path=raw_det_path,
                clean_path=clean_path,
                char_start=chunk["start"],
                char_end=chunk["end"],
            )
            blocks.append(block)
            if block_type in {"title", "section_header"}:
                stats["heading_block_count"] += 1
            elif block_type == "formula":
                stats["formula_block_count"] += 1
            elif block_type == "picture":
                stats["picture_reference_count"] += 1
            elif block_type == "caption":
                stats["caption_block_count"] += 1
            elif block_type == "list_item":
                stats["list_item_block_count"] += 1
            elif block_type == "paragraph":
                stats["paragraph_block_count"] += 1
            next_index += 1
            next_order += 1

    stats["semantic_block_count"] = len(blocks)
    return blocks, stats


def link_captions_to_nearby_objects(blocks: list[dict[str, Any]]) -> None:
    """Best-effort caption linking for provisional Markdown blocks."""
    for i, block in enumerate(blocks):
        if block.get("type") != "caption":
            continue
        text = (block.get("content", {}) or {}).get("text", "") or ""
        caption_kind = "table" if text.lower().startswith("table") else "picture" if text.lower().startswith(("figure", "fig.")) else None
        if caption_kind is None:
            continue

        target_index = None
        search_range = range(i + 1, min(len(blocks), i + 4)) if caption_kind == "table" else range(max(0, i - 3), i)
        for j in search_range:
            if blocks[j].get("type") == caption_kind:
                target_index = j
                break
        if target_index is None and caption_kind == "picture":
            for j in range(i + 1, min(len(blocks), i + 4)):
                if blocks[j].get("type") == "picture":
                    target_index = j
                    break
        if target_index is None:
            continue

        target = blocks[target_index]
        block.setdefault("refs", {}).setdefault("caption_for_refs", []).append(target["block_id"])
        block.setdefault("structure", {})["caption_for"] = target["block_id"]
        if target.get("table"):
            target["table"].setdefault("caption_block_ids", []).append(block["block_id"])
        if target.get("media"):
            target["media"].setdefault("caption_block_ids", []).append(block["block_id"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run DeepSeek-OCR-2 and write page-first extraction IR. No final Markdown export.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument("-i", "--input", required=True, metavar="PDF", help="Input PDF path.")
    p.add_argument("--out-dir", metavar="DIR", help="Base output directory. Default: .current/.")
    p.add_argument("--ir-dir", metavar="DIR", help="IR root. Default: <out-dir>/extraction_ir/<pdf_stem>.")
    p.add_argument("--run-id", default=None, metavar="ID", help="Run id. Default: generated UTC id.")
    p.add_argument("--source-id", default=None, metavar="ID", help="Source id. Default: input PDF stem.")
    p.add_argument("--backend-id", default=DEFAULT_BACKEND_ID, metavar="ID")
    p.add_argument("--backend-name", default=DEFAULT_BACKEND_NAME, metavar="NAME")
    p.add_argument("--adapter-version", default=DEFAULT_ADAPTER_VERSION, metavar="VERSION")
    p.add_argument("--discard-page-images", action="store_true")
    p.add_argument("--fail-on-empty-output", action="store_true")

    p.add_argument("--model-id", default=DEFAULT_MODEL_ID, metavar="ID")
    p.add_argument("--model-path", metavar="DIR")
    p.add_argument("--models-dir", default=DEFAULT_MODELS_DIR, metavar="DIR")
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("--repo-cache-dir", default=DEFAULT_REPO_CACHE, metavar="DIR")

    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI, metavar="N")
    p.add_argument("--base-size", type=int, default=DEFAULT_BASE_SIZE, metavar="N")
    p.add_argument("--prompt", choices=["document", "free"], default="document")

    return p


def _safe_dir_name(model_id: str) -> str:
    return model_id.replace("/", "__")


def _default_model_path(model_id: str, models_dir: str) -> Path:
    return Path(models_dir).expanduser().resolve() / _safe_dir_name(model_id)


def resolve_local_model(
    model_path: str | None,
    model_id: str,
    models_dir: str,
) -> tuple[Path | None, list[str]]:
    looked: list[str] = []

    if model_path:
        c = Path(model_path).expanduser().resolve()
        looked.append(str(c))
        if c.is_dir():
            return c, looked

    env = os.getenv("PDF2MD_DEEPSEEK_MODEL")
    if env:
        c = Path(env).expanduser().resolve()
        looked.append(str(c))
        if c.is_dir():
            return c, looked

    c = _default_model_path(model_id, models_dir)
    looked.append(str(c))
    if c.is_dir():
        return c, looked

    return None, looked


def _clone_or_pull_repo(repo_url: str, cache_dir: str) -> Path:
    cache = Path(cache_dir).expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    repo_dir = cache / repo_name

    if (repo_dir / ".git").is_dir():
        subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only"], check=True)
    else:
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(repo_dir)], check=True)

    return repo_dir


def download_model(model_id: str, models_dir: str, repo_cache_dir: str) -> Path:
    preset = _MODELS.get(model_id)
    if preset is None:
        raise SystemExit(f"error: unknown model id {model_id!r}")

    _clone_or_pull_repo(preset["repo_url"], repo_cache_dir)

    from huggingface_hub import snapshot_download  # noqa: E402

    local_dir = _default_model_path(model_id, models_dir)
    local_dir.parent.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
    )
    return local_dir


@dataclass
class RasterizedPage:
    page_index: int
    page_number: int
    pdf_width: float
    pdf_height: float
    rotation: int
    image: Any
    image_width: int
    image_height: int


def pdf_to_page_rasters(pdf_path: Path, dpi: int) -> list[RasterizedPage]:
    import fitz  # PyMuPDF
    from PIL import Image

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pages: list[RasterizedPage] = []

    try:
        for page_index, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            rect = page.rect
            pages.append(
                RasterizedPage(
                    page_index=page_index,
                    page_number=page_index + 1,
                    pdf_width=float(rect.width),
                    pdf_height=float(rect.height),
                    rotation=int(page.rotation or 0),
                    image=image,
                    image_width=int(pix.width),
                    image_height=int(pix.height),
                )
            )
    finally:
        doc.close()

    return pages


def load_model(model_dir: str, device: str):
    import torch
    from transformers import AutoModel, AutoTokenizer

    attn_impl = "flash_attention_2" if device.startswith("cuda") else "eager"

    tokenizer = AutoTokenizer.from_pretrained(
        model_dir,
        trust_remote_code=True,
        local_files_only=True,
    )
    model = AutoModel.from_pretrained(
        model_dir,
        trust_remote_code=True,
        use_safetensors=True,
        _attn_implementation=attn_impl,
        local_files_only=True,
    ).eval()

    if device.startswith("cuda"):
        model = model.to(device).to(torch.bfloat16)

    return tokenizer, model


def base_refs() -> dict[str, Any]:
    return {
        "parent_ref": None,
        "child_refs": [],
        "line_refs": [],
        "span_refs": [],
        "table_ref": None,
        "formula_ref": None,
        "media_ref": None,
        "caption_for_refs": [],
        "footnote_refs": [],
        "docling_ref": None,
    }


def source_ref(
    *,
    source_ref_id: str,
    backend_id: str,
    backend_name: str,
    raw_file: Path,
    clean_file: Path,
    raw_id: str,
    native_type: str,
    native_bbox: list[float] | None = None,
    native_coordinate_space: str | None = None,
) -> dict[str, Any]:
    return {
        "source_ref_id": source_ref_id,
        "backend_id": backend_id,
        "backend_name": backend_name,
        "raw_file": str(raw_file),
        "raw_clean_file": str(clean_file),
        "json_pointer": None,
        "raw_id": raw_id,
        "native_type": native_type,
        "native_bbox": native_bbox,
        "native_coordinate_space": native_coordinate_space,
        "confidence": None,
        "sha256": sha256_file(raw_file),
        "clean_sha256": sha256_file(clean_file),
    }


def make_page_block(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    raw_det_path: Path,
    clean_path: Path,
    clean_markdown: str,
    has_grounding: bool,
    is_empty: bool,
) -> dict[str, Any]:
    block_id = f"{page_id}_b0000"
    normalised = normalise_text(clean_markdown)

    flags: list[dict[str, Any]] = []
    if is_empty:
        flags.append(
            {
                "code": "empty_ocr_output",
                "severity": "high",
                "message": "DeepSeek-OCR-2 produced no OCR text for this page.",
            }
        )
    if not has_grounding:
        flags.append(
            {
                "code": "geometry_missing",
                "severity": "medium",
                "message": "No parseable DeepSeek-OCR-2 <|ref|>/<|det|> geometry was found for this page.",
            }
        )
    flags.append(
        {
            "code": "generated_page_markdown",
            "severity": "low",
            "message": "Page-level generated text may need later Markdown parsing into semantic blocks.",
        }
    )

    return {
        "block_id": block_id,
        "page_id": page_id,
        "document_id": source_id,
        "backend_id": backend_id,
        "page_index": page_index,
        "page_number": page_number,
        "order": 0,
        "type": "unknown",
        "subtype": "generated_markdown_page",
        "semantic_role": "generated_markdown_page",
        "docling_label_hint": "text",
        "docling": {
            "label_hint": "text",
            "level_hint": None,
            "provenance_ready": True,
            "excluded_from_docling": is_empty,
            "notes": [
                "DeepSeek-OCR-2 generated page text. Use region blocks when grounding tags are present."
            ],
        },
        "geometry": None,
        "content": {
            "text": clean_markdown,
            "normalised_text": normalised,
            "markdown": clean_markdown,
            "html": None,
            "latex": None,
            "language": None,
            "raw_markdown_with_grounding": str(raw_det_path),
        },
        "structure": {
            "heading_level": None,
            "list": None,
            "caption_for": None,
            "footnote_marker": None,
            "parent_block_id": None,
            "child_block_ids": [],
        },
        "refs": base_refs(),
        "lines": [],
        "spans": [],
        "table": None,
        "formula": None,
        "media": None,
        "confidence": {
            "overall": None,
            "layout": None,
            "text": None,
            "reading_order": 0.6 if not is_empty else None,
            "structure": 0.4 if not is_empty else None,
        },
        "comparison": {
            "compare_as": "generated_page_markdown",
            "text_hash": sha256_text(normalised),
            "geometry_hash": None,
            "candidate_group_id": None,
            "match_keys": ["page_index", "normalised_text"],
        },
        "source_refs": [
            source_ref(
                source_ref_id=f"{block_id}_src0",
                backend_id=backend_id,
                backend_name=backend_name,
                raw_file=raw_det_path,
                clean_file=clean_path,
                raw_id=f"page_{page_index}",
                native_type="markdown_generation",
            )
        ],
        "flags": flags,
    }


def crop_region_if_media(
    *,
    page_image_path: Path,
    media_dir: Path,
    region: dict[str, Any],
    page_index: int,
    region_index: int,
    image_width: int,
    image_height: int,
) -> dict[str, Any] | None:
    if region["type"] not in {"picture", "chart", "seal"}:
        return None

    try:
        from PIL import Image

        left, top, right, bottom = bbox_999_to_pixels(
            region["native_bbox"],
            image_width,
            image_height,
        )
        if right <= left or bottom <= top:
            return None

        media_dir.mkdir(parents=True, exist_ok=True)
        media_path = media_dir / f"page_{page_index:04d}_region_{region_index:04d}.png"

        with Image.open(page_image_path) as img:
            img.crop((left, top, right, bottom)).save(media_path)

        return {
            "media_id": f"p{page_index:04d}_media_{region_index:04d}",
            "kind": "picture" if region["type"] == "picture" else region["type"],
            "path": str(media_path),
            "mime_type": "image/png",
            "caption_block_ids": [],
            "alt_text": region.get("fragment") or None,
            "geometry": {
                "bbox": region["bbox"],
                "polygon": None,
                "coordinate_space": "page_normalised_1000",
                "origin": "top_left",
                "confidence": None,
            },
            "sha256": sha256_file(media_path),
        }
    except Exception:
        return None


def make_region_block(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    region: dict[str, Any],
    region_index: int,
    raw_det_path: Path,
    clean_path: Path,
    media: dict[str, Any] | None,
) -> dict[str, Any]:
    block_id = f"{page_id}_r{region_index:04d}"
    fragment = region.get("fragment") or ""
    normalised = normalise_text(fragment)
    block_type = region["type"]

    refs = base_refs()
    table_obj = None
    formula_obj = None

    if block_type == "table":
        table_obj = {
            "table_id": f"{block_id}_table",
            "representation": "ocr2_grounded_region",
            "html": None,
            "markdown": fragment or None,
            "caption_block_ids": [],
            "footnote_block_ids": [],
            "rows": None,
            "cols": None,
            "cells": [],
            "confidence": {"overall": None, "structure": None, "text": None},
        }
        refs["table_ref"] = table_obj["table_id"]

    if block_type == "formula":
        formula_obj = {
            "formula_id": f"{block_id}_formula",
            "kind": "display",
            "latex": fragment or None,
            "text": fragment or None,
            "mathml": None,
            "image_ref": None,
            "confidence": {"overall": None, "recognition": None},
        }
        refs["formula_ref"] = formula_obj["formula_id"]

    if media is not None:
        refs["media_ref"] = media["media_id"]

    return {
        "block_id": block_id,
        "page_id": page_id,
        "document_id": source_id,
        "backend_id": backend_id,
        "page_index": page_index,
        "page_number": page_number,
        "order": region_index + 1,
        "type": block_type,
        "subtype": region.get("subtype"),
        "semantic_role": region["semantic_role"],
        "docling_label_hint": region["docling_label_hint"],
        "docling": {
            "label_hint": region["docling_label_hint"],
            "level_hint": 1 if block_type in {"title", "section_header"} else None,
            "provenance_ready": True,
            "excluded_from_docling": False,
            "notes": ["Block created from DeepSeek-OCR-2 grounding tags."],
        },
        "geometry": {
            "bbox": region["bbox"],
            "polygon": None,
            "coordinate_space": "page_normalised_1000",
            "origin": "top_left",
            "confidence": None,
        },
        "content": {
            "text": fragment or None,
            "normalised_text": normalised or None,
            "markdown": fragment or None,
            "html": None,
            "latex": fragment if block_type == "formula" and fragment else None,
            "language": None,
        },
        "structure": {
            "heading_level": 1 if block_type == "title" else None,
            "list": None,
            "caption_for": None,
            "footnote_marker": None,
            "parent_block_id": None,
            "child_block_ids": [],
        },
        "refs": refs,
        "lines": [],
        "spans": [],
        "table": table_obj,
        "formula": formula_obj,
        "media": media,
        "confidence": {
            "overall": None,
            "layout": None,
            "text": None,
            "reading_order": 0.7,
            "structure": 0.5,
        },
        "comparison": {
            "compare_as": "grounded_text_block" if normalised else "layout_region",
            "text_hash": sha256_text(normalised) if normalised else None,
            "geometry_hash": sha256_text(json.dumps(region["bbox"], sort_keys=True)),
            "candidate_group_id": None,
            "match_keys": ["page_index", "type", "bbox_iou"] + (["normalised_text"] if normalised else []),
        },
        "source_refs": [
            source_ref(
                source_ref_id=f"{block_id}_src0",
                backend_id=backend_id,
                backend_name=backend_name,
                raw_file=raw_det_path,
                clean_file=clean_path,
                raw_id=f"page_{page_index}_match_{region['match_index']}_box_{region['box_index']}",
                native_type=f"ocr2_ref_det:{region['native_label']}",
                native_bbox=region["native_bbox"],
                native_coordinate_space="ocr2_0_999",
            )
        ],
        "flags": []
        if normalised
        else [
            {
                "code": "region_text_missing",
                "severity": "low",
                "message": "OCR-2 grounding region had no directly associated text fragment.",
            }
        ],
    }


def build_page_ir(
    *,
    run_id: str,
    source_id: str,
    source_pdf: Path,
    source_sha256: str | None,
    backend_id: str,
    backend_name: str,
    model_id: str,
    model_dir: str,
    prompt: str,
    prompt_mode: str,
    dpi: int,
    base_size: int,
    image_size: int,
    page: RasterizedPage,
    page_image_path: Path,
    raw_det_path: Path,
    clean_path: Path,
    capture_path: Path,
    raw_markdown: str,
    clean_markdown: str,
    capture_mode: str,
    captured_file: Path | None,
    page_image_status: str,
    media_dir: Path,
) -> dict[str, Any]:
    page_id = f"{backend_id}_p{page.page_index:04d}"
    regions = parse_ocr2_ref_det(raw_markdown)
    has_grounding = bool(regions)
    is_empty = not bool(clean_markdown.strip())

    blocks = [
        make_page_block(
            page_id=page_id,
            source_id=source_id,
            backend_id=backend_id,
            backend_name=backend_name,
            page_index=page.page_index,
            page_number=page.page_number,
            raw_det_path=raw_det_path,
            clean_path=clean_path,
            clean_markdown=clean_markdown,
            has_grounding=has_grounding,
            is_empty=is_empty,
        )
    ]

    media_refs: list[dict[str, Any]] = []
    for region_index, region in enumerate(regions):
        media = crop_region_if_media(
            page_image_path=page_image_path,
            media_dir=media_dir,
            region=region,
            page_index=page.page_index,
            region_index=region_index,
            image_width=page.image_width,
            image_height=page.image_height,
        )
        if media is not None:
            media_refs.append(media)
        blocks.append(
            make_region_block(
                page_id=page_id,
                source_id=source_id,
                backend_id=backend_id,
                backend_name=backend_name,
                page_index=page.page_index,
                page_number=page.page_number,
                region=region,
                region_index=region_index,
                raw_det_path=raw_det_path,
                clean_path=clean_path,
                media=media,
            )
        )

    semantic_blocks: list[dict[str, Any]] = []
    semantic_stats = {
        "semantic_block_count": 0,
        "table_block_count": 0,
        "formula_block_count": 0,
        "heading_block_count": 0,
        "picture_reference_count": 0,
        "caption_block_count": 0,
        "list_item_block_count": 0,
        "paragraph_block_count": 0,
    }
    if not is_empty:
        semantic_blocks, semantic_stats = create_markdown_semantic_blocks(
            page_id=page_id,
            source_id=source_id,
            backend_id=backend_id,
            backend_name=backend_name,
            page_index=page.page_index,
            page_number=page.page_number,
            clean_markdown=clean_markdown,
            raw_det_path=raw_det_path,
            clean_path=clean_path,
            start_order=len(blocks),
        )
        if semantic_blocks:
            link_captions_to_nearby_objects(semantic_blocks)
            blocks[0]["docling"]["excluded_from_docling"] = True
            blocks[0]["semantic_role"] = "raw_generated_page_evidence"
            blocks[0]["flags"].append(
                {
                    "code": "raw_page_block_excluded_from_docling",
                    "severity": "low",
                    "message": "Semantic Markdown-derived blocks are available; this page-level evidence block should not be compiled directly into Docling.",
                }
            )
            blocks[0]["structure"]["child_block_ids"] = [b["block_id"] for b in semantic_blocks]
            for semantic_block in semantic_blocks:
                semantic_block["structure"]["parent_block_id"] = blocks[0]["block_id"]
            blocks.extend(semantic_blocks)

    normalised = normalise_text(clean_markdown)
    page_flags: list[dict[str, Any]] = []
    if is_empty:
        page_flags.append(
            {
                "code": "empty_ocr_output",
                "severity": "high",
                "message": "DeepSeek-OCR-2 produced no OCR text for this page.",
            }
        )
    if not has_grounding:
        page_flags.append(
            {
                "code": "ocr2_grounding_not_found",
                "severity": "medium",
                "message": "No parseable DeepSeek-OCR-2 <|ref|>/<|det|> grounding tags were found for this page.",
            }
        )

    return {
        "schema_name": "pdf2md.extraction_ir_page",
        "schema_version": "1.0.0",
        "ir_stage": "backend_extraction_page",
        "page_id": page_id,
        "document_id": source_id,
        "backend_id": backend_id,
        "backend_name": backend_name,
        "run_id": run_id,
        "page_index": page.page_index,
        "page_number": page.page_number,
        "status": "empty_output" if is_empty else "ok",
        "dimensions": {
            "width": page.pdf_width,
            "height": page.pdf_height,
            "unit": "pt",
            "rotation": page.rotation,
        },
        "rendering": {
            "page_image_ref": {
                "artifact_id": f"{page_id}_image",
                "path": str(page_image_path),
                "mime_type": "image/png",
                "dpi": dpi,
                "width_px": page.image_width,
                "height_px": page.image_height,
                "sha256": sha256_file(page_image_path),
                "status": page_image_status,
            }
        },
        "blocks": blocks,
        "relationships": {
            "reading_order": [block["block_id"] for block in blocks],
            "docling_reading_order": [
                block["block_id"]
                for block in blocks
                if not block.get("docling", {}).get("excluded_from_docling", False)
            ],
            "parent_child": [
                {"parent": blocks[0]["block_id"], "children": blocks[0]["structure"].get("child_block_ids", [])}
            ] if blocks and blocks[0]["structure"].get("child_block_ids") else [],
            "caption_links": [
                {"caption": block["block_id"], "targets": block.get("refs", {}).get("caption_for_refs", [])}
                for block in blocks
                if block.get("type") == "caption" and block.get("refs", {}).get("caption_for_refs")
            ],
            "footnote_links": [],
            "media_refs": media_refs + [block["media"] for block in blocks if block.get("media")],
        },
        "page_text": {
            "plain_text": clean_markdown,
            "normalised_text": normalised,
            "markdown": clean_markdown,
            "text_hash": sha256_text(normalised),
        },
        "provenance": {
            "source_pdf": {
                "path": str(source_pdf),
                "sha256": source_sha256,
                "page_index": page.page_index,
                "page_number": page.page_number,
            },
            "model": {
                "model_id": model_id,
                "model_path": model_dir,
                "prompt": prompt,
                "prompt_mode": prompt_mode,
                "dpi": dpi,
                "base_size": base_size,
                "image_size": image_size,
            },
            "raw_backend_refs": [
                {
                    "artifact_id": f"{page_id}_raw_det_markdown",
                    "path": str(raw_det_path),
                    "kind": "deepseek_ocr_2_raw_detection_markdown",
                    "sha256": sha256_file(raw_det_path),
                },
                {
                    "artifact_id": f"{page_id}_clean_markdown",
                    "path": str(clean_path),
                    "kind": "deepseek_ocr_2_clean_markdown",
                    "sha256": sha256_file(clean_path),
                },
                {
                    "artifact_id": f"{page_id}_capture_metadata",
                    "path": str(capture_path),
                    "kind": "deepseek_ocr_2_capture_metadata",
                    "sha256": sha256_file(capture_path),
                },
            ],
        },
        "observed_capabilities": {
            "ocr_text_found": not is_empty,
            "grounding_refs_found": has_grounding,
            "det_bboxes_found": has_grounding,
            "det_region_count": len(regions),
            "media_crop_count": len(media_refs),
            "semantic_block_count": semantic_stats["semantic_block_count"],
            "table_block_count": semantic_stats["table_block_count"],
            "formula_block_count": semantic_stats["formula_block_count"],
            "heading_block_count": semantic_stats["heading_block_count"],
            "picture_reference_count": semantic_stats["picture_reference_count"],
            "caption_block_count": semantic_stats["caption_block_count"],
            "list_item_block_count": semantic_stats["list_item_block_count"],
            "paragraph_block_count": semantic_stats["paragraph_block_count"],
            "capture_mode": capture_mode,
            "captured_file": str(captured_file) if captured_file is not None else None,
        },
        "flags": page_flags,
    }


def build_manifest(
    *,
    run_id: str,
    created_at: str,
    source_id: str,
    source_pdf: Path,
    source_sha256: str | None,
    page_count: int,
    backend_id: str,
    backend_name: str,
    backend_version: str | None,
    adapter_version: str,
    model_id: str,
    model_dir: str,
    prompt: str,
    prompt_mode: str,
    dpi: int,
    base_size: int,
    image_size: int,
    ir_dir: Path,
    pages_dir: Path,
    page_image_dir: Path,
    raw_pages_dir: Path,
    official_results_dir: Path,
    media_dir: Path,
    page_refs: list[dict[str, Any]],
    native_output_files: list[dict[str, Any]],
    observed_totals: dict[str, Any],
    flags: list[dict[str, Any]],
) -> dict[str, Any]:
    pages_empty = sum(1 for ref in page_refs if ref["status"] == "empty_output")
    pages_ok = sum(1 for ref in page_refs if ref["status"] == "ok")

    return {
        "schema_name": "pdf2md.extraction_ir_manifest",
        "schema_version": "1.0.0",
        "ir_stage": "backend_extraction",
        "run": {
            "run_id": run_id,
            "created_at": created_at,
            "pipeline_version": "0.1.0",
        },
        "backend": {
            "backend_id": backend_id,
            "backend_name": backend_name,
            "backend_type": "local",
            "backend_version": backend_version,
            "adapter_name": DEFAULT_ADAPTER_NAME,
            "adapter_version": adapter_version,
            "config_ref": f"backends.{backend_id}",
            "model_id": model_id,
            "model_path": model_dir,
        },
        "source": {
            "source_id": source_id,
            "source_path": str(source_pdf),
            "source_sha256": source_sha256,
            "mime_type": "application/pdf",
            "page_count": page_count,
        },
        "normalisation": {
            "coordinate_space": "page_normalised_1000",
            "origin": "top_left",
            "bbox_format": "x0_y0_x1_y1",
            "text_normalisation": "unicode_nfkc_whitespace_collapsed_lowercase",
            "reading_order_base": "page_local_zero_based",
            "native_ocr2_coordinate_space": "ocr2_0_999",
        },
        "page_refs": page_refs,
        "artifacts": {
            "ir_dir": str(ir_dir),
            "pages_dir": str(pages_dir),
            "page_image_dir": str(page_image_dir),
            "raw_pages_dir": str(raw_pages_dir),
            "official_results_dir": str(official_results_dir),
            "media_dir": str(media_dir),
            "native_json_files": [],
            "native_output_files": native_output_files,
        },
        "capabilities": {
            "layout_blocks": "partial",
            "reading_order": True,
            "ocr_lines": False,
            "ocr_spans": False,
            "tables": "partial",
            "table_cells": False,
            "formulas": "partial",
            "figures": "partial",
            "captions": "partial",
            "headers_footers": "partial",
            "page_numbers": "partial",
            "geometry": "partial",
            "confidence_scores": False,
            "markdown": True,
            "html": False,
            "latex": "partial",
        },
        "observed_capabilities": observed_totals,
        "quality": {
            "pages_total": page_count,
            "pages_ok": pages_ok,
            "pages_empty": pages_empty,
            "pages_with_ocr_text": int(observed_totals.get("pages_with_ocr_text", 0)),
            "pages_with_grounding": int(observed_totals.get("pages_with_grounding", 0)),
            "det_region_count": int(observed_totals.get("det_region_count", 0)),
            "media_crop_count": int(observed_totals.get("media_crop_count", 0)),
            "pages_with_semantic_blocks": int(observed_totals.get("pages_with_semantic_blocks", 0)),
            "semantic_block_count": int(observed_totals.get("semantic_block_count", 0)),
            "table_block_count": int(observed_totals.get("table_block_count", 0)),
            "formula_block_count": int(observed_totals.get("formula_block_count", 0)),
            "heading_block_count": int(observed_totals.get("heading_block_count", 0)),
            "picture_reference_count": int(observed_totals.get("picture_reference_count", 0)),
            "caption_block_count": int(observed_totals.get("caption_block_count", 0)),
            "list_item_block_count": int(observed_totals.get("list_item_block_count", 0)),
            "paragraph_block_count": int(observed_totals.get("paragraph_block_count", 0)),
        },
        "inference": {
            "prompt": prompt,
            "prompt_mode": prompt_mode,
            "dpi": dpi,
            "base_size": base_size,
            "image_size": image_size,
            "save_results": True,
        },
        "flags": flags,
    }


def run_inference(
    *,
    input_pdf: Path,
    ir_dir: Path,
    model_dir: str,
    device: str,
    model_id: str,
    dpi: int,
    base_size: int,
    prompt_mode: str,
    run_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    adapter_version: str,
    discard_page_images: bool,
    fail_on_empty_output: bool,
) -> int:
    preset = _MODELS.get(model_id, _MODELS[DEFAULT_MODEL_ID])
    image_size = int(preset["image_size"])
    extra_infer = preset.get("extra_infer", {})
    prompt = PROMPT_DOCUMENT if prompt_mode == "document" else PROMPT_FREE_OCR

    pages_dir = ir_dir / "pages"
    page_image_dir = ir_dir / "page_images"
    raw_pages_dir = ir_dir / "raw_pages"
    official_results_dir = ir_dir / "official_results"
    media_dir = ir_dir / "media"

    for d in (pages_dir, page_image_dir, raw_pages_dir, official_results_dir, media_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"[pdf] Rasterising {input_pdf.name} at {dpi} dpi")
    pages = pdf_to_page_rasters(input_pdf, dpi=dpi)
    print(f"[pdf] {len(pages)} page(s)")

    print(f"[model] Loading from {model_dir} on {device}")
    tokenizer, model = load_model(model_dir, device)

    source_sha256 = sha256_file(input_pdf)
    created_at = now_utc()
    page_refs: list[dict[str, Any]] = []
    native_output_files: list[dict[str, Any]] = []
    observed_totals: dict[str, Any] = {
        "page_count": len(pages),
        "pages_with_ocr_text": 0,
        "pages_with_grounding": 0,
        "det_region_count": 0,
        "media_crop_count": 0,
        "semantic_block_count": 0,
        "pages_with_semantic_blocks": 0,
        "table_block_count": 0,
        "formula_block_count": 0,
        "heading_block_count": 0,
        "picture_reference_count": 0,
        "caption_block_count": 0,
        "list_item_block_count": 0,
        "paragraph_block_count": 0,
    }

    for page in pages:
        page_id = f"{backend_id}_p{page.page_index:04d}"
        img_file = page_image_dir / f"page_{page.page_index:04d}.png"
        page.image.save(img_file)

        official_page_dir = official_results_dir / f"page_{page.page_index:04d}"
        official_page_dir.mkdir(parents=True, exist_ok=True)
        before_outputs = snapshot_text_outputs(official_page_dir)

        print(f"[ocr] Page {page.page_number}/{len(pages)}", end=" ", flush=True)
        infer_result = model.infer(
            tokenizer,
            prompt=prompt,
            image_file=str(img_file),
            output_path=str(official_page_dir),
            base_size=base_size,
            image_size=image_size,
            crop_mode=True,
            save_results=True,
            **extra_infer,
        )
        raw_md, capture_mode, captured_file = coerce_infer_markdown(
            infer_result,
            official_page_dir,
            before_outputs,
        )
        clean_md = clean_ocr2_markdown(raw_md)
        is_empty = not bool(clean_md.strip())
        status = "empty_output" if is_empty else "ok"
        print(f"done ({status}, {capture_mode})")

        raw_det_path = raw_pages_dir / f"page_{page.page_index:04d}.det.mmd"
        clean_path = raw_pages_dir / f"page_{page.page_index:04d}.clean.mmd"
        capture_path = raw_pages_dir / f"page_{page.page_index:04d}.capture.json"

        write_text(raw_det_path, raw_md)
        write_text(clean_path, clean_md)
        write_json(
            capture_path,
            {
                "capture_mode": capture_mode,
                "captured_file": str(captured_file) if captured_file is not None else None,
                "official_output_dir": str(official_page_dir),
                "return_type": type(infer_result).__name__,
                "return_is_none": infer_result is None,
                "raw_length": len(raw_md),
                "clean_length": len(clean_md),
                "empty_output": is_empty,
            },
        )

        page_image_status = "available"
        if discard_page_images:
            img_file.unlink(missing_ok=True)
            page_image_status = "deleted_after_inference"

        page_ir = build_page_ir(
            run_id=run_id,
            source_id=source_id,
            source_pdf=input_pdf,
            source_sha256=source_sha256,
            backend_id=backend_id,
            backend_name=backend_name,
            model_id=model_id,
            model_dir=model_dir,
            prompt=prompt,
            prompt_mode=prompt_mode,
            dpi=dpi,
            base_size=base_size,
            image_size=image_size,
            page=page,
            page_image_path=img_file,
            raw_det_path=raw_det_path,
            clean_path=clean_path,
            capture_path=capture_path,
            raw_markdown=raw_md,
            clean_markdown=clean_md,
            capture_mode=capture_mode,
            captured_file=captured_file,
            page_image_status=page_image_status,
            media_dir=media_dir,
        )

        observed = page_ir["observed_capabilities"]
        if observed["ocr_text_found"]:
            observed_totals["pages_with_ocr_text"] += 1
        if observed["grounding_refs_found"]:
            observed_totals["pages_with_grounding"] += 1
        observed_totals["det_region_count"] += int(observed["det_region_count"])
        observed_totals["media_crop_count"] += int(observed["media_crop_count"])
        semantic_count = int(observed.get("semantic_block_count", 0))
        observed_totals["semantic_block_count"] += semantic_count
        if semantic_count:
            observed_totals["pages_with_semantic_blocks"] += 1
        for key in (
            "table_block_count",
            "formula_block_count",
            "heading_block_count",
            "picture_reference_count",
            "caption_block_count",
            "list_item_block_count",
            "paragraph_block_count",
        ):
            observed_totals[key] += int(observed.get(key, 0))

        page_json_path = pages_dir / f"page_{page.page_index:04d}.json"
        write_json(page_json_path, page_ir)

        page_refs.append(
            {
                "page_id": page_id,
                "page_index": page.page_index,
                "page_number": page.page_number,
                "path": str(page_json_path),
                "sha256": sha256_file(page_json_path),
                "status": status,
            }
        )

        native_output_files.extend(
            [
                {
                    "artifact_id": f"{page_id}_raw_det_markdown",
                    "path": str(raw_det_path),
                    "kind": "deepseek_ocr_2_raw_detection_markdown",
                    "sha256": sha256_file(raw_det_path),
                },
                {
                    "artifact_id": f"{page_id}_clean_markdown",
                    "path": str(clean_path),
                    "kind": "deepseek_ocr_2_clean_markdown",
                    "sha256": sha256_file(clean_path),
                },
                {
                    "artifact_id": f"{page_id}_capture_metadata",
                    "path": str(capture_path),
                    "kind": "deepseek_ocr_2_capture_metadata",
                    "sha256": sha256_file(capture_path),
                },
            ]
        )

    pages_empty = sum(1 for ref in page_refs if ref["status"] == "empty_output")
    flags: list[dict[str, Any]] = []
    if pages_empty:
        flags.append(
            {
                "code": "empty_ocr_pages",
                "severity": "high",
                "message": f"{pages_empty} of {len(pages)} pages produced empty OCR output.",
            }
        )
    if observed_totals["det_region_count"] == 0:
        flags.append(
            {
                "code": "deepseek_page_markdown_only",
                "severity": "medium",
                "message": "No OCR-2 grounding regions were found; IR contains page-level generated text only.",
            }
        )

    manifest = build_manifest(
        run_id=run_id,
        created_at=created_at,
        source_id=source_id,
        source_pdf=input_pdf,
        source_sha256=source_sha256,
        page_count=len(pages),
        backend_id=backend_id,
        backend_name=backend_name,
        backend_version=None,
        adapter_version=adapter_version,
        model_id=model_id,
        model_dir=model_dir,
        prompt=prompt,
        prompt_mode=prompt_mode,
        dpi=dpi,
        base_size=base_size,
        image_size=image_size,
        ir_dir=ir_dir,
        pages_dir=pages_dir,
        page_image_dir=page_image_dir,
        raw_pages_dir=raw_pages_dir,
        official_results_dir=official_results_dir,
        media_dir=media_dir,
        page_refs=page_refs,
        native_output_files=native_output_files,
        observed_totals=observed_totals,
        flags=flags,
    )

    manifest_path = ir_dir / "manifest.json"
    write_json(manifest_path, manifest)
    print(f"[out] IR manifest: {manifest_path}")
    print(f"[out] IR pages: {pages_dir}")

    if fail_on_empty_output and pages_empty:
        return 2
    return 0


def main() -> int:
    args = build_parser().parse_args()

    input_pdf = Path(args.input).expanduser().resolve()
    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        print(f"error: input must be an existing PDF: {input_pdf}", file=sys.stderr)
        return 1

    if args.device == "auto":
        try:
            import torch

            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    else:
        device = "cuda:0" if args.device == "cuda" else "cpu"

    if device == "cpu":
        print("[warn] CPU mode is experimental for DeepSeek-OCR-2 and will be slow.")

    model_dir, looked = resolve_local_model(args.model_path, args.model_id, args.models_dir)
    if model_dir is None:
        if not args.allow_download:
            looked_fmt = "\n".join(f"  - {p}" for p in looked)
            print(
                "error: DeepSeek-OCR-2 model not found locally.\n"
                f"Searched:\n{looked_fmt}\n\n"
                "Use --allow-download, --model-path, or PDF2MD_DEEPSEEK_MODEL.",
                file=sys.stderr,
            )
            return 1
        try:
            model_dir = download_model(args.model_id, args.models_dir, args.repo_cache_dir)
        except Exception as exc:
            print(f"error: download failed: {exc}", file=sys.stderr)
            return 1

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else Path(DEFAULT_CURRENT_DIR).expanduser().resolve()
    source_id = args.source_id or input_pdf.stem
    ir_dir = Path(args.ir_dir).expanduser().resolve() if args.ir_dir else (out_dir / "extraction_ir" / source_id).resolve()
    run_id = args.run_id or default_run_id()

    try:
        return run_inference(
            input_pdf=input_pdf,
            ir_dir=ir_dir,
            model_dir=str(model_dir),
            device=device,
            model_id=args.model_id,
            dpi=args.dpi,
            base_size=args.base_size,
            prompt_mode=args.prompt,
            run_id=run_id,
            source_id=source_id,
            backend_id=args.backend_id,
            backend_name=args.backend_name,
            adapter_version=args.adapter_version,
            discard_page_images=args.discard_page_images,
            fail_on_empty_output=args.fail_on_empty_output,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
