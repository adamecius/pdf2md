from __future__ import annotations
import json
from pathlib import Path
import pytest
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report

FIX_ROOT = Path('.current/latex_docling_groundtruth/batch_001')
FIXTURES = ['simple_title_paragraph','figure_caption_reference','equation_label_reference']

@pytest.fixture(params=FIXTURES)
def mock_ir(request, tmp_path):
    fdir = FIX_ROOT / request.param
    out = tmp_path / 'backend' / 'mineru' / '.current' / 'extraction_ir' / request.param
    pages_dir, manifest = generate_mock_backend_ir(fdir, out, backend_name='mineru')
    return request.param, fdir, pages_dir, manifest

def test_page_json_has_required_top_keys(mock_ir):
    _,_,pages_dir,_ = mock_ir
    page = json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())
    assert 'blocks' in page
    assert {'schema_name','page_index','page_number'}.issubset(page.keys())

def test_block_has_required_fields(mock_ir):
    _,_,pages_dir,_=mock_ir
    page=json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())
    b=page['blocks'][0]
    for k in ['block_id','type','subtype','semantic_role','docling','geometry','content','comparison','compile_role','confidence','source_refs','flags','structure']:
        assert k in b

def test_bbox_in_normalised_1000_space(mock_ir):
    _,_,pages_dir,_=mock_ir
    for pf in pages_dir.glob('page_*.json'):
        page=json.loads(pf.read_text())
        for b in page['blocks']:
            x0,y0,x1,y1=b['geometry']['bbox']
            assert 0<=x0<=1000 and 0<=y0<=1000 and 0<=x1<=1000 and 0<=y1<=1000

def test_compile_role_is_candidate(mock_ir):
    _,_,pages_dir,_=mock_ir
    page=json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())
    assert all(b['compile_role']=='candidate' for b in page['blocks'])

def test_text_hash_is_sha256(mock_ir):
    _,_,pages_dir,_=mock_ir
    page=json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())
    assert all(b['comparison']['text_hash'].startswith('sha256:') for b in page['blocks'])

def test_manifest_has_required_fields(mock_ir):
    _,_,_,manifest=mock_ir
    m=json.loads(manifest.read_text())
    assert {'schema_name','page_refs','backend'}.issubset(m.keys())

def test_consensus_report_can_consume_mock_ir(mock_ir, tmp_path):
    doc_id,fdir,_,_=mock_ir
    cfg={"consensus":{"coordinate_space":"page_normalised_1000","text_similarity_threshold":0.9,"weak_text_similarity_threshold":0.75,"bbox_iou_threshold":0.5,"weak_bbox_iou_threshold":0.25,"include_evidence_only_blocks":False},"backends":{"mineru":{"enabled":True,"root":str(tmp_path/'backend'/'mineru')},"paddleocr":{"enabled":False,"root":"backend/paddleocr"},"deepseek":{"enabled":False,"root":"backend/deepseek"}},"pymupdf":{"enabled":True,"extract_text":True}}
    report,code=consensus_report.build_consensus_report(fdir/'input'/f'{doc_id}.pdf',cfg,Path('inline'))
    assert code==0
    for p in report['pages']:
        for g in p['candidate_groups']:
            assert g['kind']!='unknown'
