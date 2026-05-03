#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, tomllib
from pathlib import Path

def check_doc(doc:Path, enabled:list[str])->dict:
    did=doc.name; errs=[]; warns=[]
    tex=doc/'input'/f'{did}.tex'
    if not tex.exists(): errs.append('missing_tex')
    gt=doc/'groundtruth'
    for f in ['source_groundtruth_ir.json','expected_semantic_contract.json','expected_docling_contract.json','provenance_manifest.json']:
        if not (gt/f).exists(): errs.append(f'missing_{f}')
    if (gt/'source_groundtruth_ir.json').exists():
        data=json.loads((gt/'source_groundtruth_ir.json').read_text())
        for k in ['schema_name','document_id','nodes','labels','references','features']:
            if k not in data: errs.append(f'bad_groundtruth_{k}')
    for b in enabled:
        edir=doc/'backend_ir'/b/'.current'/'extraction_ir'/did
        if not (edir/'manifest.json').exists(): errs.append(f'missing_backend_manifest_{b}')
        if not (edir/'pages').exists(): errs.append(f'missing_backend_pages_{b}')
    for f in ['consensus/consensus_report.json','consensus/semantic_links.json','consensus/semantic_document.json']:
        if not (doc/f).exists(): errs.append(f'missing_{f}')
    if not ((doc/'docling'/'docling_adapter_report.json').exists() or (doc/'docling'/'docling_layer_report.json').exists()): errs.append('missing_docling_report')
    preview=doc/'docling'/'docling_preview.md'
    if not preview.exists(): errs.append('missing_docling_preview')
    else:
        sem=json.loads((gt/'expected_semantic_contract.json').read_text()) if (gt/'expected_semantic_contract.json').exists() else {}
        txt=preview.read_text(encoding='utf-8')
        for s in sem.get('expected_markdown_snippets',[]):
            if s not in txt: warns.append(f'missing_snippet:{s}')
    rep={'document_id':did,'errors':errs,'warnings':warns,'ok':not errs}
    (doc/'validation_report.json').write_text(json.dumps(rep,indent=2))
    return rep

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.current/latex_docling_groundtruth'); ap.add_argument('--batch',default='batch_001'); ap.add_argument('--config',default='pdf2md.consensus.example.toml'); ap.add_argument('--verbose',action='store_true'); a=ap.parse_args()
    enabled=[k for k,v in tomllib.load(open(a.config,'rb')).get('backends',{}).items() if v.get('enabled',False)]
    root=Path(a.root)/a.batch
    reports=[check_doc(d,enabled) for d in root.iterdir() if d.is_dir()]
    out={'batch':a.batch,'documents':reports,'ok':all(r['ok'] for r in reports)}
    (root/'validation_report.json').write_text(json.dumps(out,indent=2))
    if a.verbose: print(json.dumps(out,indent=2))
    raise SystemExit(0 if out['ok'] else 1)
if __name__=='__main__': main()
