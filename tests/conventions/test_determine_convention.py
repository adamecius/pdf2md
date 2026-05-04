import json, sys, tomllib, pytest
from pathlib import Path
from pdf2md.conventions.determine_convention import main as determine_main


def _mk(tmp: Path, missing=False):
    root=tmp/'latex_docling_groundtruth'/'batch_test'; doc=root/'doc1'; doc.mkdir(parents=True)
    (doc/'a.tex').write_text(r"\begin{figure}\fbox{FIG}\caption{Boxed figure}\label{fig:one}\end{figure}\begin{equation}E=mc^2\tag{1}\label{eq:one}\end{equation}\footnote{First note.}\ref{fig:one}")
    for be in ['mineru','paddleocr','deepseek']:
        p=root/'backend_ir'/be/'doc1'; p.mkdir(parents=True)
        blocks=[] if missing else [{'block_id':'b1','type':'paragraph','content':{'text':'Figure 1 Boxed figure'}},{'block_id':'b2','type':'formula','content':{'text':'E=mc^2'}},{'block_id':'b3','type':'paragraph','content':{'text':'(1)'}},{'block_id':'b4','type':'unknown','content':{'text':'1First note.'}}]
        (p/'page.json').write_text(json.dumps({'blocks':blocks}))
    return root


def _run(root, out, monkeypatch, extra=None):
    argv=['x','--root',str(root.parent),'--batch','batch_test','--output',str(out),'--write-proposed-config','--backend','mineru','--backend','paddleocr','--backend','deepseek']+(extra or [])
    monkeypatch.setattr(sys,'argv',argv); determine_main()


def test_groundtruth_objects_have_gt_ids(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text())
    assert all('gt_id' in a for a in rep['backends']['mineru']['alignments'])


def test_every_groundtruth_object_gets_alignment_record_per_backend(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text())
    n=len(rep['backends']['mineru']['alignments'])
    assert n>0 and all(len(rep['backends'][b]['alignments'])==n for b in ['mineru','paddleocr','deepseek'])


def test_missed_object_is_reported_explicitly(tmp_path, monkeypatch):
    root=_mk(tmp_path, missing=True); out=root/'diag'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text())
    assert any(a['status']=='missed' for a in rep['backends']['mineru']['alignments'])


def test_report_has_top_level_evaluation_status(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    assert json.loads((out/'conventions_report.json').read_text())['evaluation']['status'] in {'pass','warn','fail'}


def test_report_has_backend_evaluation_status(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text())
    assert rep['backends']['mineru']['evaluation']['status'] in {'pass','warn','fail'}


def test_strict_mode_exits_nonzero_on_fail(tmp_path, monkeypatch):
    root=_mk(tmp_path, missing=True); out=root/'diag'
    with pytest.raises(SystemExit):
        _run(root,out,monkeypatch,['--strict'])


def test_generated_toml_still_parses(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    tomllib.loads((out/'ocr_conventions.proposed.toml').read_text())


def test_proposed_rules_reference_supporting_gt_ids(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    rep=json.loads((out/'conventions_report.json').read_text())
    rules=rep['backends']['paddleocr']['proposed_rules']
    assert rules and rules[0]['supporting_gt_ids']

def test_strict_mode_exits_zero_on_pass(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'
    _run(root,out,monkeypatch,['--strict','--allow-partial'])


def test_strict_mode_warn_passes_with_allow_partial(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'
    _run(root,out,monkeypatch,['--strict','--allow-partial'])
