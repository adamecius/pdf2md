from __future__ import annotations
from pathlib import Path
import pytest
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_document_builder, semantic_linker

FIX_ROOT=Path('.current/latex_docling_groundtruth/batch_001')
@pytest.fixture
def _patch(monkeypatch): monkeypatch.setattr(consensus_report,'CANONICAL_BACKENDS',('mineru','paddleocr','deepseek'))

def run_pipeline(doc_id,tmp_path):
    f=FIX_ROOT/doc_id
    generate_mock_backend_ir(f,tmp_path/'backend'/'groundtruth'/'.current'/'extraction_ir'/doc_id,backend_name='mineru')
    cfg={'consensus':{'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},'backends':{'mineru':{'enabled':True,'root':str(tmp_path/'backend'/'groundtruth')},'paddleocr':{'enabled':False,'root':'backend/paddleocr'},'deepseek':{'enabled':False,'root':'backend/deepseek'}},'pymupdf':{'enabled':True,'extract_text':True}}
    cons,code=consensus_report.build_consensus_report(f/'input'/f'{doc_id}.pdf',cfg,Path('inline')); assert code==0
    links=semantic_linker.build_semantic_links(cons,Path('inline'))
    sem=semantic_document_builder.build(cons,links,None,{'consensus':'','links':'','media':None})
    return links,sem

def test_figure_caption_reference(tmp_path,_patch):
    links,_=run_pipeline('figure_caption_reference',tmp_path); figs=[a for a in links['anchors'] if a.get('anchor_type')=='figure']; assert figs and figs[0].get('label')=='1'; assert any(r.get('resolved') for r in links['references'] if r.get('reference_type')=='figure')

def test_equation_label_reference(tmp_path,_patch):
    links,_=run_pipeline('equation_label_reference',tmp_path); eq_refs=[r for r in links['references'] if r.get('reference_type')=='equation']; assert eq_refs
    eq_anchors=[a for a in links['anchors'] if a.get('anchor_type')=='equation' and a.get('label')=='1']
    if eq_anchors: assert any(r.get('resolved') for r in eq_refs)

def test_table_caption_anchor_but_no_ref(tmp_path,_patch):
    links,_=run_pipeline('table_caption_reference',tmp_path); tabs=[a for a in links['anchors'] if a.get('anchor_type')=='table']; assert tabs and tabs[0].get('label')=='1'

def test_section_ref_detected_subsection_not(tmp_path,_patch):
    links,_=run_pipeline('section_subsection_references',tmp_path); s=[r for r in links['references'] if r.get('reference_type')=='section']; assert any(r.get('label')=='1' for r in s)

def test_two_figures(tmp_path,_patch):
    links,_=run_pipeline('two_figures_cross_references',tmp_path); assert sum(1 for a in links['anchors'] if a.get('anchor_type')=='figure')>=2

def test_footnotes_below_threshold(tmp_path,_patch):
    _,sem=run_pipeline('footnotes_basic',tmp_path); txt=' '.join(b.get('text','') for b in sem['blocks']).lower(); assert 'note' in txt

def test_multipage_consensus(tmp_path,_patch):
    _,sem=run_pipeline('multipage_references',tmp_path); assert len(sem.get('pages',[]))>=2

def test_all_features_small_anchors(tmp_path,_patch):
    links,sem=run_pipeline('all_features_small',tmp_path); kinds={b.get('type') for b in sem['blocks']}; assert 'title' in kinds and 'heading' in kinds
    ats={a.get('anchor_type') for a in links['anchors']}; assert 'figure' in ats and 'table' in ats
