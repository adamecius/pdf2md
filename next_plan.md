# Plan 007_3 — Full System Diagnostic and Human Adjudication

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

Queued: promote to current_plan.md after Plan 017_1 (Docling strict export)
is human_verified / merged.

Linked ROADMAP phase:
Phase 5b — Calibration and quality measurement

Current roadmap estimate:
From 30% to 50% (Phase 5b)

Owner:
Agent team (diagnostic) + human reviewer (adjudication)

Sequence:
Plan 007_3 (evaluation sub-plan)

Previous plan:
Plan 017_1 — Docling Strict-Conformance Export Mode

Required previous plan status:
human_verified (or agent_complete with deferred verification)

Next plan after completion:
To be determined — the adjudication results drive what comes next.

Branch name:
plan-007_3-full-system-diagnostic

---

## 1. Purpose

Run the full semantic pipeline end-to-end on all three examples with the
current code (post-006_2 equation normalization, post-006_3 theorem matcher,
post-006_5 theorem entity detector, post-006_4 PaddleOCR deprecation,
post-006_1 calibrated router) and evaluate whether the cross-reference graph
is correct.

The current baseline (`docs/reports/semantic_calibration_baseline.md`) was
generated from the `examples-only` snapshot, which **predates 006_5**
(theorem-family entities). That is why theorem/definition/corollary/proof/
example show 0% — the connector did not emit those entities when the snapshot
was created. This plan regenerates the graphs with the current code and
produces a **post-refactoring diagnostic** that shows what improved, what is
still broken, and where human adjudication is needed.

After the agent produces the diagnostic, the human opens the diagnostic page
(the Adjudicate tab in `webui/cross_ref/`), reviews the graph, identifies
markers that are not properly resolved (corollary, definitions, etc.), and
adjudicates them. The exported adjudication file is the plan's primary
deliverable — it becomes the first real ground-truth signal from the
refactored system.

This plan has **two phases**: agent-driven diagnostic, then human-driven
adjudication. Both are required for completion.

---

## 2. Source-of-truth hierarchy

Standard.

---

## 3. Repository and environment protocol

Standard branch protocol.

**This plan DOES require backend execution** for Phase 1: the agent must run
`tools/build_cross_references.py` with the `regex` backend (and optionally
`ensemble` if GROBID/VLM are available) against the example PDFs or text
files to regenerate the cross-reference graphs with the current connector +
resolver code.

If GROBID Docker or DeepSeek-VL2 are not available, the agent runs `regex`
only and reports the environment limitation. The diagnostic is still valuable
with regex alone.

NOTE (added when queued behind 017_1): Phase-1 scouting found that
`webui/cross_ref/data/<example>/` ships only pre-built per-backend marker
graphs (`regex.json`, `grobid.json`, `vlm_v4.json`, `consensus.json`),
per-OCR-backend entity proposals (`entities_*.json`), and resolved graphs
(`<sem>__resolved_with__<ocr>.json`) — **no source text or PDF inputs, and
the `entities_*.json` predate 006_5** (e.g. example01/entities_mineru.json
contains no theorem-family entity types). The real example source documents
were not in the tracked repo at scouting time (only local scratch under the
untracked `pdf2md/` clone). Phase 1 must FIRST locate/stage the real example
inputs (text for regex; PDFs + freshly-regenerated entities for resolve)
before regeneration; otherwise re-running only the resolver over the existing
pre-006_5 entities would NOT surface the theorem-family improvement and the
delta would be misleading. Resolve this input-sourcing question on promotion.

Main conda environment:

```text
pdf2md
```

---

## 4. Scope, constraints, and dependencies

In scope:

### Phase 1 — Agent diagnostic

1. Regenerate cross-reference graphs for example01, example02, and example3
   using the current code with at least the `regex` backend (and `ensemble`
   if available). Write the new graphs to `webui/cross_ref/data/`.
2. Run `tools/semantic_calibration_report.py` on the new graphs to produce
   an updated calibration report
   (`docs/reports/semantic_calibration_post_refactoring.md`).
3. Produce a **delta diagnostic** comparing the post-refactoring report to
   the baseline (`docs/reports/diagnostic_delta.md`): for each
   marker_type × backend, the change in resolution rate.
4. Flag: types that moved off 0%, regressions (should be none), types still
   at 0%, and total unresolved markers per example.

### Phase 2 — Human adjudication (in-product)

5-9. Human opens the Adjudicate tab, reviews unresolved markers, adjudicates
≥5 per unresolved type per example using the four decision types, exports the
files; the agent validates them with `tools/manage_adjudications.py` and
commits them to `docs/adjudications/<document_id>.adjudications.json`.

Out of scope:

1. Any resolver/connector/backend code change (evaluation, not feature work).
2. Adjudicate tab UI (built in 008_4); calibration report tool (built in 007_2);
   ground-truth corpus expansion (007_1).

Hard constraints:

1. No `src/` changes — read and evaluate only.
2. Regenerated graphs produced by current code, not hand-edited JSON.
3. Adjudication files validate against the `MarkerAdjudication` schema.
4. The delta diagnostic must be reproducible.

---

## 5. File whitelist and forbidden files

Whitelist:

```text
webui/cross_ref/data/example01/*.json
webui/cross_ref/data/example02/*.json
webui/cross_ref/data/example3/*.json
webui/cross_ref/data/manifest.json
docs/reports/semantic_calibration_post_refactoring.md   (new)
docs/reports/semantic_calibration_post_refactoring.json (new)
docs/reports/diagnostic_delta.md                        (new)
docs/adjudications/*.adjudications.json                 (new, from human)
```

Forbidden:

```text
src/*
backend/*
tools/*
tests/*
```

---

## 6-10 — Agent tasks, verification, hand-off

(Full text as drafted by the human: Tasks A1 regenerate graphs, A2
post-refactoring calibration + delta diagnostic, A3 validate human
adjudication files after Phase 2. Human verification IS Phase 2 —
checkpoint H1, in-product adjudication session in the Adjudicate tab. The
next plan after completion is determined by what the adjudication reveals
[theorem-family off 0% → feature work; still 0% → debug plan; new failure
pattern → targeted fix]. Push policy: agent may push, must not merge.)

Status history:

```text
date — status — actor — note
2026-06-03 — active — human — final evaluation plan; runs the full
                               refactored system and captures the first
                               real human adjudication ground-truth
2026-06-03 — draft  — agent  — re-queued behind Plan 017_1 (Docling strict
                               export) at the user's direction; recorded the
                               missing example-source-input finding for
                               Phase 1 to resolve on promotion
```
