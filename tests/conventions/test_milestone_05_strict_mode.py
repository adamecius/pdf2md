import json,sys,pytest
from pdf2md.conventions.determine_convention import main

def test_strict_mode_exits_nonzero_on_fail(tmp_path, monkeypatch):
    root=tmp_path/'r'/'b'; d=root/'d1'; d.mkdir(parents=True)
    (d/'a.tex').write_text(r"\\begin{equation}E=mc^2\\end{equation}")
    (root/'backend_ir'/'paddleocr'/'d1').mkdir(parents=True)
    out=root/'diag'
    monkeypatch.setattr(sys,'argv',['x','--root',str(root.parent),'--batch','b','--output',str(out),'--backend','paddleocr','--strict'])
    with pytest.raises(SystemExit): main()
