from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))



import json
from pathlib import Path

from pdf2md.utils import consensus_report as cr


def _mk_backend(root: Path, name: str, blocks: list[dict], stem: str = "TestDoc") -> Path:
    d = root / "backend" / name / ".current" / "extraction_ir" / stem
    (d / "pages").mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text("{}", encoding="utf-8")
    (d / "pages" / "page_0000.json").write_text(json.dumps({"blocks": blocks}), encoding="utf-8")
    return d


def _cfg(tmp: Path, alias: bool = False) -> Path:
    text = """
[consensus]
output_root = ".current/consensus"

[backends.mineru]
enabled = true
root = "backend/mineru"
label = "mineru"

[backends.paddleocr]
enabled = true
root = "backend/paddleocr"
label = "paddleocr"

[backends.deepseek]
enabled = true
root = "backend/deepseek"
label = "deepseek"

[pymupdf]
enabled = false
"""
    if alias:
        text = text.replace("backends.mineru", "backends.mineuro").replace("backends.paddleocr", "backends.paddleorc").replace("backends.deepseek", "backends.deepsek")
    p = tmp / "cfg.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_config_parser_loads_canonical_backend_keys(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    assert set(cfg["backends"].keys()) == {"mineru", "paddleocr", "deepseek"}


def test_config_aliases(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path, alias=True))
    assert set(cfg["backends"].keys()) == {"mineru", "paddleocr", "deepseek"}


