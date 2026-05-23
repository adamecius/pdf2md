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

## PR #1 — 2026-05-23T18:50:00Z — mode: agent
- tasks_attempted:
    - A1: files_touched=[], tests_pass=[tests/test_calibration_matching.py (20 tests), tests/test_calibration_metrics.py (15 tests)], tests_fail_env=[], tests_fail_real=[]
    - A2: files_touched=[src/pdf2md/calibration/vocabulary.py, tools/vocabulary_alignment_check.py, tests/test_calibration_vocabulary_alignment.py, tests/data/calibration_vocabulary_fixtures/docling_truth_root/{docA,docB}/truth.json, tests/data/calibration_vocabulary_fixtures/missing_mandatory_root/truth.json], tests_pass=[23 tests in tests/test_calibration_vocabulary_alignment.py], tests_fail_env=[], tests_fail_real=[]
    - A3: files_touched=[src/pdf2md/calibration/io.py, tests/test_calibration_io.py], tests_pass=[11 tests in tests/test_calibration_io.py], tests_fail_env=[], tests_fail_real=[]
    - A4: files_touched=[tools/calibrate_priors.py, tests/test_calibration_io.py, tests/data/calibration_prior_fixtures/canonical_truth/**], tests_pass=[test_discover_calibration_inputs_recognises_canonical_truth_layout, test_load_calibration_document_yields_canonical_truth_blocks, test_load_calibration_document_loads_pages_for_each_backend], tests_fail_env=[], tests_fail_real=[]; CALIBRATION_ROOT_FROM_A4=tests/data/calibration_prior_fixtures/canonical_truth for synthetic execution. Real calibration root cannot be supplied because no real Plan 10/11 outputs exist on disk (see blockers).
    - A5: files_touched=[tools/calibrate_priors.py], tests_pass=[exercised end-to-end against the synthetic canonical_truth fixture via the calibrate_priors CLI; produced priors/mineru.json + reports/calibration_report.json with vocabulary_alignment_report path + plan13_readiness section]; real execution against a real backend is blocked because no real Plan 10/11 outputs exist on disk.
    - A6: same — code path exercised against synthetic two-backend fixture (mineru + glm); plan13_readiness.safe_for_consensus=[glm, mineru] under the synthetic min_samples=1. Real execution blocked upstream.
    - A7: files_touched=[tools/calibrate_priors.py], tests_pass=[same as A6]; the calibration_report.json now carries `plan13_readiness` with `safe_for_consensus`, `underpowered`, `no_samples`, `blocked`, and per-backend metric tallies; calibration_summary.txt summarises the hand-off.
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_calibration_matching.py tests/test_calibration_metrics.py -q` → 35 passed
    - `conda run -n pdf2md pytest tests/test_calibration_vocabulary_alignment.py tests/test_calibration_io.py -q` → 34 passed
    - `conda run -n pdf2md pytest tests/ -q` → 774 passed, 212 skipped (environmental), 0 failed
- cli_smoke:
    - `tools/vocabulary_alignment_check.py --root tests/data/calibration_vocabulary_fixtures/docling_truth_root --out-dir /tmp/plan12_vocab_smoke --verbose` → exit 0, mandatory_mapping_passed=true, all_observed_labels_mapped=true
    - `tools/calibrate_priors.py --root tests/data/calibration_prior_fixtures/canonical_truth --out-dir /tmp/plan12_calibrate_smoke --min-samples 1 --verbose` → exit 0, two backends calibrated, vocabulary_alignment_report path emitted, plan13_readiness.safe_for_consensus=[glm, mineru]
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- conditional_file_changes: none (matching.py, metrics.py, priors.py left untouched)
- blockers:
    - real_plan10_artifacts_missing: No real Plan 10 `connector_validation_report.json` or per-backend `page_extraction_ir.json` is committed under `groundtruth/runs/connector_validation/`. The archived Plan 9 backend smoke report has zero successful real backends, so the Plan 10 -> Plan 11 chain has never been exercised against real backend output. Real A5/A6/A7 execution against `--root <real corpus>` therefore cannot produce non-synthetic priors. The agent fully implemented the vocabulary alignment gate, the io.py mapping fix, the calibrate_priors CLI extensions, and the Plan 13 readiness hand-off; real execution will become possible as soon as real Plan 9/10/11 outputs are committed.
- status: ready_for_review
