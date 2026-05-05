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
