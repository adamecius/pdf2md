import json
import subprocess
import sys
from pathlib import Path

import pytest

from pdf2md.linking.builder import build_linked_structure
from pdf2md.linking.io import load_linker_inputs, write_linker_outputs
from pdf2md.models.linked import LinkedStructure

FIX=Path('tests/data/linking_fixtures')
SCRIPT=Path('tools/build_linked_structure.py')


def test_load_linker_inputs_reads_consensus_entities_priors():
    base=FIX/'simple_document'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json',consensus_report_path=base/'consensus_report.json',entities_root=base/'entities',priors_root=base/'priors')
    assert loaded.consensus.document_id == 'linkdoc'
    assert set(loaded.entities_by_backend) == {'mineru','paddleocr'}
    assert set(loaded.priors_by_backend) == {'mineru','paddleocr'}


def test_lenient_missing_entities_prior_roots_warn():
    base=FIX/'simple_document'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json')
    assert 'entities_root_missing' in loaded.warnings
    assert 'priors_root_missing' in loaded.warnings


def test_strict_invalid_optional_input_raises(tmp_path):
    base=FIX/'simple_document'
    bad=tmp_path/'bad.json'; bad.write_text('[]')
    with pytest.raises(ValueError):
        load_linker_inputs(consensus_ir_path=base/'consensus_ir.json',consensus_report_path=bad,strict=True)


def test_write_linker_outputs_writes_both_files(tmp_path):
    base=FIX/'simple_document'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json',consensus_report_path=base/'consensus_report.json',entities_root=base/'entities',priors_root=base/'priors')
    result=build_linked_structure(consensus=loaded.consensus,entities_by_backend=loaded.entities_by_backend,priors_by_backend=loaded.priors_by_backend,consensus_report=loaded.consensus_report)
    write_linker_outputs(result=result,out_dir=tmp_path)
    assert (tmp_path/'linked_structure.json').exists()
    assert (tmp_path/'reports'/'linking_report.json').exists()


def test_cli_help_exits_zero():
    proc=subprocess.run([sys.executable,str(SCRIPT),'--help'],text=True,capture_output=True)
    assert proc.returncode == 0
    assert '--consensus-ir' in proc.stdout


def run_cli(tmp_path, fixture='simple_document', optional=True):
    base=FIX/fixture
    cmd=[sys.executable,str(SCRIPT),'--consensus-ir',str(base/'consensus_ir.json'),'--out-dir',str(tmp_path)]
    if optional:
        cmd += ['--consensus-report',str(base/'consensus_report.json'),'--entities-root',str(base/'entities'),'--priors-root',str(base/'priors')]
    return subprocess.run(cmd,text=True,capture_output=True)


def test_cli_writes_valid_linked_structure(tmp_path):
    proc=run_cli(tmp_path)
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert linked.nodes


def test_cli_unresolved_fixture_writes_conflict(tmp_path):
    proc=run_cli(tmp_path,'unresolved_ambiguity')
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert linked.conflicts


def test_cli_missing_optional_inputs_succeeds_leniently(tmp_path):
    proc=run_cli(tmp_path,optional=False)
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert 'entities_root_missing' in linked.warnings


def test_cli_strict_bad_consensus_fails(tmp_path):
    bad=tmp_path/'bad.json'; bad.write_text('{}')
    proc=subprocess.run([sys.executable,str(SCRIPT),'--consensus-ir',str(bad),'--out-dir',str(tmp_path),'--strict'],text=True,capture_output=True)
    assert proc.returncode == 1


def test_cli_report_includes_lenient_input_warnings(tmp_path):
    proc=run_cli(tmp_path,optional=False)
    assert proc.returncode == 0, proc.stderr
    report=json.loads((tmp_path/'reports'/'linking_report.json').read_text())
    assert 'entities_root_missing' in report['warnings']


def test_strict_missing_explicit_entities_root_raises(tmp_path):
    base=FIX/'simple_document'
    missing=tmp_path/'missing_entities'
    with pytest.raises(ValueError):
        load_linker_inputs(consensus_ir_path=base/'consensus_ir.json', entities_root=missing, strict=True)


def test_cli_low_confidence_threshold_option_is_applied(tmp_path):
    base=FIX/'simple_document'
    proc=subprocess.run([
        sys.executable,str(SCRIPT),'--consensus-ir',str(base/'consensus_ir.json'),'--consensus-report',str(base/'consensus_report.json'),
        '--entities-root',str(base/'entities'),'--priors-root',str(base/'priors'),'--out-dir',str(tmp_path),'--low-confidence-threshold','0.99'
    ],text=True,capture_output=True)
    assert proc.returncode == 0, proc.stderr
    linked=LinkedStructure.model_validate_json((tmp_path/'linked_structure.json').read_text())
    assert any(node.status == 'resolved_low_confidence' for node in linked.nodes[1:])
