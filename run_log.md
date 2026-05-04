# Run log

Append-only log of agent-mode PRs for the current plan. Reset only by feedback mode under `archive plan`.

## Entry format

    ## PR #N — <ISO timestamp> — mode: agent
    - tasks_completed:
        - T<k>: files_touched=[...], tests_pass=[...], tests_fail_env=[...], tests_fail_real=[...]
    - blockers: []
    - status: in_progress | ready_for_review | halted

(No PRs yet.)

## PR #1 — 2026-05-04T16:22:41Z — mode: agent
- tasks_completed:
    - T1: files_touched=[], tests_pass=[], tests_fail_env=[], tests_fail_real=[]
- blockers:
    - Missing execution mode declaration in required format (`mode: agent` on first line of invocation) per `agent.md`; halted before modifying plan-scoped files.
- status: halted

## PR #2 — 2026-05-04T16:30:00Z — mode: agent
- tasks_completed:
    - T1: files_touched=[groundtruth/corpus/latex/linked_sections_figures/linked_sections_figures.tex, groundtruth/corpus/latex/linked_sections_figures/meta.toml, groundtruth/corpus/latex/lists_footnotes_tables/lists_footnotes_tables.tex, groundtruth/corpus/latex/lists_footnotes_tables/meta.toml], tests_pass=[], tests_fail_env=[], tests_fail_real=[]
    - T2: files_touched=[scripts/compile_corpus.py], tests_pass=[A1,A2], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[scripts/certify_corpus.py], tests_pass=[A3], tests_fail_env=[], tests_fail_real=[]
    - T4: files_touched=[latex_to_pre_docling_groundtruth.py, generate_latex_docling_groundtruth.py, validate_latex_docling_groundtruth.py, compare_pre_docling_groundtruth.py, run_latex_docling_backends.sh], tests_pass=[A5], tests_fail_env=[], tests_fail_real=[]
    - T5: files_touched=[README_latex_docling_groundtruth.md, .gitignore], tests_pass=[], tests_fail_env=[], tests_fail_real=[]
- blockers:
    - A4 currently has no integration test case implementation (`-k integration` deselected all tests).
- status: ready_for_review

## PR #3 — 2026-05-04T16:40:00Z — mode: agent
- tasks_completed:
    - T2: files_touched=[scripts/compile_corpus.py], tests_pass=[A1,A2], tests_fail_env=[], tests_fail_real=[]
    - T3: files_touched=[scripts/certify_corpus.py], tests_pass=[A3], tests_fail_env=[], tests_fail_real=[]
    - T5: files_touched=[tests/test_corpus_tooling.py], tests_pass=[A5], tests_fail_env=[A4], tests_fail_real=[]
- blockers: []
- status: ready_for_review
