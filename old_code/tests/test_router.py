"""Router behavior guardrails for deterministic milestone."""

from pathlib import Path

from doc2md.models import DocumentProfile, FontEncodingQuality, PageProfile, Strategy
from doc2md.router import route_document


def _page(**overrides):
    base = dict(
        page_number=0,
        width=1000,
        height=1000,
        has_text_layer=True,
        text_render_mode=0,
        char_count=100,
        text_area_ratio=0.5,
        has_tounicode_cmap=True,
        font_encoding_quality=FontEncodingQuality.GOOD,
        image_count=0,
        image_coverage=0.05,
        char_sample="hello world",
        char_sample_valid=True,
    )
    base.update(overrides)
    return PageProfile(**base)


def test_poor_encoding_forces_visual() -> None:
    profile = DocumentProfile(path=Path("dummy.pdf"), page_count=1, pages=[
        _page(font_encoding_quality=FontEncodingQuality.POOR)
    ])
    route_document(profile)
    assert profile.pages[0].strategy == Strategy.VISUAL


def test_suspect_encoding_with_valid_sample_not_forced_visual() -> None:
    profile = DocumentProfile(path=Path("dummy.pdf"), page_count=1, pages=[
        _page(
            has_tounicode_cmap=False,
            font_encoding_quality=FontEncodingQuality.SUSPECT,
            char_sample="Readable sample",
            char_sample_valid=True,
            image_coverage=0.05,
        )
    ])
    route_document(profile)
    assert profile.pages[0].strategy == Strategy.DETERMINISTIC


def test_low_image_coverage_routes_deterministic() -> None:
    profile = DocumentProfile(path=Path("dummy.pdf"), page_count=1, pages=[
        _page(image_coverage=0.1)
    ])
    route_document(profile, text_threshold=0.8)
    assert profile.pages[0].strategy == Strategy.DETERMINISTIC
