from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
from .latex_groundtruth import extract_groundtruth_objects
from .alignment import align_groundtruth_to_backend
from .reporting import write_report


SAFE_PROPOSED_RULES_BY_CONVENTION = {
    'formula_number_split_block': {
        'text_regex': r"^\s*\(?\s*\d+(?:\.\d+)*\s*\)?\s*$",
        'normalised_type': 'paragraph',
    },
    'footnote_no_space_after_marker': {
        'text_regex': r"^\s*(\d+)(\S.*)$",
        'normalised_type': 'paragraph',
        'normalised_text_rewrite': r"\1 \2",
    },
    'table_flattened_paragraph': {
        'text_regex': r"^\s*Table\s+\d+(?:\.\d+)?\s*[:.]?.+",
        'normalised_type': 'paragraph',
    },
}


def doc_id_from_tex_path(tex: Path, batch_root: Path) -> str:
    rel = tex.relative_to(batch_root)
    if len(rel.parts) >= 3 and rel.parts[1] == 'input':
        return rel.parts[0]
    if len(rel.parts) >= 2:
        return rel.parts[-2]
    return tex.parent.name


def load_backend_blocks(batch_root: Path, doc_id: str, backend: str) -> tuple[list[dict], bool]:
    blocks: list[dict] = []
    roots = [
        batch_root / doc_id / 'backend_ir' / backend / '.current' / 'extraction_ir' / doc_id,
        batch_root / 'backend_ir' / backend / doc_id,
    ]
    seen = set()
    has_ir = False
    for root in roots:
        if not root.exists():
            continue
        has_ir = True
        for f in root.rglob('*.json'):
            if f in seen:
                continue
            seen.add(f)
            d = json.loads(f.read_text())
            b = d.get('blocks') if isinstance(d, dict) else None
            if isinstance(b, list):
                blocks.extend(b)
    return blocks, has_ir


def _detect_backends(batch_root: Path, doc_ids: list[str]) -> list[str]:
    found = set()
    for doc_id in doc_ids:
        be_root = batch_root / doc_id / 'backend_ir'
        if not be_root.exists():
            continue
        for p in be_root.iterdir():
            if p.is_dir():
                found.add(p.name)
    return sorted(found)


def _status_from_counts(c):
    if c['missed'] > 0 or c['ambiguous'] > 0: return 'fail'
    if c['partial'] > 0: return 'warn'
    return 'pass'


