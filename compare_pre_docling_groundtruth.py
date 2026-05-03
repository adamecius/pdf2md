#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path


def n(s):
    return ' '.join((s or '').split()).lower()


def canon_type(t: str) -> str:
    m = {
        'formula': 'equation',
        'picture': 'figure',
        'section_header': 'section_like',
        'heading': 'section_like',
        'section': 'section_like',
        'subsection': 'section_like',
        'text': 'paragraph',
    }
    return m.get((t or '').strip(), (t or '').strip())


def get_blocks(doc: dict, is_candidate: bool) -> list[dict]:
    if 'body' in doc and isinstance(doc['body'], list):
        return doc['body']
    if is_candidate and 'blocks' in doc and isinstance(doc['blocks'], list):
        return doc['blocks']
    raise ValueError('candidate must include `body` or `blocks`' if is_candidate else 'groundtruth missing `body`')


def normalize_relations(rels: list[dict]) -> list[dict]:
    out = []
    for r in rels or []:
        rt = r.get('type') or r.get('relation_type') or ''
        if rt == 'refers_to':
            rt = 'reference_to'
        out.append({
            'type': rt,
            'target_label': r.get('target_label') or r.get('label'),
            'caption_text': n(r.get('caption_text') or ''),
            'footnote_text': n(r.get('footnote_text') or ''),
        })
    return out


def normalize(doc: dict, is_candidate: bool) -> dict:
    blocks = get_blocks(doc, is_candidate=is_candidate)
    labels = dict(doc.get('labels') or {})
    out_blocks = []
    for b in blocks:
        t = canon_type(b.get('type', ''))
        bb = dict(b)
        bb['_canon_type'] = t
        bb['_text_n'] = n(b.get('text', ''))
        out_blocks.append(bb)
        # backend may store block-level label
        lbl = b.get('label')
        if isinstance(lbl, str) and lbl.strip() and b.get('id'):
            labels.setdefault(lbl.strip(), b['id'])

    type_counts = Counter(b['_canon_type'] for b in out_blocks)
    table_cells = [n(c.get('text')) for b in out_blocks if b['_canon_type'] == 'table' for r in b.get('table_rows', []) for c in r.get('cells', [])]
    equations = [b['_text_n'] for b in out_blocks if b['_canon_type'] == 'equation']
    footnotes = [b['_text_n'] for b in out_blocks if b['_canon_type'] == 'footnote']
    captions = [b['_text_n'] for b in out_blocks if b['_canon_type'] == 'caption']
    references = Counter((r.get('target_label') or '').strip() for r in (doc.get('references') or []) if (r.get('target_label') or '').strip())
    lists = {
        'list_count': sum(1 for b in out_blocks if b['_canon_type'] == 'list'),
        'list_item_count': sum(1 for b in out_blocks if b['_canon_type'] == 'list_item'),
    }
    relations = normalize_relations(doc.get('relations') or [])

    return {
        'title': n(doc.get('title') or doc.get('expected_title') or ''),
        'blocks': out_blocks,
        'labels': labels,
        'type_counts': type_counts,
        'table_cells': table_cells,
        'equations': equations,
        'footnotes': footnotes,
        'captions': captions,
        'references': references,
        'lists': lists,
        'relations': relations,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--groundtruth', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--contract', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    gt_raw = json.loads(Path(a.groundtruth).read_text())
    cd_raw = json.loads(Path(a.candidate).read_text())
    ct = json.loads(Path(a.contract).read_text())

    errs, warns = [], []
    try:
        gt = normalize(gt_raw, is_candidate=False)
        cd = normalize(cd_raw, is_candidate=True)
    except ValueError as e:
        errs.append(str(e))
        out = {'ok': False, 'errors': errs, 'warnings': warns}
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(json.dumps(out, indent=2))
        raise SystemExit(1)

    if gt['title'] and gt['title'] != cd['title']:
        errs.append('title_mismatch')

    for t, c in gt['type_counts'].items():
        if cd['type_counts'].get(t, 0) < c:
            errs.append(f'type_count_lt:{t}:{cd["type_counts"].get(t,0)}<{c}')

    expected = [canon_type(x) for x in ct.get('expected_ordered_block_constraints', []) if canon_type(x) == 'section_like']
    cand = [b['_canon_type'] for b in cd['blocks'] if b['_canon_type'] == 'section_like']
    if cand[:len(expected)] != expected:
        errs.append('section_order_mismatch')

    # label presence and prefix->type
    cbyid = {b.get('id'): b for b in cd['blocks'] if b.get('id')}
    for lbl in (gt_raw.get('labels') or {}).keys():
        cbid = cd['labels'].get(lbl)
        if not cbid:
            errs.append(f'missing_label:{lbl}')
            continue
        t = canon_type(cbyid.get(cbid, {}).get('type', ''))
        want = 'section_like' if (lbl.startswith('sec:') or lbl.startswith('sub:')) else 'figure' if lbl.startswith('fig:') else 'table' if lbl.startswith('tab:') else 'equation' if lbl.startswith('eq:') else None
        if want and t != want:
            errs.append(f'label_type_mismatch:{lbl}:{t}!={want}')

    for k, v in gt['references'].items():
        if cd['references'].get(k, 0) < v:
            errs.append(f'missing_repeated_reference:{k}:{cd["references"].get(k,0)}<{v}')

    for cell in gt['table_cells']:
        if cell and cell not in cd['table_cells']:
            errs.append(f'missing_table_cell:{cell[:32]}')

    for e in gt['equations']:
        if e and e not in cd['equations']:
            errs.append(f'missing_equation:{e[:24]}')

    for f in gt['footnotes']:
        if f and f not in cd['footnotes']:
            errs.append(f'missing_footnote:{f[:24]}')

    for c in gt['captions']:
        if c and c not in cd['captions']:
            errs.append(f'missing_caption_text:{c[:24]}')

    if cd['lists']['list_count'] < gt['lists']['list_count']:
        errs.append('flattened_nested_lists')

    out = {'ok': not errs, 'errors': errs, 'warnings': warns}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(out, indent=2))
    if a.verbose:
        print(json.dumps(out, indent=2))
    raise SystemExit(0 if out['ok'] else 1)


if __name__ == '__main__':
    main()
