from pathlib import Path

from pdf2md.utils import media_materializer as mm


def test_to_rect_padding_clamp():
    rect = mm._to_rect([0, 0, 1000, 1000], 200, 300, 8)
    assert rect == (0, 0, 200, 300)


def test_missing_pdf_warning(tmp_path: Path):
    c = {"pdf_path": str(tmp_path / "missing.pdf"), "pages": []}
    s = {"anchors": []}
    manifest, code = mm.materialize(c, s, tmp_path)
    assert code == 0
    assert manifest["warnings"]


def test_manifest_written(tmp_path: Path):
    c = {"pdf_path": str(tmp_path / "missing.pdf"), "pages": []}
    s = {"anchors": []}
    manifest = mm.build_manifest(c, s, tmp_path)
    assert manifest["schema_name"] == "pdf2md.media_manifest"
