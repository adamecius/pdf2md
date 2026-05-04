import json, re, sys, tomllib, pytest
from pathlib import Path
from pdf2md.conventions.determine_convention import main as determine_main
from pdf2md.conventions.normalizer import normalise_blocks
from pdf2md.conventions.rules import Rule


def _mk(tmp: Path, missing=False):
    root=tmp/'latex_docling_groundtruth'/'batch_test'; doc=root/'doc1'; doc.mkdir(parents=True)
    (doc/'a.tex').write_text(r"\begin{figure}\fbox{FIG}\caption{Boxed figure}\label{fig:one}\end{figure}\begin{equation}E=mc^2\tag{1}\label{eq:one}\end{equation}\begin{table}\caption{Sample table}\label{tab:one}\begin{tabular}{cc}A & B\\1 & 2\end{tabular}\end{table}\footnote{First note.}\ref{fig:one}")
    for be in ['mineru','paddleocr','deepseek']:
        p=root/'backend_ir'/be/'doc1'; p.mkdir(parents=True)
        blocks=[] if missing else [{'block_id':'b1','type':'paragraph','content':{'text':'Figure 1 Boxed figure'}},{'block_id':'b2','type':'formula','content':{'text':'E=mc^2'}},{'block_id':'b3','type':'paragraph','content':{'text':'(1)'}},{'block_id':'b4','type':'unknown','content':{'text':'1First note.'}},{'block_id':'b5','type':'paragraph','content':{'text':'Table 1: Sample table A B 1 2'}}]
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


def _rules_by_id(out: Path):
    cfg = tomllib.loads((out/'ocr_conventions.proposed.toml').read_text())
    return {r['id']: r for r in cfg.get('rules', [])}


def test_proposed_toml_never_emits_catch_all_regex(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    text = (out/'ocr_conventions.proposed.toml').read_text()
    assert 'text_regex = ".+"' not in text


def test_formula_split_regex_does_not_match_ordinary_text(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    rules = _rules_by_id(out)
    rgx = rules['mineru.formula_number_split_block']['text_regex']
    assert re.match(rgx, 'Detectable All FeaturesFigure 1: Boxed figure') is None


def test_footnote_regex_matches_only_no_space_marker_text(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    rules = _rules_by_id(out)
    foot = rules['mineru.footnote_no_space_after_marker']
    assert re.match(foot['text_regex'], '1First note.') is not None
    assert re.match(foot['text_regex'], 'Detectable All Features') is None
    assert 'normalised_text_rewrite' in foot


def test_table_flattened_regex_matches_table_like_text_only(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    rules = _rules_by_id(out)
    rgx = rules['mineru.table_flattened_paragraph']['text_regex']
    assert re.match(rgx, 'Table 1: Sample table A B 1 2') is not None
    assert re.match(rgx, 'Figure 1: Boxed figure') is None


def test_generated_footnote_rewrite_normalises_missing_space(tmp_path, monkeypatch):
    root=_mk(tmp_path); out=root/'diag'; _run(root,out,monkeypatch)
    cfg = tomllib.loads((out/'ocr_conventions.proposed.toml').read_text())
    rules = [Rule(**r) for r in cfg.get('rules', [])]
    block = {'block_id':'x1','type':'paragraph','content':{'text':'1First note.'},'bbox':[0,800,10,820]}
    out_blocks = normalise_blocks([block], 'mineru', rules)
    assert out_blocks[0]['content']['text'] == '1 First note.'


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
