# Current plan

## Goal

Collect every `*.tex` file present in this repository and copy it into the canonical ground-truth corpus layout at `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`, with one document directory per copied source. The canonical corpus becomes the single source of truth for LaTeX-based ground truth fixtures.

## Whitelist

Files the agent may create or modify under this plan. Anything else is forbidden.

- `groundtruth/corpus/latex/**`
- `create_latex_examples.sh`                              (for deletion after migration)
- `run_log.md`

## Tasks

### T1 — Repository-wide LaTeX corpus migration

Find all repository files matching `*.tex` (including files under `.current/latex_docling_groundtruth/**` and any other subdirectory), and copy each source into canonical layout as:

- `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`

Where `<doc_id>` is a stable, collision-free identifier derived from the source path.

For each copied document:
- preserve the exact source `.tex` content (byte-for-byte),
- include a `meta.toml` alongside each canonical `.tex`,
- keep canonical tree flat at one directory per `doc_id`.

After migration, verify the tree structure and content equality before moving to Plan 2.

Files: `groundtruth/corpus/latex/**`, `create_latex_examples.sh`.

## Tests

Tests are automated by default. A test re-tagged `human` in `run_log.md` after a verifiable environmental failure is reported but does not block `ready_for_review`.

### A1 — Enumerate all repository `.tex` sources
- command: `rg --files -g '*.tex'`
- pass: command lists all `.tex` sources to be migrated.

### A2 — Canonical layout verification
- command: `find groundtruth/corpus/latex -mindepth 2 -maxdepth 2 -type f | sort`
- pass: every canonical document directory contains `<doc_id>.tex` and `meta.toml` only.

### A3 — Content equality verification
- command: implementation-defined automated check (script or shell) comparing each source `*.tex` against its copied canonical `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`.
- pass: all copied canonical files are content-identical to their original sources.

### H1 — Manual tree review (human)
- tag: human.
- command: visual inspection of `groundtruth/corpus/latex/`.
- pass: human confirms layout matches the spec before proceeding to Plan 2.

## Status

- T1: done

## PR_reviews

(Empty. Filled by review mode, one section per PR.)

## PR_review #1

- verdict: fail
- whitelist_violations: []
- test_contract_violations: ["T1 was marked attempted, but gating automated test A1 was not executed and no environmental failure was recorded."]
- dependency_violations: []
- tasks_promoted: []
- notes:
  - "`run_log.md` was the only modified file in PR #1 and is allowed by agent protocol as whitelisted-by-default evidence log."
  - "PR #1 correctly recorded a blocker and halted status, but test execution requirements for an attempted task were not met."
  - "No `## Status` section exists in `current_plan.md`; therefore no task state promotion could be applied in this review."

## Feedback

(Empty. Filled by feedback mode in response to PR_reviews and human input.)

## Feedback #1

- closes: PR_review #1
- summary:
  - Updated the plan to remove ambiguity about next-task selection by adding `## Status` with `T1: pending`.
  - Expanded migration scope from generator-embedded fixtures to all repository `*.tex` files, explicitly including `.current/latex_docling_groundtruth/**`.
  - Added explicit automated checks for source enumeration (A1), canonical folder structure (A2), and source-to-copy content equality (A3).
- rationale:
  - Human feedback requested repository-wide `*.tex` copying and a primary verification workflow based on listing files, confirming agreed folder structure, and confirming copied content equality.


## PR_review #2

- verdict: pass
- whitelist_violations: []
- test_contract_violations: []
- dependency_violations: []
- tasks_promoted: [T1]
- notes:
  - "Modified files in PR #2 were restricted to `groundtruth/corpus/latex/**` and `run_log.md`, both allowed by the plan whitelist."
  - "`run_log.md` includes a single PR #2 entry with task evidence and reported A1/A2/A3 automated test passes for attempted task T1."
  - "No dependency additions or environment-modifying external tools were reported."
