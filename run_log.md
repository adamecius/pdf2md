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
