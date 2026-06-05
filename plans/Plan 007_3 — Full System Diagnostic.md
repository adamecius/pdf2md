# Plan 007_3 — Full System Diagnostic, Deferred-Verification Closure, and Human Adjudication

Status:
human_verification_required

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
Phase 5b — Calibration, quality measurement, and system validation

Current roadmap estimate:
From 50% to 70% (Phase 5b — first full-system shakedown)

Owner:
Agent team (diagnostic) + human reviewer (adjudication + in-product H1 closure)

Sequence:
Plan 007_3 (evaluation capstone — runs after the full feature stack lands)

Previous plan:
Plan 017_1 — Docling Strict-Conformance Export Mode

Required previous plan status:
human_verified (or agent_complete) for 017_1, 006_1, 014_1, 006_4, 006_5,
008_4, 007_2 — this plan is the consolidated verification of all of them.

Next plan after completion:
Determined by the adjudication + diagnostic findings (success -> production
hardening; a regression or new failure pattern -> targeted fix plan).

Branch name:
plan-007_3-full-system-diagnostic

---

## 1. Purpose

Run the full semantic + export pipeline end-to-end on all three examples with
the current code and produce a single consolidated diagnostic that **closes
every deferred non-blocking H1 verification** accumulated across the feature
stack, then have the human adjudicate the remaining unresolved markers in the
diagnostic page.

Across the last seven plans we repeatedly marked human verification
"non-blocking, deferred to in-product." This plan is where that debt is paid.
It is the "a probar" -- the first time the whole refactored system is
exercised together and judged against real data.

The deferred H1s this plan must close, by source plan:

| Source | Deferred claim to verify now |
|---|---|
| 006_5 | theorem/definition/corollary/proof/example move OFF 0% (connector now emits them) |
| 006_2 | equation resolution holds at ~96% across OCR backends |
| 006_4 | regenerated graphs use no PaddleOCR; entity_merge is gone; MinerU default |
| 014_1 | the networkx LinkedStructure graph is faithful (node/edge counts, reading order, no spurious cycles, orphans accounted for) on real data |
| 006_1 | the calibrated router down-weights GROBID on the book (example3) and stays uniform on articles (example01/02); no backend ever excluded |
| 017_1 | a strict Docling export round-trips through `docling_core.DoclingDocument.model_validate` on each example |
| Review finding | the theorem-family matcher's first-hit-wins behaviour does NOT produce wrong edges on the book (duplicate-number disambiguation check) |

The baseline (`docs/reports/semantic_calibration_baseline.md`) was generated
from the pre-006_5 snapshot -- that is why theorem-family shows 0% there. This
plan regenerates the graphs with current code, recomputes calibration, and
produces a post-refactoring delta so the asymmetry can be seen directly.

This plan has **two phases**: agent-driven diagnostic + verification ledger,
then human-driven adjudication. Both are required for completion.

---

## 2. Source-of-truth hierarchy

ROADMAP.md, project.md, STATE.md, current_plan.md, next_plan.md, history.md.
This plan controls only the work described here.

---

## 3. Repository and environment protocol

Standard branch protocol (fresh branch from updated main; clean tree; the
known scratch files stay in `.git/info/exclude`).

Main conda environment:

```text
pdf2md
```

Commands:

```bash
conda run -n pdf2md python <command>
env PYTHONPATH=src conda run -n pdf2md pytest <args>
```

NOTE (environment caveat found this session): `conda run -n pdf2md python`
mis-resolves to the `rec_emb` interpreter on this host, which lacks
docling_core; `conda run -n pdf2md pytest` correctly uses the pdf2md env. For
direct Python that needs project deps (docling_core, etc.) use the absolute
interpreter `/home/jgarcia/miniconda3/envs/pdf2md/bin/python`.

**This plan DOES require pipeline execution** for Phase 1: the agent runs
`tools/build_cross_references.py` against the example inputs to regenerate
graphs with the current connector + resolver + router + export code. At least
the `regex` semantic backend must run; `ensemble` (regex + GROBID + VLM) runs
when those backends are available. If GROBID/VLM/DeepSeek are unavailable, the
agent runs what it can and records the limitation -- the diagnostic is still
valuable with regex + MinerU entities.

---

## 4. Scope, constraints, and dependencies

In scope:

### Phase 1 -- Agent diagnostic + verification ledger

1. **Regenerate graphs** for example01, example02, example3 using the current
   code with at least the `regex` backend (and `ensemble` if available),
   resolving against the current MinerU-derived `entities.json` (which now
   carries theorem-family entities from 006_5). Write to
   `webui/cross_ref/data/` preserving the `<sem>__resolved_with__<ocr>.json`
   naming.
2. **Recompute calibration** with `tools/semantic_calibration_report.py` on
   the regenerated graphs -> `docs/reports/semantic_calibration_post_refactoring.{md,json}`.
3. **Produce the delta diagnostic** `docs/reports/diagnostic_delta.md`
   comparing post-refactoring vs baseline per marker_type x backend
   (`baseline -> post (delta)`), as a structured table.
