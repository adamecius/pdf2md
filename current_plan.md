# Current plan

## Goal

Remove the legacy LaTeX and PDF fixture files from:

- `.current/docling_groundtruth/**`
- `.current/latex_docling_groundtruth/**`

Then scan the whole repository for any remaining references to those deleted `.tex` or `.pdf` files. Any reference found must be redirected to the canonical corpus location under:

- `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`

The canonical `groundtruth/corpus/latex/**` tree remains the only accepted source of truth for LaTeX ground-truth fixtures.

To keep `run_log.md` compact, large intermediate diagnostic listings must be written to `booking.log` during execution and removed before task completion once verification is complete.

## Whitelist

Files the agent may create, modify, or delete under this plan. Anything else is forbidden unless first recorded as a matched legacy-reference file in `run_log.md`.

- `.current/docling_groundtruth/**/*.tex`                  deletion only
- `.current/docling_groundtruth/**/*.pdf`                  deletion only
- `.current/latex_docling_groundtruth/**/*.tex`            deletion only
- `.current/latex_docling_groundtruth/**/*.pdf`            deletion only
- `groundtruth/corpus/latex/**`
- `run_log.md`
- `booking.log`                                           create/update/delete during diagnostic-only evidence capture
- Files discovered by the reference scan as containing legacy `.current/.../*.tex` or `.current/.../*.pdf` references, only for replacing those references with their canonical `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex` path. Each such file must be listed in `run_log.md` before modification.

## Tasks

### T2 — Delete legacy `.tex` and `.pdf` files from `.current`

Find and delete every `.tex` and `.pdf` file under:

- `.current/docling_groundtruth/**`
- `.current/latex_docling_groundtruth/**`

Only files matching these patterns may be deleted:

- `.current/docling_groundtruth/**/*.tex`
- `.current/docling_groundtruth/**/*.pdf`
- `.current/latex_docling_groundtruth/**/*.tex`
- `.current/latex_docling_groundtruth/**/*.pdf`

Directories may be left in place unless they become clearly obsolete and are explicitly allowed by a later plan.

Files: `.current/docling_groundtruth/**/*.tex`, `.current/docling_groundtruth/**/*.pdf`, `.current/latex_docling_groundtruth/**/*.tex`, `.current/latex_docling_groundtruth/**/*.pdf`, `run_log.md`, `booking.log` (temporary evidence file, must be deleted before task end).

### T3 — Repository-wide legacy reference scan and redirection

Build the full list of deleted legacy `.tex` and `.pdf` source paths from within:

- `.current/docling_groundtruth/**`
- `.current/latex_docling_groundtruth/**`

For each deleted file, search every repository file for references to:

- the full legacy path,
- the relative legacy path without leading `./`,
- the filename,
- any obvious path fragments rooted at `.current/`.

If any reference is found, update the referencing file so that it points to the corresponding canonical LaTeX document under:

- `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`

Where `<doc_id>` must match the canonical document directory already created during T1.

For deleted `.pdf` references, redirect to the corresponding canonical `.tex` file when the reference is part of the ground-truth fixture workflow. If a `.pdf` reference semantically requires an actual PDF file and cannot be safely redirected to LaTeX, record it as a blocker in `run_log.md` and do not mark T3 done.

Files: reference-bearing files discovered by the scan, `groundtruth/corpus/latex/**`, `run_log.md`, `booking.log` (temporary evidence file, must be deleted before task end).

## Tests

Tests are automated by default. A test re-tagged `human` in `run_log.md` after a verifiable environmental failure is reported but does not block `ready_for_review`.

### A4 — Enumerate legacy `.tex` and `.pdf` deletion candidates

