from pathlib import Path
import importlib.util

def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m
compile_mod=_load('compile_corpus','scripts/compile_corpus.py')

def test_compile_and_hash(tmp_path):
    d=tmp_path/'d'; d.mkdir(); (d/'d.tex').write_text('x')
    h1=compile_mod.input_hash(d,'d'); (d/'d.tex').write_text('y'); h2=compile_mod.input_hash(d,'d')
    assert h1!=h2

def test_compile_and_log():
    errs=compile_mod.parse_errors('! boom\nReference x undefined\nCitation y undefined')
    assert len(errs)==3

def test_certify():
    assert Path('groundtruth/corpus/latex').exists()

def test_pipeline_paths():
    assert Path('groundtruth/corpus/latex').exists()
