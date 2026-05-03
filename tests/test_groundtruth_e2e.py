from __future__ import annotations
import json
from pathlib import Path
import pytest
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_document_builder, semantic_linker

FIX_ROOT = Path('.current/latex_docling_groundtruth/batch_001')
DOC_IDS = sorted([p.name for p in FIX_ROOT.iterdir() if p.is_dir()])

@pytest.fixture
def _patch_groundtruth_backend(monkeypatch):
    monkeypatch.setattr(consensus_report, 'CANONICAL_BACKENDS', ('groundtruth','mineru','paddleocr','deepseek'))


def _config(tmp_path: Path) -> dict:
    return {'consensus': {'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},
            'backends': {'groundtruth': {'enabled': True, 'root': str(tmp_path/'backend'/'groundtruth')}, 'mineru': {'enabled': False, 'root':'backend/mineru'}, 'paddleocr': {'enabled': False, 'root':'backend/paddleocr'}, 'deepseek': {'enabled': False, 'root':'backend/deepseek'}},
            'pymupdf': {'enabled': True, 'extract_text': True}}

def run_pipeline(doc_id: str, tmp_path: Path, _patch_groundtruth_backend):
    fixture_dir = FIX_ROOT / doc_id
    generate_mock_backend_ir(fixture_dir, tmp_path/'backend'/'groundtruth'/'.current'/'extraction_ir'/doc_id, backend_name='groundtruth')
    cons, code = consensus_report.build_consensus_report(fixture_dir/'input'/f'{doc_id}.pdf', _config(tmp_path), Path('inline'))
    assert code == 0
    links = semantic_linker.build_semantic_links(cons, Path('inline'))
    sem = semantic_document_builder.build(cons, links, None, {'consensus':'', 'links':'', 'media':None})
    sc = json.loads((fixture_dir/'groundtruth'/'expected_semantic_contract.json').read_text())
    dc = json.loads((fixture_dir/'groundtruth'/'expected_docling_contract.json').read_text())
    return cons, links, sem, sc, dc

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_title_recovered(doc_id, tmp_path):
    _, _, sem, sc, _ = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    assert any(b.get('type')=='title' and sc.get('expected_title','').lower() in b.get('text','').lower() for b in sem['blocks'])

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_sections_recovered(doc_id, tmp_path):
    _, _, sem, sc, _ = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    headings = ' '.join(b.get('text','').lower() for b in sem['blocks'] if b.get('type') in {'heading','section','section_header'})
    for sec in sc.get('expected_sections', []): assert sec.lower() in headings

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_labels_resolved(doc_id, tmp_path):
    _, links, _, sc, _ = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    labels = {a.get('label') for a in links.get('anchors',[]) if a.get('label')}
    for e in sc.get('expected_labels',[]): assert e in labels

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_references_resolved(doc_id, tmp_path):
    _, links, _, sc, _ = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    anchors = [a for a in links.get('anchors',[]) if a.get('label')]
    refs = links.get('references',[])
    for exp in sc.get('expected_references',[]):
        target = next(a for a in anchors if a.get('label') == exp.get('target_label'))
        assert any(r.get('resolved') and r.get('target_anchor_id') == target.get('anchor_id') for r in refs)

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_block_type_counts(doc_id, tmp_path):
    _, _, sem, sc, _ = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    types=[b.get('type') for b in sem.get('blocks',[])]
    constraints=sc.get('expected_ordered_block_constraints',[])
    canon={'section':'heading','subsection':'heading','equation':'formula','figure':'figure'}
    expected={}
    for t in constraints:
        tt=canon.get(t,t)
        expected[tt]=expected.get(tt,0)+1
    for t,c in expected.items():
        if t in {'title','heading','paragraph','caption','figure','table','formula','list_item','footnote','reference'}:
            assert types.count(t) >= c

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_markdown_snippets_present(doc_id, tmp_path):
    _, _, sem, sc, _ = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    txt=' '.join(b.get('text','') for b in sem.get('blocks',[])).lower()
    for s in sc.get('expected_markdown_snippets',[]): assert s.lower() in txt

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_required_docling_kinds(doc_id, tmp_path):
    _, _, sem, _, dc = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    kinds={b.get('type') for b in sem.get('blocks',[])}
    for k in dc.get('required_docling_kinds',[]): assert k in kinds

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_caption_relations(doc_id, tmp_path):
    _, _, sem, _, dc = run_pipeline(doc_id, tmp_path, _patch_groundtruth_backend)
    blocks = {b.get('id'): b for b in sem.get('blocks', [])}
    rels = [r for r in sem.get('relations', []) if r.get('relation_type') == 'caption_of']
    for req in dc.get('required_relations', []):
        if req.get('relation_type') == 'caption_to_figure':
            assert any(blocks.get(r.get('target_id'), {}).get('type') == 'figure' for r in rels)
        if req.get('relation_type') == 'caption_to_table':
            assert any(blocks.get(r.get('target_id'), {}).get('type') == 'table' for r in rels)

def test_semantic_link_figure_anchor(tmp_path, _patch_groundtruth_backend): _,l,_,_,_=run_pipeline('figure_caption_reference',tmp_path, _patch_groundtruth_backend); assert sum(1 for a in l['anchors'] if a.get('anchor_type')=='figure')>=1
def test_semantic_link_equation_anchor(tmp_path, _patch_groundtruth_backend): _,l,_,_,_=run_pipeline('equation_label_reference',tmp_path, _patch_groundtruth_backend); assert sum(1 for a in l['anchors'] if a.get('anchor_type')=='equation')>=1
def test_semantic_link_table_anchor(tmp_path, _patch_groundtruth_backend): _,l,_,_,_=run_pipeline('table_caption_reference',tmp_path, _patch_groundtruth_backend); assert sum(1 for a in l['anchors'] if a.get('anchor_type')=='table')>=1
def test_semantic_link_section_reference_resolved(tmp_path, _patch_groundtruth_backend): _,l,_,_,_=run_pipeline('section_subsection_references',tmp_path, _patch_groundtruth_backend); assert sum(1 for r in l['references'] if r.get('reference_type')=='section' and r.get('resolved'))>=1
def test_semantic_link_footnote_anchor(tmp_path, _patch_groundtruth_backend): _,l,_,_,_=run_pipeline('footnotes_basic',tmp_path, _patch_groundtruth_backend); assert sum(1 for a in l['anchors'] if a.get('anchor_type')=='footnote')>=1
