from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
from .latex_groundtruth import extract_groundtruth_objects
from .alignment import align_groundtruth_to_backend
from .reporting import write_report


def _status_from_counts(c):
    if c['missed'] > 0 or c['ambiguous'] > 0: return 'fail'
    if c['partial'] > 0: return 'warn'
    return 'pass'


def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--batch',required=True); p.add_argument('--output',required=True)
    p.add_argument('--backend',action='append'); p.add_argument('--write-proposed-config',action='store_true'); p.add_argument('--emit-markdown-report',action='store_true')
    p.add_argument('--strict',action='store_true'); p.add_argument('--allow-partial',action='store_true')
    a=p.parse_args(); root=Path(a.root)/a.batch; out=Path(a.output)
    gt_by_doc={tex.parent.name: extract_groundtruth_objects(tex.read_text(), tex.parent.name) for tex in root.rglob('*.tex')}
    backends=a.backend or ['mineru','paddleocr','deepseek','pymupdf']
    report={'batch':a.batch,'fixture_provenance':sorted(gt_by_doc.keys()),'backends':{},'evaluation':{}}
    total=defaultdict(int)
    for be in backends:
        aligns=[]; proposed={}
        for doc_id,gt in gt_by_doc.items():
            blocks=[]
            for f in (root/'backend_ir'/be/doc_id).rglob('*.json'):
                d=json.loads(f.read_text()); blocks.extend(d.get('blocks',[]))
            recs=align_groundtruth_to_backend(gt,blocks,backend=be,doc_id=doc_id)
            for r in recs:
                # classify a few conventions
                if r['object_type']=='equation' and len(r['matched_blocks'])>1: r['convention']='formula_number_split_block'
                elif r['object_type']=='table' and any('cell_text_overlap' in (m.get('match_reason') or '') for m in r['matched_blocks']): r['convention']='table_flattened_paragraph'
                elif r['object_type']=='footnote' and any('1First' in m['text'] for m in r['matched_blocks']): r['convention']='footnote_no_space_after_marker'
                aligns.append(r)
                if r['status'] in {'matched','partial'} and r.get('convention'):
                    rid=f"{be}.{r['convention']}"
                    pr=proposed.setdefault(rid,{'rule_id':rid,'backend':be,'support':0,'supporting_gt_ids':set(),'supporting_doc_ids':set(),'supporting_backend_block_ids':set(),'alignment_statuses':set(),'reason':'alignment-derived','example_before':'','example_after':'','groundtruth_source':'latex_fixture+backend_ir'})
                    pr['support']+=1; pr['supporting_gt_ids'].add(r['gt_id']); pr['supporting_doc_ids'].add(r['doc_id']); pr['alignment_statuses'].add(r['status'])
                    for mb in r['matched_blocks']: pr['supporting_backend_block_ids'].add(mb['block_id'])
                    if r['matched_blocks'] and not pr['example_before']: pr['example_before']=r['matched_blocks'][0]['text']; pr['example_after']=r['matched_blocks'][0]['text']
        counts={k: sum(1 for x in aligns if x['status']==k) for k in ['matched','partial','missed','ambiguous','unsupported']}
        counts['total_groundtruth_objects']=len(aligns); counts['status']=_status_from_counts(counts)
        report['backends'][be]={'summary':dict(counts),'examples':[{'gt_id':x['gt_id'],'convention':x.get('convention'),'object_type':x['object_type'],'groundtruth_object':x['groundtruth_object'],'backend_blocks':x['matched_blocks'],'match_reasons':[m.get('match_reason') for m in x['matched_blocks']]} for x in aligns[:30]],'alignments':aligns,'proposed_rules':[{**v,'supporting_gt_ids':sorted(v['supporting_gt_ids']),'supporting_doc_ids':sorted(v['supporting_doc_ids']),'supporting_backend_block_ids':sorted(v['supporting_backend_block_ids']),'alignment_statuses':sorted(v['alignment_statuses'])} for v in proposed.values()], 'evaluation':counts}
        for k in ['matched','partial','missed','ambiguous','unsupported']: total[k]+=counts[k]
    total['total_groundtruth_objects']=sum(v['evaluation']['total_groundtruth_objects'] for v in report['backends'].values())
    total['total_backend_alignments']=total['total_groundtruth_objects']; total['status']=_status_from_counts(total); report['evaluation']=dict(total)
    write_report(out,report,emit_markdown=a.emit_markdown_report)
    if a.write_proposed_config:
        lines=['# evidence-derived backend-scoped rules']
        for be,sec in report['backends'].items():
            for r in sec['proposed_rules']:
                lines += [f"# gt_ids={r['supporting_gt_ids']}", '[[rules]]', f"id = \"{r['rule_id']}\"", f"backend = \"{be}\"", "object_type = \"*\"", "text_regex = \".+\"", "normalised_type = \"paragraph\"", ""]
        (out/'ocr_conventions.proposed.toml').write_text('\n'.join(lines))
    if a.strict:
        st=report['evaluation']['status']
        if st=='fail' or (st=='warn' and not a.allow_partial): raise SystemExit(1)


if __name__=='__main__': main()
