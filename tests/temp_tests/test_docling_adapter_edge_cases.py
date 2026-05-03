from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.utils import docling_adapter as da


class FakeDoclingLabelText:
    def __init__(self):
        self.calls = []

    def add_text(self, label, text):
        self.calls.append((label, text))

    def add_picture(self, path, caption=None):
        self.calls.append(("picture", path, caption))

    def export_to_dict(self):
        return {"calls": self.calls}

    def export_to_markdown(self):
        return "ok"


class FakeDoclingNoPicture(FakeDoclingLabelText):
    def add_picture(self, path, caption=None):
        raise TypeError("unsupported")


class FakeDoclingNoText(FakeDoclingLabelText):
    def add_text(self, label, text):
        raise TypeError("broken add_text")


def _sem(blocks, refs=None, rels=None, validation=None, warnings=None, conflicts=None):
    return {
        "schema_name": "pdf2md.semantic_document",
        "blocks": blocks,
        "anchors": [],
        "references": refs or [],
        "relations": rels or [],
        "conflicts": conflicts or [],
        "warnings": warnings or [],
        "validation": validation or {"unresolved_references": []},
    }


def test_docling_backend_add_text_signature_label_text():
    backend = da.DoclingBackend(FakeDoclingLabelText())
    backend.add_text("hello", semantic_type="paragraph")
    assert backend.doc.calls[0][1] == "hello"


def test_picture_degrades_to_text_when_add_picture_unsupported():
    sem = _sem([{"id": "block:f", "type": "figure", "text": "Fig", "media_path": "missing.png", "anchor_id": "fig:1"}])
    doc, rel, rep, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingNoPicture()), mode="inspection")
    assert any("degraded_block:block:f:figure->text:TypeError" in w for w in rep["warnings"])
    assert rel["id_map"]["block:f"]["docling_type"] == "text"
    assert isinstance(doc, dict)
    _, _, rep_strict, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingNoPicture()), mode="strict")
    assert any(e.startswith("degraded_block:block:f:figure->text:TypeError") for e in rep_strict["errors"])


def test_add_text_unsupported_raises_adapter_error():
    backend = da.DoclingBackend(FakeDoclingNoText())
    with pytest.raises(da.AdapterError):
        backend.add_text("hello", semantic_type="paragraph")


def test_synthetic_orphan_media_default_and_strict():
    sem = _sem([{"id": "block:orphan", "type": "figure", "text": "", "media_path": "x.png", "anchor_id": None}])
    _, rel, rep, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingLabelText()), mode="inspection", include_orphan_media=False)
    assert rel["id_map"]["block:orphan"]["suppressed"] is True
    assert "orphan_media_suppressed:block:orphan" in rel["warnings"]
    assert not rep["errors"]
    _, _, rep_strict, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingLabelText()), mode="strict", include_orphan_media=False)
    assert any(e.startswith("orphan_media_suppressed:block:orphan") for e in rep_strict["errors"])


def test_duplicate_formula_and_not_fused_warning():
    sem = _sem([
        {"id": "block:f1", "type": "formula", "text": "x", "anchor_id": "eq:1", "selected_text_source": "mineru", "selected_geometry_source": "paddleocr", "bbox": [1, 2, 3, 4]},
        {"id": "block:f2", "type": "formula", "text": "x", "anchor_id": "eq:1", "selected_text_source": "mineru", "selected_geometry_source": "mineru", "bbox": None},
    ])
    _, rel, rep, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingLabelText()))
    assert any(w.startswith("duplicate_formula_candidates:eq:1:block:f1,block:f2") for w in rep["warnings"])
    assert any(w == "formula_text_geometry_not_fused:block:f1" for w in rel["warnings"])


def test_fragmented_caption_preserves_fragments():
    sem = _sem(
        [
            {"id": "block:fig", "type": "figure", "anchor_id": "fig:1.2", "media_path": "x.png", "text": ""},
            {"id": "block:c1", "type": "caption", "text": "Figure"},
            {"id": "block:c2", "type": "caption", "text": "1.2"},
        ],
        rels=[
            {"relation_id": "r1", "relation_type": "caption_of", "source_id": "block:c1", "target_id": "block:fig"},
            {"relation_id": "r2", "relation_type": "caption_of", "source_id": "block:c2", "target_id": "block:fig"},
        ],
    )
    _, rel, _, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingLabelText()), include_orphan_media=True)
    assert any(w.startswith("fragmented_caption:fig:1.2:block:c1,block:c2") for w in rel["warnings"])
    assert "block:c1" in [n["id"] for n in rel["nodes"]]


def test_unresolved_reference_and_footnote_marker_modes():
    sem = _sem([], refs=[{"reference_id": "ref1", "reference_type": "footnote", "resolved": False}], validation={"unresolved_references": ["ref1"]})
    _, rel, rep, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingLabelText()), mode="inspection")
    assert "unresolved_reference:ref1" in rel["warnings"]
    assert "footnote_marker_unresolved:ref1" in rel["warnings"]
    assert not rep["errors"]
    _, _, rep2, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingLabelText()), mode="strict")
    assert any(e.startswith("unresolved_reference:ref1") for e in rep2["errors"])


def test_table_degradation_preserves_conflict_sidecar():
    sem = _sem([{"id": "block:t1", "type": "table", "text": "", "conflicts": [{"type": "table_disagreement"}]}], conflicts=[{"type": "table_disagreement", "group_ids": ["t1"]}])
    _, rel, rep, _ = da.adapt_semantic_document(sem, backend=da.DoclingBackend(FakeDoclingLabelText()))
    assert "table_structure_degraded:block:t1" in rel["warnings"]
    assert any(c.get("type") == "table_disagreement" for c in rel["conflicts"])


def test_stale_lineage_warning_preserved_in_adapter(tmp_path: Path):
    sem = _sem([], warnings=["stale_upstream_hash_mismatch:media_manifest.upstream_sha256.semantic_links"])
    inp = tmp_path / "semantic_document.json"
    out = tmp_path / "out"
    out.mkdir()
    inp.write_text(json.dumps(sem), encoding="utf-8")
    rc = da.main
    import sys
    old = sys.argv
    try:
        sys.argv = ["x", str(inp), "--output-root", str(out), "--mode", "inspection"]
        monkey_backend = da.DoclingBackend(FakeDoclingLabelText())
        orig = da.DoclingBackend.load
        da.DoclingBackend.load = staticmethod(lambda: monkey_backend)
        assert rc() == 0
    finally:
        da.DoclingBackend.load = orig
        sys.argv = old
    rel = json.loads((out / "docling_relations.json").read_text(encoding="utf-8"))
    rep = json.loads((out / "docling_adapter_report.json").read_text(encoding="utf-8"))
    assert any("stale_upstream_hash_mismatch" in w for w in rel["warnings"] + rep["warnings"])
