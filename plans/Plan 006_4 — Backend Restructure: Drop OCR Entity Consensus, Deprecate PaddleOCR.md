# Plan 006_4 — Backend Restructure: Drop OCR Entity Consensus, Deprecate PaddleOCR

Status:
active

Linked ROADMAP phase:
Phase 4b — Semantic cross-reference layer (structural cleanup)

Branch name:
plan-006_4-backend-restructure

Previous plan:
Plan 007_2 — Per-Dimension Semantic Calibration

Next plan after completion:
To be decided (candidates: networkx in linking, 006_1 semantic router)

---

## 1. Purpose

Remove the OCR-level entity consensus from the semantic cross-reference path
and formalize the backend hierarchy: MinerU default, DeepSeek alternative,
PaddleOCR deprecated.

Evidence from the 007_2 calibration baseline (`docs/reports/semantic_calibration_baseline.md`):

- PaddleOCR: 0% resolution on the 791-page book, <3% on articles.
- `merge_entity_documents` in `entity_merge.py` is never called at runtime
  by any tool or pipeline — dead code since AP8 built it.
- MinerU and DeepSeek resolve identically on bibliography/section/table
  (68%/85%/48%), with MinerU at 96% equations post-006_2 normalization.

The page-level `ConsensusIR` (factory.py, grouping.py, scoring.py) is
retained for the Docling-export structural branch — this plan only removes
the entity-merge path.

---

## 2. Source-of-truth hierarchy

Standard: ROADMAP.md, project.md, STATE.md, current_plan.md, next_plan.md, history.md.

---

## 3. Repository and environment protocol

Standard branch protocol. No backend execution required.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Delete `src/pdf2md/consensus/entity_merge.py` (227 lines, dead code).
2. Update `src/pdf2md/consensus/__init__.py`: remove `CONSENSUS_BACKEND`
   and `merge_entity_documents` re-exports.
3. Update `src/pdf2md/semantic/candidates.py`: remove docstring reference
   to `merge_entity_documents` (line 291).
4. Update `pdf2md.backends.example.toml`: add deprecation comment to
   PaddleOCR section, add "DEFAULT" comment to MinerU section, add
   "ALTERNATIVE" comment to DeepSeek section.
5. Delete `tests/test_entity_merge.py` (tested the removed module).
6. Append M36 to `history.md` for 006_4 completion. M33–M35 were recorded
   during the 007_2 → 006_4 handoff.
7. Update `STATE.md`: connector normalization → built, teaching loop →
   built, viewer gap closed, semantic calibration → built, OCR entity
   consensus → removed, active plan → 006_4.

Out of scope:

1. `backend/paddleocr/` directory (retained for historical compatibility).
2. Test fixtures using "paddleocr" as a backend name (~30 files — these
   test consensus/calibration infrastructure, not PaddleOCR itself;
   rewriting them is a separate cleanup plan).
3. Page-level ConsensusIR (`factory.py`, `grouping.py`, `scoring.py`).
4. PaddleOCR data files in `webui/cross_ref/data/` (historical baseline).
5. Any resolver, connector, or semantic-backend code.

Hard constraints:

1. No existing test may regress (except `test_entity_merge.py` which is
   deleted alongside its module).
2. `from pdf2md.consensus import build_consensus_ir` must still work.
3. `from pdf2md.semantic.candidates import entities_to_candidates` must
   still work.

---

## 5. File whitelist and forbidden files

Whitelist:

```text
src/pdf2md/consensus/entity_merge.py    (DELETE)
src/pdf2md/consensus/__init__.py        (edit)
src/pdf2md/semantic/candidates.py       (docstring edit, 1 line)
pdf2md.backends.example.toml            (comments only)
tests/test_entity_merge.py              (DELETE)
history.md                              (append M36)
STATE.md                                (update rows)
current_plan.md                         (status update)
```

Forbidden: everything else under src/, backend/, webui/, tools/.

---

## 6. Agent tasks

### Task A1 — Remove entity_merge module and test

1. Delete `src/pdf2md/consensus/entity_merge.py`.
2. Delete `tests/test_entity_merge.py`.
3. Update `src/pdf2md/consensus/__init__.py`: remove imports of
   `CONSENSUS_BACKEND` and `merge_entity_documents`; keep only
   `build_consensus_ir`, `ConsensusFactorySettings`, `ConsensusRunResult`.
4. Update `src/pdf2md/semantic/candidates.py` line 291: replace the
   docstring mentioning `consensus.merge_entity_documents` with
   "one connector's output per backend line".

Automated tests:

```bash
conda run -n pdf2md python -c "from pdf2md.consensus import build_consensus_ir; print('OK')"
conda run -n pdf2md python -c "from pdf2md.semantic.candidates import entities_to_candidates; print('OK')"
conda run -n pdf2md pytest tests/test_semantic_resolver.py tests/test_semantic_calibration_report.py -q
```

### Task A2 — Update backend config

1. Add deprecation comment to `[backends.paddleocr]` in
   `pdf2md.backends.example.toml` citing the 007_2 baseline numbers.
2. Add "DEFAULT backend" comment to `[backends.mineru]`.
3. Add "ALTERNATIVE backend" comment to `[backends.deepseek]`.

### Task A3 — Governance sync

1. Append M36 (006_4) to history.md.
2. Update STATE.md per §4 scope item 7.

---

## 7. Human verification

Deferred to in-product. Completion gate: automated tests pass, imports
clean, entity_merge gone.

---

## 8. Completion gate

```text
entity_merge.py and test_entity_merge.py deleted.
consensus.__init__ imports cleanly without entity_merge symbols.
candidates.py imports cleanly.
Full test suite green (minus the deleted test).
No forbidden files modified.
```

---

## PR_reviews

(none yet)

## Feedback

(none yet)
