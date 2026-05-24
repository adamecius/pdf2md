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

## PR #3 — 2026-05-24T12:30:00Z — mode: agent — Additional Plan 3 (PEP compliance)
- branch: additional-plan-3-pep-compliance
- tasks_attempted:
    - A1 (docstring style guide): files_touched=[docs/docstring_style_guide.md], tests_pass=[no automated tests required]
    - A2 (module docstrings): files_touched=[src/pdf2md/backends/runner.py, src/pdf2md/cli/main.py, src/pdf2md/config.py, src/pdf2md/conventions/__init__.py, src/pdf2md/conventions/alignment.py, src/pdf2md/conventions/determine_convention.py, src/pdf2md/conventions/latex_groundtruth.py, src/pdf2md/conventions/normalizer.py, src/pdf2md/conventions/reporting.py, src/pdf2md/conventions/rules.py, src/pdf2md/conventions/schemas.py, src/pdf2md/models/__init__.py, src/pdf2md/models/semantic_document.py, src/pdf2md/testing/__init__.py, src/pdf2md/testing/fixtures.py, src/pdf2md/testing/mock_backend_ir.py], modules_with_docstrings=66/66, ast_check=PASS
    - A3 (return annotations): files_touched=[src/pdf2md/consensus/io.py, src/pdf2md/consensus/scoring.py, src/pdf2md/conventions/alignment.py, src/pdf2md/conventions/determine_convention.py, src/pdf2md/testing/fixtures.py, src/pdf2md/testing/mock_backend_ir.py], functions_without_returns_before=7, after=0, ast_check=PASS
    - A4 (Google-style docstrings): public-symbols_with_docstrings_before=~200/430, after=430/430 (incl. private _BaseModel classes), ast_check=PASS; bulk work delegated to 4 parallel subagents partitioned by subpackage (models/, consensus+conventions+backends, calibration+linking, export+local+pipeline+testing), residual ~30 items finished directly
    - A5 (ruff + mypy): files_touched=[pyproject.toml]; ruff_residuals_after_autofix=3 (RUF002 ambiguous en-dash); residuals_resolved=replaced en-dash with hyphen in src/pdf2md/conventions/rules.py, src/pdf2md/conventions/schemas.py, src/pdf2md/testing/mock_backend_ir.py; mypy_errors=0/66 source files; targeted_ignores: pyproject `ignore += UP042` (str-Enum→StrEnum rewrite would change JSON serialisation behaviour; documented inline)
- automated_test_commands:
    - `conda run -n pdf2md ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/` → exit 0, "All checks passed!"
    - `conda run -n pdf2md mypy src/pdf2md/ --exclude _legacy` → exit 0, "Success: no issues found in 66 source files"
    - `conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x` → 928 passed, 212 skipped, 16 xfailed, 0 failed
    - AST module-docstring check → 0 missing
    - AST return-annotation check → 0 missing
    - AST public-symbol docstring check → 0 missing
- dependencies_added: [ruff>=0.4 (installed ruff 0.15.14), mypy>=1.10 (installed mypy 2.1.0); declared in pyproject.toml dev extras since Additional Plan 2]
- external_tools_used: [ruff, mypy]
- forbidden_files_touched: []
- environment_modifying_commands: [conda run -n pdf2md python -m pip install "ruff>=0.4" "mypy>=1.10"]
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
