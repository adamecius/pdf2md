"""PDF structural profiler using PyMuPDF.

Analyzes PDF pages to determine extraction viability using only
software-level signals (no ML). Each page gets a PageProfile with
metrics that the router uses to assign a strategy.
"""

import unicodedata
from pathlib import Path

import pymupdf

from doc2md.models import (
    DocumentProfile,
    FontEncodingQuality,
    FontInfo,
    PageProfile,
)

# ── Constants ─────────────────────────────────────────────────

CHAR_SAMPLE_SIZE = 200       # chars to sample for mojibake detection
MOJIBAKE_THRESHOLD = 0.3     # if >30% of sample is suspect → mojibake
INVISIBLE_RENDER_MODE = 3

# Unicode categories that signal mojibake or garbage
_SUSPECT_CATEGORIES = {
    "Co",  # Private Use Area
    "Cn",  # Unassigned
    "Cc",  # Control chars (except common whitespace)
}
_WHITESPACE_CHARS = {"\n", "\r", "\t", " "}


def profile_document(path: Path) -> DocumentProfile:
    """Analyze a PDF and return a DocumentProfile with per-page signals."""

    doc = pymupdf.open(str(path))

    doc_profile = DocumentProfile(
        path=path,
        page_count=doc.page_count,
        pdf_version=f"{doc.metadata.get('format', 'unknown')}",
        is_encrypted=doc.is_encrypted,
        file_size_bytes=path.stat().st_size,
        has_forms=doc.is_form_pdf,
    )

    for page_num in range(doc.page_count):
        page = doc[page_num]
        page_profile = _profile_page(page, page_num)
        doc_profile.pages.append(page_profile)

    doc.close()
    return doc_profile


def _profile_page(page: pymupdf.Page, page_num: int) -> PageProfile:
    """Profile a single page using PyMuPDF introspection."""

    rect = page.rect
    page_area = rect.width * rect.height

    # ── Extract text dict for structural analysis ─────────────
    text_dict = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
    blocks = text_dict.get("blocks", [])

    # Separate text blocks from image blocks
    text_blocks = [b for b in blocks if b["type"] == 0]  # type 0 = text
    image_blocks = [b for b in blocks if b["type"] == 1]  # type 1 = image

    # ── Text layer signals ────────────────────────────────────
    raw_text = page.get_text()
    char_count = len(raw_text.strip())
    has_text_layer = char_count > 0

    # Text area: sum of text block bounding boxes
    text_area = 0.0
    for b in text_blocks:
        bx0, by0, bx1, by1 = b["bbox"]
        text_area += (bx1 - bx0) * (by1 - by0)
    text_area_ratio = min(text_area / page_area, 1.0) if page_area > 0 else 0.0

    # ── Image signals ─────────────────────────────────────────
    # Use both the dict image blocks AND get_images for embedded images
    page_images = page.get_images(full=True)
    image_count = len(page_images)

    image_area = 0.0
    for b in image_blocks:
        bx0, by0, bx1, by1 = b["bbox"]
        image_area += (bx1 - bx0) * (by1 - by0)
    image_coverage = min(image_area / page_area, 1.0) if page_area > 0 else 0.0

    # ── Font analysis ─────────────────────────────────────────
    fonts_raw = page.get_fonts(full=True)
    fonts, has_tounicode, encoding_quality = _analyze_fonts(fonts_raw)

    # ── Render mode heuristic ─────────────────────────────────
    # PyMuPDF doesn't expose Tr (render mode) directly in text dict.
    # Heuristic: if page has text AND a single image covering >85% of page,
    # the text is likely an invisible OCR layer (render_mode=3).
    text_render_mode = _infer_render_mode(
        has_text_layer, image_coverage, text_blocks, page
    )

    # ── Char sample validation ────────────────────────────────
    char_sample = raw_text.strip()[:CHAR_SAMPLE_SIZE]
    char_sample_valid = _validate_char_sample(char_sample) if char_sample else True

    return PageProfile(
        page_number=page_num,
        width=rect.width,
        height=rect.height,
        has_text_layer=has_text_layer,
        text_render_mode=text_render_mode,
        char_count=char_count,
        text_area_ratio=text_area_ratio,
        fonts=fonts,
        has_tounicode_cmap=has_tounicode,
        font_encoding_quality=encoding_quality,
        image_count=image_count,
        image_coverage=image_coverage,
        char_sample=char_sample,
        char_sample_valid=char_sample_valid,
    )


