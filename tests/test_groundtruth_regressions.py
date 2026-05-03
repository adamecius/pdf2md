from __future__ import annotations
from pathlib import Path
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_linker, semantic_document_builder

FIX_ROOT = Path('.current/latex_docling_groundtruth/batch_001')

def run_pipeline(doc_id: str, tmp_path: Path):
    fdir = FIX_ROOT / doc_id
    out = tmp_path / 'backend' / 'mineru' / '.current' / 'extraction_ir' / doc_id
    generate_mock_backend_ir(fdir, out, backend_name='mineru')
    cfg = {'consensus': {'coordinate_space':'page_normalised_1000','text_similarity_threshold':0.9,'weak_text_similarity_threshold':0.75,'bbox_iou_threshold':0.5,'weak_bbox_iou_threshold':0.25,'include_evidence_only_blocks':False},'backends': {'mineru': {'enabled': True, 'root': str(tmp_path / 'backend' / 'mineru')}, 'paddleocr': {'enabled': False, 'root': 'backend/paddleocr'}, 'deepseek': {'enabled': False, 'root': 'backend/deepseek'}},'pymupdf': {'enabled': True, 'extract_text': True}}
    consensus, code = consensus_report.build_consensus_report(fdir/'input'/f'{doc_id}.pdf', cfg, Path('inline'))
    assert code == 0
    links = semantic_linker.build_semantic_links(consensus, Path('inline'))
    sem = semantic_document_builder.build(consensus, links, None, {'consensus':'', 'links':'', 'media':None})
    return links, sem

def test_figure_caption_reference_figure_anchor(tmp_path):
    links,_ = run_pipeline('figure_caption_reference', tmp_path)
    assert any(a.get('anchor_type')=='figure' and a.get('label') for a in links['anchors'])

def test_equation_label_reference_eq_anchor(tmp_path):
    links,_ = run_pipeline('equation_label_reference', tmp_path)
    assert any(a.get('anchor_type')=='equation' and a.get('label') for a in links['anchors'])

def test_two_figures_both_anchored(tmp_path):
    links,_ = run_pipeline('two_figures_cross_references', tmp_path)
    assert len([a for a in links['anchors'] if a.get('anchor_type')=='figure']) >= 2

def test_multipage_cross_page_reference(tmp_path):
    links,_ = run_pipeline('multipage_references', tmp_path)
    assert any(r.get('resolved') for r in links['references'])

def test_all_features_small_completeness(tmp_path):
    _,sem = run_pipeline('all_features_small', tmp_path)
    kinds={b.get('type') for b in sem['blocks']}
    for k in ['title','heading','figure','table','formula','list_item','footnote']:
        assert k in kinds

def test_multipage_full_pipeline(tmp_path):
    links,sem = run_pipeline('multipage_all_features_references_footnotes', tmp_path)
    assert sum(1 for a in links['anchors'] if a.get('anchor_type')=='footnote') >= 1
    assert len(sem['blocks']) > 5
