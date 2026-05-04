import json
import sys
from pathlib import Path

from pdf2md.conventions.determine_convention import doc_id_from_tex_path, main as determine_main
from pdf2md.conventions.normalizer import main as normalizer_main


def test_doc_id_extraction_uses_fixture_directory(tmp_path):
    batch_root = tmp_path / 'batch_002'
    tex = batch_root / 'det_all_features' / 'input' / 'det_all_features.tex'
    tex.parent.mkdir(parents=True)
    tex.write_text('x')
    doc_id = doc_id_from_tex_path(tex, batch_root)
    assert doc_id == 'det_all_features'
    assert doc_id != 'input'


def test_determine_convention_reads_real_layout_and_autodetects_backend(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    batch = root / 'batch_002'
    doc_id = 'det_all_features'
    tex = batch / doc_id / 'input' / f'{doc_id}.tex'
    tex.parent.mkdir(parents=True)
    tex.write_text(r'\\begin{equation}E=mc^2\\tag{1}\\label{eq:one}\\end{equation}')
    page = batch / doc_id / 'backend_ir' / 'paddleocr' / '.current' / 'extraction_ir' / doc_id / 'pages' / 'page_0000.json'
    page.parent.mkdir(parents=True)
    page.write_text(json.dumps({'blocks':[{'block_id':'b1','type':'equation','content':{'text':'E=mc^2'}},{'block_id':'b2','type':'paragraph','content':{'text':'(1)'}}]}))

    out = batch / 'diagnostics' / 'conventions'
    monkeypatch.setattr(sys, 'argv', ['x', '--root', str(root), '--batch', 'batch_002', '--output', str(out), '--write-proposed-config'])
    determine_main()
    report = json.loads((out / 'conventions_report.json').read_text())
    assert report['fixture_provenance'] == ['det_all_features']
    assert list(report['backends'].keys()) == ['paddleocr']
    assert report['backends']['paddleocr']['evaluation']['matched'] > 0


def test_normalizer_reads_real_layout_and_writes_copied_output(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    input_root = root / 'batch_002'
    doc_id = 'det_all_features'
    page = input_root / doc_id / 'backend_ir' / 'paddleocr' / '.current' / 'extraction_ir' / doc_id / 'pages' / 'page_0000.json'
    page.parent.mkdir(parents=True)
    original = {'blocks':[{'block_id':'b1','type':'footnote','content':{'text':'1First note.'}}]}
    page.write_text(json.dumps(original))
    cfg = root / 'config.toml'
    cfg.write_text('[[rules]]\nid = "x"\nbackend = "*"\nobject_type = "*"\ntext_regex = "a^"\n')
    out = input_root / 'backend_ir_normalised'

    monkeypatch.setattr(sys, 'argv', ['x', '--input-root', str(input_root), '--config', str(cfg), '--output-root', str(out)])
    normalizer_main()

    output_page = out / doc_id / 'backend_ir' / 'paddleocr' / '.current' / 'extraction_ir' / doc_id / 'pages' / 'page_0000.json'
    assert output_page.exists()
    assert page.exists()
    assert json.loads(page.read_text()) == original