- command:
  ```sh
  find .current/docling_groundtruth .current/latex_docling_groundtruth \
    -type f \( -name '*.tex' -o -name '*.pdf' \) | sort
pass: command lists every legacy .tex and .pdf file targeted for deletion; the full list is recorded in `booking.log` before deletion; `run_log.md` includes a concise pointer and summary count only.
A5 — Confirm legacy .tex and .pdf files were deleted

command:

find .current/docling_groundtruth .current/latex_docling_groundtruth \
  -type f \( -name '*.tex' -o -name '*.pdf' \) | sort
pass: command returns no files.
A6 — Repository-wide reference scan for deleted legacy paths and names
command: implementation-defined automated check that searches every repository file for every deleted .tex and .pdf legacy reference pattern.
required search scope: whole repository.
required target patterns: all deleted .tex and .pdf files formerly located under .current/docling_groundtruth/** and .current/latex_docling_groundtruth/**.
pass: no repository file contains unresolved references to deleted .current/.../*.tex or .current/.../*.pdf files.
A7 — Canonical redirection verification
command: implementation-defined automated check.
pass:
every updated reference points to an existing canonical file under groundtruth/corpus/latex/<doc_id>/<doc_id>.tex;
every referenced canonical .tex file exists;
no updated reference points back into .current/docling_groundtruth/** or .current/latex_docling_groundtruth/**.
H2 — Manual reference review (human)
tag: human.
command: visual inspection of the `run_log.md` summary plus `booking.log` evidence (if present during run) for deleted files, matched references, replacements, and any blockers.
pass: human confirms that all legacy .tex and .pdf references were either correctly redirected or explicitly blocked, and that `booking.log` was deleted after verification.
Status
T1: done
T2: done
T3: pending
PR_reviews

(Empty. Filled by review mode, one section per PR.)

Feedback

(Empty. Filled by feedback mode in response to PR_reviews and human input.)

## PR_review #3
- verdict: fail
- whitelist_violations: []
- test_contract_violations:
  - A4 failed contract: candidate list was not recorded in `run_log.md` before deletion, so the stated pass condition for A4 was not met.
- dependency_violations: []
- tasks_promoted: []
- notes:
  - Required check #1 passed: modified paths were within whitelist patterns (legacy `.tex`/`.pdf` deletions plus `run_log.md`).
  - Required check #2 passed: attempted task T2 has explicit evidence in `run_log.md` PR #3 entry.
  - Required check #3 failed: not all gating automated tests for T2 passed; A4 is explicitly recorded as a real failure.
  - Required check #4 passed: no tests were re-tagged as human.
  - Required check #5 passed: no dependencies added and no external tools used.
  - Required check #6 passed: no silent retries observed in the PR evidence.
  - Required check #7 outcome: T2 is not eligible for promotion to `done` because A4 failed and verdict is `fail`.


## Feedback #3
- Responding to `PR_review #3`.
- Accepted change: diagnostic outputs that may be very large should be written to `booking.log` first, not expanded into `run_log.md`.
- Process update: agent should run diagnostics, keep full path lists in `booking.log`, write only compact counts/pointers in `run_log.md`, and remove `booking.log` at the end after dangling-reference verification.
- Status impact: no task demotion applied; `T2` and `T3` remain pending until re-attempt under updated evidence flow.


## PR_review #4
- verdict: pass
- whitelist_violations: []
- test_contract_violations: []
- dependency_violations: []
- tasks_promoted: [T2]
- notes:
  - Required check #1 passed: PR #4 modified only `run_log.md`; temporary `booking.log` usage is explicitly allowed by whitelist and was removed.
  - Required check #2 passed: attempted task T2 has explicit evidence in `run_log.md` PR #4 entry.
  - Required check #3 passed: gating automated tests for T2 (A4, A5) are both recorded as passed.
  - Required check #4 passed: no re-tagged human tests in this PR.
  - Required check #5 passed: no dependencies added and no external tools used.
  - Required check #6 passed: no silent retries observed in PR #4 evidence.
  - Required check #7 passed: T2 is eligible and promoted to `done`.


## PR_review #4
- verdict: pass
- whitelist_violations: []
- test_contract_violations: []
- dependency_violations: []
- tasks_promoted: []
- notes:
  - Re-review confirms the most recent agent-mode PR is PR #4 in `run_log.md`, with T2 evidence and no blocker.
  - Modified file set for PR #4 was constrained to `run_log.md`; temporary `booking.log` usage/removal is permitted by whitelist and task text.
  - Gating automated tests for T2 (A4 and A5) are both recorded as passed in PR #4; no env re-tags were used.
  - No dependencies or environment-modifying tools were added/used.
  - No silent retries were evidenced in PR #4 log entry.
  - T2 was already promoted to `done` by prior pass review; no additional status change is needed in this re-review.


## PR_review #5
- verdict: fail
- whitelist_violations: []
- test_contract_violations:
  - A6 failed: unresolved legacy references remained (`tests_fail_real=[A6]`) and blocker was recorded for non-writable `.current/**` JSON files under the present whitelist constraints.
- dependency_violations: []
- tasks_promoted: []
- notes:
  - Required check #1 passed: modified files (`groundtruth/corpus/latex/**`, `run_log.md`) are within whitelist scope; temporary `booking.log` usage/deletion is also allowed.
  - Required check #2 passed: attempted task T3 has explicit evidence in `run_log.md` PR #5 entry.
  - Required check #3 failed: gating automated tests for T3 did not all pass (A7 pass, A6 real fail).
  - Required check #4 passed: no human re-tagging occurred.
  - Required check #5 passed: no dependencies or external tools were added/used.
  - Required check #6 passed: no silent retries are evidenced in PR #5 logs.
  - Required check #7 outcome: T3 is not eligible for promotion to `done` because verdict is fail and A6 failed.
