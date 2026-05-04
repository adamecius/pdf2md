# Current plan

## Goal

Migrate every ad-hoc `.tex` file (from `create_latex_examples.sh` and any other generators) into the new canonical layout `groundtruth/corpus/latex/<doc_id>/`. This becomes the single source of truth for all LaTeX-based ground truth.

## Scope and non-goals

In scope: creating the new folder tree, moving/copying `.tex` files, adding `meta.toml` for each document, placing optional `.bib` and `assets/`.

Out of scope: any compilation, certification, or pipeline changes. Those come in later plans.

## Whitelist

Files the agent may create, modify, move, or delete under this plan. Anything else is forbidden.

Create or write:
- `groundtruth/corpus/latex/**`                           (corpus tree, one folder per document)

Delete (after successful migration):
- `create_latex_examples.sh`                              (will be replaced in Plan 2)

No other files may be touched.

## Per-document layout (under `groundtruth/corpus/latex/<doc_id>/`)

- `<doc_id>.tex`             source of truth, version-controlled
- `<doc_id>.bib`             optional, version-controlled if present
- `assets/`                  optional, for included figures
- `meta.toml`                version-controlled metadata

`meta.toml` schema (minimal for this plan):

    document_id = "<doc_id>"
    documentclass = "article"
    expected_features = ["equations", "figures", "tables", "footnotes", "references", "bibliography"]
    expected_counts = { sections = 3, figures = 2, tables = 1, equations = 5, footnotes = 2 }
    notes = "free text"

Every `.tex` must start with `\DocumentMetadata{testphase=phase-III, pdfstandard=ua-2}` before `\documentclass`.

## Tasks

### T1 — Migrate corpus to canonical layout

Extract every `.tex` currently embedded in `create_latex_examples.sh` (and any other generator scripts) into versioned files under `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`.

For each document:
- Ensure `\DocumentMetadata{testphase=phase-III, pdfstandard=ua-2}` is the first non-comment line.
- Ensure `\usepackage{hyperref}` is present (or implied by the metadata mode).
- Write a `meta.toml` with declared counts derived by inspection of the `.tex`.
- If a `.bib` or `assets/` folder is referenced, place them in the correct location.

After migration, verify the tree structure manually before moving to Plan 2.

Files: `groundtruth/corpus/latex/**`
