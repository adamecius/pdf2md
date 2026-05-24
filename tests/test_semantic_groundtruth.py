"""Tests for the LaTeXML ground-truth parser (Plan 007_0)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pdf2md.models import RefType
from pdf2md.semantic.groundtruth import (
    LatexMLUnavailableError,
    generate_ground_truth,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_TEX = (
    REPO_ROOT
    / "groundtruth"
    / "corpus"
    / "latex"
    / "linked_sections_figures"
    / "linked_sections_figures.tex"
)


def _have_latexml() -> bool:
    return shutil.which("latexml") is not None


@pytest.fixture
def gt_fixture(tmp_path: Path):
    if not FIXTURE_TEX.is_file():
        pytest.skip(f"missing fixture: {FIXTURE_TEX}")
    if not _have_latexml():
        pytest.skip("latexml not on PATH")
    graph = generate_ground_truth(FIXTURE_TEX, tmp_path)
    return graph, tmp_path


def test_generate_ground_truth_extracts_markers(gt_fixture) -> None:
    graph, _tmp = gt_fixture
    assert graph.markers, "ground truth produced no markers"
    types = {str(m.marker_type) for m in graph.markers}
    # The fixture has at least figure, equation, section, and footnote refs.
    assert RefType.FIGURE.value in types
    assert RefType.SECTION.value in types
    assert "ground_truth" in graph.backend_versions


def test_generate_ground_truth_resolves_edges(gt_fixture) -> None:
    graph, _tmp = gt_fixture
    assert graph.edges, "ground truth produced no edges"
    resolved = [edge for edge in graph.edges if edge.resolved]
    assert resolved, "expected at least one resolved edge"
    for edge in resolved:
        assert edge.target_ref is not None
        assert edge.target_ref.startswith("#")
        assert edge.resolution_method == "grobid_tei"


def test_generate_ground_truth_writes_latexml_xml(gt_fixture) -> None:
    _graph, tmp = gt_fixture
    xml_files = list(tmp.glob("*.latexml.xml"))
    assert len(xml_files) == 1
    body = xml_files[0].read_text(encoding="utf-8")
    assert "<document" in body or "<?xml" in body


def test_generate_ground_truth_raises_on_missing_tex(tmp_path: Path) -> None:
    if not _have_latexml():
        pytest.skip("latexml not on PATH")
    with pytest.raises(FileNotFoundError):
        generate_ground_truth(tmp_path / "missing.tex", tmp_path)


def test_generate_ground_truth_raises_when_latexml_missing(tmp_path: Path) -> None:
    if not FIXTURE_TEX.is_file():
        pytest.skip(f"missing fixture: {FIXTURE_TEX}")
    with pytest.raises(LatexMLUnavailableError):
        generate_ground_truth(
            FIXTURE_TEX,
            tmp_path,
            latexml_bin="latexml_not_a_real_binary_xyz",
        )


def test_generate_ground_truth_marker_text_is_surface_form(gt_fixture) -> None:
    """The labelref ``LABEL:fig:box-diagram`` should resolve to ``Figure 1``."""
    graph, _tmp = gt_fixture
    figure_markers = [m for m in graph.markers if m.marker_type == RefType.FIGURE.value]
    assert figure_markers, "no figure markers produced"
    # All figure markers should look like "Figure N", not the internal label.
    for marker in figure_markers:
        assert marker.marker_text.lower().startswith("figure")
