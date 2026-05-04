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
