# Plan 17 — Docling Export Wiring Hardening

Status:
draft

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Linked ROADMAP phase:
Phase 7 — Post-MVP export fidelity and downstream-tool compatibility

Current roadmap estimate:
Post-MVP refinement; does not move the pre-MVP percentage. Lifts the
predicted-vs-expected docling JSON match from "structurally close but
fails strict `docling_core` validation" to "passes `docling_core` strict
validation on aligned LaTeX-derived inputs".

Owner:
Agent team / human reviewer

Sequence:
Plan 17 of the post-MVP refinement track. The pre-MVP sequence (Plans
8–16) is complete.

Previous plan:
Plan 16 — End-to-End Runner and MVP Corpus Evaluation (human_verified)

Required previous plan status:
human_verified

Next plan after completion:
Plan 18+ — Production packaging, public CLI hardening, performance
optimisation (not yet drafted).

Branch name:
plan-17-docling-export-wiring-hardening

---

## 1. Purpose

The Plan 15 → 16 aligned-groundtruth comparison surfaced **six concrete
defects in the export wiring** (`src/pdf2md/export/docling.py` and the
upstream block-kind classification used by `src/pdf2md/connectors/common.py`).
Plan 17 fixes those defects so the predicted Docling JSON passes
`docling_core` strict validation against a representative subset of the
LaTeX-derived corpus groundtruth, with matching label distributions on
documents whose content is fully OCR-recoverable.

The six defects, in priority order:

1. `origin.binary_hash` / `origin.filename` are never populated. Every
   predicted docling JSON fails `docling_core` strict validation. The
   runner already has the source PDF path available — it just isn't
   threaded into the export `origin` block.
2. `BlockKind.PARAGRAPH` is mapped to docling label `"paragraph"` which
   is not a valid `docling_core.types.doc.DocItemLabel`. Should be
   `"text"`.
3. The connector's heuristic block classification (`classify_block` in
   `src/pdf2md/connectors/common.py`) only recognises Markdown-style
   `#` headings. PaddleOCR PP-StructureV3 emits headings as plain bold
   text or as `<h1>...</h1>` HTML; neither path triggers a `HEADING`
   classification, so `section_header` / `title` are missing from every
   predicted doc.
4. `\footnote{...}` content blends into the host paragraph in the OCR
   markdown; the connector never emits a `FOOTNOTE` block.
5. Boxed/figure regions arrive as embedded `<div><img src="..."/></div>`
   HTML inside paragraph text. They are never lifted into the docling
   `pictures` list.
6. `src/pdf2md/export/docling.py` writes a hard-coded `version = "1.7.0"`;
   the current corpus groundtruth uses `1.10.0`. Downstream tooling that
   pins on version may break.

This is a post-MVP refinement plan. The MVP boundary reached by Plan 16
remains valid: the pipeline still produces all five export artefacts and
the runner still classifies passing documents as `MVP_ready_with_warnings`.
This plan moves the predicted output closer to `docling_core` schema parity
without redesigning the export architecture.

The core question is:

```text
After this plan, does the aligned predicted docling JSON for a representative
corpus document pass docling_core strict validation, and does its label
distribution match the corpus groundtruth on title / section_header /
text / footnote / caption / picture / formula?
```

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

README.md is the public entry point.

PLAN_TEMPLATE.md is the standard format for executable plans.

current_plan.md is the active execution contract for agents.

next_plan.md is the next planned execution contract.

history.md records completed milestones after human verification.

run_log.md is append-only and implicitly allowed when required by agent.md.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-17-docling-export-wiring-hardening
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and
   report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 16 has been
   marked human_verified and archived.
8. Do not mark this plan human_verified or finished. Only the human
   reviewer may do that.

Main repository environment:

```text
pdf2md
```

Repository-level commands must run using:

```bash
conda run -n pdf2md python <command>
```

---

## 4. Scope, constraints, and dependencies

In scope:

