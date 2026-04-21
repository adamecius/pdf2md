"""Router: assigns extraction strategy to each page based on structural signals.

This is a pure function with no ML — it only reads PageProfile fields
and applies threshold logic to decide DETERMINISTIC / HYBRID / VISUAL.
"""

from doc2md.models import (
    DocumentProfile,
    FontEncodingQuality,
    PageProfile,
    Strategy,
)

# ── Default thresholds ────────────────────────────────────────

IMAGE_COVERAGE_SCAN_THRESHOLD = 0.85   # above this → likely a full-page scan
INVISIBLE_RENDER_MODE = 3


def route_document(profile: DocumentProfile, text_threshold: float = 0.8) -> None:
    """Assign a Strategy to each page in the profile (mutates in place)."""

    for page in profile.pages:
        page.strategy = _route_page(page, text_threshold)


def _route_page(page: PageProfile, text_threshold: float) -> Strategy:
    """Determine strategy for a single page.

    Decision cascade (first match wins):
      1. No text layer at all                           → VISUAL
      2. Full-page image (scanned page)                 → VISUAL
      3. Invisible render mode (OCR layer over scan)    → VISUAL
      4. Font encoding untrustworthy                    → VISUAL
      5. Char sample is mojibake                        → VISUAL
      6. Text trustworthy + low image coverage           → DETERMINISTIC
      7. Text trustworthy + significant image coverage   → HYBRID

    The text_threshold parameter controls the image_coverage boundary:
    pages with image_coverage < (1 - text_threshold) go deterministic.
    Default text_threshold=0.8 → image_coverage < 0.2 → DETERMINISTIC.
    """

    # 1. No text layer
    if not page.has_text_layer:
        return Strategy.VISUAL

    # 2. Dominated by images (scanned page with or without text)
    if page.image_coverage > IMAGE_COVERAGE_SCAN_THRESHOLD:
        return Strategy.VISUAL

    # 3. Invisible text (render mode 3)
    if page.text_render_mode == INVISIBLE_RENDER_MODE:
        return Strategy.VISUAL

    # 4. Font encoding problems
    if page.font_encoding_quality == FontEncodingQuality.POOR:
        return Strategy.VISUAL
    if not page.has_tounicode_cmap and page.font_encoding_quality == FontEncodingQuality.SUSPECT:
        return Strategy.VISUAL

    # 5. Mojibake detected in sample
    if not page.char_sample_valid:
        return Strategy.VISUAL

    # ── Text layer is trustworthy at this point ───────────────

    # 6. Low image coverage → text captures the page content
    image_threshold = 1.0 - text_threshold  # 0.8 → 0.2
    if page.image_coverage < image_threshold:
        return Strategy.DETERMINISTIC

    # 7. Significant images present → need visual pipeline for those
    return Strategy.HYBRID
