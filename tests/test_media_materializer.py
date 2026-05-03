from pathlib import Path
import sys
import types

from pdf2md.utils import media_materializer as mm


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.width = x1 - x0
        self.height = y1 - y0


class _Pix:
    def __init__(self, calls):
        self.calls = calls

    def save(self, p):
        self.calls.append(("save", p))


class _Page:
    def __init__(self, calls):
        self.rect = _Rect(0, 0, 600, 800)
        self.calls = calls

    def get_pixmap(self, matrix=None, clip=None, alpha=False):
        self.calls.append(("get_pixmap", clip is not None, matrix))
        return _Pix(self.calls)


class _Doc:
    def __init__(self, calls):
        self.calls = calls

    def load_page(self, pidx):
        return _Page(self.calls)


def _fitz_stub(calls):
    m = types.SimpleNamespace()
    m.open = lambda p: _Doc(calls)
    m.Matrix = lambda a, b: (a, b)
    m.Rect = lambda x0, y0, x1, y1: _Rect(x0, y0, x1, y1)
    def bad_pixmap(*args, **kwargs):
        raise AssertionError("Pixmap crop constructor should not be used")
    m.Pixmap = bad_pixmap
    return m


def test_policy_and_clip_render(tmp_path: Path, monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "fitz", _fitz_stub(calls))
    pdf = tmp_path / "a.pdf"; pdf.write_bytes(b"x")
    consensus = {"pdf_path": str(pdf), "pages": [{"page_index": 0, "candidate_groups": [
        {"group_id": "g1", "kind": "picture", "agreement": {"geometry": "near"}, "representative_bbox": [10,10,50,50], "sources": ["mineru"]},
        {"group_id": "g2", "kind": "picture", "agreement": {"geometry": "conflict"}, "representative_bbox": [10,10,50,50]},
        {"group_id": "g3", "kind": "picture", "agreement": {"geometry": "single_source"}, "representative_bbox": [10,10,50,50]},
        {"group_id": "g4", "kind": "picture", "compile_role": "evidence_only", "agreement": {"geometry": "near"}, "representative_bbox": [10,10,50,50]},
        {"group_id": "g5", "kind": "table", "agreement": {"geometry": "near"}, "representative_bbox": [10,10,50,50]},
    ]}]}
    sem = {"anchors": [{"anchor_type": "figure", "target_group_id": "g1", "anchor_id": "fig:1.2"}]}
    mf, code = mm.materialize(consensus, sem, tmp_path, source_consensus_report=Path("/in/c.json"), source_semantic_links=Path("/in/s.json"))
    assert code == 0
    assert any(c[0] == "get_pixmap" and c[1] for c in calls)
    assert len(mf["assets"]) == 2  # g1 near + g3 single_source
    g1 = [a for a in mf["assets"] if a["source_group_id"] == "g1"][0]
    assert g1["anchor_id"] == "fig:1.2" and g1["media_type"] == "figure"
    assert g1["media_id"] == "media:fig_1_2"
    assert any("geometry_conflict" in w for w in mf["warnings"])
    assert mf["source_consensus_report"] == "/in/c.json"
    assert "policy" in mf


def test_conflict_allowed_and_table_fallback(tmp_path: Path, monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "fitz", _fitz_stub(calls))
    pdf = tmp_path / "a.pdf"; pdf.write_bytes(b"x")
    c = {"pdf_path": str(pdf), "pages": [{"page_index": 0, "candidate_groups": [
        {"group_id": "g1", "kind": "picture", "agreement": {"geometry": "conflict"}, "representative_bbox": [10,10,50,50]},
        {"group_id": "g2", "kind": "table", "agreement": {"geometry": "near"}, "representative_bbox": [10,10,50,50]},
    ]}]}
    mf, _ = mm.materialize(c, {"anchors": []}, tmp_path, source_consensus_report=Path("c"), source_semantic_links=Path("s"), allow_conflicted_geometry=True, crop_tables_as_visual_fallback=True)
    assert any(a["status"] == "geometry_conflict" for a in mf["assets"])
    assert any(a["media_type"] == "table_visual_fallback" for a in mf["assets"])


def test_strict_all_fail(tmp_path: Path):
    mf, code = mm.materialize({"pdf_path": str(tmp_path / "missing.pdf"), "pages": []}, {"anchors": []}, tmp_path, source_consensus_report=Path("c"), source_semantic_links=Path("s"), strict=True)
    assert code != 0