def _analyze_fonts(
    fonts_raw: list[tuple],
) -> tuple[list[FontInfo], bool, FontEncodingQuality]:
    """Analyze font metadata to determine encoding trustworthiness.

    PyMuPDF's get_fonts(full=True) returns tuples:
        (xref, ext, type, basefont, name, encoding, xref_stream)
    """

    fonts: list[FontInfo] = []
    all_have_tounicode = True
    worst_quality = FontEncodingQuality.GOOD

    # Standard encodings that reliably produce valid unicode
    _GOOD_ENCODINGS = {
        "WinAnsiEncoding",
        "MacRomanEncoding",
        "MacExpertEncoding",
        "StandardEncoding",
        "UniCNS-UCS2-H",
        "UniGB-UCS2-H",
        "UniJIS-UCS2-H",
        "UniKS-UCS2-H",
        "UTF-16BE",
    }

    for font_tuple in fonts_raw:
        # Unpack — length varies by PyMuPDF version, be defensive
        xref = font_tuple[0]
        font_type = font_tuple[2] if len(font_tuple) > 2 else ""
        basefont = font_tuple[3] if len(font_tuple) > 3 else ""
        name = font_tuple[4] if len(font_tuple) > 4 else ""
        encoding = font_tuple[5] if len(font_tuple) > 5 else ""

        # Determine ToUnicode presence heuristic:
        # - Identity-H/V without a known good encoding suggests missing ToUnicode
        # - Empty encoding is suspect
        has_tu = True
        if encoding in ("Identity-H", "Identity-V") and not any(
            k in basefont for k in ("Arial", "Times", "Courier", "Helvetica")
        ):
            # Identity-H CIDFonts from non-standard fonts often lack ToUnicode
            has_tu = False
        if not encoding:
            has_tu = False

        # Encoding quality
        if encoding in _GOOD_ENCODINGS:
            quality = FontEncodingQuality.GOOD
        elif encoding in ("Identity-H", "Identity-V"):
            # Could be fine (CJK with ToUnicode) or bad (custom without)
            quality = FontEncodingQuality.SUSPECT if not has_tu else FontEncodingQuality.GOOD
        elif font_type == "Type3":
            # Type3 fonts define their own glyphs, extraction is unreliable
            quality = FontEncodingQuality.POOR
        elif not encoding:
            quality = FontEncodingQuality.SUSPECT
        else:
            quality = FontEncodingQuality.SUSPECT

        is_embedded = bool(font_tuple[6]) if len(font_tuple) > 6 else False

        fonts.append(FontInfo(
            name=name or basefont,
            encoding=encoding or "unknown",
            has_tounicode=has_tu,
            is_embedded=is_embedded,
            quality=quality,
        ))

        if not has_tu:
            all_have_tounicode = False
        if quality.value > worst_quality.value:
            worst_quality = quality

    # If no fonts found, be neutral
    if not fonts:
        return fonts, True, FontEncodingQuality.GOOD

    return fonts, all_have_tounicode, worst_quality


def _infer_render_mode(
    has_text: bool,
    image_coverage: float,
    text_blocks: list[dict],
    page: pymupdf.Page,
) -> int | None:
    """Infer the dominant text render mode heuristically.

    Returns:
        0: normal visible text
        3: likely invisible (OCR layer over scan)
        None: no text present
    """

    if not has_text:
        return None

    # Heuristic: if image covers >85% of page AND text exists,
    # it's very likely a scanned page with invisible OCR text on top.
    if image_coverage > 0.85:
        return INVISIBLE_RENDER_MODE

    # Additional heuristic: check if text blocks overlap significantly
    # with image blocks (text sitting behind/on images)
    # For now, assume normal rendering
    return 0


def _validate_char_sample(sample: str) -> bool:
    """Check if a text sample looks like valid readable text vs mojibake.

    Flags as invalid if too many characters are:
    - Private Use Area (PUA) codepoints
    - Unassigned unicode points
    - Control characters (excluding whitespace)
    - Replacement character U+FFFD
    """

    if not sample:
        return True

    suspect_count = 0
    total_checked = 0

    for ch in sample:
        if ch in _WHITESPACE_CHARS:
            continue

        total_checked += 1
        cat = unicodedata.category(ch)

        if cat in _SUSPECT_CATEGORIES:
            suspect_count += 1
        elif ch == "\ufffd":  # replacement character
            suspect_count += 1

    if total_checked == 0:
        return True

    suspect_ratio = suspect_count / total_checked
    return suspect_ratio < MOJIBAKE_THRESHOLD