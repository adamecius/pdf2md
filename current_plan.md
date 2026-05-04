# Current plan

## Goal

Migrate every ad-hoc `.tex` file (from `create_latex_examples.sh` and any other generators) into the new canonical layout `groundtruth/corpus/latex/<doc_id>/`. This becomes the single source of truth for all LaTeX-based ground truth.

## Whitelist

Files the agent may create or modify under this plan. Anything else is forbidden.

- `groundtruth/corpus/latex/**`
- `create_latex_examples.sh`                              (for deletion after migration)

## Tasks

### T1 — Migrate corpus to canonical layout

Extract every `.tex` currently embedded in `create_latex_examples.sh` (and any other generator scripts) into versioned files under `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`.

For each document:
- ensure `\DocumentMetadata{testphase=phase-III, pdfstandard=ua-2}` is the first non-comment line,
- ensure `\usepackage{hyperref}` is present (or implied by the metadata mode),
- write a `meta.toml` with declared counts derived by inspection of the `.tex`,
- if a `.bib` or `assets/` folder is referenced, place them in the correct location.

After migration, verify the tree structure manually before moving to Plan 2.

Files: `groundtruth/corpus/latex/**`, `create_latex_examples.sh`.

## Tests

Tests are automated by default. A test re-tagged `human` in `run_log.md` after a verifiable environmental failure is reported but does not block `ready_for_review`.

### A1 — Corpus layout verification
- command: `ls -R groundtruth/corpus/latex/ | head -20`
- pass: every document has `<doc_id>.tex` + `meta.toml`; no old ad-hoc files remain.

### H1 — Manual tree review (human)
- tag: human.
- command: visual inspection of `groundtruth/corpus/latex/`.
- pass: human confirms layout matches the spec before proceeding to Plan 2.

## PR_reviews

(Empty. Filled by review mode, one section per PR.)

## Feedback

(Empty. Filled by feedback mode in response to PR_reviews and human input.)
