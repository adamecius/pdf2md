from pdf2md.utils.semantic_document_builder import build


def test_conflicts_refs_media_and_relations():
    consensus = {"pdf_path": "x.pdf", "pages": [{"page_index": 0, "conflicts": [{"conflict_id": "c1", "evidence_ids": ["e2"]}], "candidate_groups": [
        {"group_id": "g1", "kind": "formula", "representative_text": "x", "representative_bbox": [1,1,2,2], "agreement": {"text": "near", "geometry": "near"}, "members": ["e2"], "sources": ["mineru"]},
        {"group_id": "g2", "kind": "header", "representative_text": "H", "agreement": {"text": "near"}, "members": [], "sources": ["mineru"]},
        {"group_id": "g3", "kind": "caption", "representative_text": "Fig", "agreement": {"text": "near"}, "members": [], "sources": ["mineru"]},
    ]}]}
    links = {
        "anchors": [{"anchor_id": "eq:1.1", "anchor_type": "equation", "target_group_id": "g1", "status": "resolved_with_conflict"}],
        "references": [{"reference_id": "r1", "source_group_id": "g3", "resolved": False}],
        "attachments": [
            {"attachment_type": "caption_to_figure", "source_group_id": "g3", "target_group_id": "g1", "anchor_id": "fig:1.1"},
            {"attachment_type": "equation_number_to_equation", "source_group_id": "g3", "target_group_id": "g1", "anchor_id": "eq:1.1"},
        ],
    }
    media = {"assets": [{"source_group_id": "g1", "media_id": "m1", "file_path": "media/g1.png"}]}
    doc = build(consensus, links, media, {"consensus": "c", "links": "s", "media": "m"})
    assert doc["conflicts"]
    b1 = [b for b in doc["blocks"] if b["source_group_id"] == "g1"][0]
    assert b1["conflicts"] and b1["status"] == "resolved_with_conflict"
    assert b1["media_id"] == "m1"
    assert doc["validation"]["unresolved_references"] == ["r1"]
    assert any(r["relation_type"] == "caption_of" for r in doc["relations"])
    assert any(r["relation_type"] == "equation_number_to_equation" for r in doc["relations"])
    hdr = [b for b in doc["blocks"] if b["source_group_id"] == "g2"][0]
    assert hdr["metadata"]["is_page_artifact"] is True
    for b in doc["blocks"]:
        for k in ["source_group_id", "source_group_members", "sources", "agreement", "status"]:
            assert k in b
