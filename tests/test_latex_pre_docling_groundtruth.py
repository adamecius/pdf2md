import json, subprocess, tempfile
from pathlib import Path


def _gen(out:Path):
    subprocess.run(["python","generate_latex_docling_groundtruth.py","--output-root",str(out),"--batch","b1"],check=True)


def test_labels_and_validator_pass():
    with tempfile.TemporaryDirectory() as td:
        out=Path(td); _gen(out)
        subprocess.run(["python","validate_latex_docling_groundtruth.py","--root",str(out),"--batch","b1"],check=True)
        for gt in (out/'b1').glob('*/groundtruth/semantic_document_groundtruth.json'):
            sem=json.loads(gt.read_text()); body={b['id']:b for b in sem['body']}
            for lbl,bid in sem['labels'].items():
                t=body[bid]['type']
                if lbl.startswith('sec:'): assert t=='section'
                if lbl.startswith('sub:'): assert t=='subsection'
                if lbl.startswith('fig:'): assert t=='figure'
                if lbl.startswith('tab:'): assert t=='table'
                if lbl.startswith('eq:'): assert t=='equation'


def test_comparator_self_and_corruptions():
    with tempfile.TemporaryDirectory() as td:
        out=Path(td); _gen(out)
        doc=out/'b1'/'multipage_all_features_references_footnotes'
        gt=doc/'groundtruth'/'semantic_document_groundtruth.json'
        ct=doc/'groundtruth'/'expected_semantic_contract.json'
        rep=doc/'reports'/'cmp.json'
        subprocess.run(["python","compare_pre_docling_groundtruth.py","--groundtruth",str(gt),"--candidate",str(gt),"--contract",str(ct),"--output",str(rep)],check=True)
        sem=json.loads(gt.read_text())
        bad=json.loads(gt.read_text())
        # remove table cell
        for b in bad['body']:
            if b.get('type')=='table' and b.get('table_rows'):
                b['table_rows'][0]['cells']=b['table_rows'][0]['cells'][:-1]
                break
        # remove repeated eq ref
        removed=False
        refs=[]
        for r in bad['references']:
            if r.get('target_label')=='eq:deep' and not removed:
                removed=True; continue
            refs.append(r)
        bad['references']=refs
        # flatten nested list
        bad['body']=[b for b in bad['body'] if not (b.get('type')=='list' and b.get('list_kind')=='enumerate')]
        cand=doc/'reports'/'cand_bad.json'; cand.write_text(json.dumps(bad))
        p=subprocess.run(["python","compare_pre_docling_groundtruth.py","--groundtruth",str(gt),"--candidate",str(cand),"--contract",str(ct),"--output",str(rep)])
        assert p.returncode!=0
