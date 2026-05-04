import json,sys
from pdf2md.conventions.determine_convention import main


def test_no_generic_dot_plus_rule_is_accepted_as_learned_pattern(tmp_path, monkeypatch):
    root=tmp_path/'r'/'b'; d=root/'d1'; d.mkdir(parents=True)
    (d/'a.tex').write_text(r"\\begin{equation}E=mc^2\\tag{1}\\end{equation}")
    p=root/'backend_ir'/'paddleocr'/'d1'; p.mkdir(parents=True)
    (p/'p.json').write_text(json.dumps({'blocks':[{'block_id':'b1','type':'formula','content':{'text':'E=mc^2'}},{'block_id':'b2','type':'paragraph','content':{'text':'(1)'}}]}))
    out=root/'diag'
    monkeypatch.setattr(sys,'argv',['x','--root',str(root.parent),'--batch','b','--output',str(out),'--backend','paddleocr','--write-proposed-config'])
    main(); txt=(out/'ocr_conventions.proposed.toml').read_text()
    assert 'text_regex = ".+"' not in txt
