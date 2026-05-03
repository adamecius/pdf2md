from __future__ import annotations

import json
import subprocess
import sys

from pdf2md.utils.semantic_linker import (
    build_semantic_links,
    extract_equation_number,
    normalise_latex,
)


def _report(groups):
    return {"schema_name": "pdf2md.consensus_report", "schema_version": "0.1.0", "pdf_path": "x.pdf", "pdf_stem": "x", "pages": [{"page_index": 0, "candidate_groups": groups, "conflicts": [], "pymupdf_page": {}}]}


def test_a_equation_number_extraction():
    assert extract_equation_number("(1.3)") == "1.3"
    assert extract_equation_number(r"\tag{1.3}") == "1.3"
    assert extract_equation_number("Eq. (1.3)") == "1.3"


def test_b_equation_attachment_geometry():
    groups = [
        {"group_id": "p0000_g0001", "kind": "formula", "representative_text": "E=mc^2", "representative_bbox": [100, 200, 300, 260]},
        {"group_id": "p0000_g0002", "kind": "paragraph", "representative_text": "(1.3)", "representative_bbox": [320, 210, 360, 240]},
    ]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any(a["attachment_type"] == "equation_number_to_equation" for a in out["attachments"])
    assert any(a["anchor_id"] == "eq:1.3" for a in out["anchors"])


def test_c_equation_attachment_reading_order_fallback():
    groups = [
        {"group_id": "p0000_g0001", "kind": "formula", "representative_text": "E=mc^2", "representative_bbox": None},
        {"group_id": "p0000_g0002", "kind": "paragraph", "representative_text": "(1.3)", "representative_bbox": None},
    ]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any(a["attachment_type"] == "equation_number_to_equation" for a in out["attachments"])


def test_d_equation_reference_resolution():
    groups = [
        {"group_id": "g1", "kind": "formula", "representative_text": "x=1 \\tag{1.3}", "representative_bbox": [1, 1, 2, 2]},
        {"group_id": "g2", "kind": "paragraph", "representative_text": "See Eq. (1.3)", "representative_bbox": [1, 3, 2, 4]},
    ]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any(r["target_anchor_id"] == "eq:1.3" and r["resolved"] for r in out["references"])


def test_e_formula_normalisation():
    a = normalise_latex(r"\mathbf{E}=\rho\mathbf{j}. \quad (1.3)")
    b = normalise_latex(r"{ \bf E } = \rho { \bf j } .\tag{1.3}")
    assert a["label"] == b["label"] == "1.3"
    assert a["body_key"].replace("{", "").replace("}", "")[:8] == b["body_key"].replace("{", "").replace("}", "")[:8]


def test_f_g_figure_anchor_and_reference():
    groups = [
        {"group_id": "pic", "kind": "picture", "representative_text": "", "representative_bbox": [100, 100, 300, 300]},
        {"group_id": "cap", "kind": "caption", "representative_text": "Figure 1.2 A thing", "representative_bbox": [100, 320, 300, 350]},
        {"group_id": "p", "kind": "paragraph", "representative_text": "As shown in Figure 1.2", "representative_bbox": [10, 10, 90, 40]},
    ]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any(a["anchor_id"] == "fig:1.2" for a in out["anchors"])
    assert any(a["attachment_type"] == "caption_to_figure" for a in out["attachments"])
    assert any(r["reference_type"] == "figure" and r["resolved"] for r in out["references"])


def test_h_i_table_anchor_and_reference():
    groups = [
        {"group_id": "tab", "kind": "table", "representative_text": "", "representative_bbox": [100, 100, 300, 300]},
        {"group_id": "cap", "kind": "caption", "representative_text": "Table 1.1 Values", "representative_bbox": [100, 320, 300, 350]},
        {"group_id": "p", "kind": "paragraph", "representative_text": "See Table 1.1", "representative_bbox": [10, 10, 90, 40]},
    ]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any(a["anchor_id"] == "table:1.1" for a in out["anchors"])
    assert any(r["reference_type"] == "table" and r["resolved"] for r in out["references"])


def test_j_k_footnote_body_and_marker_resolution():
    groups = [
        {"group_id": "p", "kind": "paragraph", "representative_text": "mark.7", "representative_bbox": [10, 10, 90, 40]},
        {"group_id": "f", "kind": "footer", "representative_text": "7 For some time...", "representative_bbox": [10, 850, 900, 920]},
    ]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any(a["anchor_id"].startswith("footnote:") for a in out["anchors"])
    assert any(r["reference_type"] == "footnote" and r["resolved"] for r in out["references"])


def test_l_unresolved_preserved():
    groups = [{"group_id": "p", "kind": "paragraph", "representative_text": "Eq. (9.9)", "representative_bbox": [1, 1, 2, 2]}]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any((not r["resolved"]) and r["label"] == "9.9" for r in out["references"])


def test_m_ambiguous_anchors():
    groups = [
        {"group_id": "f1", "kind": "formula", "representative_text": "a \\tag{1.3}", "representative_bbox": [1, 1, 2, 2]},
        {"group_id": "f2", "kind": "formula", "representative_text": "b \\tag{1.3}", "representative_bbox": [1, 3, 2, 4]},
        {"group_id": "p", "kind": "paragraph", "representative_text": "Eq. (1.3)", "representative_bbox": [1, 5, 2, 6]},
    ]
    out = build_semantic_links(_report(groups), __import__("pathlib").Path("in.json"))
    assert any(r["reference_text"].startswith("Eq") and (not r["resolved"]) and "ambiguous" in r["warnings"] for r in out["references"])


def test_n_cli_writes_semantic_links(tmp_path):
    inp = tmp_path / "consensus_report.json"
    out = tmp_path / "semantic_links.json"
    inp.write_text(json.dumps(_report([])), encoding="utf-8")
    cmd = [sys.executable, "-m", "pdf2md.utils.semantic_linker", str(inp), "--output", str(out), "--json-only"]
    res = subprocess.run(cmd, env={"PYTHONPATH": "src"}, check=False, capture_output=True, text=True)
    assert res.returncode == 0
    assert out.exists()
