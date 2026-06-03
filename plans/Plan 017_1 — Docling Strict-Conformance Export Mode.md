# Plan 017_1 — Docling Strict-Conformance Export Mode

Status:
active

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
Phase 6 — Docling-compatible export

Current roadmap estimate:
From 85% to 92% (Phase 6 — export conformance)

Owner:
Agent team / human reviewer

Sequence:
Plan 017_1 (export sub-plan, extends Plan 17 — Docling Export Wiring; this is
the deferred "Plan 17 A8" follow-up)

Previous plan:
Plan 006_1 — Semantic Router with Calibrated Weights

Required previous plan status:
human_verified (or agent_complete with deferred verification)

Next plan after completion:
Plan 007_3 — Full System Diagnostic and Human Adjudication.

Branch name:
plan-017_1-docling-strict-export

---

## 1. Purpose

Fix the critical interoperability defect the export agent surfaced: the
`*.docling.json` pdf2md writes is **Docling-flavoured but not strictly
conformant**. Any consumer in the real Docling ecosystem that calls
`DoclingDocument.model_validate(...)` rejects the file with ~99
`extra_forbidden` errors. The export's entire purpose — handing a document
to the Docling world — silently does not hold today.

The failure is currently quiet: `try_validate_with_docling_core` catches the
`ValidationError` and records it as a single warning string
(`docling_core_validation_failed:ValidationError`) in the export report. The
hard gate (`strict and structural`) only fires on pdf2md's own lightweight
structural checks, never on docling_core. So the pipeline always writes a
file that won't load in a strict consumer, and nobody is told.

Root cause (three distinct issues, confirmed in `src/pdf2md/export/docling.py`):

1. **Forbidden extras on typed items.** `_base_item` attaches a `metadata`
   block with `pdf2md_node_id`, `type`, `status`, `confidence`,
   `source_entity_ids`, plus `**node.metadata` directly onto each
   TextItem / TableItem / PictureItem. docling_core's typed models forbid
   extras → `extra_forbidden`.
2. **`prov` shape.** `_prov_for` emits `{page_no, bbox, consensus_block_id}`
   but docling_core's `ProvenanceItem` requires `charspan` and forbids
   `consensus_block_id`.
3. **`coord_origin` casing / bbox shape** not matching docling_core's
   `BoundingBox` (`CoordOrigin` enum + `l/t/r/b`).

The fix is a **strict serialization mode** that emits a clean,
docling_core-conformant document, moving all pdf2md provenance to the one
extension point docling_core permits (the top-level `metadata` bag, which is
an open dict), while preserving the current rich variant for internal use
(viewer, RAG chunking, adjudication traceability).

This plan also fixes a stale docstring in `resolver.py` (a smaller bug found
during review): `_try_theorem_family` still claims "the OCR connector does
not yet emit theorem-family ENTITIES ... resolution stays 0%", which has been
false since Plan 006_5 landed the connector-side detector.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

STATE.md is the compact current-state surface.

current_plan.md is the active execution contract for agents.

next_plan.md is the next planned execution contract.

history.md records completed milestones after human verification.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-017_1-docling-strict-export
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree (the known local scratch files —
   book_1.pdf, log, pdf2md/, pdf2md-webui/, run_example3.sh — are already in
   `.git/info/exclude` and must stay untracked; do not commit them).
3. Do not modify files outside the whitelist.
4. Do not install or use undeclared dependencies (docling-core is already a
   dependency).
5. Do not mark this plan human_verified or finished.

Main conda environment:

```text
pdf2md
```

Repository-level commands must run using:

```bash
conda run -n pdf2md python <command>
env PYTHONPATH=src conda run -n pdf2md pytest <args>
```

No backend execution required.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Add a `strict: bool = False` field to `DoclingExportSettings`. When
   `strict=True`, `build_docling_document` emits a document that passes
   `docling_core.types.doc.DoclingDocument.model_validate(...)`.
2. In strict mode:
   a. **Items carry no forbidden extras.** TextItem / TableItem /
      PictureItem contain only docling_core-allowed fields (`self_ref`,
      `prov`, `text`, `label`, `orig`, `children`, `parent`, etc. as the
      schema requires). The pdf2md `metadata` block is NOT attached per-item.
   b. **All pdf2md provenance moves to the top-level `metadata` bag** as a
      single `metadata["pdf2md"]` object keyed by node id:
      `metadata["pdf2md"]["nodes"][node_id] = {type, status, confidence,
      source_entity_ids, consensus_block_id, ...node.metadata}`. docling_core
      permits an open top-level metadata dict, so this is conformant and keeps
      full traceability.
   c. **`prov` is docling_core-shaped:** `{page_no, bbox, charspan}` with
      `bbox` as `{l, t, r, b, coord_origin}` using the `CoordOrigin` enum
      value docling_core expects (uppercase). `charspan` is emitted (default
      `[0, len(text)]` when no finer span is known). `consensus_block_id` is
      removed from `prov` (it lives in `metadata["pdf2md"]`).
