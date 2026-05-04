from __future__ import annotations
import json
from pathlib import Path
import pytest
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_document_builder, semantic_linker

FIX_ROOT=Path('.current/latex_docling_groundtruth/batch_001')
DOC_IDS=sorted(p.name for p in FIX_ROOT.iterdir() if p.is_dir())

@pytest.fixture
def _patch(monkeypatch):
    monkeypatch.setattr(consensus_report,'CANONICAL_BACKENDS',('mineru','paddleocr','deepseek'))

def run_pipeline(doc_id,tmp_path):
    f=FIX_ROOT/doc_id
    generate_mock_backend_ir(f,tmp_path/'backend'/'groundtruth'/'.current'/'extraction_ir'/doc_id,backend_name='mineru')
    cfg={'consensus':{'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},'backends':{'mineru':{'enabled':True,'root':str(tmp_path/'backend'/'groundtruth')},'paddleocr':{'enabled':False,'root':'backend/paddleocr'},'deepseek':{'enabled':False,'root':'backend/deepseek'}},'pymupdf':{'enabled':True,'extract_text':True}}
    cons,code=consensus_report.build_consensus_report(f/'input'/f'{doc_id}.pdf',cfg,Path('inline')); assert code==0
    links=semantic_linker.build_semantic_links(cons,Path('inline'))
    sem=semantic_document_builder.build(cons,links,None,{'consensus':'','links':'','media':None})
    c=json.loads((f/'groundtruth'/'expected_semantic_contract.json').read_text())
    return cons,links,sem,c

@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_consensus_succeeds(doc_id,tmp_path,_patch):
    cons,_,_,_=run_pipeline(doc_id,tmp_path)
    assert cons['pages'] and all(len(p.get('candidate_groups',[]))>=1 for p in cons['pages'])

@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_title_in_text(doc_id,tmp_path,_patch):
    _,_,sem,c=run_pipeline(doc_id,tmp_path)
    t=' '.join(b.get('text','') for b in sem['blocks']).lower(); assert c['expected_title'].lower() in t

@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_sections_in_text(doc_id,tmp_path,_patch):
    _,_,sem,c=run_pipeline(doc_id,tmp_path)
    t=' '.join(b.get('text','') for b in sem['blocks']).lower()
    for s in c.get('expected_sections',[]): assert s.lower() in t

@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_markdown_snippets(doc_id,tmp_path,_patch):
    _,_,sem,c=run_pipeline(doc_id,tmp_path)
    t=' '.join(b.get('text','') for b in sem['blocks']).lower()
    for s in c.get('expected_markdown_snippets',[]): assert s.lower() in t

@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_has_heading_blocks(doc_id,tmp_path,_patch):
    _,_,sem,c=run_pipeline(doc_id,tmp_path)
    if c.get('expected_sections'):
        assert any(b.get('type')=='heading' for b in sem['blocks'])

from pdf2md.testing import generate_batch_002

BATCH2_ROOT = Path('.current/latex_docling_groundtruth/batch_002')
BATCH2_DOCS = ['det_title_paragraph','det_figure_reference','det_table_reference','det_equation_reference','det_footnote','det_section_reference','det_bibliography','det_all_features']

@pytest.fixture(scope='session')
def batch2_ready():
    generate_batch_002(Path('.current/latex_docling_groundtruth'))
    missing=[d for d in BATCH2_DOCS if not (BATCH2_ROOT/d/'input'/f'{d}.pdf').exists()]
    if missing:
        pytest.skip(f"batch_002 PDFs missing: {missing}")
    return True

def run_pipeline_batch2(doc_id,tmp_path):
    f=BATCH2_ROOT/doc_id
    generate_mock_backend_ir(f,tmp_path/'backend'/'groundtruth'/'.current'/'extraction_ir'/doc_id,backend_name='mineru')
    cfg={'consensus':{'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},'backends':{'mineru':{'enabled':True,'root':str(tmp_path/'backend'/'groundtruth')},'paddleocr':{'enabled':False,'root':'backend/paddleocr'},'deepseek':{'enabled':False,'root':'backend/deepseek'}},'pymupdf':{'enabled':True,'extract_text':True}}
    cons,code=consensus_report.build_consensus_report(f/'input'/f'{doc_id}.pdf',cfg,Path('inline')); assert code==0
    links=semantic_linker.build_semantic_links(cons,Path('inline'))
    sem=semantic_document_builder.build(cons,links,None,{'consensus':'','links':'','media':None})
    det=json.loads((f/'groundtruth'/'expected_detectable_contract.json').read_text())
    return links,sem,det

@pytest.mark.parametrize('doc_id',BATCH2_DOCS)
def test_batch2_expected_anchors(doc_id,tmp_path,_patch,batch2_ready):
    links,_,det=run_pipeline_batch2(doc_id,tmp_path)
    for ea in det.get('expected_anchors',[]):
        assert any(a.get('anchor_type')==ea['anchor_type'] and a.get('label')==ea['numeric_label'] for a in links.get('anchors',[]))

@pytest.mark.parametrize('doc_id',BATCH2_DOCS)
def test_batch2_expected_references(doc_id,tmp_path,_patch,batch2_ready):
    links,_,det=run_pipeline_batch2(doc_id,tmp_path)
    for er in det.get('expected_resolved_references',[]):
        m=[r for r in links.get('references',[]) if r.get('reference_type')==er['reference_type'] and r.get('label')==er['label']]
        assert m
        if er.get('should_resolve'): assert any(r.get('resolved') for r in m)

@pytest.mark.parametrize('doc_id',BATCH2_DOCS)
def test_batch2_expected_block_types(doc_id,tmp_path,_patch,batch2_ready):
    _,sem,det=run_pipeline_batch2(doc_id,tmp_path)
    kinds={b.get('type') for b in sem.get('blocks',[])}
    for k in det.get('expected_block_types',[]): assert k in kinds

@pytest.mark.parametrize('doc_id',BATCH2_DOCS)
def test_batch2_footnotes(doc_id,tmp_path,_patch,batch2_ready):
    links,_,det=run_pipeline_batch2(doc_id,tmp_path)
    expected=det.get('expected_footnote_count',0)
    actual=sum(1 for a in links.get('anchors',[]) if a.get('anchor_type')=='footnote')
    if expected>0: assert actual>=expected

@pytest.mark.parametrize('doc_id',BATCH2_DOCS)
def test_batch2_bibliography_refs(doc_id,tmp_path,_patch,batch2_ready):
    links,_,det=run_pipeline_batch2(doc_id,tmp_path)
    bib={r.get('label') for r in links.get('references',[]) if r.get('reference_type')=='bibliography'}
    for x in det.get('expected_bibliography_refs',[]): assert x in bib