def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--batch',required=True); p.add_argument('--output',required=True)
    p.add_argument('--backend',action='append'); p.add_argument('--write-proposed-config',action='store_true'); p.add_argument('--emit-markdown-report',action='store_true')
    p.add_argument('--strict',action='store_true'); p.add_argument('--allow-partial',action='store_true')
    a=p.parse_args(); root=Path(a.root)/a.batch; out=Path(a.output)
    gt_by_doc={doc_id_from_tex_path(tex, root): extract_groundtruth_objects(tex.read_text(), doc_id_from_tex_path(tex, root)) for tex in root.rglob('*.tex')}
    backends=a.backend or _detect_backends(root, sorted(gt_by_doc.keys()))
    report={'batch':a.batch,'fixture_provenance':sorted(gt_by_doc.keys()),'backends':{},'evaluation':{},'skipped_no_backend_ir':0}
    total=defaultdict(int)
    for be in backends:
        aligns=[]; proposed={}; documents={}
        for doc_id,gt in gt_by_doc.items():
            blocks, has_ir = load_backend_blocks(root, doc_id, be)
            if not has_ir:
                documents[doc_id] = {'status':'skipped_no_backend_ir','groundtruth_objects':len(gt),'backend_blocks':0}
                continue
            recs=align_groundtruth_to_backend(gt,blocks,backend=be,doc_id=doc_id)
            documents[doc_id] = {'status':'evaluated','groundtruth_objects':len(recs),'backend_blocks':len(blocks)}
            for r in recs:
                if r['object_type']=='equation' and len(r['matched_blocks'])>1: r['convention']='formula_number_split_block'
                elif r['object_type']=='table' and (any('cell_text_overlap' in (m.get('match_reason') or '') for m in r['matched_blocks']) or any((m.get('text') or '').lstrip().startswith('Table ') for m in r['matched_blocks'])): r['convention']='table_flattened_paragraph'
                elif r['object_type']=='footnote' and any('1First' in m['text'] for m in r['matched_blocks']): r['convention']='footnote_no_space_after_marker'
                aligns.append(r)
                if r['status'] in {'matched','partial'} and r.get('convention'):
                    rid=f"{be}.{r['convention']}"
                    pr=proposed.setdefault(rid,{'rule_id':rid,'backend':be,'support':0,'supporting_gt_ids':set(),'supporting_doc_ids':set(),'supporting_backend_block_ids':set(),'alignment_statuses':set(),'reason':'alignment-derived','example_before':'','example_after':'','groundtruth_source':'latex_fixture+backend_ir'})
                    pr['support']+=1; pr['supporting_gt_ids'].add(r['gt_id']); pr['supporting_doc_ids'].add(r['doc_id']); pr['alignment_statuses'].add(r['status'])
                    for mb in r['matched_blocks']: pr['supporting_backend_block_ids'].add(mb['block_id'])
                    if r['matched_blocks'] and not pr['example_before']: pr['example_before']=r['matched_blocks'][0]['text']; pr['example_after']=r['matched_blocks'][0]['text']
        counts={k: sum(1 for x in aligns if x['status']==k) for k in ['matched','partial','missed','ambiguous','unsupported']}
        counts['skipped_no_backend_ir'] = sum(1 for d in documents.values() if d['status']=='skipped_no_backend_ir')
        counts['total_groundtruth_objects']=len(aligns); counts['status']=_status_from_counts(counts)
        report['backends'][be]={'summary':dict(counts),'documents':documents,'examples':[{'gt_id':x['gt_id'],'convention':x.get('convention'),'object_type':x['object_type'],'groundtruth_object':x['groundtruth_object'],'backend_blocks':x['matched_blocks'],'match_reasons':[m.get('match_reason') for m in x['matched_blocks']]} for x in aligns[:30]],'alignments':aligns,'proposed_rules':[{**v,'supporting_gt_ids':sorted(v['supporting_gt_ids']),'supporting_doc_ids':sorted(v['supporting_doc_ids']),'supporting_backend_block_ids':sorted(v['supporting_backend_block_ids']),'alignment_statuses':sorted(v['alignment_statuses'])} for v in proposed.values()], 'evaluation':counts}
        for k in ['matched','partial','missed','ambiguous','unsupported']: total[k]+=counts[k]
        total['skipped_no_backend_ir'] += counts['skipped_no_backend_ir']
    total['total_groundtruth_objects']=sum(v['evaluation']['total_groundtruth_objects'] for v in report['backends'].values())
    total['total_backend_alignments']=total['total_groundtruth_objects']; total['status']=_status_from_counts(total); report['evaluation']=dict(total); report['skipped_no_backend_ir']=total['skipped_no_backend_ir']
    write_report(out,report,emit_markdown=a.emit_markdown_report)
    if a.write_proposed_config:
        lines=['# evidence-derived backend-scoped rules']
        for be,sec in report['backends'].items():
            for r in sec['proposed_rules']:
                conv = (r.get('rule_id') or '').split('.', 1)[-1]
                safe = SAFE_PROPOSED_RULES_BY_CONVENTION.get(conv)
                if not safe:
                    continue
                lines += [
                    f"# gt_ids={r['supporting_gt_ids']}",
                    "[[rules]]",
                    f"id = \"{r['rule_id']}\"",
                    f"backend = \"{be}\"",
                    "object_type = \"*\"",
                    f"text_regex = '{safe['text_regex']}'",
                    f"normalised_type = \"{safe['normalised_type']}\"",
                ]
                if safe.get('normalised_text_rewrite'):
                    lines.append(f"normalised_text_rewrite = '{safe['normalised_text_rewrite']}'")
                lines.append("")
        (out/'ocr_conventions.proposed.toml').write_text('\n'.join(lines))
    if a.strict:
        st=report['evaluation']['status']
        if st=='fail' or (st=='warn' and not a.allow_partial): raise SystemExit(1)


if __name__=='__main__': main()
