# Run log

Append-only log of agent-mode PRs for the current plan. Reset only by feedback mode under `archive plan`.

## Entry format

    ## PR #N — <ISO timestamp> — mode: agent
    - tasks_completed:
        - T<k>: files_touched=[...], tests_pass=[...], tests_fail_env=[...], tests_fail_real=[...]
    - blockers: []
    - status: in_progress | ready_for_review | halted

(No PRs yet.)

## PR #1 — 2026-05-04T22:15:33Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[], tests_pass=[], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: ["current_plan.md has no '## Status' section, so the next pending task cannot be determined as requested by agent-mode protocol."]
- status: halted

## PR #2 — 2026-05-04T22:30:41Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[groundtruth/corpus/latex/**], tests_pass=[A1,A2,A3], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review

## PR #3 — 2026-05-04T22:45:00Z — mode: agent
- tasks_attempted:
    - T2: files_touched=[.current/docling_groundtruth/**/*.tex, .current/docling_groundtruth/**/*.pdf, .current/latex_docling_groundtruth/**/*.tex, .current/latex_docling_groundtruth/**/*.pdf, run_log.md], tests_pass=[A5], tests_fail_env=[], tests_fail_real=[A4]
- dependencies_added: []
- external_tools_used: []
- blockers: ["A4 evidence requirement not satisfied: deletion-candidate list was generated but not recorded in run_log.md before deletion."]
- status: halted

## PR #4 — 2026-05-04T23:10:00Z — mode: agent
- tasks_attempted:
    - T2: files_touched=[run_log.md, booking.log (temporary, deleted)], tests_pass=[A4,A5], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review

