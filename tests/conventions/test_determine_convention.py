import json
from pathlib import Path
from pdf2md.conventions.determine_convention import main as determine_main
import sys


def _mk_fixture(tmp_path: Path):
    root = tmp_path / "latex_docling_groundtruth" / "batch_002"
    (root / "case1").mkdir(parents=True)
    (root / "case1" / "doc.tex").write_text(r"\section{A}\begin{equation}E=mc^2\tag{1}\end{equation}")
    p = root / "backend_ir" / "mineru" / "case1"
    p.mkdir(parents=True)
    (p / "page.json").write_text(json.dumps({"blocks": [{"block_id": "b1", "content": {"text": "Figure 1"}}]}))
    for b in ["paddleocr", "deepseek"]:
        q = root / "backend_ir" / b / "case1"
        q.mkdir(parents=True)
        (q / "page.json").write_text(json.dumps({"blocks": [{"block_id": "b1", "content": {"text": "x"}}]}))
    return root


def test_determine_convention_writes_report(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path)
    out = root / "diagnostics" / "conventions"
    monkeypatch.setattr(sys, "argv", ["x", "--root", str(root.parent), "--batch", "batch_002", "--output", str(out), "--write-proposed-config", "--emit-markdown-report"])
    determine_main()
    assert (out / "conventions_report.json").exists()


def test_determine_convention_writes_proposed_config(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path)
    out = root / "diagnostics" / "conventions"
    monkeypatch.setattr(sys, "argv", ["x", "--root", str(root.parent), "--batch", "batch_002", "--output", str(out), "--write-proposed-config"])
    determine_main()
    assert (out / "ocr_conventions.proposed.toml").exists()


def test_report_contains_backend_sections(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path)
    out = root / "diagnostics" / "conventions"
    monkeypatch.setattr(sys, "argv", ["x", "--root", str(root.parent), "--batch", "batch_002", "--output", str(out)])
    determine_main()
    report = json.loads((out / "conventions_report.json").read_text())
    for b in ["mineru", "paddleocr", "deepseek"]:
        assert b in report["backends"]


def test_report_contains_examples_with_block_ids(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path)
    out = root / "diagnostics" / "conventions"
    monkeypatch.setattr(sys, "argv", ["x", "--root", str(root.parent), "--batch", "batch_002", "--output", str(out)])
    determine_main()
    report = json.loads((out / "conventions_report.json").read_text())
    assert report["backends"]["mineru"]["examples"][0]["block_id"] == "b1"


def test_report_contains_fixture_provenance(tmp_path, monkeypatch):
    root = _mk_fixture(tmp_path)
    out = root / "diagnostics" / "conventions"
    monkeypatch.setattr(sys, "argv", ["x", "--root", str(root.parent), "--batch", "batch_002", "--output", str(out)])
    determine_main()
    report = json.loads((out / "conventions_report.json").read_text())
    assert "fixture_provenance" in report
