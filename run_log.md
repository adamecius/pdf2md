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

## PR #1 — 2026-05-24T22:30:00Z — mode: agent — Additional Plan 1
- branch: plan-add1-external-dataset-downloaders
- tasks_attempted:
    - A1 (registry): files_touched=[], tests_pass=[tests/test_dataset_registry.py — 9 passed (lookup by id; lookup by alias; unknown id raises ValueError with valid choices listed; list_datasets returns all entries; arxiv-curated has status not_available; etc.)], tests_fail_env=[], tests_fail_real=[]. Existing implementation in src/pdf2md/datasets/registry.py was complete prior to this PR; no source changes needed.
    - A2 (downloader): files_touched=[], tests_pass=[tests/test_dataset_downloader.py — 10 passed: successful clone + positioning from a local fake git repo, keep/exclude filtering (BOOK-PDFS excluded for a tlc3-like fixture), --force replaces existing, missing --force raises, missing git binary raises clear error]. Existing implementation complete; all tests use local fake git repos created with subprocess git init / commit. No network access in any test.
    - A3 (manifest): files_touched=[], tests_pass=[tests/test_dataset_manifest.py — 9 passed: dataset.json generation with required schema fields, manifest.jsonl with deterministic root-file discovery, global external_datasets.json creation and update, missing-directory status detection]. Existing implementation complete.
    - A4 (CLI): files_touched=[], tests_pass=[tests/test_dataset_cli.py — 7 passed: list shows registry entries; install --dry-run produces output without side effects; install with mocked downloader succeeds; install without --force on existing raises; install arxiv-curated prints not-available (exit code non-zero per the existing merged test contract); status reads and reports from index file; --compile flag prints "Not implemented in Additional Plan 1. See Plan 18 for compilation work."]. Existing implementation already registers `datasets_app` via `app.add_typer(datasets_app, name="datasets")` in src/pdf2md/cli/main.py.
    - A5 (docs + placeholders): files_touched=[docs/datasets.md, groundtruth/external/.gitkeep, groundtruth/manifest/.gitkeep, tests/data/fake_repo/.gitkeep], tests_pass=[A5 has no automated tests per plan; verified via H1 dry-run], tests_fail_env=[], tests_fail_real=[]
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_dataset_registry.py tests/test_dataset_downloader.py tests/test_dataset_manifest.py tests/test_dataset_cli.py -q` → 35 passed
    - `conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x` → 1002 passed, 212 skipped, 16 xfailed, 0 failed (no regressions from Plan 008 baseline 1002 — the dataset modules + tests were already merged in a previous plan iteration; this PR adds only docs + .gitkeep placeholders)
- runtime_acceptance_commands_H1:
    - `conda run -n pdf2md pdf2md datasets list` → exit 0, lists tlc3-examples / latex-cookbook / arxiv-curated with id, aliases, licence, status
    - `conda run -n pdf2md pdf2md datasets install tlc3 --dry-run` → exit 0, prints dataset_id / source_url / ref / output / keep=['NORMAL','SPECIAL','SUPPORT','README.md','build.lua'] / exclude=['BOOK-PDFS'] / force_required=False; no files created under groundtruth/external/
    - `conda run -n pdf2md pdf2md datasets install latex-cookbook --dry-run` → exit 0, prints dataset_id / source_url / ref / output / keep=['.'] / exclude=[] / force_required=False; no files created
    - `conda run -n pdf2md pdf2md datasets install arxiv-curated` → exit 1 with message "Dataset arxiv-curated is not yet available for download". Note: the source plan §7 H1 "all four commands exit without error" criterion is inconsistent with the existing merged test contract (tests/test_dataset_cli.py:117 asserts `exit_code != 0` for this case). Since the implementation + tests landed in a prior cycle, this PR preserves the merged contract; the human reviewer may treat this as the intended behaviour (cleanly-reported non-zero exit to signal "cannot proceed") or flag it for a follow-up plan.
    - `conda run -n pdf2md pdf2md datasets install tlc3 --compile` → "Not implemented in Additional Plan 1. See Plan 18 for compilation work."; --limit and --engine follow the same pattern.
    - `conda run -n pdf2md pdf2md datasets status` → exit 0, reports tlc3-examples=not_installed, latex-cookbook=not_installed, arxiv-curated=not_available.
- isolation_check:
    - groundtruth/external/.gitkeep + groundtruth/manifest/.gitkeep + tests/data/fake_repo/.gitkeep created; groundtruth/corpus/ untouched.
    - No modifications to backend/, src/pdf2md/{consensus,linking,export,pipeline,models,semantic,connectors,calibration,local,conventions,testing,_legacy}/, generate_latex_docling_groundtruth.py, validate_latex_docling_groundtruth.py, pyproject.toml.
    - No additions to pyproject.toml: typer + pydantic + pytest were already required; the dataset modules use only stdlib (subprocess, pathlib, json, shutil, tempfile, hashlib, re).
- runner_contract_compliance:
    - `pdf2md datasets {list, install, status}` subcommands present and functional.
    - `--dry-run` produces zero filesystem changes (verified: ls groundtruth/external/ shows only .gitkeep after the dry-run).
    - --compile / --limit / --engine reserved flags print the documented "Not implemented..." message and exit cleanly.
- dependencies_added: []
- external_tools_used: []   # `git` is invoked only at user-runtime via `pdf2md datasets install` — not by the agent
- forbidden_files_touched: []
- environment_modifying_commands: []
- blockers:
    - One discrepancy between the source plan §7 H1 pass criterion ("All four commands exit without error.") and the merged implementation/test contract for `pdf2md datasets install arxiv-curated` (existing test asserts `exit_code != 0`). Documented above for human review; not blocking ready_for_review.
- status: ready_for_review

## Governance feedback — 2026-05-31T00:00:00Z — mode: feedback — Design architecture improvements
- branch: work
- tasks_attempted:
    - G1 (single lifecycle authority): files_touched=[agent.md, PLAN_TEMPLATE.md], tests_pass=[document review; lifecycle language now delegates status/hand-off mechanics to PLAN_TEMPLATE.md], tests_fail_env=[], tests_fail_real=[]
    - G2 (lite plan tier and verification artifacts): files_touched=[PLAN_TEMPLATE.md, PLAN_TEMPLATE_LITE.md], tests_pass=[document review; lite template added and full template checkpoint fields extended], tests_fail_env=[], tests_fail_real=[]
    - G3 (compact project state surface): files_touched=[project.md, STATE.md], tests_pass=[document review; STATE.md created and project.md points to it], tests_fail_env=[], tests_fail_real=[]
- automated_test_commands:
    - `git diff --check` → passed
    - `git status --short` → passed; only governance docs plus run_log.md changed/created
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review
