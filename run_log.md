# Run log

Append-only log of agent-mode PRs for the current plan. Reset only by feedback mode under `archive plan`.

## Entry format

    ## PR #N — <ISO timestamp> — mode: agent
    - tasks_attempted:
        - T<k>: files_touched=[...], tests_pass=[...], tests_fail_env=[...], tests_fail_real=[]
    - dependencies_added: []
    - external_tools_used: []
    - blockers: []
    - status: in_progress | ready_for_review | halted

(No PRs yet.)

## PR #1 — 2026-05-07T00:00:00Z — mode: agent
- tasks_attempted:
    - T1 LinkedStructure contracts: files_touched=[`src/pdf2md/models/linked.py`, `src/pdf2md/models/__init__.py`, `tests/test_linked_structure_contracts.py`], tests_pass=[`pytest tests/test_linked_structure_contracts.py -q`, `pytest tests/test_ir_contracts.py -q`, `pytest tests/test_entity_contracts.py -q`, `pytest tests/test_prior_contracts.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T2 extraction layer: files_touched=[`src/pdf2md/linking/__init__.py`, `src/pdf2md/linking/extract.py`, `tests/test_linking_extract.py`, `tests/data/linking_fixtures/*`], tests_pass=[`pytest tests/test_linking_extract.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T3 resolver layer: files_touched=[`src/pdf2md/linking/resolvers.py`, `tests/test_linking_resolvers.py`], tests_pass=[`pytest tests/test_linking_resolvers.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T4 builder and report: files_touched=[`src/pdf2md/linking/builder.py`, `src/pdf2md/linking/reporting.py`, `tests/test_linked_structure_builder.py`, `tests/data/linking_fixtures/*`], tests_pass=[`pytest tests/test_linked_structure_builder.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T5 I/O and CLI: files_touched=[`src/pdf2md/linking/io.py`, `tools/build_linked_structure.py`, `tests/test_build_linked_structure_cli.py`], tests_pass=[`pytest tests/test_build_linked_structure_cli.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T6 regression pass: files_touched=[], tests_pass=[`pytest tests/ -q`, `python -c "from pdf2md.models.linked import LinkedStructure; print(LinkedStructure.model_json_schema()['title'])"`, `python tools/build_linked_structure.py --consensus-ir tests/data/linking_fixtures/simple_document/consensus_ir.json --consensus-report tests/data/linking_fixtures/simple_document/consensus_report.json --entities-root tests/data/linking_fixtures/simple_document/entities --priors-root tests/data/linking_fixtures/simple_document/priors --out-dir /tmp/pdf2md_linking_smoke`, `python -c "from pathlib import Path; from pdf2md.models.linked import LinkedStructure; p=Path('/tmp/pdf2md_linking_smoke/linked_structure.json'); LinkedStructure.model_validate_json(p.read_text()); print('ok')"`], tests_fail_env=[`git diff --name-only main..HEAD` unavailable because this checkout has no `main` ref], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review

## PR #2 — 2026-05-07T00:00:00Z — mode: agent
- tasks_attempted:
    - T3 resolver follow-up fixes: files_touched=[`src/pdf2md/linking/resolvers.py`, `tests/test_linking_resolvers.py`], tests_pass=[`pytest tests/test_linking_resolvers.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T4 builder/report follow-up fixes: files_touched=[`src/pdf2md/linking/builder.py`, `tests/test_linked_structure_builder.py`], tests_pass=[`pytest tests/test_linked_structure_builder.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T1/T2/T5 test coverage completion: files_touched=[`tests/test_linked_structure_contracts.py`, `tests/test_linking_extract.py`, `tests/test_build_linked_structure_cli.py`], tests_pass=[`pytest tests/test_linked_structure_contracts.py -q`, `pytest tests/test_linking_extract.py -q`, `pytest tests/test_build_linked_structure_cli.py -q`], tests_fail_env=[], tests_fail_real=[]
    - T6 regression pass: files_touched=[], tests_pass=[`pytest tests/test_linked_structure_contracts.py -q && pytest tests/test_linking_extract.py -q && pytest tests/test_linking_resolvers.py -q && pytest tests/test_linked_structure_builder.py -q && pytest tests/test_build_linked_structure_cli.py -q`, `pytest tests/test_ir_contracts.py -q && pytest tests/test_entity_contracts.py -q && pytest tests/test_connector_common.py -q && pytest tests/test_backend_connectors.py -q && pytest tests/test_prior_contracts.py -q && pytest tests/test_calibration_matching.py -q && pytest tests/test_calibration_metrics.py -q && pytest tests/test_calibrate_priors_cli.py -q && pytest tests/test_consensus_grouping.py -q && pytest tests/test_consensus_scoring.py -q && pytest tests/test_consensus_factory.py -q && pytest tests/test_build_consensus_cli.py -q && pytest tests/test_run_backends_config.py -q && pytest tests/test_semantic_document_builder.py -q`, `pytest tests/ -q`, `python -c "from pdf2md.models.linked import LinkedStructure; print(LinkedStructure.model_json_schema()['title'])"`, `python tools/build_linked_structure.py --consensus-ir tests/data/linking_fixtures/simple_document/consensus_ir.json --consensus-report tests/data/linking_fixtures/simple_document/consensus_report.json --entities-root tests/data/linking_fixtures/simple_document/entities --priors-root tests/data/linking_fixtures/simple_document/priors --out-dir /tmp/pdf2md_linking_smoke`, `python -c "from pathlib import Path; from pdf2md.models.linked import LinkedStructure; p=Path('/tmp/pdf2md_linking_smoke/linked_structure.json'); LinkedStructure.model_validate_json(p.read_text()); print('ok')"`], tests_fail_env=[`git diff --name-only main..HEAD` unavailable because this checkout has no `main` ref], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review
