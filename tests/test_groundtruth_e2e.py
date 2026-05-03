from __future__ import annotations
import json
from pathlib import Path
import pytest
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_linker, semantic_document_builder

FIX_ROOT = Path('.current/latex_docling_groundtruth/batch_001')
DOC_IDS = sorted([p.name for p in FIX_ROOT.iterdir() if p.is_dir()])

def run_pipeline(doc_id: str, tmp_path: Path):
    fdir = FIX_ROOT / doc_id
    out = tmp_path / 'backend' / 'mineru' / '.current' / 'extraction_ir' / doc_id
    generate_mock_backend_ir(fdir, out, backend_name='mineru')
    cfg = {
        'consensus': {'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},
        'backends': {'mineru': {'enabled': True, 'root': str(tmp_path / 'backend' / 'mineru')}, 'paddleocr': {'enabled': False, 'root': 'backend/paddleocr'}, 'deepseek': {'enabled': False, 'root': 'backend/deepseek'}},
        'pymupdf': {'enabled': True, 'extract_text': True},
    }
    pdf = fdir / 'input' / f'{doc_id}.pdf'
    consensus, code = consensus_report.build_consensus_report(pdf, cfg, Path('inline'))
    assert code == 0
    links = semantic_linker.build_semantic_links(consensus, Path('inline'))
    sem = semantic_document_builder.build(consensus, links, None, {'consensus':'', 'links':'', 'media':None})
    return fdir, consensus, links, sem

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_consensus(doc_id, tmp_path):
    _,consensus,_,_ = run_pipeline(doc_id, tmp_path)
    assert consensus['pages']
    assert all(len(p.get('candidate_groups',[]))>=1 for p in consensus['pages'])

@pytest.mark.parametrize('doc_id', DOC_IDS)
def test_contracts(doc_id, tmp_path):
    fdir,_,links,sem = run_pipeline(doc_id, tmp_path)
    c = json.loads((fdir/'groundtruth'/'expected_semantic_contract.json').read_text())
    text = ' '.join(b.get('text','') for b in sem['blocks'])
    assert c['expected_title'].lower() in text.lower()
    for s in c.get('expected_sections',[]): assert s.lower() in text.lower()
    labels = {a.get('label') for a in links.get('anchors',[]) if a.get('label')}
    for lbl in c.get('expected_labels',[]): assert lbl in labels
    kinds = [b.get('type') for b in sem.get('blocks',[])]
    required = set(x for x in c.get('expected_ordered_block_constraints',[]) if x in {'title','paragraph','section','subsection','figure','table','equation','list_item','footnote','caption'})
    m={'section':'heading','subsection':'heading','figure':'figure','equation':'formula'}
    for r in required: assert m.get(r,r) in kinds
    for s in c.get('expected_markdown_snippets',[]): assert s.lower() in text.lower()
