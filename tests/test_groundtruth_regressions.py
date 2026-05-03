from __future__ import annotations

from pathlib import Path

import json
import pytest
from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report, semantic_document_builder, semantic_linker

FIX_ROOT = Path('.current/latex_docling_groundtruth/batch_001')

@pytest.fixture
def _patch_groundtruth_backend(monkeypatch):
    monkeypatch.setattr(consensus_report, 'CANONICAL_BACKENDS', ('groundtruth','mineru','paddleocr','deepseek'))


def run_pipeline(doc_id: str, tmp_path: Path, _patch_groundtruth_backend):
    fixture_dir = FIX_ROOT / doc_id
    out = tmp_path / 'backend' / 'groundtruth' / '.current' / 'extraction_ir' / doc_id
    generate_mock_backend_ir(fixture_dir, out, backend_name='groundtruth')
    cfg = {'consensus': {'coordinate_space': 'page_normalised_1000', 'text_similarity_threshold': 0.9, 'weak_text_similarity_threshold': 0.75, 'bbox_iou_threshold': 0.5, 'weak_bbox_iou_threshold': 0.25, 'include_evidence_only_blocks': False}, 'backends': {'groundtruth': {'enabled': True, 'root': str(tmp_path / 'backend' / 'groundtruth')}, 'mineru': {'enabled': False, 'root':'backend/mineru'}, 'paddleocr': {'enabled': False, 'root': 'backend/paddleocr'}, 'deepseek': {'enabled': False, 'root': 'backend/deepseek'}}, 'pymupdf': {'enabled': True, 'extract_text': True}}
    pdf = fixture_dir / 'input' / f'{doc_id}.pdf'
    cons, code = consensus_report.build_consensus_report(pdf, cfg, Path('inline'))
    assert code == 0
    links = semantic_linker.build_semantic_links(cons, Path('inline'))
    sem = semantic_document_builder.build(cons, links, None, {'consensus': '', 'links': '', 'media': None})
    return cons, links, sem, json.loads((fixture_dir / 'groundtruth' / 'expected_semantic_contract.json').read_text()), json.loads((fixture_dir / 'groundtruth' / 'expected_docling_contract.json').read_text())


def test_figure_caption_reference_figure_anchor(tmp_path, _patch_groundtruth_backend):
    _, links, sem, _, _ = run_pipeline('figure_caption_reference', tmp_path, _patch_groundtruth_backend)
    anchor = next(a for a in links['anchors'] if a.get('anchor_type') == 'figure' and a.get('label') == 'fig:1')
    target = next(b for b in sem['blocks'] if b.get('source_group_id') == anchor.get('target_group_id'))
    assert target.get('type') == 'figure'
    assert any(r.get('relation_type') == 'caption_of' and r.get('anchor_id') == anchor.get('anchor_id') for r in sem.get('relations', []))


def test_equation_label_reference_eq_anchor(tmp_path, _patch_groundtruth_backend):
    _, links, _, _, _ = run_pipeline('equation_label_reference', tmp_path, _patch_groundtruth_backend)
    anchor = next(a for a in links['anchors'] if a.get('anchor_type') == 'equation' and a.get('label') == 'eq:1')
    assert any(r.get('reference_text') == 'Eq. 1' and r.get('resolved') and r.get('target_anchor_id') == anchor.get('anchor_id') for r in links.get('references', []))


def test_two_figures_both_anchored(tmp_path, _patch_groundtruth_backend):
    _, links, _, _, _ = run_pipeline('two_figures_cross_references', tmp_path, _patch_groundtruth_backend)
    figs = [a for a in links['anchors'] if a.get('anchor_type') == 'figure']
    assert len({a.get('anchor_id') for a in figs}) >= 2
    for a in figs:
        assert any(r.get('resolved') and r.get('target_anchor_id') == a.get('anchor_id') for r in links['references'] if r.get('reference_type') == 'figure')


def test_multipage_cross_page_reference(tmp_path, _patch_groundtruth_backend):
    _, links, _, _, _ = run_pipeline('multipage_references', tmp_path, _patch_groundtruth_backend)
    anchors = {a['anchor_id']: a for a in links['anchors']}
    assert any(r.get('page_number') == 2 and r.get('resolved') and anchors.get(r.get('target_anchor_id'), {}).get('page_number') == 1 for r in links['references'])


def test_all_features_small_completeness(tmp_path, _patch_groundtruth_backend):
    _, _, sem, _, _ = run_pipeline('all_features_small', tmp_path, _patch_groundtruth_backend)
    kinds = {b.get('type') for b in sem['blocks']}
    assert 'title' in kinds
    assert any(b.get('type') in {'section','heading'} and ((b.get('metadata') or {}).get('heading_level') in {1, None}) for b in sem['blocks'])
    assert any((b.get('type') == 'subsection') or (b.get('type') == 'heading' and (b.get('metadata') or {}).get('heading_level') == 2) for b in sem['blocks'])
    assert 'figure' in kinds
    assert 'table' in kinds
    assert any(t in kinds for t in {'equation','formula'})
    assert any(t in kinds for t in {'list','list_item'})
    assert 'footnote' in kinds


def test_multipage_full_pipeline(tmp_path, _patch_groundtruth_backend):
    _, links, sem, _, _ = run_pipeline('multipage_all_features_references_footnotes', tmp_path, _patch_groundtruth_backend)
    assert len(sem.get('blocks', [])) > 0
    assert all(r.get('resolved') for r in links.get('references', []))
    assert sum(1 for a in links.get('anchors', []) if a.get('anchor_type') == 'footnote') >= 2
