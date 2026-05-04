import json,pytest
from pdf2md.conventions.evaluate_milestones import evaluate, main


def test_evaluate_milestones_writes_json_report(tmp_path):
    out=tmp_path/'o'; payload=evaluate(tmp_path,'batch_002',out)
    assert (out/'milestone_report.json').exists()
    assert payload['stage'] in payload['allowed_stages']

def test_strict_evaluator_exits_nonzero_when_milestones_incomplete(tmp_path, monkeypatch):
    out=tmp_path/'o'
    monkeypatch.setattr('sys.argv',['x','--root',str(tmp_path),'--batch','batch_002','--output',str(out),'--strict'])
    with pytest.raises(SystemExit): main()