def test_resolver_maps_pdf(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    r = cr.resolve_backend_extraction_dirs(Path("TestDoc.pdf"), cfg)
    assert str(r["mineru"]).endswith("backend/mineru/.current/extraction_ir/TestDoc")


def test_loader_reads_manifest_and_page(tmp_path: Path):
    d = _mk_backend(tmp_path, "mineru", [{"text": "a", "type": "paragraph"}])
    assert cr.load_backend_manifest(d) == {}
    assert 0 in cr.load_backend_pages(d)


def test_missing_backend_tolerated(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    _mk_backend(tmp_path, "mineru", [{"text": "x"}])
    pdf = tmp_path / "TestDoc.pdf"; pdf.write_bytes(b"%PDF-1.4")
    old = Path.cwd()
    try:
        import os; os.chdir(tmp_path)
        report, rc = cr.build_consensus_report(pdf, cfg, tmp_path / "cfg.toml", False)
    finally:
        os.chdir(old)
    assert rc == 0
    assert report["sources"]["paddleocr"]["status"] == "missing"


def test_missing_backend_fail(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    pdf = tmp_path / "TestDoc.pdf"; pdf.write_bytes(b"%PDF-1.4")
    old = Path.cwd(); import os; os.chdir(tmp_path)
    try:
        _, rc = cr.build_consensus_report(pdf, cfg, tmp_path / "cfg.toml", True)
    finally:
        os.chdir(old)
    assert rc == 1


def test_deepseek_geometry_missing_does_not_fail():
    b = cr.normalise_backend_block("deepseek", 0, 0, {"text": "t", "geometry_missing": True, "bbox": None}, "x", "/blocks/0")
    assert b["has_geometry"] is False


def test_evidence_only_not_grouped_by_default(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("deepseek", 0, 0, {"text": "x", "docling": {"excluded_from_docling": True}}, "x", "")]
    groups, _ = cr.build_candidate_groups(ev, cfg)
    assert groups == []


def test_exact_text_match_group(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("mineru",0,0,{"text":"hello","type":"paragraph"},"x",""), cr.normalise_backend_block("paddleocr",0,1,{"text":"hello","type":"paragraph"},"x",""), cr.normalise_backend_block("deepseek",0,2,{"text":"hello","type":"paragraph"},"x","")]
    g, _ = cr.build_candidate_groups(ev, cfg)
    assert len(g) == 1


def test_near_text_match_group(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("mineru",0,0,{"text":"hello world"},"x",""), cr.normalise_backend_block("paddleocr",0,1,{"text":"hello wor1d"},"x","")]
    g, _ = cr.build_candidate_groups(ev, cfg)
    assert len(g) == 1


def test_bbox_iou_match_group(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("mineru",0,0,{"text":"","bbox":[0,0,10,10],"type":"table"},"x",""), cr.normalise_backend_block("paddleocr",0,1,{"text":"","bbox":[1,1,9,9],"type":"table"},"x","")]
    g, _ = cr.build_candidate_groups(ev, cfg)
    assert len(g) == 1


def test_formula_disagreement_conflict(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("mineru",0,0,{"text":"a+b","type":"formula","bbox":[0,0,10,10]},"x",""), cr.normalise_backend_block("paddleocr",0,1,{"text":"a-b","type":"formula","bbox":[1,1,9,9]},"x","")]
    g, _ = cr.build_candidate_groups(ev, cfg)
    p = {"page_index":0,"candidate_groups":g}
    c = cr.detect_conflicts(p, ev, cfg)
    assert any(x["type"] == "formula_disagreement" for x in c)


def test_table_disagreement_conflict(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("mineru",0,0,{"text":"r1c1","type":"table","bbox":[0,0,10,10]},"x",""), cr.normalise_backend_block("paddleocr",0,1,{"text":"x","type":"table","bbox":[1,1,9,9]},"x","")]
    g, _ = cr.build_candidate_groups(ev, cfg)
    c = cr.detect_conflicts({"page_index":0,"candidate_groups":g}, ev, cfg)
    assert any(x["type"] == "table_disagreement" for x in c)


def test_missing_geometry_conflict(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("mineru",0,0,{"text":"abc","bbox":[0,0,1,1]},"x",""), cr.normalise_backend_block("paddleocr",0,1,{"text":"abc","bbox":None},"x","")]
    g, _ = cr.build_candidate_groups(ev, cfg)
    c = cr.detect_conflicts({"page_index":0,"candidate_groups":g}, ev, cfg)
    assert any(x["type"] == "missing_geometry" for x in c)


def test_possible_duplicate_conflict(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path))
    ev = [cr.normalise_backend_block("mineru",0,0,{"text":"abc"},"x",""), cr.normalise_backend_block("mineru",0,1,{"text":"abc"},"x","")]
    g, _ = cr.build_candidate_groups(ev, cfg)
    c = cr.detect_conflicts({"page_index":0,"candidate_groups":g}, ev, cfg)
    assert any(x["type"] == "possible_duplicate" for x in c)


def test_pymupdf_unavailable_records_warning(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "fitz", None)
    cfg = cr.load_config(_cfg(tmp_path))
    cfg["pymupdf"]["enabled"] = True
    _, src, _ = cr.load_pymupdf_evidence(tmp_path / "x.pdf", cfg)
    assert src["status"] in {"unavailable", "error"}


def test_pymupdf_mocked_geometry(tmp_path: Path, monkeypatch):
    class P:
        rect = type("R", (), {"width": 100.0, "height": 200.0})()
        def get_text(self, _):
            return {"blocks": [{"bbox": [10, 20, 30, 40], "lines": [{"spans": [{"text": "abc"}]}]}]}
    class D(list):
        pass
    d = D([P()])
    monkeypatch.setitem(__import__("sys").modules, "fitz", type("F", (), {"open": lambda *_: d})())
    cfg = cr.load_config(_cfg(tmp_path)); cfg["pymupdf"]["enabled"] = True
    pages, src, meta = cr.load_pymupdf_evidence(tmp_path / "x.pdf", cfg)
    assert src["status"] == "loaded" and pages[0][0]["bbox"] is not None and meta[0]["width"] == 100.0


def test_json_schema_fields(tmp_path: Path):
    cfg = cr.load_config(_cfg(tmp_path)); pdf = tmp_path / "TestDoc.pdf"; pdf.write_bytes(b"%PDF-1.4")
    _mk_backend(tmp_path, "mineru", [{"text": "x"}])
    import os
    old = Path.cwd(); os.chdir(tmp_path)
    try:
        r, rc = cr.build_consensus_report(pdf, cfg, tmp_path / "cfg.toml", False)
    finally:
        os.chdir(old)
    assert rc == 0 and r["schema_name"] == "pdf2md.consensus_report" and r["schema_version"] == "0.1.0"


def test_cli_writes_report_and_json_only(tmp_path: Path, capsys):
    _mk_backend(tmp_path, "mineru", [{"text": "x"}])
    _mk_backend(tmp_path, "paddleocr", [{"text": "x"}])
    _mk_backend(tmp_path, "deepseek", [{"text": "x"}])
    cfgp = _cfg(tmp_path)
    pdf = tmp_path / "TestDoc.pdf"; pdf.write_bytes(b"%PDF-1.4")
    import os
    old = Path.cwd(); os.chdir(tmp_path)
    try:
        rc = cr.main([str(pdf), "--config", str(cfgp), "--json-only"])
    finally:
        os.chdir(old)
    out = capsys.readouterr().out
    assert rc == 0
    assert (tmp_path / ".current/consensus/TestDoc/consensus_report.json").exists()
    assert "Page 1:" not in out


def test_real_shape_normalise_backend_block_fields():
    block = {
      "block_id": "mineru_p0000_b0001", "type": "paragraph", "subtype": None, "semantic_role": "body_text",
      "docling": {"label_hint": "text"},
      "geometry": {"bbox": [100, 100, 500, 160], "coordinate_space": "page_normalised_1000", "origin": "top_left"},
      "content": {"text": "Drude applied kinetic theory to this gas of conduction electrons.", "normalised_text": "drude applied kinetic theory to this gas of conduction electrons."},
      "confidence": {"overall": 0.9, "text": 0.95, "layout": 0.8},
      "comparison": {"text_hash": "sha256:test", "geometry_hash": "sha256:geom", "compare_as": "paragraph"},
      "source_refs": [{"backend_id": "mineru", "raw_file": "raw_pages/page_0000.content.json"}], "flags": []
    }
    e = cr.normalise_backend_block("mineru", 0, 1, block, "x", "/blocks/1")
    assert e["source_block_id"] == "mineru_p0000_b0001"
    assert e["text"].startswith("Drude applied")
    assert e["normalised_text"].startswith("drude applied")
    assert e["bbox"] == [100.0, 100.0, 500.0, 160.0]
    assert e["confidence"]["overall"] == 0.9
    assert e["comparison"]["text_hash"] == "sha256:test"
    assert e["has_geometry"] is True


def test_real_shape_deepseek_evidence_only():
    block = {
      "block_id": "deepseek_ocr_2_p0000_b0000", "type": "unknown", "subtype": "generated_markdown_page",
      "semantic_role": "raw_generated_page_evidence",
      "docling": {"label_hint": "text", "excluded_from_docling": True},
      "geometry": None,
      "content": {"text": "page text", "normalised_text": "page text", "markdown": "page text"},
      "flags": [{"code": "geometry_missing"}]
    }
    e = cr.normalise_backend_block("deepseek", 0, 0, block, "x", "/blocks/0")
    assert e["compile_role"] == "evidence_only" and e["has_geometry"] is False and e["text"] == "page text"


def test_report_real_shape_grouping_and_missing_geometry(tmp_path: Path):
    mblock = {"block_id":"m1","type":"paragraph","geometry":{"bbox":[100,100,300,140]},"content":{"text":"same text","normalised_text":"same text"}}
    pblock = {"block_id":"p1","type":"paragraph","geometry":{"bbox":[102,102,302,142]},"content":{"text":"same text","normalised_text":"same text"}}
    dblock = {"block_id":"d1","type":"paragraph","geometry":None,"content":{"text":"same text","normalised_text":"same text"}}
    _mk_backend(tmp_path, "mineru", [mblock]); _mk_backend(tmp_path, "paddleocr", [pblock]); _mk_backend(tmp_path, "deepseek", [dblock])
    cfg = cr.load_config(_cfg(tmp_path)); pdf = tmp_path / "TestDoc.pdf"; pdf.write_bytes(b"%PDF-1.4")
    import os
    old = Path.cwd(); os.chdir(tmp_path)
    try:
        r, rc = cr.build_consensus_report(pdf, cfg, tmp_path / "cfg.toml", False)
    finally:
        os.chdir(old)
    assert rc == 0 and r["schema_name"] == "pdf2md.consensus_report" and r["schema_version"] == "0.1.0"
    page = r["pages"][0]
    assert len(page["candidate_groups"]) >= 1
    assert page["counts"]["geometry_blocks_by_source"]["mineru"] > 0 and page["counts"]["geometry_blocks_by_source"]["paddleocr"] > 0
    assert page["counts"]["geometry_blocks_by_source"]["deepseek"] == 0
    assert any(c["type"] == "missing_geometry" for c in page["conflicts"])
