# Plan 006_1 — Semantic Router with Calibrated Weights

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
Phase 4b — Semantic cross-reference layer

Current roadmap estimate:
From 60% to 70% (Phase 4b)

Owner:
Agent team / human reviewer

Sequence:
Plan 006_1 (semantic sub-plan — reserved slot since M21, originally deferred)

Previous plan:
Plan 014_1 — networkx-backed LinkedStructure

Required previous plan status:
human_verified (or agent_complete with deferred verification)

Next plan after completion:
To be determined (candidates: validator real-data wiring, ground-truth
corpus expansion 007_1, PaddleOCR deep test-fixture cleanup).

Branch name:
plan-006_1-semantic-router

---

## 1. Purpose

Replace the hardcoded `GROBID_BOOK_WEIGHT = 0.65` magic number in
`ensemble.py` with data-driven weights loaded from the Plan 007_2
calibration baseline (`docs/reports/semantic_calibration_baseline.json`).
Wire auto document-class detection into the ensemble so the router does not
require the caller to supply `document_class` explicitly. Add the
`--semantic` flag to `build_cross_references.py` so the CLI can invoke the
full ensemble with calibrated routing in one command.

The infrastructure is 90% built:
- `merge_graphs(backend_weights=...)` already uses per-backend weights for
  tie-breaking.
- `run_ensemble(document_class=...)` already calls
  `weights_for_document_class()` and passes the result.
- `classify_document()` in `document_class.py` already returns
  ARTICLE/BOOK/DOCUMENT from entity features.
- The baseline JSON already contains `cross_backend_matrix` and
  `calibration_weights` per marker_type × backend.

What is missing:
1. `weights_for_document_class` is hardcoded: `if book → {"grobid": 0.65}`.
   It should load from the baseline and be per-marker-type aware.
2. `build_cross_references.py` never passes `document_class` — the weight
   slot is always None in practice.
3. No auto-classification: the ensemble should call `classify_document` on
   the entity proposals when `document_class` is not explicitly supplied.

ROADMAP principle: "no hardcoded paper-vs-book routing — every semantic
backend is a candidate." This plan honours that: the router uses calibrated
weights to *down-weight*, not *exclude*, backends per document class.

---

## 2. Source-of-truth hierarchy

Standard: ROADMAP.md, project.md, STATE.md, current_plan.md, next_plan.md,
history.md.

---

## 3. Repository and environment protocol

Standard branch protocol. No backend execution required.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Add a `load_calibration_weights(path: Path) -> dict` function in
   `src/pdf2md/semantic/ensemble.py` (or a new
   `src/pdf2md/semantic/router.py` module if cleaner) that reads the
   baseline JSON and returns a nested structure:
   `{document_class: {backend: weight}}`.
   Derivation: for each backend, its weight for `book` class = its
   aggregate resolution rate on example3 (the book) relative to the best
   backend. For `article` class = uniform (all are competitive). Default
   (unknown class) = uniform.
2. Replace `GROBID_BOOK_WEIGHT = 0.65` with weights loaded from the
   baseline. `weights_for_document_class` reads from the loaded data
   instead of returning a hardcoded dict.
3. Add auto-classification in `run_ensemble`: when `document_class` is
   None and entity proposals are available, call `classify_document` to
   derive it. Pass the result to `weights_for_document_class`.
4. Wire `document_class` (auto or explicit) into
   `tools/build_cross_references.py`: add `--document-class` optional
   CLI arg (default: auto-detect).
5. Tests: load_calibration_weights on a fixture JSON, verify weight
   derivation; run_ensemble with document_class="book" produces different
   merge than document_class="article"; auto-classification round-trip.

Out of scope:

1. Per-marker-type weighting (the infrastructure in merge_graphs is
   per-backend only; per-type weighting would require a deeper refactor
   of the merge logic). The baseline data is per-type, so a future plan
   can consume it — this plan uses the aggregate per-backend rate.
2. Changes to `classify_document` logic (it works as-is).
3. Changes to resolver, connector, or entity detection.
4. The `pdf2md convert --semantic` integrated CLI subcommand (deferred
   until the pipeline orchestrator supports the semantic layer natively).
5. Docling export or linking changes.

Hard constraints:

1. No backend is excluded — weights down-weight, never zero.
2. When no baseline file is available, uniform weights are used (graceful
   degradation — backwards compatible).
3. No existing test may regress.
4. The baseline JSON path is configurable, not hardcoded.

Allowed Python dependencies:

```text
none (json + pathlib are stdlib)
```

---

## 5. File whitelist and forbidden files

Whitelist:

```text
src/pdf2md/semantic/ensemble.py
src/pdf2md/semantic/router.py               (new, optional — or fold into ensemble.py)
tools/build_cross_references.py
tests/test_semantic_ensemble.py
tests/test_semantic_router.py               (new)
tests/data/semantic_fixtures/calibration_weights_fixture.json  (new)
```

Forbidden:

```text
src/pdf2md/semantic/document_class.py
src/pdf2md/semantic/resolver.py
src/pdf2md/semantic/candidates.py
src/pdf2md/semantic/graph_export.py
src/pdf2md/models/*
src/pdf2md/connectors/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*
src/pdf2md/calibration/*
src/pdf2md/diagnostics/*
docs/reports/*                              (read-only — do not regenerate)
backend/*
webui/*
```

---

## 6. Agent tasks

### Task A1 — Load calibration weights from baseline JSON

Title:
Replace magic constant with data-driven weights

Files allowed:

```text
src/pdf2md/semantic/ensemble.py  (or src/pdf2md/semantic/router.py)
tests/test_semantic_router.py               (new)
tests/data/semantic_fixtures/calibration_weights_fixture.json  (new)
```

Implementation requirements:

