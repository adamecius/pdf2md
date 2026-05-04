from __future__ import annotations
import argparse, json, re
from collections import defaultdict
from pathlib import Path
from .latex_groundtruth import extract_groundtruth_objects
from .reporting import write_report


def _read_tex(root: Path) -> dict[str, dict]:
    return {tex.parent.name: extract_groundtruth_objects(tex.read_text()) for tex in root.rglob('*.tex')}


def _has_geometry(b: dict) -> bool:
    return bool((b.get('geometry') or {}).get('bbox'))


def _add_rule(proposed, rule_id, doc_id, block_id, before, after, reason):
    p = proposed[rule_id]
    p['support'] += 1
    p['doc_ids'].add(doc_id)
    p['block_ids'].add(block_id)
    if not p['example_before']:
        p['example_before'] = before
        p['example_after'] = after
    p['reason'] = reason


def _infer(blocks: list[dict], backend: str, doc_id: str):
    s = defaultdict(int); ex=[]
    proposed = defaultdict(lambda: {'support': 0, 'doc_ids': set(), 'block_ids': set(), 'example_before': '', 'example_after': '', 'reason': ''})
    for i,b in enumerate(blocks):
        t=(b.get('type') or '').lower(); txt=((b.get('content') or {}).get('text') or b.get('text') or ''); bid=b.get('block_id',f'{doc_id}:{i}')
        y=(((b.get('geometry') or {}).get('bbox') or [0,0,0,0])[1])
        s['geometry_available' if _has_geometry(b) else 'geometry_missing'] += 1
        if re.match(r'^\s*(Figure|Fig\.|Table)\s+\d+', txt):
            k='caption_as_paragraph' if t=='paragraph' else ('caption_as_unknown' if t=='unknown' else 'caption_as_caption'); s[k]+=1
            ex.append({'doc_id':doc_id,'convention':k,'object_type':'caption','backend_blocks':[{'block_id':bid,'type':t,'text':txt}],'groundtruth_hint':'caption'})
            _add_rule(proposed,'caption.figure_or_table_prefix',doc_id,bid,txt,txt,'caption prefix detected')
        if re.match(r'^\s*FIG\s*$', txt):
            near = any(re.match(r'^\s*(Figure|Fig\.)\s+\d+', ((blocks[j].get('content') or {}).get('text') or blocks[j].get('text') or '')) for j in range(max(0,i-3),min(len(blocks),i+4)) if j!=i)
            if near:
                s['figure_as_text_fig'] += 1; _add_rule(proposed,'figure.placeholder_fig_near_caption',doc_id,bid,txt,'picture','FIG near figure caption')
        if backend=='paddleocr' and re.match(r'^\s*\(\s*\d+(?:\.\d+)*\s*\)\s*$', txt):
            s['formula_number_split_block'] += 1; _add_rule(proposed,'equation.number_split_block',doc_id,bid,txt,txt,'number-only equation block')
        # footnotes
        if re.match(r'^\s*\d+[A-Za-z]', txt): s['footnote_no_space_after_marker'] += 1; _add_rule(proposed,'footnote.leading_digit_without_space',doc_id,bid,txt,re.sub(r'^(\s*\d+)([A-Za-z])',r'\1 \2',txt),'footnote no-space marker')
        if re.match(r'^\s*[¹²³⁴⁵⁶⁷⁸⁹]', txt): s['footnote_marker_superscript'] += 1; _add_rule(proposed,'footnote.superscript_marker',doc_id,bid,txt,'1 '+re.sub(r'^\s*[¹²³⁴⁵⁶⁷⁸⁹]\s*','',txt),'superscript marker')
        if re.match(r'^\s*\^\d+\s+[A-Za-z]', txt): s['footnote_marker_caret'] += 1; _add_rule(proposed,'footnote.caret_marker',doc_id,bid,txt,re.sub(r'^\s*\^(\d+)\s*',r'\1 ',txt),'caret marker')
        if re.match(r'^\s*\(\d+\)\s+[A-Za-z]', txt): s['footnote_marker_parenthesised'] += 1; _add_rule(proposed,'footnote.parenthesised_marker',doc_id,bid,txt,re.sub(r'^\s*\((\d+)\)\s*',r'\1 ',txt),'parenthesised marker')
        if re.match(r'^\s*\d+\s+[A-Za-z]', txt) and y>760: s['footnote_body_bottom_page'] += 1; _add_rule(proposed,'footnote.bottom_page_body',doc_id,bid,txt,txt,'bottom-page footnote body')
        if t=='unknown' and re.match(r'^\s*\d+[A-Za-z]', txt): s['footnote_body_as_unknown'] += 1
        # table conventions
        if re.match(r'^\s*Table\s+\d+[:\s]', txt):
            toks=txt.split()
            if len(toks)>6: s['table_flattened_paragraph'] += 1; _add_rule(proposed,'table.flattened_paragraph',doc_id,bid,txt,txt,'table flattened into paragraph')
            if re.search(r':', txt) and re.search(r'\b[A-Za-z]\b', txt) and re.search(r'\b\d+\b', txt): s['table_caption_merged_with_cells'] += 1
            if not _has_geometry(b): s['table_geometryless'] += 1
        if t=='paragraph' and re.match(r'^\s*[A-Za-z](\s+[A-Za-z0-9]){1,4}\s*$', txt):
            s['table_cells_as_paragraphs'] += 1
        if t=='paragraph' and re.match(r'^\s*\d+(\s+\d+){1,4}\s*$', txt):
            s['table_rows_as_paragraphs'] += 1
    return dict(s), ex[:30], proposed


