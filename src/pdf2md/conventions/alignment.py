from __future__ import annotations
import re


def text_key(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def _block_text(b: dict) -> str:
    return ((b.get('content') or {}).get('text') or b.get('text') or '')


def align_groundtruth_to_backend(groundtruth: dict, backend_blocks: list[dict], *, backend: str, doc_id: str) -> list[dict]:
    out = []
    for eq in groundtruth.get('equations', []):
        m=[]
        for b in backend_blocks:
            t=_block_text(b)
            if eq.get('body_key') and (text_key(eq['body_key']).replace('=','') in text_key(t) or 'e=mc2' in eq.get('body_key','') and 'emc2' in text_key(t)):
                m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'formula_body_key'})
            if eq.get('numeric_label') and re.match(rf'^\s*\(?{re.escape(eq["numeric_label"])}\)?\s*$', t):
                m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'equation_number_label'})
        if m:
            out.append({'doc_id':doc_id,'backend':backend,'object_type':'equation','groundtruth':{'label':eq.get('label'),'numeric_label':eq.get('numeric_label'),'body_key':eq.get('body_key')},'matched_blocks':m,'alignment_confidence':'high' if len(m)>1 else 'medium'})
    for fg in groundtruth.get('figures', []):
        m=[]; ckey=fg.get('caption_key','')
        for b in backend_blocks:
            t=_block_text(b); tk=text_key(t)
            if ckey and ckey in tk: m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'caption_key'})
            if fg.get('placeholder_text') and fg['placeholder_text'].lower() in t.lower(): m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'placeholder_text'})
        if m: out.append({'doc_id':doc_id,'backend':backend,'object_type':'figure','groundtruth':{'label':fg.get('label'),'caption':fg.get('caption')},'matched_blocks':m,'alignment_confidence':'medium'})
    for tb in groundtruth.get('tables', []):
        m=[]; ckey=tb.get('caption_key',''); ctext=tb.get('cell_text_key','')
        for b in backend_blocks:
            t=_block_text(b); tk=text_key(t)
            if ckey and ckey in tk: m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'caption_key'})
            if ctext and any(x in tk for x in [ctext[:4], ctext[-4:]]): m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'cell_text_overlap'})
        if m: out.append({'doc_id':doc_id,'backend':backend,'object_type':'table','groundtruth':{'label':tb.get('label'),'caption':tb.get('caption'),'cell_text_key':tb.get('cell_text_key')},'matched_blocks':m,'alignment_confidence':'medium'})
    for ft in groundtruth.get('footnotes', []):
        if ft.get('marker_only'): continue
        m=[]; fkey=ft.get('text_key','')
        for b in backend_blocks:
            t=_block_text(b)
            if fkey and fkey in text_key(t): m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'footnote_text_key'})
        if m: out.append({'doc_id':doc_id,'backend':backend,'object_type':'footnote','groundtruth':{'text':ft.get('text')},'matched_blocks':m,'alignment_confidence':'medium'})
    for rf in groundtruth.get('references', []):
        m=[]; hint=rf.get('rendered_text_hint','')
        for b in backend_blocks:
            t=_block_text(b)
            if hint and text_key(hint) in text_key(t): m.append({'block_id':b.get('block_id',''),'type':b.get('type',''),'text':t,'match_reason':'rendered_text_hint'})
        if m: out.append({'doc_id':doc_id,'backend':backend,'object_type':'reference','groundtruth':{'label':rf.get('label'),'reference_kind':rf.get('reference_kind')},'matched_blocks':m,'alignment_confidence':'low'})
    return out
