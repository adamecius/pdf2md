from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pdf2md.utils.semantic_linker import build_semantic_links, extract_equation_number, normalise_latex


def _report(groups, conflicts=None):
    return {"schema_name": "pdf2md.consensus_report", "schema_version": "0.1.0", "pdf_path": "x.pdf", "pdf_stem": "x", "pages": [{"page_index": 0, "candidate_groups": groups, "conflicts": conflicts or [], "pymupdf_page": {}}]}


def test_equation_and_basic():
    assert extract_equation_number("(1.3)") == "1.3"
    assert extract_equation_number(r"\tag{1.3}") == "1.3"
    assert extract_equation_number("Eq. (1.3)") == "1.3"


def test_no_duplicate_figure_anchor_from_paragraph_and_resolve_reference():
    groups = [
        {"group_id": "pic", "kind": "picture", "representative_text": "", "representative_bbox": [100, 100, 300, 300]},
        {"group_id": "cap", "kind": "caption", "representative_text": "Figure 1.2 A thing", "representative_bbox": [100, 320, 300, 350]},
        {"group_id": "p", "kind": "paragraph", "representative_text": "As shown in Figure 1.2", "representative_bbox": [10, 10, 90, 40]},
    ]
    out = build_semantic_links(_report(groups), Path("in.json"))
    fig_anchors = [a for a in out["anchors"] if a["anchor_type"] == "figure" and a["label"] == "1.2"]
    assert len(fig_anchors) == 1
    assert any(r["reference_type"] == "figure" and r["resolved"] and r["target_anchor_id"] == "fig:1.2" for r in out["references"])


def test_caption_no_self_reference_and_table_para_no_table_anchor():
    groups = [
        {"group_id": "tab", "kind": "table", "representative_text": "", "representative_bbox": [100, 100, 300, 300]},
        {"group_id": "cap", "kind": "caption", "representative_text": "Table 1.1 Values", "representative_bbox": [100, 320, 300, 350]},
        {"group_id": "p", "kind": "paragraph", "representative_text": "See Table 1.1", "representative_bbox": [10, 10, 90, 40]},
    ]
    out = build_semantic_links(_report(groups), Path("in.json"))
    assert not any(r["source_group_id"] == "cap" for r in out["references"])
    table_anchors = [a for a in out["anchors"] if a["anchor_type"] == "table" and a["label"] == "1.1"]
    assert len(table_anchors) == 1


def test_footnote_marker_not_from_eq_fig_table_refs():
    groups = [{"group_id": "p", "kind": "paragraph", "representative_text": "Eq. (1.3) Figure 1.2 Table 1.1", "representative_bbox": [1, 1, 2, 2]}]
    out = build_semantic_links(_report(groups), Path("in.json"))
    assert not any(r["reference_type"] == "footnote" for r in out["references"])


def test_equation_attach_updates_existing_anchor_not_duplicate():
    groups = [
        {"group_id": "f1", "kind": "formula", "representative_text": "E=mc^2", "representative_bbox": [100, 200, 300, 260]},
        {"group_id": "n1", "kind": "paragraph", "representative_text": "(1.3)", "representative_bbox": [320, 210, 360, 240]},
    ]
    out = build_semantic_links(_report(groups), Path("in.json"))
    eq_for_target = [a for a in out["anchors"] if a["anchor_type"] == "equation" and a["target_group_id"] == "f1"]
    assert len(eq_for_target) == 1
    assert eq_for_target[0]["anchor_id"] == "eq:1.3"
    assert "eq:f1" in eq_for_target[0].get("alias_ids", [])


def test_conflicted_formula_group_status_and_source_fields():
    groups = [{"group_id": "f1", "kind": "formula", "representative_text": "x=1 \\tag{1.3}", "representative_bbox": [1, 1, 2, 2], "sources": ["a"], "members": ["m1"], "agreement": {"text": 0.6}}]
    conflicts = [{"group_ids": ["f1"], "type": "text_conflict"}]
    out = build_semantic_links(_report(groups, conflicts=conflicts), Path("in.json"))
    a = next(x for x in out["anchors"] if x["anchor_type"] == "equation")
    assert a["status"] == "resolved_with_conflict"
    assert a["source_group_id"] == "f1"
    assert "formula_candidates" in a and a["formula_candidates"]