def _write_proposed_toml(path: Path, rules: dict):
    rule_defs = {
        'caption.figure_or_table_prefix': {'backend':'*','object_type':'*','text_regex':r'^\s*(Figure|Fig\.|Table)\s+\d+(\.\d+)?','normalised_type':'caption'},
        'figure.placeholder_fig_near_caption': {'backend':'*','object_type':'*','text_regex':r'^\s*FIG\s*$','requires_near_caption_regex':r'^\s*(Figure|Fig\.)\s+\d+','normalised_type':'picture'},
        'equation.number_split_block': {'backend':'paddleocr','object_type':'*','text_regex':r'^\s*\(\s*\d+(\.\d+)*\s*\)\s*$','normalised_type':'equation_number'},
        'footnote.leading_digit_without_space': {'backend':'*','object_type':'*','text_regex':r'^\s*(\d+)([A-Za-z].*)','normalised_text_rewrite':r'\1 \2','normalised_type':'footnote'},
        'footnote.superscript_marker': {'backend':'*','object_type':'*','text_regex':r'^\s*([¹²³⁴⁵⁶⁷⁸⁹])\s*([A-Za-z].*)','normalised_text_rewrite':r'1 \2','normalised_type':'footnote'},
        'footnote.caret_marker': {'backend':'*','object_type':'*','text_regex':r'^\s*\^(\d+)\s*([A-Za-z].*)','normalised_text_rewrite':r'\1 \2','normalised_type':'footnote'},
        'footnote.parenthesised_marker': {'backend':'*','object_type':'*','text_regex':r'^\s*\((\d+)\)\s*([A-Za-z].*)','normalised_text_rewrite':r'\1 \2','normalised_type':'footnote'},
        'footnote.bottom_page_body': {'backend':'*','object_type':'*','text_regex':r'^\s*\d+\s+[A-Za-z].*','normalised_type':'footnote'},
        'table.flattened_paragraph': {'backend':'*','object_type':'*','text_regex':r'^\s*Table\s+\d+[:\s].+','normalised_type':'table'},
    }
    lines=['# evidence-derived rules']
    for rid,item in rules.items():
        d=rule_defs.get(rid)
        if not d: continue
        lines.append(f"# support_count={item['support']} docs={sorted(item['doc_ids'])} block_ids={sorted(item['block_ids'])}")
        lines.append('[[rules]]'); lines.append(f'id = "{rid}"')
        for k,v in d.items(): lines.append(f'{k} = {json.dumps(v)}')
        lines.append('')
    path.write_text('\n'.join(lines))


def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--batch',required=True); p.add_argument('--output',required=True)
    p.add_argument('--backend',action='append'); p.add_argument('--write-proposed-config',action='store_true'); p.add_argument('--emit-markdown-report',action='store_true'); p.add_argument('--min-support',type=int,default=1)
    a=p.parse_args(); root=Path(a.root)/a.batch
    report={'batch':a.batch,'fixture_provenance':sorted(_read_tex(root).keys()),'backends':{}}
    backends=a.backend or ['mineru','paddleocr','deepseek','pymupdf']; merged={}
    for be in backends:
        summary=defaultdict(int); examples=[]; prules={}
        for f in (root/'backend_ir'/be).rglob('*.json'):
            d=json.loads(f.read_text()); s,ex,pro=_infer(d.get('blocks',[]),be,f.parent.name)
            for k,v in s.items(): summary[k]+=v
            examples.extend(ex)
            for rid,pinfo in pro.items():
                e=prules.setdefault(rid,{'support':0,'doc_ids':set(),'block_ids':set(),'reason':pinfo['reason'],'example_before':pinfo['example_before'],'example_after':pinfo['example_after']})
                e['support']+=pinfo['support']; e['doc_ids'].update(pinfo['doc_ids']); e['block_ids'].update(pinfo['block_ids'])
        report['backends'][be]={'summary':dict(summary),'examples':examples[:30],'proposed_rules':[{'rule_id':rid,'support':info['support'],'supporting_doc_ids':sorted(info['doc_ids']),'supporting_backend_block_ids':sorted(info['block_ids']),'groundtruth_source':'latex_fixture+backend_ir','example_before':info['example_before'],'example_after':info['example_after'],'reason':info['reason']} for rid,info in prules.items()]}
        merged.update(prules)
    out=Path(a.output); write_report(out,report,emit_markdown=a.emit_markdown_report)
    if a.write_proposed_config: _write_proposed_toml(out/'ocr_conventions.proposed.toml',{k:v for k,v in merged.items() if v['support']>=a.min_support})


if __name__=='__main__': main()
