from pathlib import Path

import pytest

from tests.docling_groundtruth.tools.check_latex_support import detect_latex_support
from tests.docling_groundtruth.tools.generate_latex_fixtures import generate_pdf
from tests.groundtruth_paths import corpus_tex_path


BATCH = "batch_001"
DOCS = ["linked_sections_figures", "lists_footnotes_tables"]


def test_latex_sources_exist() -> None:
    for doc_id in DOCS:
        path = corpus_tex_path(doc_id, BATCH)
        assert path.exists(), f"missing LaTeX source: {path}"


def test_latex_support_checker() -> None:
    support = detect_latex_support()
    assert support.available or support.reason


@pytest.mark.parametrize("doc_id", DOCS)
def test_optional_pdf_generation(doc_id: str, tmp_path: Path) -> None:
    support = detect_latex_support()
    if not support.available:
        pytest.skip(support.reason)
    tex_path = corpus_tex_path(doc_id, BATCH)
    out_pdf = tmp_path / f"{doc_id}.pdf"
    assert generate_pdf(tex_path, out_pdf)
    assert out_pdf.exists() and out_pdf.stat().st_size > 0
