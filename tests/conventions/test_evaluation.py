import json, sys
from pathlib import Path
from pdf2md.conventions.determine_convention import main as determine_main


def _fixture(tmp_path):
    root=tmp_path/'latex_docling_groundtruth'/'batch_test'; d=root/'d1'; d.mkdir(parents=True)
    (d/'a.tex').write_text(r"\begin{equation}E=mc^2\tag{1}\label{eq:one}\end{equation}")
    p=root/'backend_ir'/'paddleocr'/'d1'; p.mkdir(parents=True)
    (p/'p.json').write_text(json.dumps({'blocks':[{'block_id':'b1','type':'formula','content':{'text':'E=mc^2'}},{'block_id':'b2','type':'paragraph','content':{'text':'(1)'}}]}))
    return root


def test_normalisation_evaluation_reports_before_after(tmp_path, monkeypatch):
    root=_fixture(tmp_path); out=root/'diag'
    monkeypatch.setattr(sys,'argv',['x','--root',str(root.parent),'--batch','batch_test','--output',str(out),'--write-proposed-config'])
    determine_main()
    rep=json.loads((out/'conventions_report.json').read_text())
    assert 'evaluation' in rep
