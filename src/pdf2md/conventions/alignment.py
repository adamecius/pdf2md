from __future__ import annotations
import re
from .latex_groundtruth import text_key

def _txt(b): return ((b.get('content') or {}).get('text') or b.get('text') or '')

def align_groundtruth_to_backend(groundtruth: dict, backend_blocks: list[dict], *, backend: str, doc_id: str) -> list[dict]:
    records=[]
    for gt in groundtruth.get('objects', []):
        matched=[]; reasons=[]
        for b in backend_blocks:
            t=_txt(b); tk=text_key(t)
            if gt['object_type']=='equation':
                if gt.get('body_key') and ('emc2' in tk or text_key(gt['body_key']).replace('=','') in tk): matched.append(b); reasons.append('formula_body_key')
                if gt.get('numeric_label') and re.match(rf'^\s*\(?{re.escape(gt["numeric_label"])}\)?\s*$',t): matched.append(b); reasons.append('equation_number_label')
            elif gt['object_type']=='figure':
                if gt.get('caption_key') and gt['caption_key'] in tk: matched.append(b); reasons.append('caption_key')
                if gt.get('placeholder_text') and gt['placeholder_text'].lower() in t.lower(): matched.append(b); reasons.append('placeholder_text')
            elif gt['object_type']=='table':
                if gt.get('caption_key') and gt['caption_key'] in tk: matched.append(b); reasons.append('caption_key')
                if gt.get('cell_text_key') and gt['cell_text_key'][:4] and gt['cell_text_key'][:4] in tk: matched.append(b); reasons.append('cell_text_overlap')
            elif gt['object_type']=='footnote':
                if gt.get('text_key') and gt['text_key'] in tk: matched.append(b); reasons.append('footnote_text_key')
            elif gt['object_type']=='reference':
                if any(text_key(f) in tk for f in gt.get('expected_rendered_forms', [])): matched.append(b); reasons.append('rendered_text_hint')
        uniq=[]; seen=set()
        for b in matched:
            bid=b.get('block_id','')
            if bid in seen: continue
            seen.add(bid); uniq.append({'block_id':bid,'type':b.get('type',''),'text':_txt(b),'bbox':((b.get('geometry') or {}).get('bbox')),'match_reason':'/'.join(sorted(set(reasons)))})
        status='matched' if uniq else 'missed'
        if gt['object_type'] in {'figure','table'} and uniq and len(uniq)==1 and uniq[0]['type'] in {'caption','paragraph'}: status='partial'
        records.append({'gt_id':gt['gt_id'],'doc_id':doc_id,'backend':backend,'object_type':gt['object_type'],'status':status,'confidence':'high' if status=='matched' else 'low','convention':None,'groundtruth_object':gt,'matched_blocks':uniq,'unmatched_reason':None if uniq else 'no_matching_backend_block','warnings':[]})
    return records
