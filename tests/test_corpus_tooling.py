from pathlib import Path
import importlib.util
import subprocess
import sys
import json
import pytest


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

compile_mod = _load('compile_corpus', 'scripts/compile_corpus.py')
cert_mod = _load('certify_corpus', 'scripts/certify_corpus.py')


def test_compile_and_hash(tmp_path):
    d = tmp_path / 'd'; d.mkdir()
    (d / 'd.tex').write_text('a')
    h1 = compile_mod.input_hash(d, 'd')
    (d / 'd.tex').write_text('b')
    h2 = compile_mod.input_hash(d, 'd')
    assert h1 != h2


def test_compile_and_log():
    errs = compile_mod.parse_errors('! err\nReference x undefined\nCitation y undefined')
    assert len(errs) == 3


def test_certify(tmp_path):
    d = tmp_path / 'doc'; d.mkdir()
    (d / 'doc.tex').write_text('\\DocumentMetadata{testphase=phase-III, pdfstandard=ua-2}\\n\\section{A}\\label{s}\\ref{s}')
    (d / 'doc.pdf').write_bytes(b'%PDF-1.4\n')
    (d / 'build.log').write_text('ok')
    (d / 'meta.toml').write_text('expected_counts = {}')
    out = cert_mod.cert(d, 'doc')
    assert 'checks' in out


def test_integration(tmp_path):
    if subprocess.run(['bash','-lc','command -v lualatex >/dev/null']).returncode != 0:
        pytest.skip('lualatex unavailable')
    root = tmp_path / 'corpus'; dd = root / 'tiny'; dd.mkdir(parents=True)
    (dd / 'tiny.tex').write_text('\\DocumentMetadata{testphase=phase-III, pdfstandard=ua-2}\\n\\documentclass{article}\\n\\usepackage{hyperref}\\n\\begin{document}\\n\\section{S}\\label{s}\\nSee \\ref{s}.\\n\\end{document}')
    subprocess.run([sys.executable, 'scripts/compile_corpus.py', '--corpus-root', str(root), '--doc', 'tiny'], check=True)
    subprocess.run([sys.executable, 'scripts/certify_corpus.py', '--corpus-root', str(root), '--doc', 'tiny'], check=False)
    assert (dd / 'build.log').exists()


def test_pipeline_paths(tmp_path):
    bad = tmp_path / 'missing'
    cmd = [sys.executable, 'scripts/compile_corpus.py', '--corpus-root', str(bad)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode != 0
