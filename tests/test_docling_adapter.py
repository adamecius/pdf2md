from __future__ import annotations
import json
from pathlib import Path
import pytest

from pdf2md.utils import docling_adapter as da

class FakeBackend:
    def __init__(self): self.texts=[]; self.pictures=[]
    def add_text(self,t): self.texts.append(t)
    def add_picture(self,p,caption=None): self.pictures.append((p,caption))
    def export_json(self): return {"texts":self.texts,"pictures":self.pictures}
    def export_markdown(self): return "\n\n".join(self.texts) or "preview"

def _sem(blocks, refs=None, validation=None, rels=None):
    return {"blocks":blocks,"anchors":[],"references":refs or [],"relations":rels or [],"conflicts":[],"warnings":[],"validation":validation or {"unresolved_references":[]}}

def test_no_fake_docling_package():
    assert not Path("src/docling/__init__.py").exists()

def test_loader_missing_docling_error(monkeypatch):
    monkeypatch.setattr(da.DoclingBackend, "load", staticmethod(lambda: (_ for _ in ()).throw(da.AdapterError("Docling adapter requires docling/docling-core. Install the optional Docling dependency before using this command."))))
    with pytest.raises(da.AdapterError): da.DoclingBackend.load()

def test_minimal_paragraph_mapping_and_source_path():
    b=FakeBackend(); sem=_sem([{"id":"block:g1","type":"paragraph","text":"hi","page_number":1,"bbox":[1,2,3,4],"source_group_id":"g1"}])
    _, rel, rep, _ = da.adapt_semantic_document(sem, source_semantic_document="/tmp/semantic_document.json", backend=b)
    assert rel["source_semantic_document"]=="/tmp/semantic_document.json"
    assert rel["id_map"]["block:g1"]["docling_ref"]=="#/texts/0"

def test_anchored_and_orphan_media_and_missing_file(tmp_path:Path):
    b=FakeBackend(); sem=_sem([
      {"id":"block:f1","type":"figure","text":"","page_number":1,"bbox":[1,2,3,4],"source_group_id":"f1","anchor_id":"fig:1","media_path":"missing.png","media_id":"m1"},
      {"id":"block:f2","type":"figure","text":"","page_number":1,"bbox":[1,2,3,4],"source_group_id":"f2","media_path":"missing2.png"},
    ])
    _, rel, rep, _ = da.adapt_semantic_document(sem, source_semantic_document=str(tmp_path/"semantic_document.json"), output_root=tmp_path, backend=b)
    assert any(w.startswith("missing_media_file:block:f1") for w in rep["warnings"])
    assert any(w=="orphan_media_suppressed:block:f2" for w in rel["warnings"])
    b2=FakeBackend(); _, rel2, _, _ = da.adapt_semantic_document(sem, source_semantic_document=str(tmp_path/"semantic_document.json"), output_root=tmp_path, include_orphan_media=True, backend=b2)
    assert any(w=="orphan_media_included_debug:block:f2" for w in rel2["warnings"])

def test_formula_duplicate_and_not_fused_and_unresolved_dedup():
    b=FakeBackend(); sem=_sem([
      {"id":"block:a","type":"formula","text":"x","anchor_id":"eq:1","selected_text_source":"m","selected_geometry_source":"p","bbox":[1,1,2,2],"source_group_id":"a"},
      {"id":"block:b","type":"formula","text":"x","anchor_id":"eq:1","selected_text_source":"m","selected_geometry_source":"m","bbox":[1,1,2,2],"source_group_id":"b"},
    ], refs=[{"reference_id":"r1","resolved":False}], validation={"unresolved_references":["r1"]})
    _, rel, rep, _ = da.adapt_semantic_document(sem, backend=b)
    assert any(w.startswith("duplicate_formula_candidates:eq:1:block:a,block:b") for w in rep["warnings"])
    assert any(w=="formula_text_geometry_not_fused:block:a" for w in rel["warnings"])
    assert rep["warnings"].count("unresolved_reference:r1")==1

def test_fragmented_caption_warning():
    b=FakeBackend(); sem=_sem([
      {"id":"block:fig","type":"figure","text":"","source_group_id":"fig","anchor_id":"fig:1","media_path":"x.png"},
      {"id":"block:c1","type":"caption","text":"Figure","source_group_id":"c1"},
      {"id":"block:c2","type":"caption","text":"1","source_group_id":"c2"},
    ], rels=[{"relation_id":"rel1","relation_type":"caption_of","source_id":"block:c1","target_id":"block:fig"},{"relation_id":"rel2","relation_type":"caption_of","source_id":"block:c2","target_id":"block:fig"}])
    _, rel, _, _ = da.adapt_semantic_document(sem, backend=b)
    assert any(w.startswith("fragmented_caption:fig:1:block:c1,block:c2") for w in rel["warnings"])

def test_cli_writes_files_and_strict_mode(tmp_path:Path, monkeypatch):
    monkeypatch.setattr(da.DoclingBackend, "load", staticmethod(lambda: FakeBackend()))
    inp=tmp_path/"semantic_document.json"; out=tmp_path/"o"
    inp.write_text(json.dumps(_sem([{"id":"block:x","type":"figure","text":"","media_path":"m.png","source_group_id":"x"}])))
    rc=da.main.__wrapped__ if hasattr(da.main,'__wrapped__') else None
    import sys
    old=sys.argv
    try:
      sys.argv=["x",str(inp),"--output-root",str(out),"--mode","inspection","--export-markdown"]
      assert da.main()==0
      assert (out/"docling_document.json").exists()
      assert (out/"docling_relations.json").exists()
      assert (out/"docling_adapter_report.json").exists()
      assert (out/"docling_preview.md").exists()
      sys.argv=["x",str(inp),"--output-root",str(out),"--mode","strict"]
      assert da.main()!=0
    finally:
      sys.argv=old
