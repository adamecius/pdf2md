from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.testing import generate_mock_backend_ir
from pdf2md.utils import consensus_report

FIX_ROOT = Path('.current/latex_docling_groundtruth/batch_001')
FIXTURES = ['simple_title_paragraph', 'figure_caption_reference', 'equation_label_reference']
REAL_DOC = 'Ashcroft_Mermin_sub'


def _real_key_sets() -> tuple[set[str], set[str]]:
    page_keys, block_keys = set(), set()
    for b in ('paddleocr', 'deepseek', 'mineru'):
        p = Path(f'backend/{b}/.current/extraction_ir/{REAL_DOC}/pages/page_0000.json')
        obj = json.loads(p.read_text())
        page_keys |= set(obj.keys())
        block_keys |= set((obj.get('blocks') or [{}])[0].keys())
    return page_keys, block_keys


@pytest.fixture(params=FIXTURES)
def mock_ir(request, tmp_path):
    doc_id = request.param
    fdir = FIX_ROOT / doc_id
    out = tmp_path / 'backend' / 'groundtruth' / '.current' / 'extraction_ir' / doc_id
    pages_dir, manifest = generate_mock_backend_ir(fdir, out, backend_name='groundtruth')
    return doc_id, fdir, pages_dir, manifest, tmp_path


def test_page_json_has_required_top_keys(mock_ir):
    _, _, pages_dir, _, _ = mock_ir
    real_page_keys, _ = _real_key_sets()
    page = json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())
    assert 'blocks' in page
    assert {'schema_name', 'page_index', 'page_number'}.issubset(page.keys())
    assert {'blocks', 'page_index', 'page_number'}.issubset(real_page_keys)


def test_block_has_required_fields(mock_ir):
    _, _, pages_dir, _, _ = mock_ir
    _, real_block_keys = _real_key_sets()
    page = json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())
    required = {
        'block_id', 'type', 'subtype', 'semantic_role', 'docling', 'geometry', 'content',
        'comparison', 'compile_role', 'confidence', 'source_refs', 'flags', 'structure'
    }
    for b in page['blocks']:
        assert required.issubset(b.keys())
        assert set(b.keys()).issubset(real_block_keys | required)


def test_bbox_in_normalised_1000_space(mock_ir):
    _, _, pages_dir, _, _ = mock_ir
    for pf in pages_dir.glob('page_*.json'):
        for b in json.loads(pf.read_text())['blocks']:
            x0, y0, x1, y1 = b['geometry']['bbox']
            assert 0 <= x0 <= 1000 and 0 <= y0 <= 1000 and 0 <= x1 <= 1000 and 0 <= y1 <= 1000


def test_compile_role_is_candidate(mock_ir):
    _, _, pages_dir, _, _ = mock_ir
    blocks = json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())['blocks']
    assert all(b['compile_role'] == 'candidate' for b in blocks)


def test_text_hash_is_sha256(mock_ir):
    _, _, pages_dir, _, _ = mock_ir
    blocks = json.loads(sorted(pages_dir.glob('page_*.json'))[0].read_text())['blocks']
    assert all(b['comparison']['text_hash'].startswith('sha256:') and b['comparison']['geometry_hash'].startswith('sha256:') for b in blocks)


def test_manifest_has_required_fields(mock_ir):
    _, _, _, manifest, _ = mock_ir
    m = json.loads(manifest.read_text())
    assert {'schema_name', 'page_refs', 'backend'}.issubset(m.keys())


def test_consensus_report_can_consume_mock_ir(mock_ir):
    doc_id, fdir, _, _, tmp_path = mock_ir
    cfg = {
        'consensus': {'coordinate_space': 'page_normalised_1000', 'text_similarity_threshold': 0.9, 'weak_text_similarity_threshold': 0.75, 'bbox_iou_threshold': 0.5, 'weak_bbox_iou_threshold': 0.25, 'include_evidence_only_blocks': False},
        'backends': {
            'groundtruth': {'enabled': True, 'root': str(tmp_path / 'backend' / 'groundtruth')},
            'mineru': {'enabled': False, 'root': 'backend/mineru'},
            'paddleocr': {'enabled': False, 'root': 'backend/paddleocr'},
            'deepseek': {'enabled': False, 'root': 'backend/deepseek'},
        },
        'pymupdf': {'enabled': True, 'extract_text': True},
    }
    report, code = consensus_report.build_consensus_report(fdir / 'input' / f'{doc_id}.pdf', cfg, Path('inline'))
    assert code == 0

    for pf in sorted((tmp_path / 'backend' / 'groundtruth' / '.current' / 'extraction_ir' / doc_id / 'pages').glob('page_*.json')):
        pobj = json.loads(pf.read_text())
        for i,b in enumerate(pobj.get('blocks', [])):
            assert b.get('comparison',{}).get('compare_as') == b.get('type')
            ev = consensus_report.normalise_backend_block('groundtruth', b['page_index'], i, b, str(pf), f'/blocks/{i}')
            if b.get('type') not in {'unknown', None}:
                assert ev['kind'] != 'unknown'
