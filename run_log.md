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

## PR #1 — 2026-05-23T20:45:00Z — mode: agent
- tasks_attempted:
    - A1 (pipeline skeleton + path model): files_touched=[src/pdf2md/pipeline/__init__.py (new), src/pdf2md/pipeline/artifacts.py (extended), src/pdf2md/pipeline/runner.py (new), src/pdf2md/pipeline/io.py (new), src/pdf2md/pipeline/reporting.py (new)]; tests_pass=[10 tests in tests/test_mvp_pipeline_reporting.py + 4 in tests/test_mvp_pipeline_runner.py covering stage state, path layout, manifest writing]; tests_fail_env=[]; tests_fail_real=[].
    - A2 (one-document MVP runner): files_touched=[src/pdf2md/pipeline/runner.py, tools/run_mvp_pipeline.py (new), tests/test_mvp_pipeline_runner.py (new), tests/test_mvp_pipeline_cli.py (new)]; tests_pass=[5 tests in TestRunOneDocument + 8 tests in TestModeSelection+TestOneDocumentMode in test_mvp_pipeline_cli.py]; supports --pdf, --out-dir, --work-dir (defaults to <out-dir>/work), --backends, --strict, --verbose, --timeout-seconds; produces pipeline_manifest.json, pipeline_summary.txt, stage_status.json, plus the five export artefacts under <out-dir>; skips downstream stages with reason=upstream_blocked when a stage is blocked or fails.
    - A3 (corpus/subset mode + MVP readiness reporting): files_touched=[src/pdf2md/pipeline/runner.py, src/pdf2md/pipeline/reporting.py, src/pdf2md/pipeline/io.py, tools/run_mvp_pipeline.py, tests/test_mvp_pipeline_runner.py, tests/test_mvp_pipeline_cli.py, tests/test_mvp_pipeline_reporting.py, tests/data/mvp_pipeline_fixtures/sample_corpus/doc_{a,b}/{,doc_*.pdf}]; tests_pass=[6 tests in TestRunCorpus + 3 tests in TestCorpusMode]; supports --corpus-root, --max-documents, --document-list, plus mutual exclusion with --pdf; produces mvp_corpus_evaluation.json + mvp_corpus_summary.txt at top-level; per-document nested under documents/<doc_id>/; classifies each document as passed/passed_with_warnings/failed/blocked/skipped; classifies the run as MVP_ready/MVP_ready_with_warnings/MVP_not_ready/diagnostic_only.
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_mvp_pipeline_runner.py tests/test_mvp_pipeline_cli.py tests/test_mvp_pipeline_reporting.py -q` → 32 passed (all new)
    - `conda run -n pdf2md pytest tests/ -q` → 843 passed, 212 skipped (environmental), 0 failed
- cli_smoke:
    - `tools/run_mvp_pipeline.py --help` → prints the full one-document + corpus-mode usage cleanly; mode mutual exclusion enforced by argparse.
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- conditional_file_changes: none (src/pdf2md/cli/main.py is untouched per the plan's "no public CLI hardening" hard constraint)
- stage_chain_design:
    Seven canonical stages in order: backend_smoke -> connector_canonical -> connector_validation -> entity_proposal_validation -> consensus -> linked_structure -> export. Each stage is a callable that returns a payload dict; the runner records a StageRecord per call and reduces the sequence into a per-document DocumentResult. Stage callables are dependency-injected via _StageOverrides so unit tests bypass real backends.
- backend_execution_isolation:
    The backend_smoke stage flows through the existing `pdf2md.local.backend_smoke.build_backend_smoke_report` (which uses subprocess via `pdf2md.backends.runner.run_configured_backends`) to honour conda environment isolation. All downstream stages call module-level entry points directly.
- blockers: []
- status: ready_for_review
