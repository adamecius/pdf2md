"""Shared data models for doc2md pipeline."""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class Strategy(Enum):
    """Extraction strategy assigned to a page by the router."""
    DETERMINISTIC = auto()
    HYBRID = auto()
    VISUAL = auto()


class FontEncodingQuality(Enum):
    """How trustworthy the font encoding is for text extraction."""
    GOOD = auto()      # Standard encodings (WinAnsi, MacRoman, Identity-H with ToUnicode)
    SUSPECT = auto()   # Non-standard but partially decodable
    POOR = auto()      # No ToUnicode, custom encoding, likely mojibake


@dataclass
class FontInfo:
    """Metadata for a single font used in a page."""
    name: str
    encoding: str
    has_tounicode: bool
    is_embedded: bool
    quality: FontEncodingQuality = FontEncodingQuality.GOOD


@dataclass
class PageProfile:
    """Structural profile of a single PDF page, computed without ML."""
    page_number: int
    width: float
    height: float

    # ── Text layer signals ────────────────────────────────────
    has_text_layer: bool             # any text operators in content stream?
    text_render_mode: int | None     # dominant render mode (0=normal, 3=invisible, None=no text)
    char_count: int                  # total extractable characters
    text_area_ratio: float           # fraction of page area covered by text blocks (0-1)

    # ── Font signals ──────────────────────────────────────────
    fonts: list[FontInfo] = field(default_factory=list)
    has_tounicode_cmap: bool = True  # do ALL fonts have ToUnicode?
    font_encoding_quality: FontEncodingQuality = FontEncodingQuality.GOOD

    # ── Image signals ─────────────────────────────────────────
    image_count: int = 0
    image_coverage: float = 0.0      # fraction of page area covered by images (0-1)

    # ── Sample validation ─────────────────────────────────────
    char_sample: str = ""            # first N chars extracted
    char_sample_valid: bool = True   # is the sample valid unicode / not mojibake?

    # ── Router decision (filled by router, not profiler) ──────
    strategy: Strategy | None = None


@dataclass
class DocumentProfile:
    """Aggregated profile for an entire PDF document."""
    path: Path
    page_count: int
    pages: list[PageProfile] = field(default_factory=list)

    # ── Document-level metadata ───────────────────────────────
    pdf_version: str = ""
    is_encrypted: bool = False
    is_linearized: bool = False
    has_forms: bool = False
    file_size_bytes: int = 0

    @property
    def deterministic_pages(self) -> list[PageProfile]:
        return [p for p in self.pages if p.strategy == Strategy.DETERMINISTIC]

    @property
    def hybrid_pages(self) -> list[PageProfile]:
        return [p for p in self.pages if p.strategy == Strategy.HYBRID]

    @property
    def visual_pages(self) -> list[PageProfile]:
        return [p for p in self.pages if p.strategy == Strategy.VISUAL]
