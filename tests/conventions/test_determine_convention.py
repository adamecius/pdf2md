import json, sys, tomllib
from pathlib import Path
from pdf2md.conventions.determine_convention import main as determine_main


def _mk_fixture(tmp_path: Path):
    root = tmp_path / 'latex_docling_groundtruth' / 'batch_002'; case=root/'det_all_features'; case.mkdir(parents=True)
    (case/'doc.tex').write_text(r'\section{A} \begin{equation}E=mc^2\tag{1}\end{equation}')
    datasets={
      'mineru':[{'block_id':'m1','type':'paragraph','content':{'text':'Figure 1: Boxed figure'}},{'block_id':'m2','type':'paragraph','content':{'text':'Table 1: Sample table A B 1 2'}},{'block_id':'m3','type':'paragraph','content':{'text':'A B'}},{'block_id':'m4','type':'paragraph','content':{'text':'1 2'}},{'block_id':'m5','type':'unknown','content':{'text':'1First note.'},'geometry':{'bbox':[0,900,1,910]}},{'block_id':'m6','type':'paragraph','content':{'text':'1 First note.'},'geometry':{'bbox':[0,880,1,890]}}],
      'paddleocr':[{'block_id':'p1','type':'formula','content':{'text':'E=mc^2'}},{'block_id':'p2','type':'paragraph','content':{'text':'(1)'}},{'block_id':'p3','type':'paragraph','content':{'text':'^1 First note.'}}],
      'deepseek':[{'block_id':'d1','type':'paragraph','content':{'text':'¹First note.'}},{'block_id':'d2','type':'paragraph','content':{'text':'(1) First note.'},'geometry':{'bbox':[0,800,1,810]}}],
    }
    for b,blocks in datasets.items():
        p=root/'backend_ir'/b/'det_all_features'; p.mkdir(parents=True); (p/'page.json').write_text(json.dumps({'blocks':blocks}))
    return root


def _run(root,out,monkeypatch):
    monkeypatch.setattr(sys,'argv',['x','--root',str(root.parent),'--batch','batch_002','--output',str(out),'--write-proposed-config','--emit-markdown-report']); determine_main()


def test_proposed_config_is_valid_toml(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    tomllib.loads((out/'ocr_conventions.proposed.toml').read_text())


def test_determine_convention_infers_footnote_no_space_after_marker(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['mineru']['summary']['footnote_no_space_after_marker']>=1


def test_determine_convention_infers_footnote_marker_superscript(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['deepseek']['summary']['footnote_marker_superscript']>=1


def test_determine_convention_infers_footnote_marker_parenthesised(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['deepseek']['summary']['footnote_marker_parenthesised']>=1


def test_determine_convention_infers_footnote_body_bottom_page(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['mineru']['summary']['footnote_body_bottom_page']>=1


def test_determine_convention_infers_table_flattened_paragraph(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['mineru']['summary']['table_flattened_paragraph']>=1


def test_determine_convention_infers_table_caption_merged_with_cells(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['mineru']['summary']['table_caption_merged_with_cells']>=1


def test_determine_convention_infers_table_rows_as_paragraphs(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['mineru']['summary']['table_rows_as_paragraphs']>=1


def test_determine_convention_infers_table_geometryless(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text()); assert rep['backends']['mineru']['summary']['table_geometryless']>=1


def test_proposed_rules_include_supporting_block_ids(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    pr=json.loads((out/'conventions_report.json').read_text())['backends']['paddleocr']['proposed_rules']
    assert any(r['supporting_backend_block_ids'] for r in pr)


def test_proposed_rules_include_doc_id(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    pr=json.loads((out/'conventions_report.json').read_text())['backends']['mineru']['proposed_rules']
    assert any('det_all_features' in r['supporting_doc_ids'] for r in pr)


def test_proposed_rules_include_reason_and_examples(tmp_path, monkeypatch):
    root=_mk_fixture(tmp_path); out=root/'diagnostics'/'conventions'; _run(root,out,monkeypatch)
    pr=json.loads((out/'conventions_report.json').read_text())['backends']['mineru']['proposed_rules']
    assert all(r['reason'] and r['example_before'] is not None and r['example_after'] is not None for r in pr)