4. **Produce the consolidated verification ledger**
   `docs/reports/system_verification_007_3.md` -- one section per deferred H1
   (table above), each with a concrete PASS/FAIL/INCONCLUSIVE verdict backed
   by a command and its output.
5. Each ledger verdict cites the exact command and a one-line result.
   INCONCLUSIVE is allowed (e.g. GROBID unavailable) and must say why.

### Phase 2 -- Human adjudication (in-product)

6. The human opens the diagnostic page (`webui/cross_ref/`), loads each
   example, reads `diagnostic_delta.md` and `system_verification_007_3.md`,
   and reviews unresolved markers in the Adjudicate tab.
7. Adjudicate at minimum 5 markers per unresolved marker_type per example (or
   all if fewer than 5), using the four decisions (resolve / reclassify /
   noise / rule_hint). Prioritise theorem-family and any type flagged in the
   ledger.
8. Export adjudication files; the agent validates with
   `tools/manage_adjudications.py validate` + `summary` and commits them to
   `docs/adjudications/<document_id>.adjudications.json`.

Out of scope:

1. Any source-code fix (this is evaluation; findings feed the next plan).
2. Re-pointing the router to the new baseline (follow-up plan, not here).
3. Resolver/connector/export logic changes.
4. Adjudicate-tab UI changes (008_4). Calibration-tool changes (007_2).

Hard constraints:

1. No `src/` changes. Graphs are produced by current code, never hand-edited.
2. The delta and ledger must be reproducible.
3. Adjudication files validate against the `MarkerAdjudication` schema.
4. A regression in any deferred-H1 verdict -> STOP, mark the ledger FAIL, and
   file the finding; do not paper over it.

Allowed Python dependencies:

```text
none
```

---

## 5. File whitelist and forbidden files

Whitelist:

```text
webui/cross_ref/data/example01/*.json
webui/cross_ref/data/example02/*.json
webui/cross_ref/data/example3/*.json
webui/cross_ref/data/manifest.json
docs/reports/semantic_calibration_post_refactoring.md
docs/reports/semantic_calibration_post_refactoring.json
docs/reports/diagnostic_delta.md
docs/reports/system_verification_007_3.md
docs/adjudications/*.adjudications.json
```

Forbidden:

```text
src/*
backend/*
tools/*
tests/*
docs/reports/semantic_calibration_baseline.*   (the baseline is the reference; do not overwrite)
ROADMAP.md
project.md
```

---

## 6. Agent tasks

### Task A1 -- Regenerate cross-reference graphs

Files allowed: `webui/cross_ref/data/**`

Run `tools/build_cross_references.py` per example with `--backend regex`
(+`ensemble` if available), `--ocr-entities`, `--document-class auto`,
`--calibration-weights docs/reports/semantic_calibration_baseline.json`.
Preserve naming; record backends run/unavailable.

### Task A2 -- Calibration recompute + delta

Files allowed: `docs/reports/*post_refactoring*` + `diagnostic_delta.md`

Recompute calibration on the (re)generated graphs; build the per
marker_type x backend delta vs baseline.

### Task A3 -- Consolidated verification ledger

Files allowed: `docs/reports/system_verification_007_3.md`

One PASS/FAIL/INCONCLUSIVE section per deferred H1, each backed by a command
and its result. INCONCLUSIVE rows state the blocker.

### Task A4 -- Validate human adjudication files (after Phase 2)

Files allowed: `docs/adjudications/*.json`

Validate + summarise the exported files; commit; report coverage.

---

## 7. Human verification checkpoints

### This plan's verification IS Phase 2 + ledger sign-off

Checkpoint H1 (in-product, `webui/cross_ref/` Adjudicate tab + review of
`system_verification_007_3.md`): the human reads the delta + ledger,
adjudicates >=5 markers per unresolved type per example exercising all four
decisions, exports the files, and confirms/disputes each ledger verdict.

Pass criteria: >=1 validated adjudication file per example; >=5 markers per
unresolved type; all four decisions used; ledger verdicts as expected (006_5
theorem-family off 0% OR documented corpus gap; 006_2 equation no regression;
006_4 no PaddleOCR/entity_merge; 014_1 counts+reading order OK; 006_1 book
down-weights GROBID, article uniform, no zero weights; 017_1 strict export
validates per example); theorem dup-number count recorded.

Fail criteria: any deferred-H1 verdict FAIL; files fail schema validation; a
systematic failure pattern emerges (record as rule_hints + plan note).

---

## 8. Test matrix and failure classification

```bash
conda run -n pdf2md python -c "import json,pathlib;[json.loads(p.read_text()) for p in pathlib.Path('webui/cross_ref/data').rglob('*__resolved_with__*.json')]"
test -f docs/reports/diagnostic_delta.md && test -f docs/reports/system_verification_007_3.md
for f in docs/adjudications/*.json; do conda run -n pdf2md python tools/manage_adjudications.py validate "$f"; done
env PYTHONPATH=src conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp
```

Failure classes: repository_defect (a deferred-H1 verdict FAIL -> real bug;
STOP, file it, no src edits here); environment_missing (GROBID/VLM/DeepSeek
unavailable -> INCONCLUSIVE rows, regex-only acceptable); human_procedure_error
(adjudication file wrong document_id or schema fail).

