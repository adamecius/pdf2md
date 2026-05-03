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


def test_comparator_backend_style_candidate_passes():
    with tempfile.TemporaryDirectory() as td:
        out=Path(td); _gen(out)
        doc=out/'b1'/'multipage_all_features_references_footnotes'
        gt=json.loads((doc/'groundtruth'/'semantic_document_groundtruth.json').read_text())
        ct=doc/'groundtruth'/'expected_semantic_contract.json'

        blocks=[]
        for b in gt['body']:
            nb={k:v for k,v in b.items() if k!='labels'}
            if b.get('labels'):
                nb['label']=b['labels'][0]
            if nb.get('type')=='equation': nb['type']='formula'
            if nb.get('type')=='figure': nb['type']='picture'
            if nb.get('type') in ('section','subsection'): nb['type']='section_header'
            if nb.get('type')=='paragraph': nb['type']='text'
            blocks.append(nb)
        rels=[{'relation_type':('refers_to' if r.get('type')=='reference_to' else r.get('type')),'target_label':r.get('target_label'),'caption_text':r.get('caption_text'),'footnote_text':r.get('footnote_text')} for r in gt.get('relations',[])]
        refs_backend=[]
        for r in gt['references']:
            rr=dict(r); rr['label']=rr.get('target_label'); rr.pop('target_label',None); refs_backend.append(rr)
        cand={'blocks':blocks,'references':refs_backend,'relations':rels}

        (doc/'reports').mkdir(exist_ok=True)
        cand_path=doc/'reports'/'cand_backend_style.json'; cand_path.write_text(json.dumps(cand))
        rep=doc/'reports'/'cmp_backend_style.json'
        subprocess.run(['python','compare_pre_docling_groundtruth.py','--groundtruth',str(doc/'groundtruth'/'semantic_document_groundtruth.json'),'--candidate',str(cand_path),'--contract',str(ct),'--output',str(rep)],check=True)

        report=json.loads(rep.read_text())
        assert report['ok']
        # helper-only source block types absent in backend candidate should still pass
        helper_trimmed=dict(cand)
        helper_trimmed['blocks']=[b for b in blocks if b.get('type') not in ('page_break','display_math','inline_math','reference','bibliography_like')]
        helper_path=doc/'reports'/'cand_backend_style_no_helpers.json'; helper_path.write_text(json.dumps(helper_trimmed))
        subprocess.run(['python','compare_pre_docling_groundtruth.py','--groundtruth',str(doc/'groundtruth'/'semantic_document_groundtruth.json'),'--candidate',str(helper_path),'--contract',str(ct),'--output',str(rep)],check=True)