1. Thread `source_pdf` from the runner into `origin.filename` and compute
   `origin.binary_hash` (sha256) in the export module.
2. Replace the literal `BlockKind` → docling label map in
   `src/pdf2md/export/docling.py` so every emitted label belongs to
   `docling_core.types.doc.DocItemLabel`.
3. Extend `classify_block()` (or add a sibling helper) in
   `src/pdf2md/connectors/common.py` to recognise PaddleOCR-style
   non-Markdown headings: short uppercase or title-case lines under N
   characters, `<h1>..<h6>` HTML, and bold-only lines.
4. Add a footnote post-processing pass that extracts trailing
   `\footnote{...}`-derived spans into a dedicated `FOOTNOTE` block.
5. Add a picture post-processing pass that lifts inline
   `<img src="..."/>` HTML out of paragraph text into a `picture` entity
   in the docling JSON.
6. Bump the schema version literal to match the latest `docling_core`
   stable version supported by the locally installed package; record the
   chosen version constant in one place.
7. Add tests covering every fix, plus an end-to-end aligned-groundtruth
   test that compiles `linked_sections_figures.tex`, runs the MVP
   pipeline, and asserts `docling_core` strict validation passes.

Out of scope:

1. Public Typer CLI hardening (still Plan 18+).
2. Backend script changes (PaddleOCR / mineru / deepseek scripts).
3. Reading-order optimisation beyond what the existing pipeline produces.
4. Multi-page picture stitching.
5. Embedded-text / tagged-PDF candidate generation.
6. Real calibration prior generation (Plan 12-style work) — that's a
   prerequisite for production-quality consensus, but is a separate
   plan.
7. Production deployment, web / API surfaces.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as `human_verified` or `finished`.
3. Stage modules outside the export+connector whitelist must not change.
4. Plan 17 must reuse `docling_core` as the schema source of truth; do
   not invent new DocItemLabel values.
5. Plan 17 must not break the 32 Plan 16 MVP-pipeline tests or any
   Plan 15 export test. Every change must keep `pytest tests/ -q` green.
6. Plan 17 must not silently coerce unknown block kinds into a default
   label; unmappable cases must raise a warning recorded on the export
   result.
7. The fix for `origin.binary_hash` must compute the sha256 lazily and
   cache it, so it does not add measurable runtime on the existing
   sub-second `export` stage.
8. Aligned-groundtruth tests must use the existing `tools/compile_latex_groundth.py`
   so the tests automatically benefit from future LaTeX-tool fixes.

Allowed Python dependencies:

```text
docling_core (optional, already declared)
none beyond existing repository dependencies
```

Allowed external tools for automated tests:

```text
lualatex / latexml / kpsewhich via tools/compile_latex_groundth.py
  (only when running the optional aligned-groundtruth e2e test)
```

Allowed environment-modifying commands:

```text
none
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these implementation and test files:

```text
src/pdf2md/export/docling.py
src/pdf2md/export/io.py
src/pdf2md/export/__init__.py
src/pdf2md/connectors/common.py
src/pdf2md/connectors/__init__.py

tools/run_mvp_pipeline.py
tools/export_linked_docling.py

