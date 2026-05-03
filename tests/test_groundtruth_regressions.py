from __future__ import annotations
from pathlib import Path
import pytest
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_document_builder, semantic_linker

FIX_ROOT=Path('.current/latex_docling_groundtruth/batch_001')
@pytest.fixture
def _patch_groundtruth_backend(monkeypatch):
    monkeypatch.setattr(consensus_report,'CANONICAL_BACKENDS',('mineru','paddleocr','deepseek'))

def run_pipeline(doc_id,tmp_path):
    f=FIX_ROOT/doc_id
    generate_mock_backend_ir(f,tmp_path/'backend'/'groundtruth'/'.current'/'extraction_ir'/doc_id,backend_name='mineru')
    cfg={'consensus':{'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},'backends':{'mineru':{'enabled':True,'root':str(tmp_path/'backend'/'groundtruth')},'paddleocr':{'enabled':False,'root':'backend/paddleocr'},'deepseek':{'enabled':False,'root':'backend/deepseek'}},'pymupdf':{'enabled':True,'extract_text':True}}
    cons,code=consensus_report.build_consensus_report(f/'input'/f'{doc_id}.pdf',cfg,Path('inline')); assert code==0
    links=semantic_linker.build_semantic_links(cons,Path('inline'))
    sem=semantic_document_builder.build(cons,links,None,{'consensus':'','links':'','media':None})
    return links,sem

def test_figure_caption_reference_figure_anchor(tmp_path,_patch_groundtruth_backend):
    links,_=run_pipeline('figure_caption_reference',tmp_path); fa=[a for a in links['anchors'] if a.get('anchor_type')=='figure']; assert len(fa)>=1; assert fa[0].get('label')=='1'; assert fa[0].get('target_group_id')

def test_equation_label_reference_eq_anchor(tmp_path,_patch_groundtruth_backend):
    links,_=run_pipeline('equation_label_reference',tmp_path); ea=[a for a in links['anchors'] if a.get('anchor_type')=='equation']; assert len(ea)>=1; assert any(a.get('label')=='1' for a in ea); assert any(r.get('resolved') for r in links['references'] if r.get('reference_type')=='equation')

def test_table_caption_reference_table_anchor(tmp_path,_patch_groundtruth_backend):
    links,_=run_pipeline('table_caption_reference',tmp_path); ta=[a for a in links['anchors'] if a.get('anchor_type')=='table']; assert len(ta)>=1; assert ta[0].get('label')=='1'

def test_two_figures_both_anchored(tmp_path,_patch_groundtruth_backend):
    links,_=run_pipeline('two_figures_cross_references',tmp_path); labs={a.get('label') for a in links['anchors'] if a.get('anchor_type')=='figure'}; assert '1' in labs and '2' in labs

def test_section_reference_detected(tmp_path,_patch_groundtruth_backend):
    links,_=run_pipeline('section_subsection_references',tmp_path); s=[r for r in links['references'] if r.get('reference_type')=='section']; assert any(r.get('label')=='1' for r in s)

def test_multipage_cross_page_reference(tmp_path,_patch_groundtruth_backend):
    _,sem=run_pipeline('multipage_references',tmp_path); assert len(sem.get('pages',[]))>=2

def test_footnotes_basic_pipeline_runs(tmp_path,_patch_groundtruth_backend):
    _,sem=run_pipeline('footnotes_basic',tmp_path); text=' '.join(b.get('text','') for b in sem['blocks']); assert 'note' in text.lower() or 'footnote' in text.lower()

def test_all_features_small_completeness(tmp_path,_patch_groundtruth_backend):
    links,sem=run_pipeline('all_features_small',tmp_path); kinds={b.get('type') for b in sem['blocks']}; assert 'title' in kinds; assert 'heading' in kinds; assert 'formula' in kinds or 'table' in kinds; at={a.get('anchor_type') for a in links['anchors']}; assert 'figure' in at and 'table' in at

def test_multipage_full_pipeline(tmp_path,_patch_groundtruth_backend):
    links,sem=run_pipeline('multipage_all_features_references_footnotes',tmp_path); assert len(sem.get('pages',[]))>=2; assert len(sem['blocks'])>5; at={a.get('anchor_type') for a in links['anchors']}; assert 'figure' in at and 'table' in at
