import json
import subprocess
import tempfile
from pathlib import Path


def test_backend_alias_normalisation_and_adapter_preference():
    script = Path('run_latex_docling_backends.sh').read_text()
    assert 'mineruo|minero' in script
    assert 'paddle|paddle_ocr' in script
    assert 'deep_seek|deepseek_ocr' in script
    assert Path('backend/deepseek/pdf2ir_deepseek.py').exists()
    assert 'pdf2ir_${b}.py' in script


def test_validator_backend_not_run_warnings_keep_ok_true():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        batch = root / 'b1'
        doc = batch / 'd1'
        (doc / 'input').mkdir(parents=True)
        (doc / 'groundtruth').mkdir(parents=True)
        (doc / 'input' / 'd1.tex').write_text('\\section{A}\\label{sec:a}')
        (doc / 'groundtruth' / 'source_groundtruth_ir.json').write_text(json.dumps({
            'schema_name': 'x', 'document_id': 'd1', 'nodes': [{'id':'n1','type':'section'}],
            'labels': {'sec:a':'n1'}, 'references': [], 'features': [], 'pages_expected_min': 1
        }))
        (doc / 'groundtruth' / 'expected_semantic_contract.json').write_text(json.dumps({
            'document_id': 'd1', 'expected_title': 'A', 'expected_sections': [],
            'expected_labels': ['sec:a'], 'required_node_types': []
        }))
        (doc / 'groundtruth' / 'expected_docling_contract.json').write_text(json.dumps({
            'document_id': 'd1', 'required_docling_kinds': []
        }))
        (doc / 'groundtruth' / 'provenance_manifest.json').write_text('{}')
        cfg = root / 'cfg.toml'
        cfg.write_text('[backends.mineruo]\nenabled=true\n[backends.paddle_ocr]\nenabled=true\n[backends.deep_seek]\nenabled=true\n')

        subprocess.run([
            'python', 'validate_latex_docling_groundtruth.py', '--root', str(root), '--batch', 'b1', '--config', str(cfg)
        ], check=True)
        report = json.loads((batch / 'validation_report.json').read_text())
        assert report['ok'] is True
        warns = report['documents'][0]['warnings']
        assert 'backend_not_run_mineru' in warns
        assert 'backend_not_run_paddleocr' in warns
        assert 'backend_not_run_deepseek' in warns