tests/test_docling_export_wiring.py
tests/test_docling_export.py
tests/test_connector_common.py
tests/test_export_io_cli.py
tests/test_mvp_pipeline_runner.py
tests/test_compile_latex_groundth.py
```

The agent may create test fixtures only under:

```text
tests/data/docling_export_wiring_fixtures/**
```

run_log.md is append-only and implicitly allowed when required by
agent.md.

The agent may create temporary outputs only through CLI execution and
those outputs must not be committed by default.

The agent must not modify these files unless this plan is explicitly
amended by the human reviewer:

```text
README.md
ROADMAP.md
PLAN_TEMPLATE.md
project.md
current_plan.md
next_plan.md
history.md
agent.md
pyproject.toml

config/*

src/pdf2md/local/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/pipeline/*
src/pdf2md/cli/main.py

src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/reporting.py
src/pdf2md/models/*

tools/backend_smoke.py
tools/validate_connectors_page_ir.py
tools/validate_entity_proposals.py
tools/vocabulary_alignment_check.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py
tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py
tools/compile_latex_groundth.py

backend/*
groundtruth/corpus/*
```

If a defect is found outside the whitelist, the agent must stop and
report a blocker rather than modifying those files.

---

## 6. Agent tasks

### Task A1 — `origin.binary_hash` and `origin.filename`

Title:
Populate the docling origin block from the source PDF path.

Goal:
Every exported docling document carries the source PDF's `filename` and
sha256 `binary_hash` so it passes `docling_core` strict validation.

Files allowed:
```text
src/pdf2md/export/docling.py
src/pdf2md/export/__init__.py
tools/run_mvp_pipeline.py
tests/test_docling_export_wiring.py
```

Implementation requirements:

1. Add a `compute_origin(source_pdf: Path | None) -> dict` helper that
   returns `{"filename": str | None, "binary_hash": int, "mimetype":
   "application/pdf"}`. `binary_hash` is the lower 63 bits of the
   sha256 digest (matches the docling-core schema, which uses a
   positive 64-bit int).
2. `build_docling_document()` accepts the new `source_pdf` argument and
   threads it into the `origin` block of the produced document dict.
3. `tools/run_mvp_pipeline.py` passes the PDF path it already has into
   the export stage's `source_pdf` kwarg (already wired in
   `_default_export_stage`, just plumb the actual path through).
4. When `source_pdf` is `None`, fall back to `binary_hash = 0` and
   `filename = "unknown.pdf"` so validation still passes; record an
   `origin_pdf_path_unknown` warning on the export report.

Automated tests required:
```bash
conda run -n pdf2md pytest tests/test_docling_export_wiring.py::TestOriginBlock -q
```

Expected output:
A unit test asserts every produced docling JSON has `origin.filename`
and `origin.binary_hash` populated and passes
`docling_core.types.doc.DoclingDocument.model_validate(...)`.

Human verification required:
no. Covered by H1 + H4.

---

### Task A2 — Map BlockKind to valid DocItemLabel values

Title:
Replace the literal BlockKind → docling label mapping.

Files allowed:
```text
src/pdf2md/export/docling.py
tests/test_docling_export_wiring.py
```

Implementation requirements:

1. Add a `_BLOCK_KIND_TO_LABEL: dict[BlockKind, str]` table mapping every
   `pdf2md.models.ir.BlockKind` value to the closest valid
   `docling_core.types.doc.DocItemLabel` string value:
   - `PARAGRAPH` → `"text"`
   - `HEADING` → `"section_header"` (a future helper distinguishes
     title vs section_header by position; for now everything maps to
     `section_header` except the first heading on page 1, which maps
     to `"title"`).
   - `FORMULA` → `"formula"`
   - `FIGURE` → `"picture"` (used for picture entity emission too)
   - `TABLE` → `"table"`
   - `CAPTION` → `"caption"`
   - `LIST` → `"list_item"`
   - `LIST_ITEM` → `"list_item"`
   - `FOOTNOTE` → `"footnote"`
   - `PAGE_NUMBER` → `"page_footer"` (best-fit; flagged in metadata)
   - `HEADER` → `"page_header"`
   - `FOOTER` → `"page_footer"`
   - `REFERENCE` → `"text"` (with `metadata.reference_role = "body"`)
   - `BIBITEM` → `"text"` (with `metadata.reference_role = "bib_item"`)
   - `CODE` → `"code"`
   - `UNKNOWN` → `"text"` with a `block_kind_unmapped` warning.
2. Document the mapping in a module-level docstring + reference the
   `docling_core.types.doc.DocItemLabel` enum in a comment.
3. Replace every literal `"paragraph"`, `"heading"`, etc. in
   `build_docling_document()` with `_BLOCK_KIND_TO_LABEL[block.kind]`
   lookups.
4. If a block kind is missing from the table, raise a warning on the
   export result and use `"text"` as a fallback.

Human verification required:
no. Covered by H1.

---

### Task A3 — Detect non-Markdown headings (title / section_header)

Title:
Promote OCR-style headings to BlockKind.HEADING during connector
classification.

Files allowed:
```text
src/pdf2md/connectors/common.py
src/pdf2md/connectors/__init__.py
tests/test_connector_common.py
```

Implementation requirements:

1. Extend `classify_block()` so it recognises the following patterns as
   `BlockKind.HEADING` even without `#`:
   - HTML `<h1>...</h1>` through `<h6>...</h6>` tags (any case).
   - Single-line, mostly-uppercase or title-case text under 80 chars
     when followed by a body paragraph in the same page.
   - Lines that begin with `\section`, `\subsection`, `\subsubsection`
     (LaTeX residual).
2. Add a metadata key `heading_level` (1 for top-level / title, 2..N for
   nested) so the export stage can pick `title` for level 1 on page 1.
3. Do not regress the existing markdown `# ` detection — the existing
   test must still pass.
4. Add metadata field `heading_source` ∈ {`markdown_hash`, `html_tag`,
   `latex_command`, `formatting_heuristic`} so failures can be
   diagnosed.

Human verification required:
no. Covered by H1.

---

### Task A4 — Footnote post-processing

Title:
Extract footnote spans into dedicated FOOTNOTE blocks.

Files allowed:
```text
src/pdf2md/connectors/common.py
src/pdf2md/connectors/__init__.py
tests/test_connector_common.py
```

Implementation requirements:

1. After `markdown_to_pages()` builds the per-page block list, walk each
   page and detect footnote markers:
   - Trailing `\footnote{...}` (LaTeX residual).
   - Superscript digit followed by a line break and a same-page
     line beginning with the same digit (Docling-style footnote anchor).
   - Lines whose entire content matches `^\d+\.\s+.*` AND that come
     after a non-trivial paragraph AND whose page position is the
     bottom third of the page (heuristic via block order index).
2. When found, emit a new `BlockKind.FOOTNOTE` block AND replace the
   marker in the host paragraph with a clean anchor (`[^N]`).
3. Carry `metadata.footnote_marker = "N"` and the host block id under
   `metadata.footnote_host_block_id` so the linker can resolve them.

Human verification required:
no. Covered by H1.

---

### Task A5 — Picture post-processing

Title:
Lift inline `<img>` HTML out of paragraph text into picture entities.

Files allowed:
```text
src/pdf2md/connectors/common.py
src/pdf2md/connectors/__init__.py
src/pdf2md/export/docling.py
tests/test_connector_common.py
tests/test_docling_export_wiring.py
```

Implementation requirements:

1. Scan each block's text for `<img\b[^>]*src=...>` matches.
2. For each match, emit a separate `BlockKind.FIGURE` block with
   `metadata.image_src = <src>` and `metadata.image_origin =
   "inline_html"`.
3. Strip the matched `<div>...<img/>...</div>` (or bare `<img>`) from the
   host block's text. If the host block becomes empty, drop it.
4. The export module emits these as docling `pictures` entries with
   `label = "picture"` and a `prov` block carrying the originating
   page reference.

Human verification required:
no. Covered by H1 + H4.

---

### Task A6 — Schema version + final report aggregation

Title:
Bump the docling schema version and surface mapping warnings in the
export report.

Files allowed:
```text
src/pdf2md/export/docling.py
tests/test_docling_export_wiring.py
tests/test_export_io_cli.py
```

Implementation requirements:

1. Compute the schema version at module load from the installed
   `docling_core` package. Fall back to `"1.7.0"` if the package is not
   installed or doesn't expose a version constant.
2. Surface every `block_kind_unmapped`, `origin_pdf_path_unknown`,
   `image_post_processed`, `footnote_lifted`, and `heading_promoted`
   warning on the export report's existing `warnings` list, with
   counts in a new `plan17_wiring_summary` block of the export report.
3. Do NOT add a new top-level disk artefact — the wiring summary lives
   inside `reports/export_report.json`.

Human verification required:
yes. Covered by H4.

---

### Task A7 — End-to-end aligned-groundtruth test

Title:
Add a single integration test that runs the full Plan 9 → 15 chain on
the smallest compilable corpus document and asserts the predicted
docling JSON passes `docling_core` strict validation.

Files allowed:
```text
tests/test_docling_export_wiring.py
tests/data/docling_export_wiring_fixtures/**
```

Implementation requirements:

1. Skip the test cleanly when `docling_core`, `lualatex`, or
   `paddleocr` are unavailable (use `pytest.importorskip` /
   `shutil.which`).
2. When prerequisites are present:
   - Compile `linked_sections_figures.tex` via
     `tools/compile_latex_groundth.py`.
   - Run `tools/run_mvp_pipeline.py` against the compiled PDF with
     `--backends paddleocr`.
   - Load the produced docling JSON and call
     `DoclingDocument.model_validate(...)` on it.
   - Assert no exception is raised.
   - Assert the label distribution contains at least one of
     `section_header` and exactly one `formula`.
3. Mark the test with `pytest.mark.slow` or skip it from the default
   suite — it requires a GPU and ~30 s wall clock.
4. Tag the test as `human` in the test taxonomy when the local env
   lacks GPU; the agent's automated CI run can keep it skipped while
   the human reviewer reruns it on a GPU host.

Human verification required:
yes. Covered by H2.

---

## 7. Human verification checkpoints

### Checkpoint H1 — automated unit tests

Title:
Run automated unit tests for the wiring fixes.

Command:
```bash
conda run -n pdf2md pytest tests/test_docling_export_wiring.py \
    tests/test_connector_common.py tests/test_export_io_cli.py \
    tests/test_mvp_pipeline_runner.py -q
```

Pass criteria:

```text
All tests pass.
Exit code 0.
Every test asserts both that the targeted defect is fixed AND that
existing behaviour for other block kinds is preserved.
```

Fail criteria:

```text
Any test fails.
Any test requires real backend execution to pass.
Any test silently skips its main assertion.
```

Evidence to record:

```text
Paste the pytest output.
Paste the exit code.
```

---

### Checkpoint H2 — aligned-groundtruth e2e test

Title:
Run the optional aligned-groundtruth integration test on GPU.

Preconditions:

- A working CUDA GPU.
- `pdf2md.backends.toml` configured for the paddleocr backend per
  `backend/paddleocr/README.md`.
- TeX Live ≥ 2024 with LuaHBTeX ≥ 1.17.0 (this host: TeX Live 2026 /
  LuaHBTeX 1.24.0).

Command:
```bash
PYTEST_SLOW=1 conda run -n pdf2md pytest \
    tests/test_docling_export_wiring.py::TestAlignedGroundtruth -v
```

Pass criteria:

```text
The compiled PDF exists at the expected path.
The MVP runner reports the document as passed_with_warnings or passed.
The produced docling JSON loads cleanly via
DoclingDocument.model_validate(...).
The label distribution contains section_header at least once.
The label distribution contains formula exactly once.
```

Fail criteria:

```text
docling_core strict validation rejects the predicted JSON.
The predicted JSON contains label "paragraph".
section_header is absent when the source LaTeX has \section{}.
```

Evidence to record:

```text
Paste the pytest output.
Paste the produced docling JSON's first 20 lines.
Paste the `plan17_wiring_summary` block from the export report.
```

---

### Checkpoint H3 — sandbox end-to-end re-run

Title:
Re-run the MVP pipeline through the CLI with the wiring fixes applied
and verify the output passes docling_core strict validation.

Command:
```bash
conda run -n pdf2md python tools/compile_latex_groundth.py --doc linked_sections_figures
conda run -n pdf2md python tools/run_mvp_pipeline.py \
    --pdf groundtruth/corpus/latex/linked_sections_figures/linked_sections_figures.pdf \
    --out-dir /tmp/plan17_hv --backends paddleocr --verbose
conda run -n pdf2md python -c "
import json
from docling_core.types.doc import DoclingDocument
d = json.load(open('/tmp/plan17_hv/docling/linked_sections_figures.docling.json'))
DoclingDocument.model_validate(d)
print('docling_core strict validation: OK')
"
```

Pass criteria:

```text
The DoclingDocument.model_validate call returns without exception.
The exported origin block has both filename and binary_hash populated.
The exported docling JSON does NOT contain the literal label "paragraph".
```

Fail criteria:

```text
The DoclingDocument.model_validate call raises ValidationError.
Any block in the exported texts list has label == "paragraph".
The origin block is missing filename or binary_hash.
```

Evidence to record:

```text
Paste the pytest output.
Paste the relevant docling JSON head.
```

---

### Checkpoint H4 — wiring report summary

Title:
Confirm the export report includes the `plan17_wiring_summary` block.

Command:
```bash
python -c "import json; print(json.dumps(json.load(open('/tmp/plan17_hv/reports/export_report.json')).get('plan17_wiring_summary'), indent=2))"
```

Pass criteria:

```text
The plan17_wiring_summary block exists and contains:
  block_kind_unmapped_count: int
  origin_pdf_path_unknown_count: int
  image_post_processed_count: int
  footnote_lifted_count: int
  heading_promoted_count: int
  docling_core_validation_attempted: bool
  docling_core_validation_passed: bool
```

Fail criteria:

```text
plan17_wiring_summary is missing or null.
docling_core_validation_passed is false on the aligned-groundtruth
input.
```

Evidence to record:

```text
Paste the plan17_wiring_summary JSON.
```

---

### Checkpoint H5 — forbidden-layer diff check

Title:
Confirm no out-of-whitelist files were modified.

Command:
```bash
git diff --name-only main..HEAD
```

Pass criteria:

```text
Only whitelisted files (see Section 5) are modified.
No changes under src/pdf2md/{local,calibration,consensus,linking,pipeline}/.
No changes to src/pdf2md/export/{rag,markdown,io,reporting}.py.
No changes to src/pdf2md/cli/main.py or backend/*.
No changes to model files in src/pdf2md/models/.
```

Fail criteria:

```text
Any forbidden file is modified.
```

Evidence to record:

```text
Paste the git diff --name-only output.
List each changed file and why it's allowed.
```

---

## 8. Test matrix and failure classification

Test taxonomy:

- `automated`: runnable in the agent's sandbox without GPU / real
  backends. Covers Tasks A1–A6 unit tests plus the connector and export
  test suites.
- `human` / `slow`: requires GPU + paddleocr. Covers Task A7
  aligned-groundtruth e2e.

Failure classes:

```text
export_origin_defect: origin block is missing or invalid.
export_label_defect: any emitted DocItemLabel is invalid.
connector_classification_defect: a real heading / footnote / picture
  is missed by the connector.
schema_version_defect: emitted schema version != docling_core's.
docling_core_strict_failure: predicted docling JSON fails strict
  model_validate.
test_expectation_wrong: a test asserts on stale expectations.
```

---

## 9. Hand-off procedure after human verification

1. Archive current_plan.md as:
   ```text
   plans/archive/plan-17-docling-export-wiring-hardening.md
   ```
2. Append milestone M18 to history.md.
3. Promote the next prepared plan (or keep the placeholder if Plan 18 is
   not yet drafted).
4. Record the commit SHA / PR number in the milestone entry.

---

## 10. Status history

Status history:

```text
date — status — actor — note
```
