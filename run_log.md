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

## PR #1 — 2026-05-24T00:00:00Z — mode: agent — Additional Plan 1
- tasks_attempted:
    - A1 (dataset registry): files_touched=[src/pdf2md/datasets/__init__.py, src/pdf2md/datasets/registry.py, tests/test_dataset_registry.py], tests_pass=[10/10 in tests/test_dataset_registry.py], tests_fail_env=[], tests_fail_real=[]
    - A2 (git downloader): files_touched=[src/pdf2md/datasets/downloader.py, tests/test_dataset_downloader.py], tests_pass=[7/7 in tests/test_dataset_downloader.py — local git fixtures, no network], tests_fail_env=[], tests_fail_real=[]
    - A3 (manifest): files_touched=[src/pdf2md/datasets/manifest.py, tests/test_dataset_manifest.py], tests_pass=[8/8 in tests/test_dataset_manifest.py], tests_fail_env=[], tests_fail_real=[]
    - A4 (Typer CLI): files_touched=[src/pdf2md/datasets/cli.py, src/pdf2md/cli/main.py, tests/test_dataset_cli.py], tests_pass=[10/10 in tests/test_dataset_cli.py — downloader mocked, no network]; CLI exposes `pdf2md datasets list / install / status` with --dry-run, --force, --manifest-only, --output, --ref; reserved --compile/--limit/--engine print Plan 18 deferral
    - A5 (docs): files_touched=[docs/datasets.md, run_log.md (this entry)], tests_pass=[no automated tests required]
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_dataset_registry.py tests/test_dataset_downloader.py tests/test_dataset_manifest.py tests/test_dataset_cli.py -q` → 35 passed
    - `conda run -n pdf2md pytest tests/ -q` → 878 passed, 212 skipped, 16 xfailed (carried over from Plan 17), 0 failed
- cli_smoke:
    - `pdf2md datasets list` → prints all three registry entries with status
    - `pdf2md datasets install tlc3 --dry-run --output /tmp/external` → exits 0 with `[dry-run]` plan; no files touched
    - `pdf2md datasets install arxiv-curated` → exits non-zero with "not yet available for download" message
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- conditional_file_changes: src/pdf2md/cli/main.py — single-line `app.add_typer(datasets_app, name="datasets")` import + registration, exactly per the plan whitelist
- blockers: []
- status: ready_for_review

## PR #2 — 2026-05-24T11:30:00Z — mode: agent — Plan 19
- branch: plan-19-uninformative-priors-consensus-bootstrap
- tasks_attempted:
    - A1 (UNINFORMATIVE status + build_uninformative_prior): files_touched=[src/pdf2md/models/priors.py, tests/test_uninformative_priors.py], tests_pass=[12/12 in tests/test_uninformative_priors.py], tests_fail_env=[], tests_fail_real=[]
    - A2 (factory_priors dir + load_factory_prior + package-data): files_touched=[src/pdf2md/models/priors.py, src/pdf2md/data/__init__.py, src/pdf2md/data/factory_priors/__init__.py, src/pdf2md/data/factory_priors/paddleocr.json, src/pdf2md/data/factory_priors/deepseek.json, src/pdf2md/data/factory_priors/mineru.json, pyproject.toml, tests/test_factory_priors.py], tests_pass=[15/15], tests_fail_env=[], tests_fail_real=[]
    - A3 (three-level fallback in consensus io): files_touched=[src/pdf2md/consensus/io.py, tests/test_consensus_prior_fallback.py], tests_pass=[11/11 incl. A4 end-to-end tests in same file], tests_fail_env=[], tests_fail_real=[]
    - A4 (end-to-end consensus at each prior level): co-located in tests/test_consensus_prior_fallback.py (TestEndToEndConsensusBuilds + TestPriorByBackendNeverEmpty); covered by the 11/11 count above
    - A5 (--from-scratch flag): files_touched=[tools/calibrate_priors.py, tests/test_uninformative_priors.py], tests_pass=[2 additional subprocess tests stamping calibration_mode]
- automated_test_commands:
    - `pytest tests/test_uninformative_priors.py tests/test_factory_priors.py tests/test_consensus_prior_fallback.py tests/test_calibration_matching.py tests/test_calibration_metrics.py -q` → 74 passed
    - `pytest tests/ -q` → 932 passed, 219 skipped, 16 xfailed, 0 failed
- factory_priors_committed: paddleocr (calibrated against synthetic LaTeX corpus, support=571), deepseek (calibrated against synthetic LaTeX corpus, support=582), mineru (uninformative_placeholder until benchmark run finishes)
- stale_test_expectations_updated: tests/test_prior_contracts.py (CalibrationStatus enum list now includes UNINFORMATIVE); tests/test_build_consensus_cli.py (prior_missing warning replaced by prior_factory or prior_uninformative)
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- blockers: []
- status: ready_for_review
