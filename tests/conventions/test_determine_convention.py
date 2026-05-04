import json, sys
from pathlib import Path
from pdf2md.conventions.determine_convention import main as determine_main


def _mk_fixture(tmp_path: Path):
    root = tmp_path / "latex_docling_groundtruth" / "batch_002"
    case = root / "det_all_features"
    case.mkdir(parents=True)
    (case / "doc.tex").write_text(r"\section{A} Figure~\ref{fig:one} \begin{equation}E=mc^2\tag{1}\end{equation}")
    for b, blocks in {
        "mineru": [{"block_id": "m1", "type": "paragraph", "content": {"text": "Figure 1: Boxed figure"}}],
        "paddleocr": [{"block_id": "p1", "type": "formula", "content": {"text": "E=mc^2"}}, {"block_id": "p2", "type": "paragraph", "content": {"text": "(1)"}}],
        "deepseek": [{"block_id": "d1", "type": "paragraph", "content": {"text": "x"}}],
    }.items():
        p = root / "backend_ir" / b / "det_all_features"
        p.mkdir(parents=True)
        (p / "page.json").write_text(json.dumps({"blocks": blocks}))
    return root


def _run(root, out, monkeypatch, extra=None):
    argv = ["x", "--root", str(root.parent), "--batch", "batch_002", "--output", str(out), "--write-proposed-config", "--emit-markdown-report"]
    if extra:
        argv.extend(extra)
    monkeypatch.setattr(sys, "argv", argv)
    determine_main()


def test_determine_convention_infers_caption_as_paragraph(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path); out = root / "diagnostics" / "conventions"; _run(root, out, monkeypatch)
    report = json.loads((out / "conventions_report.json").read_text())
    assert report["backends"]["mineru"]["summary"]["caption_as_paragraph"] >= 1


def test_determine_convention_infers_formula_number_split_block(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path); out = root / "diagnostics" / "conventions"; _run(root, out, monkeypatch)
    report = json.loads((out / "conventions_report.json").read_text())
    assert report["backends"]["paddleocr"]["summary"]["formula_number_split_block"] >= 1


def test_proposed_rules_include_supporting_block_id(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path); out = root / "diagnostics" / "conventions"; _run(root, out, monkeypatch)
    report = json.loads((out / "conventions_report.json").read_text())
    pr = report["backends"]["paddleocr"]["proposed_rules"]
    assert any("p2" in ",".join(r["supporting_backend_block_ids"]) for r in pr)


def test_proposed_config_is_evidence_derived(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path); out = root / "diagnostics" / "conventions"; _run(root, out, monkeypatch)
    txt = (out / "ocr_conventions.proposed.toml").read_text()
    assert "support_count=" in txt and "equation.number_split_block" in txt
