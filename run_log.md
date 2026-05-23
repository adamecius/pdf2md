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

## PR #1 — 2026-05-23T18:30:00Z — mode: agent
- tasks_attempted:
    - A1: files_touched=[src/pdf2md/local/entity_proposal_validation.py, tests/test_entity_proposal_validation.py], tests_pass=[18/18 in tests/test_entity_proposal_validation.py], tests_fail_env=[], tests_fail_real=[]
    - A2: files_touched=[src/pdf2md/local/entity_proposal_validation.py, tests/test_entity_proposal_validation.py], tests_pass=[test_valid_entity_document_classifies_validated, test_empty_entity_document_classifies_no_entities_produced, test_invalid_entity_document_classifies_schema_failed, test_connector_crash_classification, test_deferred_from_plan10_classification, test_entity_type_counts_are_reported, test_relation_type_counts_are_reported, test_relation_endpoints_are_validated_by_schema, test_evidence_references_are_validated_by_schema, test_preferred_gate_passes_with_two_validated_backends, test_preferred_gate_fails_with_one_validated_backend, test_minimum_gate_passes_with_one_validated_backend, test_no_entities_produced_does_not_count_toward_validated_gate, test_semantic_plausibility_passes_for_plausible_entities, test_semantic_plausibility_fails_for_noise_or_empty_entities, test_report_json_contract], tests_fail_env=[], tests_fail_real=[]
    - A3: files_touched=[tools/validate_entity_proposals.py, tests/test_entity_proposal_validation.py], tests_pass=[test_allow_reduced_gate_sets_human_required_flag], tests_fail_env=[], tests_fail_real=[]
    - A4: files_touched=[tests/test_entity_proposal_validation.py, tests/data/entity_proposal_validation_fixtures/valid_entities/entities.json, tests/data/entity_proposal_validation_fixtures/valid_entities/page_extraction_ir.json, tests/data/entity_proposal_validation_fixtures/no_entities/entities.json, tests/data/entity_proposal_validation_fixtures/no_entities/page_extraction_ir.json, tests/data/entity_proposal_validation_fixtures/schema_failure/entities.json, tests/data/entity_proposal_validation_fixtures/schema_failure/page_extraction_ir.json], tests_pass=[all 18 required tests], tests_fail_env=[], tests_fail_real=[]
    - A5: files_touched=[src/pdf2md/local/entity_proposal_validation.py, tools/validate_entity_proposals.py, tests/test_entity_proposal_validation.py], tests_pass=[test_summary_is_written], tests_fail_env=[], tests_fail_real=[]
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -q` → 18 passed
    - `conda run -n pdf2md pytest tests/test_entity_proposal_validation.py tests/test_connector_page_ir_validation.py tests/test_backend_smoke.py -q` → 48 passed
    - `conda run -n pdf2md pytest tests/ -q` → 740 passed, 212 skipped (environmental), 0 failed
- dependencies_added: []
- external_tools_used: []
- connector_code_changes: none (existing pdf2md.connectors.common.connect_raw_dir reused without modification; EntityProposalDocument schema, EntityType, RelationType reused unchanged)
- blockers: []
- status: ready_for_review
