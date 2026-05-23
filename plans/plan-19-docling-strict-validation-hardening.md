# Plan 18 — Docling Strict-Validation Hardening (Plan 17 A8 follow-up)

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
Post-MVP refinement. Closes the docling-core strict-validation gap left
open by Plan 17.

Owner:
Agent team / human reviewer

Sequence:
Plan 18 of the post-MVP refinement track.

Previous plan:
Plan 17 — Docling Export Wiring Hardening (human_verified)

Required previous plan status:
human_verified

Next plan after completion:
Plan 19+ — TBD.

Branch name:
plan-18-docling-strict-validation-hardening

---

## 1. Purpose

Plan 17 fixed the three highest-impact export wiring defects (origin
block, label vocabulary, schema version). Two strict-validation cases
remained xfailed in
`tests/test_docling_export_wiring.py::TestDoclingCoreStrictValidation`
with a documented "A8 follow-up" reason — Plan 18 closes them.

The four concrete defects to fix, all in
`src/pdf2md/export/docling.py`:

1. `pictures[*].text` is emitted but `docling_core.types.doc.PictureItem`
   forbids extras. Drop the `text` key on picture items (the visible
   text is captured in their captions and prov instead).
2. `pictures[*].metadata` and `tables[*].metadata` carry pdf2md-only
   keys (`pdf2md_node_id`, `captions`, `links`, `relations`, etc.)
   which docling-core rejects with `extra_forbidden`. Move every
   pdf2md-only key into a single nested `pdf2md` envelope and emit
   only fields docling-core knows about at the top level.
3. `tables[*].text` is emitted but `docling_core.types.doc.TableItem`
   forbids it. Drop it.
4. `prov[*].bbox.coord_origin` is emitted lowercase (`"bottomleft"`)
   but `docling_core.types.doc.CoordOrigin` is an enum of
   `"TOPLEFT"` / `"BOTTOMLEFT"` (uppercase). Uppercase the value
   when serialising prov.
5. `prov[*].charspan` is required by `docling_core.types.doc.ProvenanceItem`
   but is never emitted. Add a default `[0, 0]` charspan to every prov
   entry, with an extension hook so future work can fill in real
   character offsets when the linker exposes them.

After this plan, the two existing xfailed strict-validation tests must
flip to passing, with no `pytest.mark.xfail` decorator left.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

README.md is the public entry point.

PLAN_TEMPLATE.md is the standard format for executable plans.

current_plan.md is the active execution contract for agents.

next_plan.md is the next planned execution contract.

history.md records completed milestones after human verification.

run_log.md is append-only and implicitly allowed when required by
agent.md.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-18-docling-strict-validation-hardening
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. Do not modify files outside the whitelist.
4. Do not install or use undeclared dependencies.
5. Do not change ROADMAP.md progress.
6. Do not mark this plan human_verified or finished.

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

1. Move all pdf2md-only metadata on items (texts, pictures, tables,
   groups) into a nested `metadata.pdf2md` envelope. Top-level item
   metadata stays clean for docling-core.
2. Strip `text` from picture and table items.
3. Strip `name` from group items if docling-core forbids it there too
   (verify before stripping).
4. Uppercase `coord_origin` when serialising prov bboxes.
5. Emit `prov[*].charspan` (default `[0, 0]`) on every prov entry.
6. Flip the two A8 xfailed tests in
   `tests/test_docling_export_wiring.py::TestDoclingCoreStrictValidation`
   to passing assertions and remove the `pytest.mark.xfail` decorator.
7. Add new strict-validation coverage for picture+table fixtures.

Out of scope:

1. Real charspan computation from linker spans. The default `[0, 0]`
   is intentionally a placeholder — a future plan can wire real
   character offsets from the linker.
2. New schema fields on docling-core.
3. The Plan 17 A3/A4/A5 connector heuristics (non-Markdown headings,
   footnote post-processing, inline picture lifting).
4. The PR #100 follow-up test rewrites in
   `tests/test_compile_latex_groundth.py`.
5. RAG / Markdown / linking / pipeline runner changes.

Hard constraints:

1. Whitelist enforcement is absolute.
2. No `docling_core` model is allowed to receive an `extra_forbidden`
   field after this plan — the new strict-validation tests must pass
   without `xfail`.
3. pdf2md-internal metadata MUST survive into the JSON output, but
   under a nested `metadata.pdf2md` envelope so docling-core's
   `extra="forbid"` validators don't see it.
4. Existing tests in `tests/test_docling_export.py` must continue to
   pass; any test that asserts on the OLD top-level metadata key
   names must be updated to read from `metadata.pdf2md.*` instead.

Allowed Python dependencies:

```text
docling_core (optional, already declared)
none beyond existing repository dependencies
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these implementation and test files:

```text
src/pdf2md/export/docling.py
src/pdf2md/export/__init__.py

