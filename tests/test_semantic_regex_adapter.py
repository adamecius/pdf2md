"""Tests for the in-process regex semantic adapter (Plan 006_0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf2md.models import RefType
from pdf2md.semantic.regex_adapter import RegexSemanticBackend


REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TEXT = REPO_ROOT / "tests" / "data" / "semantic_fixtures" / "sample_text.txt"


@pytest.fixture(scope="module")
def fixture_text() -> str:
    if not SAMPLE_TEXT.is_file():
        pytest.skip(f"missing fixture: {SAMPLE_TEXT}")
    return SAMPLE_TEXT.read_text(encoding="utf-8")


def test_regex_adapter_reports_metadata() -> None:
    backend = RegexSemanticBackend()
    assert backend.name() == "regex"
    assert backend.version()
    assert backend.is_available() is True


def test_regex_adapter_produces_distinct_marker_types(fixture_text: str, tmp_path: Path) -> None:
    backend = RegexSemanticBackend(source_ref="#/texts/0")
    graph = backend.extract(pdf_path=None, text=fixture_text, output_dir=tmp_path)

    assert graph.markers, "regex adapter returned no markers"
    distinct = {str(m.marker_type) for m in graph.markers}
    assert len(distinct) >= 3, f"expected ≥3 distinct marker types, got {distinct}"
    assert "regex" in graph.backend_versions
    assert graph.backend_versions["regex"]
    assert graph.doc_hash.startswith("sha256:")


def test_regex_adapter_marker_taxonomy_is_canonical(fixture_text: str, tmp_path: Path) -> None:
    backend = RegexSemanticBackend()
    graph = backend.extract(pdf_path=None, text=fixture_text, output_dir=tmp_path)
    canonical = {t.value for t in RefType}
    for marker in graph.markers:
        assert str(marker.marker_type) in canonical


def test_regex_adapter_accepts_txt_path(tmp_path: Path) -> None:
    txt = tmp_path / "input.txt"
    txt.write_text("See Figure 3 and Table 2 for details.", encoding="utf-8")
    backend = RegexSemanticBackend()
    graph = backend.extract(pdf_path=txt, text=None, output_dir=tmp_path)
    types = {str(m.marker_type) for m in graph.markers}
    assert RefType.FIGURE.value in types
    assert RefType.TABLE.value in types


def test_regex_adapter_rejects_non_text_input(tmp_path: Path) -> None:
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    backend = RegexSemanticBackend()
    with pytest.raises(ValueError):
        backend.extract(pdf_path=pdf, text=None, output_dir=tmp_path)


def test_regex_adapter_uses_supplied_source_ref(tmp_path: Path) -> None:
    backend = RegexSemanticBackend(source_ref="#/texts/42")
    graph = backend.extract(pdf_path=None, text="See Figure 1.", output_dir=tmp_path)
    assert graph.markers, "no markers detected for 'See Figure 1.'"
    assert all(marker.source_ref == "#/texts/42" for marker in graph.markers)