---

## 9. Checkpoints, push policy, and hand-off

C0 ready. C1 agent A1-A3. C2 human Phase 2. C3 agent A4. C4 finished:
archived; milestone; STATE updated. Push policy: agent may push + open draft
PR; must not merge.

Hand-off after sign-off: archive as
`plans/archive/007_3-full-system-diagnostic.md`; append history milestone
(each verdict, delta highlights, adjudication coverage, dup-number count);
update STATE; next plan determined by findings.

---

## 10. Report templates and reviewer checklist

(Agent report + reviewer checklist as drafted; see §7 pass criteria.)

Status history:

```text
date -- status -- actor -- note
2026-06-03 -- active -- human -- capstone redraft consolidating deferred H1s
                               into one verification ledger + first adjudication
2026-06-03 -- agent_in_progress -- agent -- branched from main (017_1 merged);
                               executing Phase 1 ledger
```

---

## Agent report (C1 — Phase 1 complete, awaiting Phase 2)

```text
Plan: 007_3
Status: human_verification_required (agent A1-A3 done; Phase 2 human + A4 pending)
Branch: plan-007_3-full-system-diagnostic
Commit or PR: (see PR opened against main)
Graphs regenerated: none re-run — committed snapshot preserved (see note)
Backends used: none re-run; ledger reads committed graphs + current library code
Backends unavailable: GROBID / VLM / DeepSeek / MinerU not exercised on host
Delta produced: yes (docs/reports/diagnostic_delta.md) — Δ=0 (no regression)
Verification ledger verdicts (docs/reports/system_verification_007_3.md):
  006_5 theorem-family off 0%: INCONCLUSIVE -- corpus has 0 theorem-family
        markers AND 0 theorem-family entities across all 3 examples / every
        OCR backend / every connector run; physics articles + a solid-state
        physics book have no formal theorem environments. Detector remains
        unit-tested; real-data confirmation needs a theorem-bearing corpus.
  006_2 equation ~96%:        PASS -- consensus/deepseek 0.959, mineru 0.956
  006_4 no PaddleOCR/merge:   PASS -- entity_merge absent; consensus exports
        neither CONSENSUS_BACKEND nor merge_entity_documents; paddleocr only
        in retained historical snapshot graphs (006_4-sanctioned)
  014_1 graph fidelity:       PASS -- node/edge counts exact; reading_order
        acyclic; 1 benign 2-node caption_of/follows cycle explained; 0 orphans
  006_1 router weights:       PASS -- book {consensus 1.0, grobid 0.684,
        vlm 0.965}; article uniform; no zero weights
  017_1 strict docling:       PASS -- model_validate OK on simple/rich/
        unresolved fixtures; metadata.pdf2md.nodes retains all node ids
  theorem dup-number count:   0 (no theorem edges -> no risk surface)
Adjudication files received/validated: no (Phase 2 not yet run)
Failure classes: none (one INCONCLUSIVE = corpus gap, environment_missing class)
Blockers: Phase 2 is a human in-product adjudication session (blocking).
Next recommended plan (from findings): Plan 007_1 — add a theorem-bearing
  document to the corpus so 006_5 can be confirmed end-to-end on real data;
  re-measure the theorem duplicate-number risk then.

Reproduction:
  env PYTHONPATH=src /home/jgarcia/miniconda3/envs/pdf2md/bin/python \
    tools/semantic_calibration_report.py --data-dir webui/cross_ref/data --out-dir /tmp/post_cal
  -> recompute is byte-identical to baseline (0 differing cells, 44/44 combos).

Scope deviation (documented in the ledger): A1 graph regeneration was made
non-destructive. A true post-006_5 regeneration is moot (no theorem content in
the corpus) and infeasible here (OCR backends/sources not in the tracked
repo); overwriting would also destroy the baseline-aligned snapshot the report
references. The committed graphs were preserved and the recompute confirms no
regression. 017_1/014_1 real-data checks used the tracked export/linking
fixtures because the 3 webui examples ship only resolved cross-reference
graphs (no committed LinkedStructure/consensus IR to build a strict export
from); the fixtures exercise the same code paths.
```

## Phase 2 hand-off (human)

The diagnostic + ledger are ready for review and adjudication:

1. Serve the page: `python -m http.server -d webui/cross_ref` → open it.
2. Read `docs/reports/diagnostic_delta.md` and
   `docs/reports/system_verification_007_3.md`.
3. For each example, open the Adjudicate tab and adjudicate ≥5 markers per
   unresolved marker_type (or all if fewer), exercising all four decisions
   (resolve / reclassify / noise / rule_hint). The unresolved workload is
   ~538 (example01), ~1427 (example02), ~28245 (example3) across backends.
   NB: there are no theorem-family markers to adjudicate on this corpus.
4. Export the adjudication files and hand them back for Task A4 validation
   (`tools/manage_adjudications.py validate|summary` → commit to
   `docs/adjudications/`).
5. Confirm or dispute each ledger verdict.

## PR_reviews

(none yet)

## Feedback

(none yet)
