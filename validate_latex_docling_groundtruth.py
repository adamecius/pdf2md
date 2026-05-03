#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, tomllib
from pathlib import Path

REQ_GT={"schema_name","document_id","nodes","labels","references","features","pages_expected_min"}
REQ_SEM={"document_id","expected_title","expected_sections","expected_labels","required_node_types"}
REQ_DOC={"document_id","required_docling_kinds"}

def check_doc(doc:Path, enabled:list[str])->dict:
    did=doc.name; errs=[]; warns=[]
    gt=doc/'groundtruth'; tex=doc/'input'/f'{did}.tex'
    for f in ['source_groundtruth_ir.json','expected_semantic_contract.json','expected_docling_contract.json','provenance_manifest.json']:
        if not (gt/f).exists(): errs.append(f'missing_{f}')
    if not tex.exists(): errs.append('missing_tex')
    g=s=d=None
    if (gt/'source_groundtruth_ir.json').exists():
        g=json.loads((gt/'source_groundtruth_ir.json').read_text())
        for k in REQ_GT:
            if k not in g: errs.append(f'bad_groundtruth_{k}')
        if not g.get('nodes'): errs.append('empty_nodes')
        for r in g.get('references',[]):
            tid=r.get('target_node_id'); target=next((n for n in g['nodes'] if n['id']==tid),None)
            if not target or target.get('type')=='reference': errs.append(f'bad_reference_target:{r.get("target_label")}')
    if (gt/'expected_semantic_contract.json').exists():
        s=json.loads((gt/'expected_semantic_contract.json').read_text())
        for k in REQ_SEM:
            if k not in s: errs.append(f'bad_semantic_{k}')
    if (gt/'expected_docling_contract.json').exists():
        d=json.loads((gt/'expected_docling_contract.json').read_text())
        for k in REQ_DOC:
            if k not in d: errs.append(f'bad_docling_{k}')
    if tex.exists() and s:
        src=tex.read_text()
        for lbl in s.get('expected_labels',[]):
            if f'\\label{{{lbl}}}' not in src: errs.append(f'label_not_in_tex:{lbl}')
    preview=doc/'docling'/'docling_preview.md'
    if preview.exists() and s:
        txt=preview.read_text()
        allowed=set(s.get('allowed_missing_snippets',[]))
        for snip in s.get('expected_markdown_snippets',[]):
            if snip not in txt and snip not in allowed: errs.append(f'missing_snippet:{snip}')
    for b in enabled:
        edir=doc/'backend_ir'/b/'.current'/'extraction_ir'/did
        if not (edir/'manifest.json').exists(): warns.append(f'missing_backend_manifest_{b}')
    return {'document_id':did,'errors':errs,'warnings':warns,'ok':not errs}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.current/latex_docling_groundtruth'); ap.add_argument('--batch',default='batch_001'); ap.add_argument('--config',default='pdf2md.consensus.example.toml'); ap.add_argument('--verbose',action='store_true'); a=ap.parse_args()
    enabled=[k for k,v in tomllib.load(open(a.config,'rb')).get('backends',{}).items() if v.get('enabled',False)]
    root=Path(a.root)/a.batch
    reps=[check_doc(d,enabled) for d in root.iterdir() if d.is_dir()]
    out={'batch':a.batch,'documents':reps,'ok':all(r['ok'] for r in reps)}
    (root/'validation_report.json').write_text(json.dumps(out,indent=2))
    if a.verbose: print(json.dumps(out,indent=2))
    raise SystemExit(0 if out['ok'] else 1)

if __name__=='__main__': main()