3. The default (`strict=False`) path is **unchanged** — the rich variant with
   per-item metadata is preserved exactly for the viewer, RAG, and
   adjudication consumers.
4. `build_export_run` / `write_export_outputs`: when `strict=True` is passed
   through, the docling_core validation result becomes a **hard gate** — if
   docling_core is installed and rejects the strict document, raise
   `ValueError` (not just a warning). When docling_core is unavailable, fall
   back to the structural check with a recorded warning.
5. Un-xfail the two tests in
   `tests/test_docling_export_wiring.py::TestDoclingCoreStrictValidation`
   (`test_simple_document_passes_strict_validation_with_origin`,
   `test_rich_document_passes_strict_validation_with_origin`) and make them
   call `build_docling_document(..., settings=DoclingExportSettings(strict=True))`.
   They must pass (real passes, not xfail).
6. Add a test asserting the **non-strict default is byte-for-byte unchanged**
   (regression guard: the rich variant still carries `pdf2md_node_id` per item).
7. Add a test asserting strict mode round-trips through
   `DoclingDocument.model_validate` AND that `metadata["pdf2md"]["nodes"]`
   still contains every emitted node id (traceability preserved).
8. **Resolver docstring fix:** in `src/pdf2md/semantic/resolver.py`, replace
   the stale `_try_theorem_family` NOTE that claims the connector emits no
   theorem entities with an accurate description (Plan 006_5 landed the
   detector; candidates now exist on real data).

Out of scope:

1. Changing the default export to strict (the rich variant stays the default;
   strict is opt-in until consumers are migrated).
2. Markdown / RAG export changes.
3. Any resolver logic change beyond the docstring (the matcher is correct).
4. The theorem-family duplicate-number disambiguation issue (a separate,
   genuinely-distinct problem — see Plan note below; not bundled here).
5. Viewer or validator changes.
6. ConsensusIR, linking, connector, or calibration changes.

Hard constraints:

1. The non-strict (`strict=False`) output must be identical to pre-plan for
   the same input — verified by a regression test.
2. Strict mode must pass `DoclingDocument.model_validate` on both the
   `simple_document` and `rich_document` fixtures.
3. Strict mode must preserve full pdf2md provenance in
   `metadata["pdf2md"]` — no traceability is lost, only relocated.
4. No new dependency.
5. No existing test may regress.

Allowed Python dependencies:

```text
none (docling-core already present)
```

Allowed external tools:

```text
none
```

Allowed environment-modifying commands:

