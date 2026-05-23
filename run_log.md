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

## PR #1 — 2026-05-23T17:57:00Z — mode: agent
- tasks_attempted:
    - A1: files_touched=[src/pdf2md/local/connector_validation.py, tests/test_connector_page_ir_validation.py], tests_pass=[test_reuses_existing_connector_entrypoint], tests_fail_env=[], tests_fail_real=[]
    - A2: files_touched=[src/pdf2md/local/connector_validation.py, tests/test_connector_page_ir_validation.py], tests_pass=[test_valid_backend_output_produces_page_extraction_ir, test_missing_required_output_classification, test_connector_crash_classification, test_schema_failed_classification, test_deferred_from_plan9_classification, test_preferred_gate_passes_with_two_validated_backends, test_preferred_gate_fails_with_one_validated_backend, test_minimum_gate_passes_with_one_validated_backend, test_semantic_quality_passes_for_nonempty_document_text, test_semantic_quality_fails_for_empty_or_noise_ir, test_report_json_contract], tests_fail_env=[], tests_fail_real=[]
    - A3: files_touched=[tools/validate_connectors_page_ir.py, tests/test_connector_page_ir_validation.py], tests_pass=[test_allow_reduced_gate_sets_human_required_flag], tests_fail_env=[], tests_fail_real=[]
    - A4: files_touched=[tests/test_connector_page_ir_validation.py, tests/data/connector_validation_fixtures/minimal_markdown_backend/output.md, tests/data/connector_validation_fixtures/missing_output_backend/.gitkeep, tests/data/connector_validation_fixtures/schema_failure_backend/output.md], tests_pass=[all 15 required tests in tests/test_connector_page_ir_validation.py], tests_fail_env=[], tests_fail_real=[]
    - A5: files_touched=[src/pdf2md/local/connector_validation.py, tools/validate_connectors_page_ir.py, tests/test_connector_page_ir_validation.py], tests_pass=[test_entity_proposals_are_ignored_for_plan10_acceptance, test_summary_is_written], tests_fail_env=[], tests_fail_real=[]
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q` → 15 passed
    - `conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py tests/test_backend_smoke.py tests/test_local_groundtruth_validate.py -q` → 44 passed
    - `conda run -n pdf2md pytest tests/ -q` → 722 passed, 212 skipped (environmental), 0 failed
- dependencies_added: []
- external_tools_used: []
- connector_code_changes: none (existing pdf2md.connectors.common.connect_raw_dir reused without modification)
- blockers: []
- status: ready_for_review
