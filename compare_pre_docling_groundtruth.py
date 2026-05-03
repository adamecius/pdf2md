#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

def n(s): return ' '.join((s or '').split()).lower()

def list_shape(body):
    return sorted([(b['id'], b.get('parent_id')) for b in body if b.get('type') in ('list','list_item')], key=lambda x:x[0])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--groundtruth',required=True); ap.add_argument('--candidate',required=True); ap.add_argument('--contract',required=True); ap.add_argument('--output',required=True); ap.add_argument('--verbose',action='store_true'); a=ap.parse_args()
    gt=json.loads(Path(a.groundtruth).read_text()); cd=json.loads(Path(a.candidate).read_text()); ct=json.loads(Path(a.contract).read_text())
    errs=[]; warns=[]
    if n(gt.get('title'))!=n(cd.get('title')): errs.append('title_mismatch')
    gcount=Counter(b.get('type') for b in gt.get('body',[])); ccount=Counter(b.get('type') for b in cd.get('body',[]))
    for t,c in gcount.items():
        if ccount.get(t,0)<c: errs.append(f'type_count_lt:{t}:{ccount.get(t,0)}<{c}')
    # section/subsection order in candidate
    expected=[x for x in ct.get('expected_ordered_block_constraints',[]) if x in ('section','subsection')]
    cand=[b.get('type') for b in cd.get('body',[]) if b.get('type') in ('section','subsection')]
    if cand[:len(expected)]!=expected: errs.append('section_order_mismatch')
    # labels/type by prefix
    cmap={b['id']:b for b in cd.get('body',[])}
    for lbl,bid in gt.get('labels',{}).items():
        cbid=cd.get('labels',{}).get(lbl)
        if not cbid: errs.append(f'missing_label:{lbl}'); continue
        t=cmap.get(cbid,{}).get('type')
        want='section' if lbl.startswith('sec:') else 'subsection' if lbl.startswith('sub:') else 'figure' if lbl.startswith('fig:') else 'table' if lbl.startswith('tab:') else 'equation' if lbl.startswith('eq:') else None
        if want and t!=want: errs.append(f'label_type_mismatch:{lbl}:{t}!={want}')
    # references repeated count by target label
    gr=Counter(r.get('target_label') for r in gt.get('references',[])); cr=Counter(r.get('target_label') for r in cd.get('references',[]))
    for k,v in gr.items():
        if cr.get(k,0)<v: errs.append(f'missing_repeated_reference:{k}:{cr.get(k,0)}<{v}')
    # caption text
    gcap=[n(b.get('text')) for b in gt.get('body',[]) if b.get('type')=='caption']; ccap=[n(b.get('text')) for b in cd.get('body',[]) if b.get('type')=='caption']
    for t in gcap:
        if t not in ccap: errs.append(f'missing_caption_text:{t[:32]}')
    # table cells
    gcells=[n(c['text']) for b in gt.get('body',[]) if b.get('type')=='table' for r in b.get('table_rows',[]) for c in r.get('cells',[])]
    ccells=[n(c['text']) for b in cd.get('body',[]) if b.get('type')=='table' for r in b.get('table_rows',[]) for c in r.get('cells',[])]
    for cell in gcells:
        if cell and cell not in ccells: errs.append(f'missing_table_cell:{cell[:32]}')
    # equation text
    geq=[n(b.get('text')) for b in gt.get('body',[]) if b.get('type')=='equation']; ceq=[n(b.get('text')) for b in cd.get('body',[]) if b.get('type')=='equation']
    for e in geq:
        if e and e not in ceq: errs.append(f'missing_equation:{e[:24]}')
    # footnotes
    gft=[n(b.get('text')) for b in gt.get('body',[]) if b.get('type')=='footnote']; cft=[n(b.get('text')) for b in cd.get('body',[]) if b.get('type')=='footnote']
    for f in gft:
        if f not in cft: errs.append(f'missing_footnote:{f[:24]}')
    if len([b for b in cd.get('body',[]) if b.get('type')=='list']) < len([b for b in gt.get('body',[]) if b.get('type')=='list']):
        errs.append('flattened_nested_lists')
    out={'ok':not errs,'errors':errs,'warnings':warns}
    Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,indent=2))
    if a.verbose: print(json.dumps(out,indent=2))
    raise SystemExit(0 if out['ok'] else 1)

if __name__=='__main__': main()
