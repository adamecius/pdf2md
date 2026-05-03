from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pdf2md.utils.docling_adapter import adapt_semantic_document


def _semantic(blocks, anchors=None, refs=None, rels=None, warnings=None):
    return {
        "schema_name": "pdf2md.semantic_document",
        "blocks": blocks,
        "anchors": anchors or [],
        "references": refs or [],
        "relations": rels or [],
        "conflicts": [],
        "warnings": warnings or [],
        "validation": {"unresolved_references": ["ref:1"]},
    }


def test_minimal_paragraph_maps():
    sem = _semantic([{"id": "block:g1", "type": "paragraph", "text": "hello", "page_number": 1, "bbox": [1,2,3,4], "source_group_id": "g1", "sources": ["a"]}])
    doc, rel, rep = adapt_semantic_document(sem)
    assert doc["texts"][0]["text"] == "hello"
    assert rel["id_map"]["block:g1"]["docling_ref"] == "#/texts/0"
    assert any(w.startswith("unresolved_reference:") for w in rep["warnings"])


def test_anchored_figure_maps_picture_and_sidecar():
    blocks = [{"id": "block:g1", "type": "figure", "text": "", "page_number": 1, "bbox": [1,2,3,4], "source_group_id": "g1", "media_path": "media/f.png", "anchor_id": "fig:1.2"}]
    sem = _semantic(blocks)
    doc, rel, _ = adapt_semantic_document(sem)
    assert doc["pictures"] and doc["pictures"][0]["image_path"] == "media/f.png"
    assert rel["id_map"]["block:g1"]["docling_type"] == "picture"


def test_orphan_media_suppressed_by_default_and_included_when_enabled():
    blocks = [{"id": "block:g1", "type": "figure", "text": "", "page_number": 1, "bbox": [1,2,3,4], "source_group_id": "g1", "media_path": "media/f.png"}]
    sem = _semantic(blocks)
    doc, rel, _ = adapt_semantic_document(sem)
    assert not doc["pictures"]
    assert any("orphan_media_suppressed:block:g1" == w for w in rel["warnings"])
    doc2, _, _ = adapt_semantic_document(sem, include_orphan_media=True)
    assert doc2["pictures"]


def test_duplicate_formula_and_fragmented_caption_warnings_preserved():
    blocks = [
        {"id": "block:f1", "type": "formula", "text": "E=mc^2", "anchor_id": "eq:1", "page_number": 1, "source_group_id": "f1"},
        {"id": "block:f2", "type": "formula", "text": "E=mc^2", "anchor_id": "eq:1", "page_number": 1, "source_group_id": "f2"},
        {"id": "block:c1", "type": "caption", "text": "Figure", "anchor_id": "fig:1.2", "page_number": 1, "source_group_id": "c1"},
        {"id": "block:c2", "type": "caption", "text": "1.2", "anchor_id": "fig:1.2", "page_number": 1, "source_group_id": "c2"},
    ]
    sem = _semantic(blocks)
    _, rel, rep = adapt_semantic_document(sem)
    assert any(w.startswith("duplicate_formula_candidates:eq:1") for w in rep["warnings"])
    assert any(w.startswith("fragmented_caption:fig:1.2") for w in rel["warnings"])


def test_cli_writes_expected_files(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "docling", object())
    inp = tmp_path / "semantic_document.json"
    out = tmp_path / "out"
    inp.write_text(json.dumps(_semantic([{"id": "block:g1", "type": "paragraph", "text": "hi", "page_number": 1, "source_group_id": "g1"}])), encoding="utf-8")
    res = subprocess.run([sys.executable, "-m", "pdf2md.utils.docling_adapter", str(inp), "--output-root", str(out), "--export-markdown", "--mode", "inspection"], env={"PYTHONPATH": "src"}, capture_output=True, text=True)
    assert res.returncode == 0
    assert (out / "docling_document.json").exists()
    assert (out / "docling_relations.json").exists()
    assert (out / "docling_adapter_report.json").exists()
    assert (out / "docling_preview.md").exists()