```text
none
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these files:

```text
src/pdf2md/export/docling.py
src/pdf2md/export/io.py
src/pdf2md/semantic/resolver.py           (docstring fix only)
tests/test_docling_export_wiring.py
tests/test_docling_export.py              (may add strict-mode + regression tests)
```

The agent must not modify these files:

```text
README.md
ROADMAP.md
project.md
STATE.md
current_plan.md
next_plan.md
history.md
src/pdf2md/export/markdown.py
src/pdf2md/export/rag.py
src/pdf2md/models/*
src/pdf2md/linking/*
src/pdf2md/connectors/*
src/pdf2md/consensus/*
src/pdf2md/semantic/candidates.py
src/pdf2md/semantic/ensemble.py
src/pdf2md/semantic/router.py
src/pdf2md/calibration/*
src/pdf2md/diagnostics/*
backend/*
webui/*
tools/*
```

Expected output artefacts:

```text
none beyond modified source + test changes
```

---

## 6. Agent tasks

### Task A1 — Strict serialization in build_docling_document

Title:
Add `strict` mode that emits a docling_core-conformant document

Files allowed:

```text
src/pdf2md/export/docling.py
```

Implementation requirements:

1. Add `strict: bool = False` to `DoclingExportSettings`.
2. Add a top-level `metadata["pdf2md"]` object to the document. Populate
   `metadata["pdf2md"]["nodes"][node.id]` with the per-node provenance that
   strict mode strips from items: `type`, `status`, `confidence`,
   `source_entity_ids`, `consensus_block_id` (if any), and `**node.metadata`.
   Prefer strict-only population to satisfy the byte-identical constraint.
3. Refactor `_base_item(node, self_ref, consensus, *, strict)`:
   - `strict=False`: current behaviour (per-item `metadata` block).
   - `strict=True`: omit the `metadata` block entirely; emit only
     docling_core-allowed fields.
4. Refactor `_prov_for(node, consensus, *, strict)`:
   - `strict=False`: current shape.
   - `strict=True`: `{page_no, bbox, charspan}` with `bbox` as
     `{l, t, r, b, coord_origin}` (uppercase `CoordOrigin` value), `charspan`
     defaulting to `[0, len(node.text or "")]`; no `consensus_block_id`.
5. Thread `strict` from settings through `build_docling_document` to
   `_base_item` / `_prov_for` and any item builders (`texts`, `tables`,
   `pictures`, `groups`).
6. Ensure `label` and other required docling_core fields are present on each
   item in strict mode (consult the actual `docling_core` model for the exact
   required field set — do not guess; import it and inspect).

Automated tests required:

```bash
env PYTHONPATH=src conda run -n pdf2md pytest tests/test_docling_export_wiring.py -q
```

Completion evidence:
Files changed, the docling_core field set used, tests run, blockers.

Human verification required:
no

### Task A2 — Strict gate in build_export_run

Title:
Make docling_core rejection a hard gate in strict mode

Files allowed:

```text
src/pdf2md/export/io.py
```

Implementation requirements:

1. Thread the `strict` setting (from `DoclingExportSettings`) into
   `build_export_run`.
2. When `settings.strict` is True and docling_core is installed: if
   `try_validate_with_docling_core` returns `ok=False`, raise `ValueError`
   with the reason — the strict export must not silently write a
   non-conformant file.
3. When docling_core is unavailable in strict mode: record the
   `docling_core_unavailable` warning and fall back to the structural check
   (do not raise — absence of the validator is an environment condition, not
   a document defect).
4. Non-strict behaviour is unchanged (warning-only, as today).

Automated tests required:

```bash
env PYTHONPATH=src conda run -n pdf2md pytest tests/test_docling_export.py -q
```

Completion evidence:
Files changed, tests run, blockers.

Human verification required:
no

### Task A3 — Un-xfail + regression + traceability tests

Title:
Prove strict conformance, non-strict stability, and preserved provenance

Files allowed:

```text
tests/test_docling_export_wiring.py
tests/test_docling_export.py
```

Implementation requirements:

1. Remove the two `@pytest.mark.xfail` decorators on
   `TestDoclingCoreStrictValidation` and update both tests to build with
   `DoclingExportSettings(strict=True)`; assert
   `DoclingDocument.model_validate(doc)` succeeds.
2. Add `test_non_strict_default_unchanged`: build with default settings and
   assert a TextItem still carries `metadata["pdf2md_node_id"]` (the rich
   variant is preserved).
3. Add `test_strict_preserves_provenance_in_metadata`: build strict, assert
   `metadata["pdf2md"]["nodes"]` contains every emitted node id and the
   status/confidence/source_entity_ids for at least one node match the
   linked structure.
4. Add `test_strict_export_run_raises_on_nonconformant` (if a fixture can be
   constructed that docling_core rejects) OR
   `test_strict_export_run_passes_on_conformant`: `build_export_run(...,
   strict=True)` does not raise on the conformant fixtures.

Automated tests required:

```bash
env PYTHONPATH=src conda run -n pdf2md pytest tests/test_docling_export_wiring.py tests/test_docling_export.py -q
```

Completion evidence:
Files changed, tests run, exit codes, blockers.

Human verification required:
no

### Task A4 — Resolver docstring fix

Title:
Remove the stale "connector emits no theorem entities" NOTE

Files allowed:

```text
src/pdf2md/semantic/resolver.py
```

Implementation requirements:

1. Replace the `_try_theorem_family` docstring NOTE (lines ~317-324) that
   claims theorem entities are never emitted with an accurate statement:
   Plan 006_5 added the connector-side theorem-family detector, so
   candidates now exist on real pipeline data and this matcher resolves them
   by hierarchical number identity.
2. No logic change.

Automated tests required:

```bash
env PYTHONPATH=src conda run -n pdf2md pytest tests/test_semantic_resolver.py -q
```

Completion evidence:
Diff of the docstring, tests still green.

Human verification required:
no

---

## 7. Human verification checkpoints

### Verification model

Human verification is **non-blocking**. The completion gate is automated
tests (strict round-trip through real docling_core is itself the proof).
In-product confirmation — loading a strict export in an external Docling
consumer — is deferred and recorded in STATE.md.

### Deferred checkpoint H1 (in-product / external)

Title:
Load a strict export in an external Docling consumer

Verification surface:
in_product (external docling_core round-trip, or the diagnostic page if it
gains a strict-export preview)

Pass criteria:

```text
A strict export of example01 loads via DoclingDocument.model_validate with
  zero errors.
metadata["pdf2md"]["nodes"] contains all node ids (traceability intact).
The non-strict default export is byte-identical to pre-plan.
```

### Completion gate

```text
The two TestDoclingCoreStrictValidation tests pass (real, not xfail).
Non-strict regression test passes (default output unchanged).
Strict traceability test passes.
Full suite green; xfail count drops from 2 to 0.
No forbidden files modified. No new dependency.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
env PYTHONPATH=src conda run -n pdf2md pytest tests/test_docling_export_wiring.py tests/test_docling_export.py tests/test_semantic_resolver.py -q
env PYTHONPATH=src conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp
```

Failure classes:

repository_defect:
Strict document still has extras; prov shape wrong; non-strict output
changed; provenance lost from metadata; gate does not raise when it should.

environment_missing:
docling_core not installed (strict tests use `importorskip` — skip, not fail).

test_expectation_wrong:
A test asserts a docling_core field set that the installed version does not
require (resolve by inspecting the installed model, not guessing).

upstream_dependency_issue:
docling_core version exposes a different required field set than expected —
record the version and adapt.

Failure handling:

If repository_defect: agent fixes or reports.
If test_expectation_wrong / upstream: inspect the installed docling_core model
and align the strict serializer to it; record the version in the report.

---

## 9. Checkpoints, push policy, and hand-off

C0 Plan ready: status active; whitelist complete; tasks A1–A4; tests listed;
next plan slot identified.

C1 Agent complete: all tasks attempted; xfails removed and passing; non-strict
regression green; full suite green; no forbidden files; report done; status
agent_complete.

C2 Human signs off: reviews report + test results; sets human_verified.

C3 Finished and promoted: archived as
`plans/archive/017_1-docling-strict-export.md`; milestone appended to
history.md; STATE.md updated ("Docling export → strict-conformant mode
available; xfail debt cleared"); next plan promoted.

Push and PR policy:

```text
Agent may push the branch and open a draft PR.
Agent must not merge to main.
Agent must not direct-push to main.
```

Hand-off after human sign-off:

1. Archive as `plans/archive/017_1-docling-strict-export.md`.
2. Append milestone to history.md (record: strict mode added, 2 xfails
   cleared, resolver docstring corrected, non-strict output unchanged).
3. Update STATE.md: "LinkedStructure and Docling export" notes →
   "strict docling_core-conformant export mode available (opt-in);
   provenance relocated to metadata.pdf2md in strict mode."
4. Promote next_plan.md (Plan 007_3) to current_plan.md.
5. Create new next_plan.md.
6. Record commit SHA / PR number.

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan: 017_1
Status:
Branch: plan-017_1-docling-strict-export
Commit or PR:
Files changed:
Forbidden files touched:
Tasks attempted: A1 / A2 / A3 / A4
docling_core version used:
docling_core required field set for items:
Automated tests run / passed / failed:
xfail count before/after: 2 → ?
Non-strict output unchanged: verified yes/no
Strict provenance preserved in metadata.pdf2md: yes/no
Failure classes:
Blockers:
```

Reviewer checklist:

1. Only whitelisted files changed?
2. No forbidden files (models, linking, connectors, etc.) modified?
3. Both TestDoclingCoreStrictValidation tests pass as real passes (no xfail)?
4. Non-strict default output is byte-identical to pre-plan (regression test)?
5. Strict mode round-trips through real `DoclingDocument.model_validate`?
6. All pdf2md provenance preserved in `metadata["pdf2md"]` in strict mode?
7. Strict `build_export_run` raises on a non-conformant document?
8. Resolver docstring no longer claims theorem entities are unemitted?
9. Full suite green; xfail count 0?
10. No new dependency?
11. Safe to mark human_verified?

Status history:

```text
date — status — actor — note
2026-06-03 — active — human — drafted from export agent's critical finding;
                               implements the deferred Plan 17 A8 strict
                               docling_core conformance + resolver docstring fix
```

---

## PR_reviews

(none yet)

## Feedback

(none yet)
