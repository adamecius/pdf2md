from pdf2md.utils.semantic_document_builder import build


def test_media_metadata_and_relations():
    consensus = {"pdf_path": "x.pdf", "pages": [{"page_index": 0, "conflicts": [], "candidate_groups": [
        {"group_id": "g1", "kind": "picture", "representative_text": "img", "representative_bbox": [1,1,2,2], "agreement": {"text": "near", "geometry": "near"}, "members": [], "sources": ["mineru"]},
        {"group_id": "g2", "kind": "table", "representative_text": "tbl", "representative_bbox": [1,2,2,3], "agreement": {"text": "near", "geometry": "near"}, "members": [], "sources": ["mineru"]},
        {"group_id": "g3", "kind": "caption", "representative_text": "cap", "agreement": {"text": "near"}, "members": [], "sources": ["mineru"]},
    ]}]}
    links = {"anchors": [{"anchor_id": "fig:1.2", "anchor_type": "figure", "target_group_id": "g1"}], "references": [], "attachments": [{"attachment_type": "caption_to_figure", "source_group_id": "g3", "target_group_id": "g1"}]}
    media = {"assets": [
        {"source_group_id": "g1", "media_id": "media:fig_1_2", "file_path": "media/fig_1_2.png", "status": "geometry_conflict", "media_type": "figure", "policy": {"render_dpi": 200}},
        {"source_group_id": "g2", "media_id": "media:g2", "file_path": "media/g2.png", "status": "resolved", "media_type": "table_visual_fallback", "policy": {"render_dpi": 200}},
    ]}
    doc = build(consensus, links, media, {"consensus": "c", "links": "s", "media": "m"})
    fig = [b for b in doc["blocks"] if b["source_group_id"] == "g1"][0]
    assert fig["media_id"] == "media:fig_1_2"
    assert fig["metadata"]["media_status"] == "geometry_conflict"
    assert fig["metadata"]["media_policy"]["render_dpi"] == 200
    assert any("media_status" in w for w in fig["warnings"])
    assert fig["status"] == "resolved_with_conflict"
    tbl = [b for b in doc["blocks"] if b["source_group_id"] == "g2"][0]
    assert tbl["type"] == "table"
    assert tbl["metadata"]["media_type"] == "table_visual_fallback"
    assert any(r["relation_type"] == "caption_of" for r in doc["relations"])


def test_selection_mode_and_evidence_and_hash_warning(tmp_path):
    cpath = tmp_path / "c.json"; lpath = tmp_path / "l.json"; mpath = tmp_path / "m.json"
    consensus = {"pdf_path": "x.pdf", "pages": [{"page_index": 0, "conflicts": [], "candidate_groups": [
        {"group_id": "g1", "kind": "paragraph", "representative_text": "(1.1)", "agreement": {"text": "near"}, "sources": ["a", "b"]},
        {"group_id": "g2", "kind": "footer", "representative_text": "footer", "agreement": {"text": "near"}, "sources": ["a", "b"]},
    ]}]}
    links = {"upstream_sha256": {"consensus_report": "bad"}, "anchors": [{"anchor_id": "footnote:1", "anchor_type": "footnote", "target_group_id": "g1"}], "references": [], "attachments": []}
    media = {"upstream_sha256": {"consensus_report": "bad", "semantic_links": "bad2"}, "assets": []}
    cpath.write_text("{}", encoding="utf-8"); lpath.write_text("{}", encoding="utf-8"); mpath.write_text("{}", encoding="utf-8")
    doc = build(consensus, links, media, {"consensus": str(cpath), "links": str(lpath), "media": str(mpath)})
    p = doc["pages"][0]
    assert p["evidence_block_ids"]
    assert p["page_artifact_ids"]
    b1 = [b for b in doc["blocks"] if b["source_group_id"] == "g1"][0]
    assert b1["type"] == "footnote"
    assert b1["selection_mode"] == "consensus"
    assert doc["validation"]["warnings"]
