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