1. `load_calibration_weights(path: Path) -> dict[str, dict[str, float]]`:
   - Read the baseline JSON.
   - From `cross_backend_matrix`, compute per-backend aggregate rate for
     each example separately (example3 = book, example01/02 = article).
   - Derive weights: for `book` class, each backend's weight =
     `backend_rate / max_rate` (relative to best). For `article` class,
     uniform (all rates are close).
   - Return `{"book": {"grobid": 0.xx, "regex": 0.xx, "vlm_v4": 0.xx},
     "article": {}, "document": {}}`.
2. Replace `GROBID_BOOK_WEIGHT = 0.65` constant with a module-level
   `_CALIBRATION_WEIGHTS: dict | None = None` that is lazily loaded on
   first call to `weights_for_document_class`.
3. `weights_for_document_class(document_class, calibration_path=None)`:
   - If `_CALIBRATION_WEIGHTS` is None and `calibration_path` is provided,
     load it.
   - If still None or document_class not in weights, return {} (uniform).
   - Otherwise return the per-backend weights for that class.
4. Fixture JSON: a small synthetic baseline with 2 backends, 2 types,
   known rates.
5. Tests: load fixture → verify derived weights; unknown class → uniform;
   missing file → uniform (graceful degradation).

Automated tests:

```bash
conda run -n pdf2md pytest tests/test_semantic_router.py -q
```

Human verification required:
no

### Task A2 — Auto document-class detection in run_ensemble

Title:
Auto-classify when document_class is not supplied

Files allowed:

```text
src/pdf2md/semantic/ensemble.py
tests/test_semantic_ensemble.py
```

Implementation requirements:

1. In `run_ensemble`, when `document_class is None` and at least one
   backend produced a graph with entities: call `classify_document` on
   the first available `EntityProposalDocument` (or a merged one) to
   derive `document_class`.
2. Pass the derived (or explicit) `document_class` to
   `weights_for_document_class` as before.
3. If no entities are available (text-only backends), keep
   `document_class = None` → uniform weights.
4. Add a test: mock two backends, one producing a book-like entity set
   (many chapters, high page count), verify that auto-classification
   triggers and the book weights are applied.

Automated tests:

```bash
conda run -n pdf2md pytest tests/test_semantic_ensemble.py -q
```

Human verification required:
no

### Task A3 — Wire --document-class into build_cross_references CLI

Title:
CLI flag for explicit or auto document-class routing

Files allowed:

```text
tools/build_cross_references.py
```

Implementation requirements:

1. Add `--document-class` optional arg (choices: article, book, document,
   auto; default: auto).
2. When `auto`: pass `document_class=None` to `run_ensemble` (it will
   auto-detect per A2).
3. When explicit: pass the string directly.
4. Add `--calibration-weights` optional arg (path to baseline JSON;
   default: `docs/reports/semantic_calibration_baseline.json`). Pass to
   `weights_for_document_class` via the ensemble.

Automated tests:

```bash
conda run -n pdf2md python tools/build_cross_references.py --help
# verify --document-class and --calibration-weights appear
```

Human verification required:
no

---

## 7. Human verification checkpoints

### Verification model

Human verification is **non-blocking**. Real-data validation (that the
router correctly down-weights GROBID on a book-class document and produces
a different merge than uniform weights) will be performed **in the
diagnostic page**. The completion gate is automated tests only.

### Deferred checkpoint H1 (in-product)

Title:
Verify calibrated routing on example3 (book) vs example01 (article)

Verification surface:
in_product (cross-reference diagnostic page)

Pass criteria:

```text
On example3 (book): GROBID weight < 1.0 (down-weighted).
On example01 (article): all weights ≈ 1.0 (uniform).
No backend weight is ever 0.0 (no exclusion).
When baseline file is absent, uniform weights are used (no crash).
No existing test regresses.
```

### Completion gate

```text
All A1/A2/A3 automated tests pass.
Full suite green.
No forbidden files modified.
No new dependencies.
Backward compatible: without baseline file, behavior is identical to pre-plan.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_semantic_router.py -q
conda run -n pdf2md pytest tests/test_semantic_ensemble.py -q
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

Failure classes:

repository_defect: weight derivation wrong; auto-classification not triggered;
  a backend gets weight 0.0; graceful degradation fails.
environment_missing: n/a.
test_expectation_wrong: fixture doesn't match the baseline schema.

---

## 9. Checkpoints, push policy, and hand-off

C0 Plan ready. C1 Agent complete. C2 Human signs off (non-blocking H1).
C3 Finished: archived as `plans/archive/006_1-semantic-router.md`;
milestone appended; STATE.md updated ("Semantic router" → built); next
plan promoted.

Push policy: agent may push branch + draft PR; must not merge to main.

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan: 006_1
Status:
Branch: plan-006_1-semantic-router
Commit or PR:
Files changed:
Forbidden files touched:
Tasks attempted: A1 / A2 / A3
Automated tests run / passed / failed:
Backward compat (no baseline → uniform): verified yes/no
Failure classes:
Blockers:
```

Reviewer checklist:

1. Only whitelisted files changed?
2. No forbidden files modified?
3. All tests green?
4. GROBID_BOOK_WEIGHT constant removed (replaced by data-driven)?
5. Graceful degradation works (no baseline → uniform)?
6. No backend weight is 0.0?
7. Auto-classification wired in run_ensemble?
8. --document-class and --calibration-weights in CLI?
9. Safe to mark human_verified?

Status history:

```text
date — status — actor — note
2026-06-03 — active — human — plan drafted from ensemble.py audit;
                               fills the reserved 006_1 slot with
                               data-driven routing from 007_2 baseline
```

---

## PR_reviews

(none yet)

## Feedback

(none yet)
