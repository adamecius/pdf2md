import json,sys
from pdf2md.conventions.determine_convention import main


def test_report_has_top_level_evaluation_status(tmp_path, monkeypatch):
    root=tmp_path/'r'/'b'; d=root/'d1'; d.mkdir(parents=True)
    (d/'a.tex').write_text(r"\\begin{equation}E=mc^2\\end{equation}")
    p=root/'backend_ir'/'paddleocr'/'d1'; p.mkdir(parents=True)
    (p/'p.json').write_text(json.dumps({'blocks':[{'block_id':'b1','type':'formula','content':{'text':'E=mc^2'}}]}))
    out=root/'diag'
    monkeypatch.setattr(sys,'argv',['x','--root',str(root.parent),'--batch','b','--output',str(out),'--backend','paddleocr'])
    main(); rep=json.loads((out/'conventions_report.json').read_text())
    assert rep['evaluation']['status'] in {'pass','warn','fail'}