def test_cli_writes_semantic_links(tmp_path):
    inp = tmp_path / "consensus_report.json"
    out = tmp_path / "semantic_links.json"
    inp.write_text(json.dumps(_report([])), encoding="utf-8")
    cmd = [sys.executable, "-m", "pdf2md.utils.semantic_linker", str(inp), "--output", str(out), "--json-only"]
    res = subprocess.run(cmd, env={"PYTHONPATH": "src"}, check=False, capture_output=True, text=True)
    assert res.returncode == 0
    assert out.exists()


def test_formula_normalization_still_works():
    a = normalise_latex(r"\mathbf{E}=\rho\mathbf{j}. \quad (1.3)")
    b = normalise_latex(r"{ \bf E } = \rho { \bf j } .\tag{1.3}")
    assert a["label"] == b["label"] == "1.3"


def test_conflict_via_evidence_ids_real_shape():
    groups = [{
        "group_id": "p0003_g0003",
        "kind": "formula",
        "representative_text": r"x=1 \tag{1.3}",
        "members": ["mineru:p0003:b0003", "paddleocr:p0003:b0011"],
        "sources": ["mineru", "paddleocr"],
        "agreement": {"text": "conflict", "geometry": "near"},
        "representative_bbox": [1, 1, 2, 2],
    }]
    conflicts = [{"type": "formula_disagreement", "evidence_ids": ["mineru:p0003:b0003", "paddleocr:p0003:b0011"]}]
    out = build_semantic_links(_report(groups, conflicts=conflicts), Path("in.json"))
    a = next(x for x in out["anchors"] if x["anchor_type"] == "equation")
    assert a["status"] == "resolved_with_conflict"
    assert any(c.get("type") == "formula_disagreement" for c in a.get("source_group_conflicts", []))


def test_page_anchor_ids_updated_after_equation_relabel():
    groups = [
        {"group_id": "f1", "kind": "formula", "representative_text": "E=mc^2", "representative_bbox": [100, 200, 300, 260]},
        {"group_id": "n1", "kind": "paragraph", "representative_text": "(1.3)", "representative_bbox": [320, 210, 360, 240]},
    ]
    out = build_semantic_links(_report(groups), Path("in.json"))
    eq_for_target = [a for a in out["anchors"] if a["anchor_type"] == "equation" and a["target_group_id"] == "f1"]
    assert len(eq_for_target) == 1
    assert eq_for_target[0]["anchor_id"] == "eq:1.3"
    assert "eq:1.3" in out["pages"][0]["anchors"]
    assert "eq:f1" not in out["pages"][0]["anchors"]


def test_figure_compact_target_and_dedup_evidence():
    groups = [
        {"group_id": "p_bad", "kind": "picture", "representative_text": "Figure 1.2", "representative_bbox": [303, 176, 1000, 308]},
        {"group_id": "p_good", "kind": "picture", "representative_text": "", "representative_bbox": [132, 108, 444, 185], "sources": ["paddleocr"], "agreement": {"geometry": "single_source"}},
        {"group_id": "cap", "kind": "caption", "representative_text": "Figure 1.2", "representative_bbox": [461, 109, 542, 122]},
    ]
    out = build_semantic_links(_report(groups), Path("in.json"))
    fig = [a for a in out["anchors"] if a["anchor_id"] == "fig:1.2"]
    assert len(fig) == 1
    assert fig[0]["target_group_id"] == "p_good"
    assert out["pages"][0]["anchors"].count("fig:1.2") == 1


def test_reference_ids_unique_same_page():
    groups = [{"group_id": "p", "kind": "paragraph", "representative_text": "See Figure 1.2 and Table 1.1", "representative_bbox": [1, 1, 2, 2]}]
    out = build_semantic_links(_report(groups), Path("in.json"))
    ids = [r["reference_id"] for r in out["references"]]
    assert len(ids) == len(set(ids))
