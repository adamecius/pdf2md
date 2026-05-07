import json, tomllib
from pathlib import Path


def test_proposed_rules_are_backend_scoped(tmp_path):
    p = Path('.current/latex_docling_groundtruth/batch_002/diagnostics/conventions/conventions_report.json')
    if not p.exists():
        return
    r=json.loads(p.read_text())
    for be,sec in r['backends'].items():
        for rule in sec.get('proposed_rules',[]):
            assert rule.get('backend')==be
            assert rule.get('supporting_gt_ids')


def test_paddleocr_equation_split_rule_has_specific_regex():
    p=Path('configs/ocr_conventions/scientific_latex.example.toml')
    d=tomllib.loads(p.read_text())
    rs=[x for x in d['rules'] if x['id']=='equation.number_split_block']
    assert rs and '(' in rs[0]['text_regex'] and rs[0]['text_regex']!='.+'


def test_mineru_footnote_no_space_rule_has_specific_regex():
    d=tomllib.loads(Path('configs/ocr_conventions/default.toml').read_text())
    rs=[x for x in d['rules'] if x['id']=='footnote.leading_digit_without_space']
    assert rs and '\\d+' in rs[0]['text_regex'] and 'normalised_text_rewrite' in rs[0]