## PR #5 — 2026-05-04T23:45:00Z — mode: agent
- tasks_attempted:
    - T3: files_touched=[groundtruth/corpus/latex/**, run_log.md, booking.log (temporary, deleted)], tests_pass=[A7], tests_fail_env=[], tests_fail_real=[A6]
- dependencies_added: []
- external_tools_used: []
- blockers: ["A6 unresolved legacy references remain in 174 files under .current/** (mostly groundtruth/provenance/backend_ir JSON). Those files are not writable under the whitelist for T3 because only .current/**/*.tex|.pdf are allowed there."]
- status: halted

## PR #6 — 2026-05-05T00:25:00Z — mode: agent
- tasks_attempted:
    - T3: files_touched=[.current/**/*.json, run_log.md, booking.log (temporary, deleted)], tests_pass=[A7], tests_fail_env=[], tests_fail_real=[A6]
- dependencies_added: []
- external_tools_used: []
- blockers: ["A6 unresolved references remain in 2 backend manifest JSON files under .current/.../backend_ir/mineru/.current/extraction_ir/*/manifest.json. These references did not map to canonical groundtruth/corpus/latex/<doc_id>/<doc_id>.tex targets and require plan-level guidance on whether to preserve backend artifact-local source pointers or map them to canonical corpus paths."]
- status: halted

## Human change — 2026-05-05T08:01:09Z — mode: human
- commit: d1d82840ae37e4e1751fea5a8144dd8270302f4e
- summary: "perform pending file cleaning"
- files_touched_scope:
    - deleted repository planning/status files (`.agent/PLANS.md`, `current_status.md`, `next_plan.md`, `description.md`)
    - deleted local visual test artifacts (`test_visual.md`, `test_visual.pdf`)
    - deleted large generated trees under `.current/docling_groundtruth/**` and `.current/latex_docling_groundtruth/**`
- traceability_notes:
    - author: Jose H Garcia <adamecius@gmail.com>
    - author_date: 2026-05-05T10:01:09+02:00
    - rationale inferred from commit message: repository hygiene / pending generated-file cleanup
- blockers: []
- status: recorded

## PR #7 — 2026-05-05T08:27:57Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[run_log.md], tests_pass=[], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: ["current_plan.md has no '## Status' section, so the next pending task cannot be determined as required by this prompt."]
- status: halted

## PR #8 — 2026-05-05T08:34:56Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[tools/compile_latex_groundth.py, run_log.md], tests_pass=[A1], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: in_progress

## PR #9 — 2026-05-05T14:15:59Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[tools/compile_latex_groundth.py], tests_pass=[A1], tests_fail_env=[], tests_fail_real=[]
    - T2: files_touched=[tests/test_compile_latex_groundth.py], tests_pass=[A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[run_log.md], tests_pass=[], tests_fail_env=[A5], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: ["A5 artifact inspection command found no generated PDF/XML/build.log files in this checkout; human reported local generation run cannot be verified in-repo from current environment."]
- status: halted

## PR #10 — 2026-05-06T08:24:49Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[], tests_pass=[A1], tests_fail_env=[], tests_fail_real=[]
    - T2: files_touched=[tests/test_compile_latex_groundth.py], tests_pass=[A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[run_log.md], tests_pass=[], tests_fail_env=[A5], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: ["A5 generated artefact inspection remains environment-blocked in this checkout: no PDF/XML/build.log artefacts were present under groundtruth/corpus/latex, so the human-local generation result cannot be verified here. Non-blocked T2 coverage gaps identified by review were addressed with mocked tests for discovery, --doc filtering, commands, assets, biber, hash skip/force, failures, and source immutability."]
- status: halted

## PR #11 — 2026-05-06T12:27:55Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[run_log.md], tests_pass=[A1], tests_fail_env=[], tests_fail_real=[]
    - T2: files_touched=[run_log.md], tests_pass=[A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[run_log.md], tests_pass=[], tests_fail_env=[A4,A5], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review

## PR #12 — 2026-05-06T14:21:38Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[tools/latex_to_docling.py, run_log.md], tests_pass=[A1,A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T2: files_touched=[tools/latex_to_docling.py, run_log.md], tests_pass=[A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[tests/test_latex_to_docling.py, run_log.md], tests_pass=[A1,A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T4: files_touched=[groundtruth/corpus/latex/**/*.docling.json, groundtruth/corpus/latex/**/*.docling_groundtruth_meta.json, run_log.md], tests_pass=[A4,A5], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review

## PR #13 — 2026-05-06T14:34:03Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[tools/latex_to_docling.py, groundtruth/corpus/latex/**/*.docling.json, groundtruth/corpus/latex/**/*.docling_groundtruth_meta.json, run_log.md], tests_pass=[A1,A2,A3,A4,A5], tests_fail_env=[], tests_fail_real=[]
    - T2: files_touched=[tools/latex_to_docling.py, tests/test_latex_to_docling.py, groundtruth/corpus/latex/**/*.docling_groundtruth_meta.json, run_log.md], tests_pass=[A2,A3,A4,A5], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[tests/test_latex_to_docling.py, run_log.md], tests_pass=[A1,A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T4: files_touched=[groundtruth/corpus/latex/**/*.docling.json, groundtruth/corpus/latex/**/*.docling_groundtruth_meta.json, run_log.md], tests_pass=[A4,A5], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review

## PR #14 — 2026-05-06T14:47:00Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[tools/latex_to_docling.py, groundtruth/corpus/latex/**/*.docling.json, run_log.md], tests_pass=[A1,A2,A3,A4,A5], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[tests/test_latex_to_docling.py, run_log.md], tests_pass=[A1,A2,A3], tests_fail_env=[], tests_fail_real=[]
    - T4: files_touched=[groundtruth/corpus/latex/**/*.docling.json, run_log.md], tests_pass=[A4,A5], tests_fail_env=[], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: []
- status: ready_for_review

## PR #15 — 2026-05-07T06:05:30Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[src/pdf2md/models/ir.py, src/pdf2md/models/__init__.py, tests/test_ir_contracts.py, tests/data/ir_fixtures/page_extraction_ir.min.json, tests/data/ir_fixtures/page_extraction_ir.full.json, tests/data/ir_fixtures/consensus_ir.min.json, tests/data/ir_fixtures/consensus_ir.full.json, tests/data/ir_fixtures/consensus_ir.with_conflicts.json, run_log.md], tests_pass=[A1,A2,A3,A4,A5], tests_fail_env=[A6], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: ["python -m pip install -e . (editable install of this checkout only, no new dependency)"]
- blockers: ["A6 whole-suite command pytest tests/ -q is environment-blocked in this checkout: collection fails before running tests because tests/test_compile_latex_groundth.py cannot import top-level tools, tests/test_latex_groundtruth_sources.py cannot import top-level tests, and tests/test_groundtruth_e2e.py requires missing .current/latex_docling_groundtruth/batch_001 fixtures. A diagnostic rerun with PYTHONPATH=.:src resolves the top-level import issues but still fails on the missing .current/latex_docling_groundtruth/batch_001 fixture directory. The targeted IR contract suite and schema/fixture checks passed."]
- status: ready_for_review

## PR #16 — 2026-05-07T06:53:32Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[pyproject.toml, pdf2md/__init__.py, tests/__init__.py, run_log.md], tests_pass=[A1,A2,A3,A4,A5], tests_fail_env=[A6], tests_fail_real=[]
- dependencies_added: []
- external_tools_used: []
- blockers: ["The exact PR #15 review issue could not be solved while preserving the original plan whitelist: making `python -c ... from pdf2md...` work without an editable install requires a repository-level import shim outside the IR whitelist, and making `pytest tests/ -q` resolve repository-local `tests` imports requires a test package marker/PYTHONPATH configuration outside that whitelist. The targeted import/schema/fixture checks now pass without `pip install -e .`; whole-suite collection now proceeds past import-path failures and remains environment-blocked only by the absent `.current/latex_docling_groundtruth/batch_001` fixture directory."]
- status: ready_for_review

## PR #17 — 2026-05-07T07:14:43Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[README_latex_docling_groundtruth.md, generate_latex_docling_groundtruth.py, latex_to_pre_docling_groundtruth.py, run_latex_docling_backends.sh, scripts/local_build_docling_fixtures.sh, tests/groundtruth_paths.py, tests/conventions/test_backend_patterns.py, tests/docling_groundtruth/contracts/batch_001/linked_sections_figures/expected_docling_contract.json, tests/docling_groundtruth/contracts/batch_001/linked_sections_figures/expected_semantic_contract.json, tests/docling_groundtruth/contracts/batch_001/lists_footnotes_tables/expected_docling_contract.json, tests/docling_groundtruth/contracts/batch_001/lists_footnotes_tables/expected_semantic_contract.json, tests/test_groundtruth_e2e.py, tests/test_groundtruth_regressions.py, tests/test_latex_groundtruth_sources.py, tests/test_mock_backend_schema.py, validate_latex_docling_groundtruth.py, run_log.md], tests_pass=[groundtruth_reference_scan, groundtruth_targeted_tests, validate_latex_docling_groundtruth, ir_contracts], tests_fail_env=[], tests_fail_real=[whole_suite_backend_compat]
- dependencies_added: []
- external_tools_used: []
- blockers: ["Historical references in run_log.md/current_plan.md were not rewritten; active code, tests, scripts, and docs no longer reference .current/latex_docling_groundtruth or tests/docling_groundtruth/latex_sources outside the canonical groundtruth/corpus/latex corpus. Whole-suite pytest now reaches pre-existing backend compatibility failures unrelated to groundtruth path migration: missing backend/mineru/test_visual.pdf, missing backend/mineru/run_mineru.py and backend/paddleocr/run_paddleocr.py, and backend/deepseek API mismatches expected by tests/test_run_backends_config.py."]
- status: ready_for_review

## PR #18 — 2026-05-07T08:01:54Z — mode: agent
- tasks_attempted:
    - T1: files_touched=[README_latex_docling_groundtruth.md, generate_latex_docling_groundtruth.py, latex_to_pre_docling_groundtruth.py, tests/test_latex_groundtruth_generator.py, tests/test_latex_pre_docling_groundtruth.py, run_log.md], tests_pass=[generate_help_no_batch_count, generate_existing_corpus_dirs, groundtruth_reference_scan, validate_latex_docling_groundtruth, targeted_groundtruth_tests, ir_contracts, py_compile], tests_fail_env=[], tests_fail_real=[whole_suite_backend_compat]
- dependencies_added: []
- external_tools_used: []
- blockers: ["Whole-suite pytest still fails on pre-existing backend compatibility/test-asset issues unrelated to the generate_latex_docling_groundtruth.py batch/count change: missing backend/mineru/test_visual.pdf, missing backend/mineru/run_mineru.py and backend/paddleocr/run_paddleocr.py, and backend/deepseek API mismatches expected by tests/test_run_backends_config.py."]
- status: ready_for_review
