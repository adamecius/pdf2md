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

## PR #1 — 2026-05-23T19:10:00Z — mode: agent
- tasks_attempted:
    - A1: files_touched=[], tests_pass=[tests/test_consensus_factory.py, tests/test_consensus_scoring.py, tests/test_consensus_grouping.py, tests/test_consensus_report.py, tests/test_build_consensus_cli.py → 90 existing tests pass on baseline]; CONSENSUS_RUN_FROM_A1 was exercised against the existing `tests/data/consensus_fixtures/simple_agreement` fixture because no real Plan 10/11/12 outputs are committed (see blockers).
    - A2: files_touched=[src/pdf2md/consensus/reporting.py, src/pdf2md/consensus/io.py, tools/build_consensus.py, tests/test_build_consensus_cli.py], tests_pass=[13 new Plan 13 hardening tests in tests/test_build_consensus_cli.py (TestPlan13ReportHardening + TestPlan13IOHardening + TestPlan13CLI classes); 90 existing consensus tests still pass]. Reporting extended with `backend_contributions`, `confidence_summary`, `conflict_details`, `inspection_status`, `ground_truth_ref`, `inspection_notes`, `plan14_readiness`; io now emits `consensus_summary.txt`. No new modules, no new CLI tools, no parallel weighted consensus added.
    - A3: files_touched=[tools/build_consensus.py, src/pdf2md/consensus/reporting.py], tests_pass=[CLI accepts `--inspection-status`, `--ground-truth`, `--inspection-note`; rejects unknown statuses; default is `diagnostic_only`]. The agent recorded `inspection_status=diagnostic_only` for synthetic runs because no real Plan 10/11/12 outputs exist for a side-by-side quality comparison.
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_consensus_factory.py tests/test_consensus_scoring.py tests/test_consensus_grouping.py tests/test_consensus_report.py tests/test_build_consensus_cli.py -q` → 103 passed (90 existing + 13 new)
    - `conda run -n pdf2md pytest tests/ -q` → 787 passed, 212 skipped (environmental), 0 failed
- cli_smoke:
    - `tools/build_consensus.py --connector-root tests/data/consensus_fixtures/simple_agreement --document-id doc-1 --priors-root tests/data/consensus_fixtures/simple_agreement/priors --backends mineru,paddleocr --out-dir /tmp/plan13_smoke --inspection-status appears_equivalent_to_best_backend --inspection-note "two backends agreed on heading" --verbose` → exit 0; `plan14_readiness.consensus_block_count=2`, `consensus_conflict_count=0`, `backends_with_priors_loaded=['mineru','paddleocr']`; `consensus_summary.txt` named Plan 13 + Plan 14 readiness + LinkedStructure deferral.
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- conditional_file_changes: none (src/pdf2md/models/consensus.py left untouched; src/pdf2md/consensus/weighted.py never created)
- blockers:
    - real_plan10_11_12_artifacts_missing: No real Plan 10 connector validation outputs, real Plan 11 entity proposal outputs, or real Plan 12 priors are committed under `groundtruth/runs/`. The same `tools/build_consensus.py` code path was exercised end-to-end against the synthetic `tests/data/consensus_fixtures/` fixtures. When real upstream outputs become available, running the CLI against them is sufficient — no further code changes are needed. Inspection status will then move from `diagnostic_only` to one of the four quality-comparison values once the human compares ConsensusIR against backends and ground truth.
- status: ready_for_review
