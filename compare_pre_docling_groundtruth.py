#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def norm(s:str)->str: return ' '.join((s or '').split())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--groundtruth',required=True); ap.add_argument('--candidate',required=True); ap.add_argument('--contract',required=True); ap.add_argument('--output',required=True); ap.add_argument('--verbose',action='store_true'); a=ap.parse_args()
    gt=json.loads(Path(a.groundtruth).read_text()); cd=json.loads(Path(a.candidate).read_text()); ct=json.loads(Path(a.contract).read_text())
    errs=[]; warns=[]
    if norm(gt.get('title',''))!=norm(cd.get('title','')): errs.append('title_mismatch')
    gtypes=[b.get('type') for b in gt.get('body',[])]; ctypes=[b.get('type') for b in cd.get('body',[])]
    for t in set(gtypes):
        if t not in ctypes: errs.append(f'missing_type:{t}')
    if gtypes[:len(ct.get('expected_ordered_block_constraints',[]))] != ct.get('expected_ordered_block_constraints',[]):
        warns.append('groundtruth_contract_order_mismatch')
    glabels=set(gt.get('labels',{}).keys()); clabels=set(cd.get('labels',{}).keys())
    for l in glabels:
        if l not in clabels: errs.append(f'missing_label:{l}')
    c_rel=cd.get('relations',[])
    for rr in [r for r in gt.get('relations',[]) if r.get('type') in ('caption_of','reference_to','footnote_of')]:
        if not any(x.get('type')==rr.get('type') and x.get('target_id')==rr.get('target_id') for x in c_rel): errs.append(f"missing_relation:{rr.get('type')}:{rr.get('target_id')}")
    out={'ok':not errs,'errors':errs,'warnings':warns}
    Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,indent=2))
    if a.verbose: print(json.dumps(out,indent=2))
    raise SystemExit(0 if out['ok'] else 1)

if __name__=='__main__': main()
