#!/usr/bin/env python3
"""pdf2ir_paddleocr.py - PaddleOCR PDF to page-first extraction IR.

This script is an adapter, not a final Markdown renderer. It writes an
extraction IR compatible in spirit with the DeepSeek-OCR-2 adapter:

  .current/extraction_ir/<pdf_stem>/
    manifest.json
    pages/page_0000.json
    page_images/page_0000.png              # if PyMuPDF/Pillow are available
    raw_pages/page_0000.official.json      # direct result.json snapshot
    raw_pages/page_0000.markdown.json      # direct result.markdown snapshot
    raw_pages/page_0000.clean.md           # page Markdown evidence
    raw_pages/page_0000.capture.json       # adapter capture metadata
    official_results/page_0000/            # save_to_json/save_to_markdown/save_to_img output
    media/                                 # markdown images and optional crops

The adapter exploits PaddleOCR's richer structured output when available:
PP-StructureV3 parsing_res_list, overall OCR lines, table_res_list,
formula_res_list, seal_res_list, markdown payloads, visual outputs and official
saved JSON/Markdown files. PaddleOCR-VL and PP-OCRv5 are supported as fallback
backends, but PP-StructureV3 is the preferred structural backend.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import sys
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PIPELINES = ["pp_structurev3", "paddleocr_vl", "pp_ocrv5"]
DEFAULT_CURRENT_DIR = ".current"
DEFAULT_BACKEND_ID = "paddleocr_pp_structurev3"
DEFAULT_BACKEND_NAME = "paddleocr_pp_structurev3"
DEFAULT_ADAPTER_NAME = "paddleocr_adapter"
DEFAULT_ADAPTER_VERSION = "0.3.0"
DEFAULT_DPI = 300
TEXT_OUTPUT_SUFFIXES = {".md", ".markdown", ".txt"}
JSON_OUTPUT_SUFFIXES = {".json"}


# ---------------------------------------------------------------------------
# Small filesystem and hashing helpers
# ---------------------------------------------------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_run_id() -> str:
    return f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalise_text(text: str | None) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def safe_rel(path: Path) -> str:
    return str(path)


# ---------------------------------------------------------------------------
# Object normalisation for PaddleX/PaddleOCR Result objects
# ---------------------------------------------------------------------------

def object_to_mapping(obj: Any) -> dict[str, Any]:
    """Best-effort shallow conversion of Paddle result-like objects."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj

    try:
        converted = dict(obj)
        if isinstance(converted, dict):
            return converted
    except Exception:
        pass

    for attr in ("model_dump", "dict", "to_dict", "as_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                converted = fn()
                if isinstance(converted, dict):
                    return converted
            except Exception:
                pass

    data: dict[str, Any] = {}
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            continue
        data[name] = value
    return data


def to_plain(obj: Any, *, max_depth: int = 10) -> Any:
    """Convert common Paddle/PaddleX/numpy/PIL structures into JSON-safe data."""
    if max_depth <= 0:
        return repr(obj)

    if obj is None or isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

    if isinstance(obj, Path):
        return str(obj)

    # numpy arrays and scalars
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return to_plain(tolist(), max_depth=max_depth - 1)
        except Exception:
            pass

    # PIL Image-like objects. Do not serialise pixels into JSON.
    if hasattr(obj, "save") and hasattr(obj, "size"):
        try:
            width, height = obj.size
            return {
                "__kind__": "image_object",
                "class": type(obj).__name__,
                "width": int(width),
                "height": int(height),
            }
        except Exception:
            return {"__kind__": "image_object", "class": type(obj).__name__}

    if isinstance(obj, dict):
        return {str(k): to_plain(v, max_depth=max_depth - 1) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [to_plain(v, max_depth=max_depth - 1) for v in obj]

    mapping = object_to_mapping(obj)
    if mapping:
        return {str(k): to_plain(v, max_depth=max_depth - 1) for k, v in mapping.items()}

    return repr(obj)


def get_nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_value(data: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


# ---------------------------------------------------------------------------
# Markdown, official output and media helpers
# ---------------------------------------------------------------------------

def extract_markdown_payload(payload: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return markdown text, markdown images and a plain snapshot."""
    if isinstance(payload, str):
        return payload, {}, {"markdown_texts": payload}

    data = to_plain(payload)
    if not isinstance(data, dict):
        return str(payload or ""), {}, {"coerced": data}

    text = first_value(data, ("markdown_texts", "markdown_text", "markdown", "text", "content"))
    images = first_value(data, ("markdown_images", "images", "imgs"))
    if not isinstance(images, dict):
        images = {}

    if not isinstance(text, str):
        for nested_key in ("res", "result", "data", "output", "markdown"):
            nested = data.get(nested_key)
            if nested is None:
                continue
            nested_text, nested_images, nested_plain = extract_markdown_payload(nested)
            if nested_text:
                merged = dict(images)
                merged.update(nested_images)
                data[f"__normalised_{nested_key}"] = nested_plain
                return nested_text, merged, data
        text = ""

    return text, images, data


def save_markdown_images(
    markdown_images: dict[str, Any],
    media_dir: Path,
    *,
    page_index: int,
) -> list[dict[str, Any]]:
    media_dir.mkdir(parents=True, exist_ok=True)
    refs: list[dict[str, Any]] = []
    for idx, (relative_path, image_obj) in enumerate(markdown_images.items()):
        if not relative_path:
            continue
        rel = Path(str(relative_path))
        target = media_dir / f"page_{page_index:04d}" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        saved = False
        mime_type = "image/png"

        save_fn = getattr(image_obj, "save", None)
        if callable(save_fn):
            try:
                save_fn(str(target))
                saved = True
            except Exception:
                pass

        if not saved and isinstance(image_obj, bytes):
            target.write_bytes(image_obj)
            saved = True

        if not saved:
            try:
                source = Path(str(image_obj)).expanduser()
                if source.is_file():
                    target.write_bytes(source.read_bytes())
                    saved = True
            except Exception:
                pass

        if saved:
            suffix = target.suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                mime_type = "image/jpeg"
            elif suffix == ".webp":
                mime_type = "image/webp"
            refs.append(
                {
                    "media_id": f"p{page_index:04d}_markdown_image_{idx:04d}",
                    "kind": "markdown_image",
                    "path": safe_rel(target),
                    "mime_type": mime_type,
                    "caption_block_ids": [],
                    "alt_text": None,
                    "geometry": None,
                    "sha256": sha256_file(target),
                    "source_relative_path": str(relative_path),
                }
            )
    return refs


def safe_save_result(result: Any, out_dir: Path, *, save_markdown: bool = True, save_img: bool = True) -> dict[str, Any]:
    """Call official PaddleOCR save methods when available."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Any] = {"save_to_json": False, "save_to_markdown": False, "save_to_img": False}

    save_to_json = getattr(result, "save_to_json", None)
    if callable(save_to_json):
        try:
            save_to_json(save_path=str(out_dir))
            saved["save_to_json"] = True
        except Exception as exc:
            saved["save_to_json_error"] = str(exc)

    if save_markdown:
        save_to_markdown = getattr(result, "save_to_markdown", None)
        if callable(save_to_markdown):
            try:
                save_to_markdown(save_path=str(out_dir))
                saved["save_to_markdown"] = True
            except Exception as exc:
                saved["save_to_markdown_error"] = str(exc)

    if save_img:
        save_to_img = getattr(result, "save_to_img", None)
        if callable(save_to_img):
            try:
                save_to_img(save_path=str(out_dir))
                saved["save_to_img"] = True
            except Exception as exc:
                saved["save_to_img_error"] = str(exc)

    return saved


def snapshot_outputs(root: Path) -> dict[str, tuple[int, int]]:
    if not root.exists():
        return {}
    snap: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_OUTPUT_SUFFIXES | JSON_OUTPUT_SUFFIXES:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        snap[str(path)] = (int(st.st_mtime_ns), int(st.st_size))
    return snap


def new_files(root: Path, before: dict[str, tuple[int, int]]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    if not root.exists():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        current = (int(st.st_mtime_ns), int(st.st_size))
        if before.get(str(path)) == current:
            continue
        files.append(
            {
                "path": safe_rel(path),
                "size": int(st.st_size),
                "sha256": sha256_file(path),
                "suffix": path.suffix.lower(),
            }
        )
    files.sort(key=lambda item: item["path"])
    return files


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def as_float_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception:
            pass
    if not isinstance(value, (list, tuple)):
        return None
    try:
        return [float(v) for v in value]
    except Exception:
        return None


def bbox_from_shape(shape: Any) -> list[float] | None:
    """Accept [x0,y0,x1,y1], [[x,y],...], flattened 8 point poly, or dict."""
    if shape is None:
        return None
    if hasattr(shape, "tolist"):
        try:
            shape = shape.tolist()
        except Exception:
            pass

    if isinstance(shape, dict):
        for key in ("bbox", "block_bbox", "rec_box", "rec_boxes", "box", "poly", "polygon", "rec_poly", "rec_polys", "dt_poly", "dt_polys"):
            if key in shape:
                bbox = bbox_from_shape(shape[key])
                if bbox is not None:
                    return bbox
        return None

    if not isinstance(shape, (list, tuple)):
        return None

    flat = as_float_list(shape)
    if flat is not None and len(flat) == 4:
        x0, y0, x1, y1 = flat
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        return [x0, y0, x1, y1]

    if flat is not None and len(flat) >= 8 and len(flat) % 2 == 0:
        xs = flat[0::2]
        ys = flat[1::2]
        return [min(xs), min(ys), max(xs), max(ys)]

    points: list[tuple[float, float]] = []
    for item in shape:
        if hasattr(item, "tolist"):
            try:
                item = item.tolist()
            except Exception:
                pass
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                points.append((float(item[0]), float(item[1])))
            except Exception:
                pass
    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return [min(xs), min(ys), max(xs), max(ys)]

    return None


def polygon_from_shape(shape: Any) -> list[list[float]] | None:
    if shape is None:
        return None
    if hasattr(shape, "tolist"):
        try:
            shape = shape.tolist()
        except Exception:
            pass
    if isinstance(shape, dict):
        for key in ("poly", "polygon", "rec_poly", "rec_polys", "dt_poly", "dt_polys", "block_poly"):
            if key in shape:
                poly = polygon_from_shape(shape[key])
                if poly is not None:
                    return poly
        return None
    if not isinstance(shape, (list, tuple)):
        return None
    flat = as_float_list(shape)
    if flat is not None and len(flat) >= 8 and len(flat) % 2 == 0:
        return [[flat[i], flat[i + 1]] for i in range(0, len(flat), 2)]
    points: list[list[float]] = []
    for item in shape:
        if hasattr(item, "tolist"):
            try:
                item = item.tolist()
            except Exception:
                pass
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                points.append([float(item[0]), float(item[1])])
            except Exception:
                pass
    return points or None




def bbox_union_from_shapes(shape: Any) -> list[float] | None:
    """Return a union bbox for a bbox, polygon, dict, or list of boxes/polygons.

    PaddleOCR/PaddleX geometry is not stable across result types:
    some fields are [x0, y0, x1, y1], some are 4-point polygons, and table
    fields may be lists of cell boxes. This helper deliberately accepts all of
    those shapes and returns one enclosing native-pixel bbox.
    """
    if shape is None:
        return None
    if hasattr(shape, "tolist"):
        try:
            shape = shape.tolist()
        except Exception:
            pass

    if isinstance(shape, dict):
        for key in (
            "table_bbox",
            "bbox",
            "block_bbox",
            "block_poly",
            "rec_box",
            "rec_boxes",
            "box",
            "cell_box_list",
            "poly",
            "polygon",
            "rec_poly",
            "rec_polys",
            "dt_poly",
            "dt_polys",
        ):
            if key in shape:
                bbox = bbox_union_from_shapes(shape.get(key))
                if bbox is not None:
                    return bbox
        return None

    direct = bbox_from_shape(shape)

    if isinstance(shape, (list, tuple)):
        child_boxes: list[list[float]] = []
        for item in shape:
            child = bbox_from_shape(item)
            if child is not None:
                child_boxes.append(child)
        if len(child_boxes) > 1:
            return [
                min(b[0] for b in child_boxes),
                min(b[1] for b in child_boxes),
                max(b[2] for b in child_boxes),
                max(b[3] for b in child_boxes),
            ]

    return direct


def native_geometry_from_candidates(*candidates: Any) -> tuple[list[float] | None, list[list[float]] | None]:
    """Pick the richest native bbox and polygon available from candidates."""
    native_bbox: list[float] | None = None
    native_poly: list[list[float]] | None = None
    for candidate in candidates:
        if native_bbox is None:
            native_bbox = bbox_union_from_shapes(candidate)
        if native_poly is None:
            native_poly = polygon_from_shape(candidate)
        if native_bbox is not None and native_poly is not None:
            break
    return native_bbox, native_poly


def normalise_bbox(bbox: list[float] | None, width: float | None, height: float | None) -> list[float] | None:
    if bbox is None or not width or not height or width <= 0 or height <= 0:
        return None
    x0, y0, x1, y1 = bbox
    return [
        round(clamp(x0 / width * 1000.0, 0.0, 1000.0), 3),
        round(clamp(y0 / height * 1000.0, 0.0, 1000.0), 3),
        round(clamp(x1 / width * 1000.0, 0.0, 1000.0), 3),
        round(clamp(y1 / height * 1000.0, 0.0, 1000.0), 3),
    ]


def normalise_polygon(poly: list[list[float]] | None, width: float | None, height: float | None) -> list[list[float]] | None:
    if poly is None or not width or not height or width <= 0 or height <= 0:
        return None
    return [
        [
            round(clamp(x / width * 1000.0, 0.0, 1000.0), 3),
            round(clamp(y / height * 1000.0, 0.0, 1000.0), 3),
        ]
        for x, y in poly
    ]


def bbox_center(bbox: list[float] | None) -> tuple[float, float] | None:
    if bbox is None:
        return None
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def contains_point(bbox: list[float] | None, point: tuple[float, float] | None, pad: float = 0.0) -> bool:
    if bbox is None or point is None:
        return False
    x, y = point
    return bbox[0] - pad <= x <= bbox[2] + pad and bbox[1] - pad <= y <= bbox[3] + pad


def bbox_iou(a: list[float] | None, b: list[float] | None) -> float:
    if a is None or b is None:
        return 0.0
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


# ---------------------------------------------------------------------------
# PDF rasterisation for evidence/cropping
# ---------------------------------------------------------------------------

@dataclass
class PageRaster:
    page_index: int
    page_number: int
    pdf_width: float | None
    pdf_height: float | None
    rotation: int | None
    image_path: Path | None
    image_width: int | None
    image_height: int | None
    status: str


def rasterise_pdf(pdf_path: Path, page_image_dir: Path, dpi: int) -> list[PageRaster]:
    page_image_dir.mkdir(parents=True, exist_ok=True)
    try:
        import fitz  # PyMuPDF
        from PIL import Image
    except Exception:
        return []

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pages: list[PageRaster] = []
    try:
        for page_index, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            image_path = page_image_dir / f"page_{page_index:04d}.png"
            image.save(image_path)
            rect = page.rect
            pages.append(
                PageRaster(
                    page_index=page_index,
                    page_number=page_index + 1,
                    pdf_width=float(rect.width),
                    pdf_height=float(rect.height),
                    rotation=int(page.rotation or 0),
                    image_path=image_path,
                    image_width=int(pix.width),
                    image_height=int(pix.height),
                    status="available",
                )
            )
    finally:
        doc.close()
    return pages


def fallback_raster(page_index: int) -> PageRaster:
    return PageRaster(
        page_index=page_index,
        page_number=page_index + 1,
        pdf_width=None,
        pdf_height=None,
        rotation=None,
        image_path=None,
        image_width=None,
        image_height=None,
        status="unavailable",
    )


def recover_raster_from_official_outputs(
    raster: PageRaster,
    saved_files: list[dict[str, Any]],
    page_image_dir: Path,
    *,
    dpi: int,
) -> PageRaster:
    """Copy a PaddleOCR-saved page/preprocessed image into page_images.

    This is a safety net for environments where PyMuPDF or Pillow rasterisation
    is unavailable. The file copied into page_images is kept even when
    official_results is later deleted.
    """
    if raster.image_path is not None and raster.image_path.exists():
        return raster

    candidates: list[Path] = []
    preferred_tokens = ("_preprocessed_img", "_overall_ocr_res", "_layout_order_res", "_layout_det_res")
    for token in preferred_tokens:
        for item in saved_files:
            path = Path(str(item.get("path") or ""))
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"} and token in path.name and path.exists():
                candidates.append(path)
    if not candidates:
        for item in saved_files:
            path = Path(str(item.get("path") or ""))
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"} and path.exists():
                candidates.append(path)

    if not candidates:
        return raster

    source = candidates[0]
    page_image_dir.mkdir(parents=True, exist_ok=True)
    target = page_image_dir / f"page_{raster.page_index:04d}{source.suffix.lower() or '.png'}"
    try:
        shutil.copy2(source, target)
        width = height = None
        try:
            from PIL import Image
            with Image.open(target) as img:
                width, height = img.size
        except Exception:
            pass
        raster.image_path = target
        raster.image_width = int(width) if width is not None else None
        raster.image_height = int(height) if height is not None else None
        raster.status = "available_from_paddleocr_official_output"
    except Exception:
        pass
    return raster


def page_image_quality(image_path: Path | None, *, dpi: int | None) -> dict[str, Any]:
    """Small, dependency-tolerant scan diagnostics for image-first documents."""
    if image_path is None or not image_path.exists():
        return {"available": False, "dpi": dpi}

    quality: dict[str, Any] = {"available": True, "dpi": dpi}
    try:
        from PIL import Image, ImageStat

        with Image.open(image_path) as img:
            width, height = img.size
            gray = img.convert("L")
            stat = ImageStat.Stat(gray)
            mean_luma = float(stat.mean[0])
            std_luma = float(stat.stddev[0])
            quality.update(
                {
                    "width_px": int(width),
                    "height_px": int(height),
                    "aspect_ratio": round(float(width) / float(height), 6) if height else None,
                    "mean_luma": round(mean_luma, 3),
                    "std_luma": round(std_luma, 3),
                    "contrast_estimate": round(std_luma / 127.5, 6),
                }
            )

            hist = gray.histogram()
            total = max(1, width * height)
            dark = sum(hist[:32]) / total
            bright = sum(hist[224:]) / total
            quality.update(
                {
                    "dark_fraction": round(dark, 6),
                    "bright_fraction": round(bright, 6),
                }
            )

            try:
                import numpy as np

                arr = np.asarray(gray, dtype=np.float32)
                gx = np.abs(np.diff(arr, axis=1)).mean() if arr.shape[1] > 1 else 0.0
                gy = np.abs(np.diff(arr, axis=0)).mean() if arr.shape[0] > 1 else 0.0
                edge_energy = float(gx + gy)
                quality["edge_energy"] = round(edge_energy, 6)

                # Laplacian variance proxy. Low values often indicate blur, but this is not a hard judgement.
                if arr.shape[0] > 2 and arr.shape[1] > 2:
                    lap = (
                        -4.0 * arr[1:-1, 1:-1]
                        + arr[:-2, 1:-1]
                        + arr[2:, 1:-1]
                        + arr[1:-1, :-2]
                        + arr[1:-1, 2:]
                    )
                    quality["laplacian_variance"] = round(float(lap.var()), 6)
            except Exception:
                quality["edge_energy"] = None
                quality["laplacian_variance"] = None

    except Exception as exc:
        quality.update({"available": False, "error": str(exc)})

    return quality


def scan_quality_flags(quality: dict[str, Any], *, dpi: int | None, scan_profile: str) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if scan_profile != "scanned_book":
        return flags

    if dpi is not None and dpi < 250:
        flags.append(
            {
                "code": "scan_dpi_below_recommended",
                "severity": "medium",
                "message": "Evidence page image DPI is below the recommended range for scanned books; use around 300 dpi for robust crops and review.",
            }
        )

    contrast = quality.get("contrast_estimate")
    if isinstance(contrast, (int, float)) and contrast < 0.08:
        flags.append(
            {
                "code": "low_scan_contrast",
                "severity": "medium",
                "message": "The page image has low estimated contrast; OCR quality may be degraded.",
            }
        )

    lap_var = quality.get("laplacian_variance")
    if isinstance(lap_var, (int, float)) and lap_var < 20.0:
        flags.append(
            {
                "code": "possible_blur",
                "severity": "low",
                "message": "The page image has low Laplacian variance; this may indicate blur or very smooth content.",
            }
        )

    return flags


# ---------------------------------------------------------------------------
# IR block construction helpers
# ---------------------------------------------------------------------------

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
    raw_json_file: Path,
    raw_markdown_file: Path,
    json_pointer: str | None,
    raw_id: str,
    native_type: str,
    native_bbox: list[float] | None = None,
    native_polygon: list[list[float]] | None = None,
    native_coordinate_space: str | None = "paddleocr_image_pixels",
    confidence: float | None = None,
    clean_char_start: int | None = None,
    clean_char_end: int | None = None,
) -> dict[str, Any]:
    ref = {
        "source_ref_id": source_ref_id,
        "backend_id": backend_id,
        "backend_name": backend_name,
        "raw_file": safe_rel(raw_json_file),
        "raw_clean_file": safe_rel(raw_markdown_file),
        "json_pointer": json_pointer,
        "raw_id": raw_id,
        "native_type": native_type,
        "native_bbox": native_bbox,
        "native_polygon": native_polygon,
        "native_coordinate_space": native_coordinate_space,
        "confidence": confidence,
        "sha256": sha256_file(raw_json_file),
        "clean_sha256": sha256_file(raw_markdown_file),
    }
    if clean_char_start is not None:
        ref["clean_char_start"] = clean_char_start
    if clean_char_end is not None:
        ref["clean_char_end"] = clean_char_end
    return ref


def classify_paddle_label(label: str | None) -> tuple[str, str | None, str, str]:
    native = normalise_text(label).replace(" ", "_") or "unknown"
    mapping: dict[str, tuple[str, str | None, str, str]] = {
        "doc_title": ("title", "doc_title", "title", "title"),
        "title": ("title", None, "title", "title"),
        "paragraph_title": ("section_header", "paragraph_title", "section_header", "section_header"),
        "section_header": ("section_header", None, "section_header", "section_header"),
        "text": ("paragraph", None, "body_text", "text"),
        "paragraph": ("paragraph", None, "body_text", "text"),
        "content": ("paragraph", "content", "body_text", "text"),
        "list": ("list_item", "list", "list_item", "list_item"),
        "table": ("table", None, "table", "table"),
        "formula": ("formula", None, "formula", "formula"),
        "equation": ("formula", "equation", "formula", "formula"),
        "image": ("picture", "image", "picture", "picture"),
        "figure": ("picture", "figure", "picture", "picture"),
        "chart": ("chart", None, "chart", "picture"),
        "seal": ("seal", None, "seal", "picture"),
        "header": ("page_header", None, "page_header", "page_header"),
        "header_image": ("page_header", "header_image", "page_header", "picture"),
        "footer": ("page_footer", None, "page_footer", "page_footer"),
        "footer_image": ("page_footer", "footer_image", "page_footer", "picture"),
        "number": ("page_number", None, "page_number", "page_number"),
        "page_number": ("page_number", None, "page_number", "page_number"),
        "footnote": ("footnote", None, "footnote", "footnote"),
        "aside_text": ("aside", "aside_text", "aside", "text"),
        "reference": ("reference", None, "reference", "text"),
        "caption": ("caption", None, "caption", "caption"),
        "abstract": ("abstract", None, "abstract", "text"),
    }
    return mapping.get(native, ("unknown", f"paddleocr_{native}", native, "text"))


def build_ocr_lines(
    official_json: dict[str, Any],
    *,
    page_id: str,
    width: float | None,
    height: float | None,
) -> list[dict[str, Any]]:
    overall = official_json.get("overall_ocr_res") or get_nested(official_json, "res", "overall_ocr_res") or {}
    if not isinstance(overall, dict):
        return []

    texts = overall.get("rec_texts") or []
    scores = overall.get("rec_scores") or []
    polys = overall.get("rec_polys") or overall.get("dt_polys") or []
    boxes = overall.get("rec_boxes") or []
    orientations = overall.get("textline_orientation_angles") or []

    if not isinstance(texts, list):
        return []

    lines: list[dict[str, Any]] = []
    for idx, text in enumerate(texts):
        raw_poly = polys[idx] if isinstance(polys, list) and idx < len(polys) else None
        raw_box = boxes[idx] if isinstance(boxes, list) and idx < len(boxes) else raw_poly
        native_bbox = bbox_from_shape(raw_box) or bbox_from_shape(raw_poly)
        native_poly = polygon_from_shape(raw_poly)
        bbox = normalise_bbox(native_bbox, width, height)
        poly = normalise_polygon(native_poly, width, height)
        score = scores[idx] if isinstance(scores, list) and idx < len(scores) else None
        try:
            score_f = float(score) if score is not None else None
        except Exception:
            score_f = None
        orientation = orientations[idx] if isinstance(orientations, list) and idx < len(orientations) else None
        lines.append(
            {
                "line_id": f"{page_id}_l{idx:04d}",
                "order": idx,
                "text": str(text),
                "normalised_text": normalise_text(str(text)),
                "geometry": {
                    "bbox": bbox,
                    "polygon": poly,
                    "coordinate_space": "page_normalised_1000" if bbox else None,
                    "origin": "top_left" if bbox else None,
                    "confidence": score_f,
                },
                "native": {
                    "bbox": native_bbox,
                    "polygon": native_poly,
                    "coordinate_space": "paddleocr_image_pixels",
                    "orientation_angle": orientation,
                },
                "confidence": {"text": score_f, "detection": None},
            }
        )
    return lines


def make_page_markdown_block(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    raw_json_path: Path,
    clean_md_path: Path,
    markdown: str,
    is_empty: bool,
) -> dict[str, Any]:
    block_id = f"{page_id}_b0000"
    normalised = normalise_text(markdown)
    flags: list[dict[str, Any]] = [
        {
            "code": "generated_page_markdown",
            "severity": "low",
            "message": "PaddleOCR generated page Markdown preserved as page-level evidence.",
        }
    ]
    if is_empty:
        flags.append(
            {
                "code": "empty_ocr_output",
                "severity": "high",
                "message": "PaddleOCR produced no OCR text for this page.",
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
            "notes": ["PaddleOCR page Markdown. Prefer structural blocks when parsing_res_list is present."],
        },
        "geometry": None,
        "content": {
            "text": markdown,
            "normalised_text": normalised,
            "markdown": markdown,
            "html": None,
            "latex": None,
            "language": None,
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
            "reading_order": 0.7 if not is_empty else None,
            "structure": 0.5 if not is_empty else None,
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
                raw_json_file=raw_json_path,
                raw_markdown_file=clean_md_path,
                json_pointer="/markdown",
                raw_id=f"page_{page_index}",
                native_type="markdown_generation",
                native_coordinate_space=None,
            )
        ],
        "flags": flags,
    }


def find_best_table(table_res_list: list[Any], block_bbox: list[float] | None, table_order: int) -> dict[str, Any] | None:
    if not table_res_list:
        return None
    best_idx = None
    best_score = 0.0
    for idx, table in enumerate(table_res_list):
        if not isinstance(table, dict):
            continue
        table_ocr = table.get("table_ocr_pred") if isinstance(table.get("table_ocr_pred"), dict) else {}
        native_bbox = bbox_union_from_shapes(table.get("table_bbox") or table.get("bbox") or table.get("cell_box_list") or table_ocr.get("rec_boxes") or table_ocr.get("rec_polys"))
        score = bbox_iou(block_bbox, native_bbox)
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is not None and best_score > 0.01:
        return table_res_list[best_idx]
    if table_order < len(table_res_list) and isinstance(table_res_list[table_order], dict):
        return table_res_list[table_order]
    return None


def build_table_object(
    block_id: str,
    table_res: dict[str, Any] | None,
    *,
    width: float | None,
    height: float | None,
) -> dict[str, Any] | None:
    if not table_res:
        return None
    pred_html = table_res.get("pred_html")
    table_ocr = table_res.get("table_ocr_pred") or {}
    if not isinstance(table_ocr, dict):
        table_ocr = {}

    parsed_cells, parsed_rows, parsed_cols, html_plain_text = parse_html_table_cells(pred_html if isinstance(pred_html, str) else None)
    cell_boxes = table_res.get("cell_box_list") or table_ocr.get("rec_boxes") or table_ocr.get("rec_polys") or []
    rec_texts = table_ocr.get("rec_texts") or []
    rec_scores = table_ocr.get("rec_scores") or []
    rec_boxes = table_ocr.get("rec_boxes") or table_ocr.get("rec_polys") or cell_boxes

    native_geometries: list[tuple[list[float] | None, list[list[float]] | None, float | None]] = []
    max_len = max(
        len(cell_boxes) if isinstance(cell_boxes, list) else 0,
        len(rec_boxes) if isinstance(rec_boxes, list) else 0,
        len(parsed_cells),
        len(rec_texts) if isinstance(rec_texts, list) else 0,
    )
    for idx in range(max_len):
        raw_cell = cell_boxes[idx] if isinstance(cell_boxes, list) and idx < len(cell_boxes) else None
        raw_rec = rec_boxes[idx] if isinstance(rec_boxes, list) and idx < len(rec_boxes) else None
        native_bbox, native_poly = native_geometry_from_candidates(raw_cell, raw_rec)
        score = rec_scores[idx] if isinstance(rec_scores, list) and idx < len(rec_scores) else None
        try:
            score_f = float(score) if score is not None else None
        except Exception:
            score_f = None
        native_geometries.append((native_bbox, native_poly, score_f))

    cells: list[dict[str, Any]] = []
    if parsed_cells:
        for idx, parsed in enumerate(parsed_cells):
            native_bbox, native_poly, score_f = native_geometries[idx] if idx < len(native_geometries) else (None, None, None)
            cells.append(
                {
                    "cell_id": f"{block_id}_table_r{parsed['row_index']:04d}_c{parsed['col_index']:04d}",
                    "row_index": parsed["row_index"],
                    "col_index": parsed["col_index"],
                    "row_span": parsed["row_span"],
                    "col_span": parsed["col_span"],
                    "is_header": parsed["is_header"],
                    "text": parsed["text"],
                    "normalised_text": parsed["normalised_text"],
                    "html": parsed.get("html"),
                    "geometry": {
                        "bbox": normalise_bbox(native_bbox, width, height),
                        "polygon": normalise_polygon(native_poly, width, height),
                        "coordinate_space": "page_normalised_1000" if native_bbox else None,
                        "origin": "top_left" if native_bbox else None,
                        "confidence": score_f,
                    },
                    "native_bbox": native_bbox,
                    "confidence": {"text": score_f, "structure": None},
                }
            )
    else:
        for idx in range(max_len):
            native_bbox, native_poly, score_f = native_geometries[idx] if idx < len(native_geometries) else (None, None, None)
            text = rec_texts[idx] if isinstance(rec_texts, list) and idx < len(rec_texts) else None
            cells.append(
                {
                    "cell_id": f"{block_id}_cell_{idx:04d}",
                    "row_index": None,
                    "col_index": None,
                    "row_span": None,
                    "col_span": None,
                    "is_header": None,
                    "text": str(text) if text is not None else None,
                    "normalised_text": normalise_text(str(text)) if text is not None else None,
                    "html": None,
                    "geometry": {
                        "bbox": normalise_bbox(native_bbox, width, height),
                        "polygon": normalise_polygon(native_poly, width, height),
                        "coordinate_space": "page_normalised_1000" if native_bbox else None,
                        "origin": "top_left" if native_bbox else None,
                        "confidence": score_f,
                    },
                    "native_bbox": native_bbox,
                    "confidence": {"text": score_f, "structure": None},
                }
            )

    return {
        "table_id": f"{block_id}_table",
        "representation": "paddleocr_table_res_list",
        "html": pred_html if isinstance(pred_html, str) else None,
        "markdown": pred_html if isinstance(pred_html, str) else None,
        "caption_block_ids": [],
        "footnote_block_ids": [],
        "rows": parsed_rows,
        "cols": parsed_cols,
        "cells": cells,
        "plain_text": html_plain_text or " ".join(str(t) for t in rec_texts if t is not None),
        "confidence": {"overall": None, "structure": None, "text": None},
    }

def find_best_formula(formula_res_list: list[Any], block_bbox: list[float] | None, formula_order: int) -> dict[str, Any] | None:
    if not formula_res_list:
        return None
    best_idx = None
    best_score = 0.0
    for idx, formula in enumerate(formula_res_list):
        if not isinstance(formula, dict):
            continue
        native_bbox = bbox_from_shape(formula.get("rec_polys") or formula.get("rec_poly") or formula.get("bbox"))
        score = bbox_iou(block_bbox, native_bbox)
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is not None and best_score > 0.01:
        return formula_res_list[best_idx]
    if formula_order < len(formula_res_list) and isinstance(formula_res_list[formula_order], dict):
        return formula_res_list[formula_order]
    return None


def build_formula_object(block_id: str, formula_res: dict[str, Any] | None, fallback_text: str | None) -> dict[str, Any] | None:
    if not formula_res and not fallback_text:
        return None
    rec = formula_res.get("rec_formula") if isinstance(formula_res, dict) else None
    text = rec if isinstance(rec, str) and rec.strip() else fallback_text
    return {
        "formula_id": f"{block_id}_formula",
        "kind": "display",
        "latex": text,
        "text": text,
        "mathml": None,
        "image_ref": None,
        "confidence": {"overall": None, "recognition": None},
    }


def crop_block_media(
    *,
    page_image_path: Path | None,
    media_dir: Path,
    page_index: int,
    block_index: int,
    block_type: str,
    bbox_norm: list[float] | None,
    alt_text: str | None,
) -> dict[str, Any] | None:
    if block_type not in {"picture", "chart", "seal"} or page_image_path is None or bbox_norm is None:
        return None
    if not page_image_path.exists():
        return None
    try:
        from PIL import Image

        with Image.open(page_image_path) as img:
            width, height = img.size
            left = int(clamp(round(bbox_norm[0] / 1000.0 * width), 0, width))
            top = int(clamp(round(bbox_norm[1] / 1000.0 * height), 0, height))
            right = int(clamp(round(bbox_norm[2] / 1000.0 * width), 0, width))
            bottom = int(clamp(round(bbox_norm[3] / 1000.0 * height), 0, height))
            if right <= left or bottom <= top:
                return None
            media_dir.mkdir(parents=True, exist_ok=True)
            path = media_dir / f"page_{page_index:04d}_block_{block_index:04d}.png"
            img.crop((left, top, right, bottom)).save(path)
        return {
            "media_id": f"p{page_index:04d}_media_{block_index:04d}",
            "kind": "picture" if block_type == "picture" else block_type,
            "path": safe_rel(path),
            "mime_type": "image/png",
            "caption_block_ids": [],
            "alt_text": alt_text,
            "geometry": {
                "bbox": bbox_norm,
                "polygon": None,
                "coordinate_space": "page_normalised_1000",
                "origin": "top_left",
                "confidence": None,
            },
            "sha256": sha256_file(path),
        }
    except Exception:
        return None


def make_layout_block(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    block_index: int,
    block: dict[str, Any],
    raw_json_path: Path,
    clean_md_path: Path,
    width: float | None,
    height: float | None,
    ocr_lines: list[dict[str, Any]],
    table_obj: dict[str, Any] | None,
    formula_obj: dict[str, Any] | None,
    media_obj: dict[str, Any] | None,
) -> dict[str, Any]:
    native_label = str(block.get("block_label") or block.get("label") or block.get("type") or "unknown")
    block_type, subtype, semantic_role, docling_hint = classify_paddle_label(native_label)
    raw_id = str(block.get("block_id") if block.get("block_id") is not None else block_index)
    native_bbox = bbox_from_shape(block.get("block_bbox") or block.get("bbox") or block.get("box"))
    native_poly = polygon_from_shape(block.get("block_poly") or block.get("poly") or block.get("polygon"))
    bbox = normalise_bbox(native_bbox, width, height)
    polygon = normalise_polygon(native_poly, width, height)
    content = block.get("block_content") or block.get("content") or block.get("text") or ""
    content_text = str(content) if content is not None else ""
    normalised = normalise_text(content_text)
    block_id = f"{page_id}_r{block_index:04d}"

    matched_lines = [line for line in ocr_lines if contains_point(bbox, bbox_center(line.get("geometry", {}).get("bbox")), pad=8.0)]
    refs = base_refs()
    refs["line_refs"] = [line["line_id"] for line in matched_lines]
    if table_obj is not None:
        refs["table_ref"] = table_obj["table_id"]
    if formula_obj is not None:
        refs["formula_ref"] = formula_obj["formula_id"]
    if media_obj is not None:
        refs["media_ref"] = media_obj["media_id"]

    heading_level = 1 if block_type == "title" else 2 if block_type == "section_header" else None

    return {
        "block_id": block_id,
        "page_id": page_id,
        "document_id": source_id,
        "backend_id": backend_id,
        "page_index": page_index,
        "page_number": page_number,
        "order": int(block.get("__ir_order_override") if block.get("__ir_order_override") is not None else (block.get("block_order") if block.get("block_order") is not None else block_index + 1)),
        "type": block_type,
        "subtype": subtype,
        "semantic_role": semantic_role,
        "docling_label_hint": docling_hint,
        "docling": {
            "label_hint": docling_hint,
            "level_hint": heading_level,
            "provenance_ready": bool(bbox),
            "excluded_from_docling": block_type in {"page_header", "page_footer", "page_number"},
            "notes": ["Block created from PaddleOCR parsing_res_list."],
        },
        "geometry": {
            "bbox": bbox,
            "polygon": polygon,
            "coordinate_space": "page_normalised_1000" if bbox else None,
            "origin": "top_left" if bbox else None,
            "confidence": None,
        }
        if bbox or polygon
        else None,
        "content": {
            "text": content_text or None,
            "normalised_text": normalised or None,
            "markdown": content_text or None,
            "html": table_obj.get("html") if table_obj else None,
            "latex": formula_obj.get("latex") if formula_obj else None,
            "language": None,
        },
        "structure": {
            "heading_level": heading_level,
            "list": None,
            "caption_for": None,
            "footnote_marker": None,
            "parent_block_id": None,
            "child_block_ids": [],
        },
        "refs": refs,
        "lines": matched_lines,
        "spans": [],
        "table": table_obj,
        "formula": formula_obj,
        "media": media_obj,
        "confidence": {
            "overall": None,
            "layout": None,
            "text": None,
            "reading_order": 0.85,
            "structure": 0.75,
        },
        "comparison": {
            "compare_as": "grounded_text_block" if normalised else "layout_region",
            "text_hash": sha256_text(normalised) if normalised else None,
            "geometry_hash": sha256_text(json.dumps(bbox, sort_keys=True)) if bbox else None,
            "candidate_group_id": None,
            "match_keys": ["page_index", "type", "bbox_iou"] + (["normalised_text"] if normalised else []),
        },
        "source_refs": [
            source_ref(
                source_ref_id=f"{block_id}_src0",
                backend_id=backend_id,
                backend_name=backend_name,
                raw_json_file=raw_json_path,
                raw_markdown_file=clean_md_path,
                json_pointer=f"/parsing_res_list/{block_index}",
                raw_id=f"page_{page_index}_block_{raw_id}",
                native_type=f"paddleocr_layout:{normalise_text(native_label).replace(' ', '_') or 'unknown'}",
                native_bbox=native_bbox,
                native_polygon=native_poly,
                native_coordinate_space="paddleocr_image_pixels",
            )
        ],
        "flags": []
        if normalised or block_type in {"picture", "chart", "table", "formula", "seal"}
        else [
            {
                "code": "block_text_missing",
                "severity": "low",
                "message": "PaddleOCR layout block has no block_content text.",
            }
        ],
    }


def make_ocr_line_block(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    line: dict[str, Any],
    line_index: int,
    order: int,
    raw_json_path: Path,
    clean_md_path: Path,
) -> dict[str, Any]:
    block_id = f"{page_id}_ocrline_{line_index:04d}"
    text = line.get("text") or ""
    normalised = normalise_text(str(text))
    return {
        "block_id": block_id,
        "page_id": page_id,
        "document_id": source_id,
        "backend_id": backend_id,
        "page_index": page_index,
        "page_number": page_number,
        "order": order,
        "type": "ocr_line",
        "subtype": "overall_ocr_res",
        "semantic_role": "ocr_line",
        "docling_label_hint": "text",
        "docling": {
            "label_hint": "text",
            "level_hint": None,
            "provenance_ready": bool(line.get("geometry")),
            "excluded_from_docling": True,
            "notes": ["Fallback line-level OCR block created from overall_ocr_res."],
        },
        "geometry": line.get("geometry"),
        "content": {
            "text": str(text),
            "normalised_text": normalised,
            "markdown": None,
            "html": None,
            "latex": None,
            "language": None,
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
        "lines": [line],
        "spans": [],
        "table": None,
        "formula": None,
        "media": None,
        "confidence": {
            "overall": line.get("confidence", {}).get("text"),
            "layout": None,
            "text": line.get("confidence", {}).get("text"),
            "reading_order": 0.6,
            "structure": 0.2,
        },
        "comparison": {
            "compare_as": "ocr_line",
            "text_hash": sha256_text(normalised),
            "geometry_hash": sha256_text(json.dumps(line.get("geometry", {}).get("bbox"), sort_keys=True)),
            "candidate_group_id": None,
            "match_keys": ["page_index", "normalised_text", "bbox_iou"],
        },
        "source_refs": [
            source_ref(
                source_ref_id=f"{block_id}_src0",
                backend_id=backend_id,
                backend_name=backend_name,
                raw_json_file=raw_json_path,
                raw_markdown_file=clean_md_path,
                json_pointer=f"/overall_ocr_res/rec_texts/{line_index}",
                raw_id=f"page_{page_index}_ocr_line_{line_index}",
                native_type="paddleocr_overall_ocr_line",
                native_bbox=line.get("native", {}).get("bbox"),
                native_polygon=line.get("native", {}).get("polygon"),
                confidence=line.get("confidence", {}).get("text"),
            )
        ],
        "flags": [],
    }



# ---------------------------------------------------------------------------
# Semantic Markdown enrichment
# ---------------------------------------------------------------------------

TABLE_RE = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)
DISPLAY_FORMULA_RE = re.compile(r"\\\[(.*?)\\\]|\$\$(.*?)\$\$", re.DOTALL)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)|<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
SPECIAL_MARKDOWN_RE = re.compile(
    r"<table\b.*?</table>|\\\[.*?\\\]|\$\$.*?\$\$|!\[[^\]]*\]\([^)]+\)|<img\b[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$", re.DOTALL)
CAPTION_RE = re.compile(r"^\s*(figure|fig\.|table)\s*\d+(?:\.\d+)?\b", re.IGNORECASE)
FOOTNOTE_RE = re.compile(r"^\s*(?:\\\(\s*\^|\[?\d+\]?\s{2,}|\*\s+)", re.IGNORECASE)
LIST_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def strip_html(text: str) -> str:
    text = re.sub(r"<\s*/\s*(td|th|tr|p|div|br)\s*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def html_attr(tag: str, name: str) -> str | None:
    """Extract one HTML attribute value without pulling in a DOM dependency."""
    quoted = re.search(rf"\b{name}\s*=\s*(['\"])(.*?)\1", tag, flags=re.IGNORECASE | re.DOTALL)
    if quoted:
        return unescape(quoted.group(2).strip())
    unquoted = re.search(rf"\b{name}\s*=\s*([^\s>]+)", tag, flags=re.IGNORECASE | re.DOTALL)
    if unquoted:
        return unescape(unquoted.group(1).strip())
    return None


def normalise_paddle_markdown_for_semantic(markdown: str) -> str:
    """Remove PaddleOCR presentation wrappers before semantic splitting.

    PaddleOCR often wraps tables/images/captions in centre-aligned div/html/body
    fragments. Those wrappers are useful as raw evidence but harmful for the IR
    semantic layer, where they create paragraph blocks that Docling should not
    compile. This function preserves the underlying table, image or text while
    dropping wrapper-only markup.
    """
    text = markdown or ""
    # A complete table wrapped by div/html/body should be represented by the table only.
    text = re.sub(
        r"<div\b[^>]*>\s*(?:<html>\s*)?(?:<body>\s*)?(<table\b.*?</table>)\s*(?:</body>\s*)?(?:</html>\s*)?</div>",
        r"\1",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # A centred image wrapper should become a direct image token.
    text = re.sub(
        r"<div\b[^>]*>\s*(<img\b[^>]*>)\s*</div>",
        r"\1",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Pure text divs should not be treated as HTML paragraphs.
    text = re.sub(
        r"<div\b[^>]*>\s*([^<>]*?\S[^<>]*?)\s*</div>",
        lambda m: unescape(m.group(1)).strip(),
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Remove orphan body/html fragments left by partial wrappers.
    text = re.sub(r"</?(?:html|body)>", "", text, flags=re.IGNORECASE)
    return text


class _TableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict[str, Any]]] = []
        self._row: list[dict[str, Any]] | None = None
        self._cell: dict[str, Any] | None = None
        self._text_parts: list[str] = []
        self._cell_html_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        if tag_l == "tr":
            self._row = []
        elif tag_l in {"td", "th"} and self._row is not None:
            attrs_d = {k.lower(): v for k, v in attrs if k}
            def _int_attr(name: str, default: int) -> int:
                try:
                    return max(1, int(attrs_d.get(name) or default))
                except Exception:
                    return default
            self._cell = {
                "tag": tag_l,
                "row_span": _int_attr("rowspan", 1),
                "col_span": _int_attr("colspan", 1),
                "is_header": tag_l == "th",
            }
            self._text_parts = []
            self._cell_html_parts = [self.get_starttag_text() or f"<{tag_l}>"]
        elif self._cell is not None:
            self._cell_html_parts.append(self.get_starttag_text() or f"<{tag_l}>")

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l in {"td", "th"} and self._row is not None and self._cell is not None:
            self._cell_html_parts.append(f"</{tag_l}>")
            text = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
            self._cell["text"] = text
            self._cell["html"] = "".join(self._cell_html_parts)
            self._row.append(self._cell)
            self._cell = None
            self._text_parts = []
            self._cell_html_parts = []
        elif tag_l == "tr":
            if self._row is not None:
                self.rows.append(self._row)
            self._row = None
        elif self._cell is not None:
            self._cell_html_parts.append(f"</{tag_l}>")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._text_parts.append(data)
            self._cell_html_parts.append(data)


def parse_html_table_cells(html: str | None) -> tuple[list[dict[str, Any]], int | None, int | None, str]:
    if not isinstance(html, str) or not html.strip():
        return [], None, None, ""
    parser = _TableHTMLParser()
    try:
        parser.feed(html)
    except Exception:
        return [], None, None, strip_html(html)

    occupied: set[tuple[int, int]] = set()
    cells: list[dict[str, Any]] = []
    max_col = 0
    for row_index, row in enumerate(parser.rows):
        col_index = 0
        for raw_cell in row:
            while (row_index, col_index) in occupied:
                col_index += 1
            row_span = int(raw_cell.get("row_span") or 1)
            col_span = int(raw_cell.get("col_span") or 1)
            for rr in range(row_index, row_index + row_span):
                for cc in range(col_index, col_index + col_span):
                    occupied.add((rr, cc))
            text = str(raw_cell.get("text") or "").strip()
            cells.append(
                {
                    "row_index": row_index,
                    "col_index": col_index,
                    "row_span": row_span,
                    "col_span": col_span,
                    "is_header": bool(raw_cell.get("is_header") or row_index == 0),
                    "text": text,
                    "normalised_text": normalise_text(text),
                    "html": raw_cell.get("html"),
                }
            )
            col_index += col_span
            max_col = max(max_col, col_index)
    plain_text = " ".join(cell["text"] for cell in cells if cell.get("text")).strip()
    return cells, len(parser.rows) or None, max_col or None, plain_text


def _markdown_segments(text: str, absolute_start: int) -> list[tuple[str, int, int]]:
    segments: list[tuple[str, int, int]] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, re.DOTALL):
        raw = match.group(0)
        stripped = raw.strip()
        if not stripped:
            continue
        leading_ws = len(raw) - len(raw.lstrip())
        trailing_ws = len(raw) - len(raw.rstrip())
        segments.append((stripped, absolute_start + match.start() + leading_ws, absolute_start + match.end() - trailing_ws))
    return segments


def _semantic_kind_from_text(text: str) -> tuple[str, str | None, str, str, int | None, str, str]:
    stripped = strip_html(text) if "<" in text and ">" in text else text.strip()
    candidate = stripped or text.strip()
    heading = HEADING_RE.match(candidate)
    if heading:
        level = len(heading.group(1))
        clean = heading.group(2).strip()
        if CAPTION_RE.match(clean):
            return "caption", "markdown_heading_caption", "caption", "caption", None, clean, clean
        return "section_header", "markdown_heading", "section_header", "section_header", level, clean, clean
    if CAPTION_RE.match(candidate):
        return "caption", None, "caption", "caption", None, candidate, candidate
    if FOOTNOTE_RE.match(candidate):
        return "footnote", None, "footnote", "footnote", None, candidate, candidate
    if LIST_RE.match(candidate):
        return "list_item", "markdown_list_item", "list_item", "list_item", None, candidate, candidate
    return "paragraph", None, "body_text", "text", None, candidate, candidate


def make_semantic_markdown_block(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    semantic_index: int,
    order: int,
    block_type: str,
    subtype: str | None,
    semantic_role: str,
    docling_hint: str,
    text: str | None,
    markdown: str | None,
    html: str | None,
    latex: str | None,
    heading_level: int | None,
    raw_json_path: Path,
    clean_md_path: Path,
    char_start: int,
    char_end: int,
    table_obj: dict[str, Any] | None = None,
    formula_obj: dict[str, Any] | None = None,
    media_obj: dict[str, Any] | None = None,
) -> dict[str, Any]:
    block_id = f"{page_id}_m{semantic_index:04d}"
    if table_obj is not None:
        table_obj["table_id"] = f"{block_id}_table"
    if formula_obj is not None:
        formula_obj["formula_id"] = f"{block_id}_formula"
    if media_obj is not None:
        media_obj["media_id"] = f"{block_id}_media"

    refs = base_refs()
    if table_obj is not None:
        refs["table_ref"] = table_obj["table_id"]
    if formula_obj is not None:
        refs["formula_ref"] = formula_obj["formula_id"]
    if media_obj is not None:
        refs["media_ref"] = media_obj["media_id"]

    normalised = normalise_text(text)
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
            "notes": ["Provisional semantic block parsed from PaddleOCR generated Markdown; native PaddleOCR layout blocks may provide geometry."],
        },
        "geometry": None,
        "content": {
            "text": text,
            "normalised_text": normalised or None,
            "markdown": markdown,
            "html": html,
            "latex": latex,
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
            "text_hash": sha256_text(normalised) if normalised else None,
            "geometry_hash": None,
            "candidate_group_id": None,
            "match_keys": ["page_index", "type", "normalised_text"],
        },
        "source_refs": [
            source_ref(
                source_ref_id=f"{block_id}_src0",
                backend_id=backend_id,
                backend_name=backend_name,
                raw_json_file=raw_json_path,
                raw_markdown_file=clean_md_path,
                json_pointer=None,
                raw_id=f"page_{page_index}_markdown_block_{semantic_index}",
                native_type=f"markdown_enrichment:{block_type}",
                native_bbox=None,
                native_coordinate_space=None,
                confidence=None,
                clean_char_start=char_start,
                clean_char_end=char_end,
            )
        ],
        "flags": [
            {
                "code": "geometry_missing",
                "severity": "low",
                "message": "Block was parsed from generated Markdown and has no direct Markdown geometry; PaddleOCR native layout blocks may provide geometry separately.",
            }
        ],
    }


def _match_markdown_image_ref(media_refs: list[dict[str, Any]], rel_path: str) -> dict[str, Any] | None:
    rel_norm = rel_path.strip()
    for ref in media_refs:
        if str(ref.get("source_relative_path") or "").strip() == rel_norm:
            return dict(ref)
        if str(ref.get("path") or "").endswith(rel_norm):
            return dict(ref)
    return None


def build_semantic_markdown_blocks(
    *,
    page_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    page_index: int,
    page_number: int,
    markdown_text: str,
    markdown_image_refs: list[dict[str, Any]],
    raw_json_path: Path,
    clean_md_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    markdown_text = normalise_paddle_markdown_for_semantic(markdown_text or "")
    blocks: list[dict[str, Any]] = []
    media_refs: list[dict[str, Any]] = []
    caption_links: list[dict[str, Any]] = []
    semantic_index = 0
    order = 1

    def add_block(**kwargs: Any) -> dict[str, Any]:
        nonlocal semantic_index, order
        block = make_semantic_markdown_block(
            page_id=page_id,
            source_id=source_id,
            backend_id=backend_id,
            backend_name=backend_name,
            page_index=page_index,
            page_number=page_number,
            semantic_index=semantic_index,
            order=order,
            raw_json_path=raw_json_path,
            clean_md_path=clean_md_path,
            **kwargs,
        )
        blocks.append(block)
        semantic_index += 1
        order += 1
        if block.get("media") is not None:
            media_refs.append(block["media"])
        return block

    last_end = 0
    for match in SPECIAL_MARKDOWN_RE.finditer(markdown_text or ""):
        prefix = markdown_text[last_end:match.start()]
        for segment, seg_start, seg_end in _markdown_segments(prefix, last_end):
            b_type, subtype, role, hint, level, clean_text, md = _semantic_kind_from_text(segment)
            add_block(
                block_type=b_type,
                subtype=subtype,
                semantic_role=role,
                docling_hint=hint,
                text=clean_text,
                markdown=md,
                html=None,
                latex=None,
                heading_level=level,
                char_start=seg_start,
                char_end=seg_end,
            )

        token = match.group(0)
        token_start, token_end = match.start(), match.end()
        if token.lower().startswith("<table"):
            cells, rows, cols, plain_text = parse_html_table_cells(token)
            block_id_preview = f"{page_id}_m{semantic_index:04d}"
            table_obj = {
                "table_id": f"{block_id_preview}_table",
                "representation": "html_from_generated_markdown",
                "html": token,
                "markdown": token,
                "caption_block_ids": [],
                "footnote_block_ids": [],
                "rows": rows,
                "cols": cols,
                "cells": [
                    {
                        "cell_id": f"{block_id_preview}_table_r{cell['row_index']:04d}_c{cell['col_index']:04d}",
                        "row_index": cell["row_index"],
                        "col_index": cell["col_index"],
                        "row_span": cell["row_span"],
                        "col_span": cell["col_span"],
                        "is_header": cell["is_header"],
                        "text": cell["text"],
                        "normalised_text": cell["normalised_text"],
                        "html": cell.get("html"),
                        "geometry": None,
                        "confidence": {"text": None, "structure": None},
                    }
                    for cell in cells
                ],
                "confidence": {"overall": None, "structure": None, "text": None},
            }
            add_block(
                block_type="table",
                subtype="html_from_markdown",
                semantic_role="table",
                docling_hint="table",
                text=plain_text or strip_html(token),
                markdown=token,
                html=token,
                latex=None,
                heading_level=None,
                char_start=token_start,
                char_end=token_end,
                table_obj=table_obj,
            )
        elif token.startswith("![") or token.lower().startswith("<img"):
            img_match = IMAGE_RE.match(token)
            if token.lower().startswith("<img"):
                alt_text = html_attr(token, "alt")
                rel_path = html_attr(token, "src") or token
            else:
                alt_text = img_match.group(1).strip() if img_match and img_match.group(1) is not None else None
                rel_path = img_match.group(2).strip() if img_match and img_match.group(2) is not None else token
            matched_ref = _match_markdown_image_ref(markdown_image_refs, rel_path)
            media_obj = matched_ref or {
                "media_id": f"{page_id}_m{semantic_index:04d}_media",
                "kind": "image_reference",
                "path": rel_path,
                "mime_type": None,
                "caption_block_ids": [],
                "alt_text": alt_text or None,
                "geometry": None,
                "sha256": None,
                "source_relative_path": rel_path,
            }
            media_obj["kind"] = media_obj.get("kind") or "image_reference"
            media_obj["alt_text"] = media_obj.get("alt_text") or alt_text or None
            add_block(
                block_type="picture",
                subtype="markdown_image_reference",
                semantic_role="picture",
                docling_hint="picture",
                text=token,
                markdown=token,
                html=None,
                latex=None,
                heading_level=None,
                char_start=token_start,
                char_end=token_end,
                media_obj=media_obj,
            )
        else:
            f_match = DISPLAY_FORMULA_RE.match(token)
            latex = (f_match.group(1) or f_match.group(2) or "").strip() if f_match else token.strip()
            formula_obj = {
                "formula_id": f"{page_id}_m{semantic_index:04d}_formula",
                "kind": "display",
                "latex": latex,
                "text": latex,
                "mathml": None,
                "image_ref": None,
                "confidence": {"overall": None, "recognition": None},
            }
            add_block(
                block_type="formula",
                subtype="display",
                semantic_role="formula",
                docling_hint="formula",
                text=latex,
                markdown=token,
                html=None,
                latex=latex,
                heading_level=None,
                char_start=token_start,
                char_end=token_end,
                formula_obj=formula_obj,
            )
        last_end = match.end()

    suffix = markdown_text[last_end:]
    for segment, seg_start, seg_end in _markdown_segments(suffix, last_end):
        b_type, subtype, role, hint, level, clean_text, md = _semantic_kind_from_text(segment)
        add_block(
            block_type=b_type,
            subtype=subtype,
            semantic_role=role,
            docling_hint=hint,
            text=clean_text,
            markdown=md,
            html=None,
            latex=None,
            heading_level=level,
            char_start=seg_start,
            char_end=seg_end,
        )

    def link_caption(caption: dict[str, Any], target: dict[str, Any]) -> None:
        target_id = target["block_id"]
        caption["structure"]["caption_for"] = target_id
        caption["refs"]["caption_for_refs"] = [target_id]
        link = {"caption_block_id": caption["block_id"], "target_block_id": target_id}
        if link not in caption_links:
            caption_links.append(link)
        if target.get("media") is not None:
            target["media"].setdefault("caption_block_ids", [])
            if caption["block_id"] not in target["media"]["caption_block_ids"]:
                target["media"]["caption_block_ids"].append(caption["block_id"])
        if target.get("table") is not None:
            target["table"].setdefault("caption_block_ids", [])
            if caption["block_id"] not in target["table"]["caption_block_ids"]:
                target["table"]["caption_block_ids"].append(caption["block_id"])

    previous_picture: dict[str, Any] | None = None
    previous_table: dict[str, Any] | None = None
    pending_figure_caption: dict[str, Any] | None = None
    pending_table_caption: dict[str, Any] | None = None
    for block in blocks:
        if block["type"] in {"picture", "chart"}:
            previous_picture = block
            if pending_figure_caption is not None and pending_figure_caption["structure"].get("caption_for") is None:
                link_caption(pending_figure_caption, block)
                pending_figure_caption = None
        elif block["type"] == "table":
            previous_table = block
            if pending_table_caption is not None and pending_table_caption["structure"].get("caption_for") is None:
                link_caption(pending_table_caption, block)
                pending_table_caption = None
        elif block["type"] == "caption":
            text = block.get("content", {}).get("text") or ""
            if re.match(r"^\s*(figure|fig\.)\s*\d", text, re.IGNORECASE):
                if previous_picture is not None:
                    link_caption(block, previous_picture)
                else:
                    pending_figure_caption = block
            elif re.match(r"^\s*table\s*\d", text, re.IGNORECASE):
                if previous_table is not None:
                    link_caption(block, previous_table)
                else:
                    pending_table_caption = block

    return blocks, media_refs, caption_links


# ---------------------------------------------------------------------------
# Docling-readiness consolidation helpers
# ---------------------------------------------------------------------------

TEXTLIKE_TYPES = {"paragraph", "text", "section_header", "title", "caption", "list_item", "footnote", "abstract", "reference"}


def block_family_for(block: dict[str, Any]) -> str:
    block_id = str(block.get("block_id") or "")
    block_type = str(block.get("type") or "")
    native_type = " ".join(str(ref.get("native_type") or "") for ref in block.get("source_refs") or [])
    if block_id.endswith("_b0000") or block.get("subtype") == "generated_markdown_page":
        return "raw_page_evidence"
    if "_ocrline_" in block_id or block_type == "ocr_line":
        return "paddleocr_ocr_line"
    if "markdown_enrichment" in native_type or "_m" in block_id:
        return "markdown_semantic"
    if block_type == "table" and "table_res" in native_type:
        return "paddleocr_table_native"
    if block_type == "formula" and "formula" in native_type:
        return "paddleocr_formula_native"
    if block_type in {"picture", "chart", "seal"}:
        return "paddleocr_media_native" if "paddleocr_layout" in native_type else "markdown_semantic"
    if "paddleocr_layout" in native_type or "_r" in block_id:
        return "paddleocr_layout_native"
    return "backend_evidence"


def text_similarity(a: str | None, b: str | None) -> float:
    aa = normalise_text(a)
    bb = normalise_text(b)
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    # Avoid over-penalising block-vs-line differences.
    if len(aa) > 24 and len(bb) > 24 and (aa in bb or bb in aa):
        return min(len(aa), len(bb)) / max(len(aa), len(bb))
    return float(SequenceMatcher(None, aa, bb).ratio())


def _append_unique_flag(block: dict[str, Any], code: str, severity: str, message: str) -> None:
    flags = block.setdefault("flags", [])
    if not any(f.get("code") == code for f in flags):
        flags.append({"code": code, "severity": severity, "message": message})


def _append_page_flag(page_ir: dict[str, Any], code: str, severity: str, message: str) -> None:
    flags = page_ir.setdefault("flags", [])
    if not any(f.get("code") == code for f in flags):
        flags.append({"code": code, "severity": severity, "message": message})


def _table_quality_flags(block: dict[str, Any]) -> None:
    table = block.get("table") or {}
    if not table:
        return
    cells = table.get("cells") or []
    if table.get("representation") in {"html_from_generated_markdown", "html_from_markdown"}:
        _append_unique_flag(block, "table_html_only", "low", "Table structure was parsed from generated Markdown/HTML; preserve native table evidence if available.")
    if cells and not any((cell.get("geometry") or {}).get("bbox") for cell in cells if isinstance(cell, dict)):
        _append_unique_flag(block, "table_cells_missing_geometry", "medium", "Table cells have logical row/column positions but no cell-level geometry.")
    row_counts: dict[int, int] = {}
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        ri = cell.get("row_index")
        cs = cell.get("col_span") or 1
        if isinstance(ri, int):
            row_counts[ri] = row_counts.get(ri, 0) + int(cs)
    if len(set(row_counts.values())) > 1:
        _append_unique_flag(block, "table_grid_suspect", "medium", "Parsed table rows have inconsistent apparent column counts; later compilation should treat the table grid as uncertain.")


def _formula_quality_flags(block: dict[str, Any]) -> None:
    formula = block.get("formula") or {}
    latex = str(formula.get("latex") or block.get("content", {}).get("latex") or "")
    if not latex:
        return
    suspicious = False
    if "\\sqrt" in latex and len(latex) > 60:
        suspicious = True
    if "\\mathbb" in latex and any(token in latex for token in ("\\mathbf{j}", "\\rho", "\\sigma")):
        suspicious = True
    if suspicious:
        _append_unique_flag(block, "formula_text_suspect", "low", "Formula recognition contains patterns that may be OCR artefacts; preserve formula image/native evidence for later review.")


def _compile_role_for(block: dict[str, Any], has_native_type: dict[str, bool]) -> str:
    family = block.get("block_family") or block_family_for(block)
    block_type = block.get("type")
    if family == "raw_page_evidence":
        return "evidence_only"
    if family == "paddleocr_ocr_line":
        return "evidence_only"
    if family in {"paddleocr_layout_native", "paddleocr_table_native", "paddleocr_formula_native", "paddleocr_media_native"}:
        if block_type in {"page_header", "page_footer", "page_number"}:
            return "evidence_only"
        return "use"
    if family == "markdown_semantic":
        if block_type in {"table", "formula", "picture", "chart"} and not has_native_type.get(str(block_type), False):
            return "use"
        return "fallback_only"
    return "evidence_only"


def finalise_page_ir_for_docling(page_ir: dict[str, Any]) -> dict[str, Any]:
    blocks = page_ir.get("blocks") or []
    for block in blocks:
        block["block_family"] = block_family_for(block)

    native_blocks = [b for b in blocks if str(b.get("block_family", "")).startswith("paddleocr_") and b.get("block_family") != "paddleocr_ocr_line"]
    semantic_blocks = [b for b in blocks if b.get("block_family") == "markdown_semantic"]
    has_native_type: dict[str, bool] = {}
    for b in native_blocks:
        has_native_type[str(b.get("type"))] = True

    semantic_to_native: list[dict[str, Any]] = []
    native_to_semantic_map: dict[str, list[dict[str, Any]]] = {}

    for sem in semantic_blocks:
        sem_text = (sem.get("content") or {}).get("normalised_text") or (sem.get("content") or {}).get("text")
        best: tuple[float, dict[str, Any] | None, float, float] = (0.0, None, 0.0, 0.0)
        for native in native_blocks:
            native_text = (native.get("content") or {}).get("normalised_text") or (native.get("content") or {}).get("text")
            ts = text_similarity(str(sem_text or ""), str(native_text or ""))
            same_type = sem.get("type") == native.get("type") or (sem.get("type") in TEXTLIKE_TYPES and native.get("type") in TEXTLIKE_TYPES)
            if not same_type and ts < 0.88:
                continue
            iou = bbox_iou((sem.get("geometry") or {}).get("bbox"), (native.get("geometry") or {}).get("bbox"))
            order_gap = abs(int(sem.get("order") or 0) - int(native.get("order") or 0))
            order_score = max(0.0, 1.0 - min(order_gap, 20) / 20.0)
            confidence = max(ts, (0.7 * ts + 0.2 * iou + 0.1 * order_score))
            if confidence > best[0]:
                best = (confidence, native, ts, iou)
        if best[1] is not None and best[0] >= 0.55:
            native = best[1]
            match = {
                "semantic_block_id": sem["block_id"],
                "native_block_id": native["block_id"],
                "text_similarity": round(best[2], 6),
                "bbox_iou": round(best[3], 6),
                "confidence": round(best[0], 6),
            }
            semantic_to_native.append(match)
            native_to_semantic_map.setdefault(native["block_id"], []).append(match)
            sem.setdefault("refs", {}).setdefault("native_match_refs", [])
            if native["block_id"] not in sem["refs"]["native_match_refs"]:
                sem["refs"]["native_match_refs"].append(native["block_id"])
            native.setdefault("refs", {}).setdefault("semantic_match_refs", [])
            if sem["block_id"] not in native["refs"]["semantic_match_refs"]:
                native["refs"]["semantic_match_refs"].append(sem["block_id"])

    for block in blocks:
        docling = block.setdefault("docling", {})
        role = _compile_role_for(block, has_native_type)
        if block.get("block_family") == "markdown_semantic" and block.get("refs", {}).get("native_match_refs") and block.get("type") not in {"table", "formula", "picture", "chart"}:
            role = "duplicate_candidate"
            _append_unique_flag(block, "duplicate_docling_candidate", "low", "Markdown semantic block appears to duplicate a native PaddleOCR layout block.")
        docling["compile_role"] = role
        docling.setdefault("compile_notes", [])
        if role in {"evidence_only", "duplicate_candidate"}:
            docling["excluded_from_docling"] = True
        elif role in {"use", "fallback_only"}:
            docling["excluded_from_docling"] = False
        _table_quality_flags(block)
        _formula_quality_flags(block)
        content_text = str((block.get("content") or {}).get("markdown") or "")
        if block.get("type") == "paragraph" and re.search(r"</?(?:div|html|body)\b", content_text, re.IGNORECASE):
            _append_unique_flag(block, "html_wrapper_not_semantic", "medium", "HTML presentation wrapper remained as paragraph content; this should be treated as evidence, not canonical Docling text.")
            if docling.get("compile_role") == "use":
                docling["compile_role"] = "evidence_only"
                docling["excluded_from_docling"] = True

    native_to_semantic = []
    for native_id, matches in native_to_semantic_map.items():
        native_to_semantic.append({"native_block_id": native_id, "semantic_matches": matches})

    relationships = page_ir.setdefault("relationships", {})
    relationships["semantic_to_native_matches"] = semantic_to_native
    relationships["native_to_semantic_matches"] = native_to_semantic
    relationships["docling_reading_order"] = [
        b.get("block_id") for b in sorted(blocks, key=lambda item: item.get("order") or 0)
        if (b.get("docling") or {}).get("compile_role") in {"use", "fallback_only"}
    ]
    relationships["table_refs"] = [
        {"block_id": b.get("block_id"), "table_id": (b.get("table") or {}).get("table_id"), "block_family": b.get("block_family"), "compile_role": (b.get("docling") or {}).get("compile_role")}
        for b in blocks if b.get("table")
    ]
    relationships["formula_refs"] = [
        {"block_id": b.get("block_id"), "formula_id": (b.get("formula") or {}).get("formula_id"), "block_family": b.get("block_family"), "compile_role": (b.get("docling") or {}).get("compile_role")}
        for b in blocks if b.get("formula")
    ]
    relationships["media_block_refs"] = [
        {"block_id": b.get("block_id"), "media_id": (b.get("media") or {}).get("media_id"), "block_family": b.get("block_family"), "compile_role": (b.get("docling") or {}).get("compile_role")}
        for b in blocks if b.get("media")
    ]

    page_img_status = ((page_ir.get("rendering") or {}).get("page_image_ref") or {}).get("status")
    has_page_image = bool(page_img_status and str(page_img_status).startswith("available"))
    if not has_page_image:
        _append_page_flag(page_ir, "missing_page_image", "high", "No retained page image is available for visual provenance or Docling bounding-box verification.")

    def _count_by(key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for b in blocks:
            value = str(b.get(key) or "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

    role_counts: dict[str, int] = {}
    for b in blocks:
        role = str((b.get("docling") or {}).get("compile_role") or "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    severity_counts: dict[str, int] = {}
    for f in page_ir.get("flags") or []:
        sev = str(f.get("severity") or "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    for b in blocks:
        for f in b.get("flags") or []:
            sev = str(f.get("severity") or "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

    page_ir["extraction_summary"] = {
        "block_counts_by_type": _count_by("type"),
        "block_counts_by_family": _count_by("block_family"),
        "docling_candidate_counts": role_counts,
        "flags_by_severity": severity_counts,
        "has_page_image": has_page_image,
        "has_native_layout": any(b.get("block_family") == "paddleocr_layout_native" for b in blocks),
        "has_ocr_lines": bool((page_ir.get("observed_capabilities") or {}).get("ocr_line_count")),
        "has_tables": any(b.get("table") for b in blocks),
        "has_formulas": any(b.get("formula") for b in blocks),
        "has_media": any(b.get("media") for b in blocks) or bool((page_ir.get("relationships") or {}).get("media_refs")),
        "semantic_native_match_count": len(semantic_to_native),
    }
    return page_ir


# ---------------------------------------------------------------------------
# Page and manifest builders
# ---------------------------------------------------------------------------

def extract_page_index(official_json: dict[str, Any], fallback: int) -> int:
    page_index = official_json.get("__adapter_page_index")
    if page_index is None:
        page_index = official_json.get("page_index")
    if page_index is None:
        page_index = get_nested(official_json, "res", "page_index")
    try:
        if page_index is not None:
            return int(page_index)
    except Exception:
        pass
    return fallback


def extract_dimensions(official_json: dict[str, Any]) -> tuple[float | None, float | None]:
    width = official_json.get("width") or get_nested(official_json, "res", "width")
    height = official_json.get("height") or get_nested(official_json, "res", "height")
    try:
        width_f = float(width) if width is not None else None
    except Exception:
        width_f = None
    try:
        height_f = float(height) if height is not None else None
    except Exception:
        height_f = None
    return width_f, height_f


def build_page_ir(
    *,
    run_id: str,
    source_id: str,
    source_pdf: Path,
    source_sha256: str | None,
    backend_id: str,
    backend_name: str,
    pipeline_name: str,
    adapter_version: str,
    page_index: int,
    raster: PageRaster,
    official_json: dict[str, Any],
    markdown_plain: dict[str, Any],
    markdown_text: str,
    markdown_image_refs: list[dict[str, Any]],
    raw_json_path: Path,
    markdown_json_path: Path,
    clean_md_path: Path,
    capture_path: Path,
    official_page_dir: Path,
    official_saved_files: list[dict[str, Any]],
    media_dir: Path,
    dpi: int,
    scan_profile: str,
    predict_from_page_images: bool,
) -> dict[str, Any]:
    page_index = extract_page_index(official_json, page_index)
    page_number = page_index + 1
    page_id = f"{backend_id}_p{page_index:04d}"
    width_px, height_px = extract_dimensions(official_json)
    normalised_page_text = normalise_text(markdown_text)
    is_empty = not bool(normalised_page_text)

    blocks: list[dict[str, Any]] = [
        make_page_markdown_block(
            page_id=page_id,
            source_id=source_id,
            backend_id=backend_id,
            backend_name=backend_name,
            page_index=page_index,
            page_number=page_number,
            raw_json_path=raw_json_path,
            clean_md_path=clean_md_path,
            markdown=markdown_text,
            is_empty=is_empty,
        )
    ]

    ocr_lines = build_ocr_lines(official_json, page_id=page_id, width=width_px, height=height_px)

    semantic_blocks, semantic_media_refs, semantic_caption_links = build_semantic_markdown_blocks(
        page_id=page_id,
        source_id=source_id,
        backend_id=backend_id,
        backend_name=backend_name,
        page_index=page_index,
        page_number=page_number,
        markdown_text=markdown_text,
        markdown_image_refs=markdown_image_refs,
        raw_json_path=raw_json_path,
        clean_md_path=clean_md_path,
    )
    if semantic_blocks:
        blocks[0]["semantic_role"] = "raw_generated_page_evidence"
        blocks[0]["docling"]["excluded_from_docling"] = True
        blocks[0]["structure"]["child_block_ids"] = [block["block_id"] for block in semantic_blocks]
        blocks[0]["flags"].append(
            {
                "code": "raw_page_block_excluded_from_docling",
                "severity": "low",
                "message": "Semantic Markdown-derived blocks are available; this page-level evidence block should not be compiled directly into Docling.",
            }
        )
        blocks.extend(semantic_blocks)

    parsing_res = official_json.get("parsing_res_list") or get_nested(official_json, "res", "parsing_res_list") or []
    table_res_list = official_json.get("table_res_list") or get_nested(official_json, "res", "table_res_list") or []
    formula_res_list = official_json.get("formula_res_list") or get_nested(official_json, "res", "formula_res_list") or []
    if not isinstance(parsing_res, list):
        parsing_res = []
    if not isinstance(table_res_list, list):
        table_res_list = []
    if not isinstance(formula_res_list, list):
        formula_res_list = []

    table_seen = 0
    formula_seen = 0
    media_refs: list[dict[str, Any]] = list(markdown_image_refs)
    media_refs.extend(ref for ref in semantic_media_refs if ref not in media_refs)

    for block_index, raw_block in enumerate(parsing_res):
        if not isinstance(raw_block, dict):
            continue
        native_label = str(raw_block.get("block_label") or raw_block.get("label") or raw_block.get("type") or "unknown")
        block_type, _, _, _ = classify_paddle_label(native_label)
        native_bbox = bbox_from_shape(raw_block.get("block_bbox") or raw_block.get("bbox") or raw_block.get("box"))
        bbox_norm = normalise_bbox(native_bbox, width_px, height_px)

        table_obj = None
        if block_type == "table":
            table_obj = build_table_object(
                f"{page_id}_r{block_index:04d}",
                find_best_table(table_res_list, native_bbox, table_seen),
                width=width_px,
                height=height_px,
            )
            table_seen += 1

        formula_obj = None
        if block_type == "formula":
            formula_obj = build_formula_object(
                f"{page_id}_r{block_index:04d}",
                find_best_formula(formula_res_list, native_bbox, formula_seen),
                str(raw_block.get("block_content") or "") or None,
            )
            formula_seen += 1

        raw_block["__ir_order_override"] = (len(semantic_blocks) + 1) + int(raw_block.get("block_order") if raw_block.get("block_order") is not None else block_index + 1)

        media_obj = crop_block_media(
            page_image_path=raster.image_path,
            media_dir=media_dir,
            page_index=page_index,
            block_index=block_index,
            block_type=block_type,
            bbox_norm=bbox_norm,
            alt_text=str(raw_block.get("block_content") or "") or None,
        )
        if media_obj is not None:
            media_refs.append(media_obj)

        blocks.append(
            make_layout_block(
                page_id=page_id,
                source_id=source_id,
                backend_id=backend_id,
                backend_name=backend_name,
                page_index=page_index,
                page_number=page_number,
                block_index=block_index,
                block=raw_block,
                raw_json_path=raw_json_path,
                clean_md_path=clean_md_path,
                width=width_px,
                height=height_px,
                ocr_lines=ocr_lines,
                table_obj=table_obj,
                formula_obj=formula_obj,
                media_obj=media_obj,
            )
        )

    # If the pipeline gives OCR lines but no structural regions, preserve them as fallback blocks.
    if not parsing_res and ocr_lines:
        for line_index, line in enumerate(ocr_lines):
            blocks.append(
                make_ocr_line_block(
                    page_id=page_id,
                    source_id=source_id,
                    backend_id=backend_id,
                    backend_name=backend_name,
                    page_index=page_index,
                    page_number=page_number,
                    line=line,
                    line_index=line_index,
                    order=(len(semantic_blocks) + 1) + line_index,
                    raw_json_path=raw_json_path,
                    clean_md_path=clean_md_path,
                )
            )

    image_quality = page_image_quality(raster.image_path, dpi=dpi if raster.image_path else None)

    flags: list[dict[str, Any]] = []
    flags.extend(scan_quality_flags(image_quality, dpi=dpi if raster.image_path else None, scan_profile=scan_profile))
    if is_empty:
        flags.append({"code": "empty_ocr_output", "severity": "high", "message": "PaddleOCR produced no OCR text for this page."})
    if not parsing_res:
        flags.append({"code": "layout_blocks_missing", "severity": "medium", "message": "No parsing_res_list layout blocks found in PaddleOCR output."})
    if width_px is None or height_px is None:
        flags.append({"code": "native_dimensions_missing", "severity": "medium", "message": "PaddleOCR page width/height missing; geometry normalisation may be unavailable."})

    page_ir = {
        "schema_name": "pdf2md.extraction_ir_page",
        "schema_version": "1.0.0",
        "ir_stage": "backend_extraction_page",
        "page_id": page_id,
        "document_id": source_id,
        "backend_id": backend_id,
        "backend_name": backend_name,
        "run_id": run_id,
        "page_index": page_index,
        "page_number": page_number,
        "status": "empty_output" if is_empty else "ok",
        "dimensions": {
            "width": raster.pdf_width,
            "height": raster.pdf_height,
            "unit": "pt" if raster.pdf_width is not None else None,
            "rotation": raster.rotation,
            "native_width_px": width_px,
            "native_height_px": height_px,
        },
        "rendering": {
            "page_image_ref": {
                "artifact_id": f"{page_id}_image",
                "path": safe_rel(raster.image_path) if raster.image_path else None,
                "mime_type": "image/png" if raster.image_path else None,
                "dpi": dpi if raster.image_path else None,
                "width_px": raster.image_width,
                "height_px": raster.image_height,
                "sha256": sha256_file(raster.image_path) if raster.image_path else None,
                "status": raster.status,
            },
            "page_image_quality": image_quality,
            "inference_input_ref": {
                "mode": "page_image" if predict_from_page_images else "pdf",
                "path": safe_rel(raster.image_path) if predict_from_page_images and raster.image_path else safe_rel(source_pdf),
                "coordinate_alignment": "native_pixel_geometry_matches_page_image" if predict_from_page_images else "normalised_geometry_projected_to_evidence_image",
            },
        },
        "blocks": blocks,
        "relationships": {
            "reading_order": [block["block_id"] for block in sorted(blocks, key=lambda item: item.get("order") or 0)],
            "parent_child": [],
            "caption_links": semantic_caption_links,
            "footnote_links": [],
            "media_refs": media_refs,
        },
        "page_text": {
            "plain_text": markdown_text,
            "normalised_text": normalised_page_text,
            "markdown": markdown_text,
            "text_hash": sha256_text(normalised_page_text),
        },
        "provenance": {
            "source_pdf": {
                "path": safe_rel(source_pdf),
                "sha256": source_sha256,
                "page_index": page_index,
                "page_number": page_number,
            },
            "model": {
                "model_id": pipeline_name,
                "model_path": None,
                "prompt": None,
                "prompt_mode": None,
                "dpi": dpi,
                "base_size": None,
                "image_size": None,
            },
            "raw_backend_refs": [
                {
                    "artifact_id": f"{page_id}_official_json",
                    "path": safe_rel(raw_json_path),
                    "kind": "paddleocr_result_json_attribute",
                    "sha256": sha256_file(raw_json_path),
                },
                {
                    "artifact_id": f"{page_id}_markdown_json",
                    "path": safe_rel(markdown_json_path),
                    "kind": "paddleocr_markdown_attribute",
                    "sha256": sha256_file(markdown_json_path),
                },
                {
                    "artifact_id": f"{page_id}_clean_markdown",
                    "path": safe_rel(clean_md_path),
                    "kind": "paddleocr_clean_markdown",
                    "sha256": sha256_file(clean_md_path),
                },
                {
                    "artifact_id": f"{page_id}_capture_metadata",
                    "path": safe_rel(capture_path),
                    "kind": "paddleocr_capture_metadata",
                    "sha256": sha256_file(capture_path),
                },
            ],
            "official_output_dir": safe_rel(official_page_dir),
            "official_saved_files": official_saved_files,
        },
        "observed_capabilities": {
            "ocr_text_found": not is_empty,
            "layout_blocks_found": bool(parsing_res),
            "layout_block_count": len(parsing_res),
            "semantic_markdown_block_count": len(semantic_blocks),
            "ocr_line_count": len(ocr_lines),
            "table_count": len(table_res_list),
            "formula_count": len(formula_res_list),
            "seal_count": len(official_json.get("seal_res_list") or get_nested(official_json, "res", "seal_res_list") or []),
            "media_count": len(media_refs),
            "markdown_image_count": len(markdown_image_refs),
            "has_markdown_payload": bool(markdown_plain),
            "scan_profile": scan_profile,
            "predict_from_page_images": predict_from_page_images,
            "page_image_quality_available": bool(image_quality.get("available")),
        },
        "flags": flags,
    }
    return finalise_page_ir_for_docling(page_ir)


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
    pipeline_name: str,
    device: str,
    ir_dir: Path,
    pages_dir: Path,
    page_image_dir: Path,
    raw_pages_dir: Path,
    official_results_dir: Path,
    media_dir: Path,
    page_refs: list[dict[str, Any]],
    native_json_files: list[dict[str, Any]],
    native_output_files: list[dict[str, Any]],
    observed_totals: dict[str, Any],
    flags: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    pages_empty = sum(1 for ref in page_refs if ref["status"] == "empty_output")
    pages_ok = sum(1 for ref in page_refs if ref["status"] == "ok")
    is_structure = pipeline_name == "pp_structurev3"
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
            "model_id": pipeline_name,
            "model_path": None,
            "device": device,
        },
        "source": {
            "source_id": source_id,
            "source_path": safe_rel(source_pdf),
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
            "native_paddleocr_coordinate_space": "paddleocr_image_pixels",
        },
        "page_refs": page_refs,
        "artifacts": {
            "ir_dir": safe_rel(ir_dir),
            "pages_dir": safe_rel(pages_dir),
            "page_image_dir": safe_rel(page_image_dir),
            "raw_pages_dir": safe_rel(raw_pages_dir),
            "official_results_dir": safe_rel(official_results_dir),
            "media_dir": safe_rel(media_dir),
            "native_json_files": native_json_files,
            "native_output_files": native_output_files,
        },
        "capabilities": {
            "layout_blocks": bool(is_structure),
            "reading_order": True,
            "ocr_lines": True,
            "ocr_spans": False,
            "tables": True if is_structure else "partial",
            "table_cells": True if is_structure else False,
            "formulas": True if is_structure else "partial",
            "figures": "partial",
            "captions": "partial",
            "headers_footers": "partial" if is_structure else False,
            "page_numbers": "partial" if is_structure else False,
            "geometry": True,
            "confidence_scores": "partial",
            "markdown": True,
            "semantic_markdown_blocks": True,
            "html": True if is_structure else "partial",
            "latex": "partial",
            "official_json": True,
        },
        "observed_capabilities": observed_totals,
        "quality": {
            "pages_total": page_count,
            "pages_ok": pages_ok,
            "pages_empty": pages_empty,
            "pages_with_ocr_text": int(observed_totals.get("pages_with_ocr_text", 0)),
            "pages_with_layout": int(observed_totals.get("pages_with_layout", 0)),
            "layout_block_count": int(observed_totals.get("layout_block_count", 0)),
            "ocr_line_count": int(observed_totals.get("ocr_line_count", 0)),
            "table_count": int(observed_totals.get("table_count", 0)),
            "formula_count": int(observed_totals.get("formula_count", 0)),
            "media_count": int(observed_totals.get("media_count", 0)),
            "semantic_markdown_block_count": int(observed_totals.get("semantic_markdown_block_count", 0)),
            "pages_with_page_images": int(observed_totals.get("pages_with_page_images", 0)),
        },
        "inference": config,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# PaddleOCR runners
# ---------------------------------------------------------------------------

def validate_input(path: str) -> Path:
    pdf = Path(path).expanduser().resolve()
    if not pdf.is_file():
        raise FileNotFoundError(f"Input file does not exist: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a .pdf file, got: {pdf.suffix}")
    return pdf


def validate_page_range(start: int | None, end: int | None) -> None:
    if start is not None and start < 0:
        raise ValueError("--start must be >= 0")
    if end is not None and end < 0:
        raise ValueError("--end must be >= 0")
    if start is not None and end is not None and end < start:
        raise ValueError("--end must be greater than or equal to --start")


def build_predict_kwargs(input_pdf: Path, page_start: int | None, page_end: int | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"input": str(input_pdf)}
    if page_start is not None:
        kwargs["start_page_idx"] = page_start
    if page_end is not None:
        kwargs["end_page_idx"] = page_end
    return kwargs


def _paddle_allowed_kwargs(cls: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Keep only explicit constructor args plus stable PaddleX wrapper args.

    PaddleOCR 3.x pipeline classes often expose ``**kwargs`` for the PaddleX
    wrapper. Passing a pipeline-specific flag that the class does not explicitly
    consume can therefore reach PaddleX and fail with errors such as:
    ``Unknown argument: use_ocr_for_image_block``. We filter proactively and also
    retry below if the local package still rejects a key.
    """
    try:
        sig = inspect.signature(cls)
    except Exception:
        return dict(kwargs)

    explicit = {
        name
        for name, param in sig.parameters.items()
        if name != "self" and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
    }

    # Known generic arguments accepted by the PaddleX wrapper even when not
    # declared on the thin PaddleOCR pipeline class.
    base_wrapper_args = {
        "device",
        "paddlex_config",
        "use_hpip",
        "hpi_config",
    }
    allowed = explicit | base_wrapper_args
    return {k: v for k, v in kwargs.items() if k in allowed and v is not None}


def _drop_unknown_arg_from_error(exc: BaseException) -> str | None:
    text = str(exc)
    patterns = (
        r"Unknown argument:\s*([A-Za-z_][A-Za-z0-9_]*)",
        r"unexpected keyword argument ['\"]([^'\"]+)['\"]",
        r"got an unexpected keyword argument ['\"]([^'\"]+)['\"]",
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return None


def instantiate_paddle_pipeline(cls: Any, kwargs: dict[str, Any], *, label: str) -> Any:
    """Instantiate a PaddleOCR pipeline while tolerating minor API drift."""
    filtered = _paddle_allowed_kwargs(cls, kwargs)
    dropped = sorted(set(kwargs) - set(filtered))
    if dropped:
        print(
            f"[warn] {label}: ignoring unsupported constructor option(s): {', '.join(dropped)}",
            file=sys.stderr,
        )

    attempts = 0
    while True:
        attempts += 1
        try:
            return cls(**filtered)
        except Exception as exc:
            bad_arg = _drop_unknown_arg_from_error(exc)
            if bad_arg and bad_arg in filtered and attempts <= 12:
                filtered.pop(bad_arg, None)
                print(
                    f"[warn] {label}: local PaddleOCR rejected {bad_arg!r}; retrying without it",
                    file=sys.stderr,
                )
                continue
            raise


def create_pipeline(
    pipeline_name: str,
    *,
    device: str,
    lang: str | None,
    engine: str | None,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    use_textline_orientation: bool,
    use_layout_detection: bool | None,
    use_chart_recognition: bool,
    use_seal_recognition: bool,
    use_ocr_for_image_block: bool,
    text_recognition_model_name: str | None,
) -> Any:
    if pipeline_name == "pp_structurev3":
        from paddleocr import PPStructureV3

        # Important: use_ocr_for_image_block is a PaddleOCR-VL option, not a
        # PP-StructureV3 constructor option in current PaddleOCR. Passing it to
        # PPStructureV3 can reach the PaddleX wrapper and fail as an unknown arg.
        kwargs: dict[str, Any] = {
            "device": device,
            "use_doc_orientation_classify": use_doc_orientation_classify,
            "use_doc_unwarping": use_doc_unwarping,
            "use_textline_orientation": use_textline_orientation,
            "use_chart_recognition": use_chart_recognition,
            "use_seal_recognition": use_seal_recognition,
            "lang": lang,
            "text_recognition_model_name": text_recognition_model_name,
        }
        if engine:
            kwargs["engine"] = engine
        return instantiate_paddle_pipeline(PPStructureV3, kwargs, label="PPStructureV3")

    if pipeline_name == "paddleocr_vl":
        from paddleocr import PaddleOCRVL

        kwargs = {
            "device": device,
            "use_doc_orientation_classify": use_doc_orientation_classify,
            "use_doc_unwarping": use_doc_unwarping,
            "use_layout_detection": use_layout_detection,
            "use_chart_recognition": use_chart_recognition,
            "use_seal_recognition": use_seal_recognition,
            "use_ocr_for_image_block": use_ocr_for_image_block,
        }
        if engine:
            kwargs["engine"] = engine
        return instantiate_paddle_pipeline(PaddleOCRVL, kwargs, label="PaddleOCRVL")

    if pipeline_name == "pp_ocrv5":
        from paddleocr import PaddleOCR

        kwargs = {
            "device": device,
            "use_doc_orientation_classify": use_doc_orientation_classify,
            "use_doc_unwarping": use_doc_unwarping,
            "use_textline_orientation": use_textline_orientation,
            "lang": lang,
        }
        return instantiate_paddle_pipeline(PaddleOCR, kwargs, label="PaddleOCR")

    raise ValueError(f"Unknown pipeline: {pipeline_name}")


def result_json(result: Any) -> dict[str, Any]:
    attr = getattr(result, "json", None)
    if attr is not None:
        plain = to_plain(attr)
        if isinstance(plain, dict):
            return plain
    plain = to_plain(result)
    if isinstance(plain, dict):
        res = plain.get("res")
        if isinstance(res, dict):
            merged = dict(res)
            for key, value in plain.items():
                if key not in merged:
                    merged[key] = value
            return merged
        return plain
    return {"coerced_result": plain}


def result_markdown(result: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
    payload = getattr(result, "markdown", None)
    if payload is None:
        return "", {}, {}
    return extract_markdown_payload(payload)


def run_inference(
    *,
    input_pdf: Path,
    ir_dir: Path,
    run_id: str,
    source_id: str,
    backend_id: str,
    backend_name: str,
    adapter_version: str,
    pipeline_name: str,
    device: str,
    lang: str | None,
    engine: str | None,
    dpi: int,
    scan_profile: str,
    predict_from_page_images: bool,
    page_start: int | None,
    page_end: int | None,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    use_textline_orientation: bool,
    use_layout_detection: bool | None,
    use_chart_recognition: bool,
    use_seal_recognition: bool,
    use_ocr_for_image_block: bool,
    text_recognition_model_name: str | None,
    keep_official_output: bool,
    discard_page_images: bool,
    fail_on_empty_output: bool,
) -> int:
    pages_dir = ir_dir / "pages"
    page_image_dir = ir_dir / "page_images"
    raw_pages_dir = ir_dir / "raw_pages"
    official_results_dir = ir_dir / "official_results"
    media_dir = ir_dir / "media"
    for d in (pages_dir, page_image_dir, raw_pages_dir, official_results_dir, media_dir):
        d.mkdir(parents=True, exist_ok=True)

    rasters = rasterise_pdf(input_pdf, page_image_dir, dpi=dpi)
    raster_by_index = {r.page_index: r for r in rasters}

    pipeline = create_pipeline(
        pipeline_name,
        device=device,
        lang=lang,
        engine=engine,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=use_textline_orientation,
        use_layout_detection=use_layout_detection,
        use_chart_recognition=use_chart_recognition,
        use_seal_recognition=use_seal_recognition,
        use_ocr_for_image_block=use_ocr_for_image_block,
        text_recognition_model_name=text_recognition_model_name,
    )

    if predict_from_page_images:
        if not rasters:
            raise RuntimeError("--predict-from-page-images requires PyMuPDF/Pillow rasterisation to succeed")
        selected_rasters = [
            r
            for r in rasters
            if (page_start is None or r.page_index >= page_start) and (page_end is None or r.page_index <= page_end)
        ]
        page_results: list[Any] = []
        for r in selected_rasters:
            if r.image_path is None:
                continue
            for res in pipeline.predict(input=safe_rel(r.image_path)):
                official_for_index = result_json(res)
                # Image-input prediction is page-local; preserve the original PDF page index.
                setattr(res, "__adapter_page_index", r.page_index) if hasattr(res, "__dict__") else None
                page_results.append((r.page_index, res, official_for_index))
        if not page_results:
            raise RuntimeError("PaddleOCR returned no pages from rasterised page images")
    else:
        predict_kwargs = build_predict_kwargs(input_pdf, page_start, page_end)
        output = pipeline.predict(**predict_kwargs)
        raw_results = list(output)
        if not raw_results:
            raise RuntimeError("PaddleOCR returned no pages")
        page_results = [(None, res, None) for res in raw_results]

    source_sha256 = sha256_file(input_pdf)
    created_at = now_utc()
    page_refs: list[dict[str, Any]] = []
    native_json_files: list[dict[str, Any]] = []
    native_output_files: list[dict[str, Any]] = []
    observed_totals: dict[str, Any] = {
        "page_count": len(page_results),
        "pages_with_ocr_text": 0,
        "pages_with_layout": 0,
        "layout_block_count": 0,
        "semantic_markdown_block_count": 0,
        "ocr_line_count": 0,
        "table_count": 0,
        "formula_count": 0,
        "media_count": 0,
        "pages_with_page_images": 0,
    }

    for fallback_index, packed in enumerate(page_results):
        forced_page_index, res, precomputed_official = packed
        official = precomputed_official if isinstance(precomputed_official, dict) else result_json(res)
        if forced_page_index is not None:
            official["__adapter_page_index"] = forced_page_index
        page_index = extract_page_index(official, forced_page_index if forced_page_index is not None else (page_start + fallback_index if page_start is not None else fallback_index))
        page_id = f"{backend_id}_p{page_index:04d}"
        official_page_dir = official_results_dir / f"page_{page_index:04d}"
        before = snapshot_outputs(official_page_dir)
        save_status = safe_save_result(res, official_page_dir, save_markdown=True, save_img=True)
        saved_files = new_files(official_page_dir, before)

        markdown_text, markdown_images, markdown_plain = result_markdown(res)
        markdown_image_refs = save_markdown_images(markdown_images, media_dir, page_index=page_index)

        raw_json_path = raw_pages_dir / f"page_{page_index:04d}.official.json"
        markdown_json_path = raw_pages_dir / f"page_{page_index:04d}.markdown.json"
        clean_md_path = raw_pages_dir / f"page_{page_index:04d}.clean.md"
        capture_path = raw_pages_dir / f"page_{page_index:04d}.capture.json"

        write_json(raw_json_path, official)
        write_json(markdown_json_path, markdown_plain if isinstance(markdown_plain, dict) else {"markdown": markdown_plain})
        write_text(clean_md_path, markdown_text)
        write_json(
            capture_path,
            {
                "pipeline": pipeline_name,
                "result_type": type(res).__name__,
                "official_output_dir": safe_rel(official_page_dir),
                "save_status": save_status,
                "official_saved_files": saved_files,
                "markdown_length": len(markdown_text),
                "markdown_image_count": len(markdown_image_refs),
                "result_json_keys": sorted(official.keys()),
                "markdown_keys": sorted(markdown_plain.keys()) if isinstance(markdown_plain, dict) else [],
            },
        )

        raster = raster_by_index.get(page_index) or fallback_raster(page_index)
        raster = recover_raster_from_official_outputs(raster, saved_files, page_image_dir, dpi=dpi)
        if discard_page_images and raster.image_path is not None:
            raster.image_path.unlink(missing_ok=True)
            raster.status = "deleted_after_inference"

        page_ir = build_page_ir(
            run_id=run_id,
            source_id=source_id,
            source_pdf=input_pdf,
            source_sha256=source_sha256,
            backend_id=backend_id,
            backend_name=backend_name,
            pipeline_name=pipeline_name,
            adapter_version=adapter_version,
            page_index=page_index,
            raster=raster,
            official_json=official,
            markdown_plain=markdown_plain if isinstance(markdown_plain, dict) else {},
            markdown_text=markdown_text,
            markdown_image_refs=markdown_image_refs,
            raw_json_path=raw_json_path,
            markdown_json_path=markdown_json_path,
            clean_md_path=clean_md_path,
            capture_path=capture_path,
            official_page_dir=official_page_dir,
            official_saved_files=saved_files,
            media_dir=media_dir,
            dpi=dpi,
            scan_profile=scan_profile,
            predict_from_page_images=predict_from_page_images,
        )

        page_json_path = pages_dir / f"page_{page_index:04d}.json"
        write_json(page_json_path, page_ir)

        obs = page_ir["observed_capabilities"]
        if obs["ocr_text_found"]:
            observed_totals["pages_with_ocr_text"] += 1
        if obs["layout_blocks_found"]:
            observed_totals["pages_with_layout"] += 1
        observed_totals["layout_block_count"] += int(obs["layout_block_count"])
        observed_totals["semantic_markdown_block_count"] += int(obs.get("semantic_markdown_block_count", 0))
        observed_totals["ocr_line_count"] += int(obs["ocr_line_count"])
        observed_totals["table_count"] += int(obs["table_count"])
        observed_totals["formula_count"] += int(obs["formula_count"])
        observed_totals["media_count"] += int(obs["media_count"])
        if (page_ir.get("extraction_summary") or {}).get("has_page_image"):
            observed_totals["pages_with_page_images"] += 1

        page_refs.append(
            {
                "page_id": page_id,
                "page_index": page_index,
                "page_number": page_index + 1,
                "path": safe_rel(page_json_path),
                "sha256": sha256_file(page_json_path),
                "status": page_ir["status"],
            }
        )
        native_json_files.append(
            {
                "artifact_id": f"{page_id}_official_json",
                "path": safe_rel(raw_json_path),
                "kind": "paddleocr_result_json_attribute",
                "sha256": sha256_file(raw_json_path),
            }
        )
        native_output_files.extend(
            [
                {
                    "artifact_id": f"{page_id}_markdown_json",
                    "path": safe_rel(markdown_json_path),
                    "kind": "paddleocr_markdown_attribute",
                    "sha256": sha256_file(markdown_json_path),
                },
                {
                    "artifact_id": f"{page_id}_clean_markdown",
                    "path": safe_rel(clean_md_path),
                    "kind": "paddleocr_clean_markdown",
                    "sha256": sha256_file(clean_md_path),
                },
                {
                    "artifact_id": f"{page_id}_capture_metadata",
                    "path": safe_rel(capture_path),
                    "kind": "paddleocr_capture_metadata",
                    "sha256": sha256_file(capture_path),
                },
            ]
        )
        for saved in saved_files:
            native_output_files.append(
                {
                    "artifact_id": f"{page_id}_official_saved_{len(native_output_files):04d}",
                    "path": saved["path"],
                    "kind": f"paddleocr_official_saved{saved.get('suffix', '')}",
                    "sha256": saved.get("sha256"),
                }
            )

    flags: list[dict[str, Any]] = []
    pages_empty = sum(1 for ref in page_refs if ref["status"] == "empty_output")
    if pages_empty:
        flags.append({"code": "empty_ocr_pages", "severity": "high", "message": f"{pages_empty} of {len(page_refs)} pages produced empty OCR output."})
    if observed_totals["layout_block_count"] == 0:
        flags.append({"code": "paddleocr_layout_missing", "severity": "medium", "message": "No PaddleOCR parsing_res_list layout blocks were found."})
    if not rasters:
        flags.append({"code": "page_images_unavailable", "severity": "medium", "message": "PyMuPDF/Pillow were not available, so page_images were not generated."})

    config = {
        "pipeline": pipeline_name,
        "device": device,
        "lang": lang,
        "engine": engine,
        "dpi": dpi,
        "scan_profile": scan_profile,
        "predict_from_page_images": predict_from_page_images,
        "page_start": page_start,
        "page_end": page_end,
        "use_doc_orientation_classify": use_doc_orientation_classify,
        "use_doc_unwarping": use_doc_unwarping,
        "use_textline_orientation": use_textline_orientation,
        "use_layout_detection": use_layout_detection,
        "use_chart_recognition": use_chart_recognition,
        "use_seal_recognition": use_seal_recognition,
        "use_ocr_for_image_block": use_ocr_for_image_block,
        "text_recognition_model_name": text_recognition_model_name,
        "save_results": True,
    }

    manifest = build_manifest(
        run_id=run_id,
        created_at=created_at,
        source_id=source_id,
        source_pdf=input_pdf,
        source_sha256=source_sha256,
        page_count=len(page_refs),
        backend_id=backend_id,
        backend_name=backend_name,
        backend_version=None,
        adapter_version=adapter_version,
        pipeline_name=pipeline_name,
        device=device,
        ir_dir=ir_dir,
        pages_dir=pages_dir,
        page_image_dir=page_image_dir,
        raw_pages_dir=raw_pages_dir,
        official_results_dir=official_results_dir,
        media_dir=media_dir,
        page_refs=page_refs,
        native_json_files=native_json_files,
        native_output_files=native_output_files,
        observed_totals=observed_totals,
        flags=flags,
        config=config,
    )
    manifest_path = ir_dir / "manifest.json"
    write_json(manifest_path, manifest)

    if not keep_official_output:
        # Keep our normalised raw_pages, but allow deletion of bulky Paddle visual outputs.
        shutil.rmtree(official_results_dir, ignore_errors=True)
        official_results_dir.mkdir(parents=True, exist_ok=True)

    print(f"[out] IR manifest: {manifest_path}")
    print(f"[out] IR pages: {pages_dir}")

    if fail_on_empty_output and pages_empty:
        return 2
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run PaddleOCR and write page-first extraction IR. No final Markdown export.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("-i", "--input", required=True, metavar="PDF", help="Input PDF path.")
    parser.add_argument("--out-dir", metavar="DIR", help="Base output directory. Default: .current/.")
    parser.add_argument("--ir-dir", metavar="DIR", help="IR root. Default: <out-dir>/extraction_ir/<pdf_stem>.")
    parser.add_argument("--run-id", default=None, metavar="ID", help="Run id. Default: generated UTC id.")
    parser.add_argument("--source-id", default=None, metavar="ID", help="Source id. Default: input PDF stem.")
    parser.add_argument("--backend-id", default=None, metavar="ID")
    parser.add_argument("--backend-name", default=None, metavar="NAME")
    parser.add_argument("--adapter-version", default=DEFAULT_ADAPTER_VERSION, metavar="VERSION")
    parser.add_argument("--discard-page-images", action="store_true")
    parser.add_argument("--fail-on-empty-output", action="store_true")
    parser.add_argument("--keep-official-output", action="store_true", help="Keep bulky PaddleOCR official_results visual/json/md files.")

    parser.add_argument("-p", "--pipeline", choices=PIPELINES, default="pp_structurev3")
    parser.add_argument("--device", default="gpu:0", metavar="DEV", help="Examples: gpu:0, cpu, xpu, dcu, metax_gpu.")
    parser.add_argument("--lang", default=None, metavar="LANG", help="Language hint, e.g. en, ch. Useful for PPStructureV3/PP-OCRv5.")
    parser.add_argument("--engine", default=None, choices=["paddle", "paddle_static", "paddle_dynamic", "transformers"], help="Optional inference engine where supported.")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, metavar="N", help="DPI used for evidence page images and optional page-image inference.")
    parser.add_argument("--scan-profile", choices=["scanned_book", "digital_pdf", "auto"], default="digital_pdf", help="Extraction profile. Use scanned_book to enable scan-oriented orientation/unwarping defaults.")
    parser.add_argument("--predict-from-page-images", action="store_true", help="Rasterise each PDF page and send the page PNG to PaddleOCR. Recommended for scanned books when you want coordinate-perfect evidence images.")
    parser.add_argument("--start", type=int, default=None, metavar="N", help="0-based inclusive start page.")
    parser.add_argument("--end", type=int, default=None, metavar="N", help="0-based end page passed to PaddleOCR.")

    parser.add_argument("--use-doc-orientation-classify", action="store_true")
    parser.add_argument("--use-doc-unwarping", action="store_true")
    parser.add_argument("--use-textline-orientation", action="store_true")
    parser.add_argument("--use-layout-detection", choices=["true", "false"], default=None, help="PaddleOCR-VL only. Omit to use Paddle default.")
    parser.add_argument("--use-chart-recognition", action="store_true")
    parser.add_argument("--use-seal-recognition", action="store_true")
    parser.add_argument("--use-ocr-for-image-block", action="store_true")
    parser.add_argument("--text-recognition-model-name", default=None, help="For English-only PDFs, e.g. en_PP-OCRv4_mobile_rec.")
    parser.add_argument("--disable-model-source-check", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.disable_model_source_check:
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    if args.scan_profile == "scanned_book":
        # Book scans are commonly skewed, rotated or slightly warped. These defaults
        # favour robust OCR evidence over speed and coordinate-stable page-image input.
        args.use_doc_orientation_classify = True
        args.use_textline_orientation = True
        args.predict_from_page_images = True

    try:
        input_pdf = validate_input(args.input)
        validate_page_range(args.start, args.end)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else Path(DEFAULT_CURRENT_DIR).expanduser().resolve()
    source_id = args.source_id or input_pdf.stem
    ir_dir = Path(args.ir_dir).expanduser().resolve() if args.ir_dir else (out_dir / "extraction_ir" / source_id).resolve()
    run_id = args.run_id or default_run_id()
    backend_id = args.backend_id or (DEFAULT_BACKEND_ID if args.pipeline == "pp_structurev3" else f"paddleocr_{args.pipeline}")
    backend_name = args.backend_name or backend_id
    use_layout_detection = None
    if args.use_layout_detection == "true":
        use_layout_detection = True
    elif args.use_layout_detection == "false":
        use_layout_detection = False

    try:
        return run_inference(
            input_pdf=input_pdf,
            ir_dir=ir_dir,
            run_id=run_id,
            source_id=source_id,
            backend_id=backend_id,
            backend_name=backend_name,
            adapter_version=args.adapter_version,
            pipeline_name=args.pipeline,
            device=args.device,
            lang=args.lang,
            engine=args.engine,
            dpi=args.dpi,
            scan_profile=args.scan_profile,
            predict_from_page_images=args.predict_from_page_images,
            page_start=args.start,
            page_end=args.end,
            use_doc_orientation_classify=args.use_doc_orientation_classify,
            use_doc_unwarping=args.use_doc_unwarping,
            use_textline_orientation=args.use_textline_orientation,
            use_layout_detection=use_layout_detection,
            use_chart_recognition=args.use_chart_recognition,
            use_seal_recognition=args.use_seal_recognition,
            use_ocr_for_image_block=args.use_ocr_for_image_block,
            text_recognition_model_name=args.text_recognition_model_name,
            keep_official_output=args.keep_official_output,
            discard_page_images=args.discard_page_images,
            fail_on_empty_output=args.fail_on_empty_output,
        )
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
