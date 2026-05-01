# pdf2md

## 1) Project description
pdf2md is a multi-backend PDF-to-Markdown conversion system. It runs configured extraction backends, preserves their raw outputs, normalises their page-level building blocks into a shared extraction IR, compares those blocks page by page to detect agreement and conflicts, and then compiles the agreed result into a rich semantic document structure for Markdown and other exports.

The project intentionally separates early extraction comparison from later semantic document construction. Low-level page comparison is performed before compiling into richer formats such as DoclingDocument, Pandoc AST, JSON, or final Markdown.

## 2) Architecture direction
The intended processing flow is:

```text
PDF
  -> backend raw outputs
  -> low-level page extraction IR
  -> page-by-page block comparison
  -> page consensus IR
  -> whole-document semantic compilation
  -> rich document format
  -> Markdown / JSON / DoclingDocument / Pandoc export
```

Important design rule: comparison happens at the earliest practical extraction stage, page by page, before semantic compilation.

## 3) Current stage
This repository currently provides backend wrappers and config-driven backend orchestration.

## 4) What exists now
- Core `pdf2md` package in `src/pdf2md`
- Backend wrappers under `backend/`
- Config-driven `run-backends` CLI command
- Minimal canonical schema (`Document -> Page -> Block`) with `BBox`, `SourceRef`, and `Flag`
- Placeholder `convert_pdf` path that currently runs one backend and one adapter into `Document`

## 5) What is not implemented yet
- Full adapter coverage
- PageExtractionIR normalisation pipeline
- Page-level comparison and candidate grouping
- PageConsensusIR and agreement/conflict resolution
- Whole-document semantic compilation stage
- Final full convert pipeline and rich export targets

## 6) Setup
Install the central package:

```bash
python -m pip install -e .
```

## 7) Config
Copy the example config and edit backend settings:

```bash
cp pdf2md.backends.example.toml pdf2md.backends.toml
```

Then update enabled backends, model paths, and environment variables.

## 8) Running
Run configured and enabled backends only:

```bash
pdf2md run-backends test.pdf --config pdf2md.backends.toml
```

No backend runs unless it appears in config and is enabled.

## 9) Output folder
Runs are stored under:

```text
.tmp/<run-name>/
```

## 10) Safety
- Only configured and enabled backends run.
- API backends do not run unless explicitly configured.
- Local `pdf2md.backends.toml` is gitignored.

## 11) Tests
```bash
python -m pytest -q tests/test_models_and_rendering.py tests/smoke/test_backend_clis.py tests/test_run_backends_config.py
```

## 12) Near-term plan focus
The next planning milestone is to define the page-level extraction IR and consensus-ready architecture while keeping current backend runner behavior intact and avoiding heavy new dependencies.
