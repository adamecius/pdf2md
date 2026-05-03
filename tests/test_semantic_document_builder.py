from pathlib import Path

from pdf2md.utils.semantic_document_builder import build


def _sample():
    consensus = {
        "schema_name": "pdf2md.consensus_report",
        "pdf_path": "x.pdf",
        "pages": [{"page_index": 0, "candidate_groups": [
            {"group_id": "p0001_g0001", "kind": "paragraph", "representative_text": "hello", "representative_bbox": [10,10,20,20], "agreement": {"text": "near", "geometry": "near"}, "members": [], "sources": ["mineru"]},
            {"group_id": "p0001_g0002", "kind": "formula", "representative_text": "x", "representative_bbox": [10,30,20,40], "agreement": {"text": "conflict", "geometry": "near"}, "members": [], "sources": ["mineru"]},
        ]}],
    }
    sem = {"schema_name": "pdf2md.semantic_links", "anchors": [{"anchor_id": "eq:1.1", "anchor_type": "equation", "label": "1.1", "target_group_id": "p0001_g0002", "status": "resolved_with_conflict"}], "references": [], "attachments": []}
    return consensus, sem


def test_build_semantic_document():
    c, s = _sample()
    doc = build(c, s, None, {"consensus": "c.json", "links": "s.json", "media": None})
    assert doc["schema_name"] == "pdf2md.semantic_document"
    formula = [b for b in doc["blocks"] if b["type"] == "formula"][0]
    assert formula["status"] == "resolved_with_conflict"
    assert formula["anchor_id"] == "eq:1.1"
