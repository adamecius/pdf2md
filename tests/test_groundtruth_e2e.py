from __future__ import annotations
import json
from pathlib import Path
import pytest
from pdf2md.testing import build_label_map, generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_document_builder, semantic_linker

FIX_ROOT=Path('.current/latex_docling_groundtruth/batch_001')
DOC_IDS=sorted(p.name for p in FIX_ROOT.iterdir() if p.is_dir())

@pytest.fixture
def _patch_groundtruth_backend(monkeypatch):
    monkeypatch.setattr(consensus_report,'CANONICAL_BACKENDS',('mineru','paddleocr','deepseek'))

def _config(tmp_path:Path):
    return {'consensus':{'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},'backends':{'mineru':{'enabled':True,'root':str(tmp_path/'backend'/'groundtruth')},'paddleocr':{'enabled':False,'root':'backend/paddleocr'},'deepseek':{'enabled':False,'root':'backend/deepseek'}},'pymupdf':{'enabled':True,'extract_text':True}}

def run_pipeline(doc_id,tmp_path):
    f=FIX_ROOT/doc_id
    generate_mock_backend_ir(f,tmp_path/'backend'/'groundtruth'/'.current'/'extraction_ir'/doc_id,backend_name='mineru')
    cons,code=consensus_report.build_consensus_report(f/'input'/f'{doc_id}.pdf',_config(tmp_path),Path('inline'))
    assert code==0
    links=semantic_linker.build_semantic_links(cons,Path('inline'))
    sem=semantic_document_builder.build(cons,links,None,{'consensus':'','links':'','media':None})
    return f,cons,links,sem

def load_contract(f): return json.loads((f/'groundtruth'/'expected_semantic_contract.json').read_text())
def load_doc_contract(f): return json.loads((f/'groundtruth'/'expected_docling_contract.json').read_text())

@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_title_recovered(doc_id,tmp_path,_patch_groundtruth_backend):
    f,_,_,sem=run_pipeline(doc_id,tmp_path); c=load_contract(f); text=' '.join(b.get('text','') for b in sem['blocks']); assert c['expected_title'].lower() in text.lower()
@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_sections_recovered(doc_id,tmp_path,_patch_groundtruth_backend):
    f,_,_,sem=run_pipeline(doc_id,tmp_path); c=load_contract(f); text=' '.join(b.get('text','') for b in sem['blocks']);
    for s in c.get('expected_sections',[]): assert s.lower() in text.lower()
@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_anchor_counts(doc_id,tmp_path,_patch_groundtruth_backend):
    f,_,links,_=run_pipeline(doc_id,tmp_path); lm=build_label_map(f)
    ef=sum(1 for v in lm.values() if v['kind']=='figure' and v['detectable']); et=sum(1 for v in lm.values() if v['kind']=='table' and v['detectable']); ee=sum(1 for v in lm.values() if v['kind']=='equation' and v['detectable'])
    af=sum(1 for a in links['anchors'] if a.get('anchor_type')=='figure'); at=sum(1 for a in links['anchors'] if a.get('anchor_type')=='table'); ae=sum(1 for a in links['anchors'] if a.get('anchor_type')=='equation')
    if ef>0: assert af>=ef
    if et>0: assert at>=et
    if ee>0: assert ae>=ee
@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_block_types_present(doc_id,tmp_path,_patch_groundtruth_backend):
    f,_,_,sem=run_pipeline(doc_id,tmp_path); c=load_contract(f); kinds={b.get('type') for b in sem['blocks']}; m={'section':'heading','subsection':'heading','figure':'figure','equation':'formula','table':'table','caption':'caption'}
    req=set();
    for t in c.get('expected_ordered_block_constraints',[]):
        mt=m.get(t,t)
        if mt in {'heading','paragraph','formula','table','figure','caption','title'}: req.add(mt)
    for r in req: assert r in kinds
@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_markdown_snippets(doc_id,tmp_path,_patch_groundtruth_backend):
    f,_,_,sem=run_pipeline(doc_id,tmp_path); c=load_contract(f); text=' '.join(b.get('text','') for b in sem['blocks'])
    for s in c.get('expected_markdown_snippets',[]): assert s.lower() in text.lower()
@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_required_docling_kinds(doc_id,tmp_path,_patch_groundtruth_backend):
    f,_,_,sem=run_pipeline(doc_id,tmp_path); dc=load_doc_contract(f); kinds={b.get('type') for b in sem['blocks']}
    for k in dc.get('required_docling_kinds',[]): assert k in kinds
@pytest.mark.parametrize('doc_id',DOC_IDS)
def test_caption_relations(doc_id,tmp_path,_patch_groundtruth_backend):
    f,_,_,sem=run_pipeline(doc_id,tmp_path); dc=load_doc_contract(f); blocks={b.get('id'):b for b in sem.get('blocks',[])}; rels=[r for r in sem.get('relations',[]) if r.get('relation_type')=='caption_of']
    for req in dc.get('required_relations',[]):
        if req.get('relation_type')=='caption_to_figure': assert any(blocks.get(r.get('target_id'),{}).get('type')=='figure' for r in rels)
        if req.get('relation_type')=='caption_to_table': assert any(blocks.get(r.get('target_id'),{}).get('type')=='table' for r in rels)
