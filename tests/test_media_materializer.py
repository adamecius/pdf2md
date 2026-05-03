from pathlib import Path
import sys
import types

from pdf2md.utils import media_materializer as mm


class _Pix:
    width = 1000
    height = 1000


class _Page:
    def get_pixmap(self, matrix=None, alpha=False):
        return _Pix()


class _Doc:
    def load_page(self, pidx):
        return _Page()


def _fitz_stub(saved):
    m = types.SimpleNamespace()
    m.open = lambda p: _Doc()
    m.Matrix = lambda a, b: (a, b)
    m.IRect = lambda *r: r

    class PM:
        def __init__(self, pix, rect):
            self.rect = rect

        def save(self, p):
            saved.append(p)

    m.Pixmap = PM
    return m


def test_media_rules(tmp_path: Path, monkeypatch):
    saved = []
    monkeypatch.setitem(sys.modules, "fitz", _fitz_stub(saved))
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"x")
    consensus = {"pdf_path": str(pdf), "pages": [{"page_index": 0, "candidate_groups": [
        {"group_id": "g1", "kind": "picture", "agreement": {"geometry": "near"}, "representative_bbox": [10, 10, 20, 20], "sources": ["mineru"], "members": ["e1"]},
        {"group_id": "g2", "kind": "picture", "agreement": {"geometry": "conflict"}, "representative_bbox": [10, 10, 20, 20], "members": ["e2"]},
        {"group_id": "g3", "kind": "picture", "agreement": {"geometry": "single_source"}, "representative_bbox": [10, 10, 20, 20], "members": ["e3"]},
        {"group_id": "g4", "kind": "picture", "agreement": {"geometry": "near"}, "compile_role": "evidence_only", "representative_bbox": [10,10,20,20]},
        {"group_id": "g5", "kind": "picture", "agreement": {"geometry": "near"}},
    ]}]}
    sem = {"anchors": [{"anchor_type": "figure", "target_group_id": "g1", "anchor_id": "fig:1.1"}]}
    mf, code = mm.materialize(consensus, sem, tmp_path, source_consensus_report=Path("/x/c.json"), source_semantic_links=Path("/x/s.json"))
    assert code == 0
    assert len(mf["assets"]) == 2
    a1 = [a for a in mf["assets"] if a["source_group_id"] == "g1"][0]
    assert a1["anchor_id"] == "fig:1.1"
    assert any("conflict" in w for w in mf["warnings"])
    assert any("No bbox" in w for w in mf["warnings"])
    assert mf["source_consensus_report"] == "/x/c.json"


def test_strict_missing_pdf(tmp_path: Path):
    mf, code = mm.materialize({"pdf_path": str(tmp_path / "x.pdf"), "pages": []}, {"anchors": []}, tmp_path, source_consensus_report=Path("c"), source_semantic_links=Path("s"), strict=True)
    assert code != 0