tests/test_docling_export_wiring.py
tests/test_docling_export.py
tests/test_export_io_cli.py
```

run_log.md is append-only and implicitly allowed.

The agent may NOT modify these files:

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

src/pdf2md/connectors/*
src/pdf2md/local/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/pipeline/*
src/pdf2md/datasets/*
src/pdf2md/cli/main.py
src/pdf2md/models/*

src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py

tools/*

backend/*
groundtruth/corpus/*
```

---

## 6. Agent tasks

### Task A1 — Move pdf2md-only metadata into a nested envelope

Implement a `_pdf2md_envelope(node_or_payload)` helper in `docling.py`
that returns a dict carrying every pdf2md-specific field
(`pdf2md_node_id`, `captions`, `links`, `relations`, `footnote_anchors`,
`footnote_anchor_targets`, etc.). Replace each top-level item's
`metadata` so docling-core sees only fields it knows about, with a
single `pdf2md` sub-key holding the rest.

Tests in `tests/test_docling_export.py` that currently read
`item["metadata"]["captions"]`, `item["metadata"]["links"]`, or
`item["metadata"]["footnote_anchors"]` must be updated to read from
`item["metadata"]["pdf2md"]["captions"]` etc.

### Task A2 — Strip `text` from pictures and tables

`build_docling_document()` must NOT emit `"text"` keys on picture or
table items. Caption text already lives on the linked caption item; the
table cells/text live in `data.table_cells`.

### Task A3 — Uppercase coord_origin on prov bboxes

When serialising a bbox into a prov block (in `_prov_for` or wherever
the bbox is materialised), uppercase the `coord_origin` value so it
matches `docling_core.types.doc.CoordOrigin`. The source `BBox.coord_origin`
field stays lowercase to match the existing pdf2md schema; only the
docling export coerces.

### Task A4 — Default `charspan` on every prov entry

Every prov dict emitted into the docling JSON gains a `charspan` key.
Use `[0, 0]` as a sentinel default. The pdf2md envelope captures the
fact that this is a placeholder (`metadata.pdf2md.charspan_origin =
"placeholder_zero_zero"`).

### Task A5 — Flip the xfailed strict-validation tests + add coverage

Remove the `@pytest.mark.xfail(...)` decorator from
`TestDoclingCoreStrictValidation::test_simple_document_passes_strict_validation_with_origin`
and
`TestDoclingCoreStrictValidation::test_rich_document_passes_strict_validation_with_origin`.
Both must now pass.

Add at least two new tests:

- `test_pictures_have_no_text_or_pdf2md_extras_at_top_level`
- `test_tables_have_no_text_or_pdf2md_extras_at_top_level`
- `test_prov_charspan_is_present_and_well_formed`
- `test_prov_coord_origin_is_uppercase`

### Task A6 — Update legacy test assertions

Wherever the test suite reads pdf2md-only fields directly under
`metadata[...]`, redirect to `metadata["pdf2md"][...]`. This is a
mechanical update; the helpful contract is that the existing test
expectations stay equivalent — `pdf2md_captions == pdf2md_captions`,
just relocated.

---

## 7. Human verification checkpoints

### Checkpoint H1 — automated tests

```bash
conda run -n pdf2md pytest tests/test_docling_export_wiring.py tests/test_docling_export.py tests/test_export_io_cli.py -q
```

Pass criteria:

- All tests pass.
- No `xfailed` entries from the wiring test file (Plan 17 left 2; Plan
  18 must remove them).

### Checkpoint H2 — full repo

```bash
conda run -n pdf2md pytest tests/ -q
```

Pass criteria:

- Pass count ≥ Plan 17's count (878) plus the new Plan 18 tests.
- xfailed count drops by 2 (Plan 17's A8 follow-up xfails are gone).
- 0 failed.

### Checkpoint H3 — real end-to-end strict validation

After running `tools/run_mvp_pipeline.py` against the aligned
`linked_sections_figures.pdf`, the produced
`docling/<doc>.docling.json` must load cleanly via
`docling_core.types.doc.DoclingDocument.model_validate(...)`.

```bash
conda run -n pdf2md python tools/compile_latex_groundth.py --doc linked_sections_figures
conda run -n pdf2md python tools/run_mvp_pipeline.py \
    --pdf groundtruth/corpus/latex/linked_sections_figures/linked_sections_figures.pdf \
    --out-dir /tmp/plan18_hv --backends paddleocr --verbose
conda run -n pdf2md python -c "
import json
from docling_core.types.doc import DoclingDocument
d = json.load(open('/tmp/plan18_hv/docling/linked_sections_figures.docling.json'))
DoclingDocument.model_validate(d)
print('docling_core strict validation: OK')
"
```

### Checkpoint H4 — forbidden-layer diff

```bash
git diff --name-only main..HEAD
```

Only files in the whitelist may appear.

---

## 8. Hand-off procedure

1. Archive `current_plan.md` to
   `plans/archive/plan-18-docling-strict-validation-hardening.md`.
2. Append milestone M19 to `history.md`.
3. Reset `current_plan.md` to the Plan 19+ placeholder.
4. Record commit SHA / PR number in the milestone entry.

---

## 9. Status history

```text
date — status — actor — note
```
