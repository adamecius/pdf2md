# Plan 007_2 — Per-Dimension Semantic Calibration

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
Phase 5b — Calibration and quality measurement

Current roadmap estimate:
From 0% to 30% (Phase 5b)

Owner:
Agent team / human reviewer

Sequence:
Plan 007_2 (calibration sub-plan track)

Previous plan:
Plan 008_4 — Unresolved-Marker Diagnostic and Human Teaching Loop

Required previous plan status:
human_verified (or agent_complete with deferred H1)

Next plan after completion:
To be decided (candidates: 006_4 backend restructure, networkx in linking,
006_1 semantic router with calibrated weights).

Branch name:
plan-007_2-semantic-calibration

---

## 1. Purpose

Produce a per-backend, per-marker-type quality report for the semantic
cross-reference layer. The infrastructure exists: `evaluate_semantic()` in
`src/pdf2md/semantic/evaluation.py` computes marker P/R/F1, resolution
accuracy, and per-`RefType` breakdowns given an extracted graph and a ground-
truth graph; `tools/run_semantic_benchmark.py` runs this across a corpus.

What is missing: (1) nobody has run the benchmark across the full
`examples-only` corpus with the post-006_2/006_3/006_5 code and published
the results; (2) the benchmark does not yet produce a **cross-backend
comparison matrix** (backend × RefType → resolution rate) that makes the
asymmetries visible at a glance — the kind of table we built ad hoc from
the snapshot earlier in the project; (3) there is no per-backend,
per-RefType **calibration weight** derived from measured quality, which is
what Plan 006_1 (semantic router) will eventually consume.

This plan adds: a `tools/semantic_calibration_report.py` CLI that runs
`evaluate_semantic` across all (backend, example) pairs in the `examples-only`
data, emits a structured JSON report + a human-readable markdown summary,
and optionally ingests adjudication labels from Plan 008_4 as ground-truth
corrections. The report becomes the evidence base for routing decisions and
the input to a future calibration-weight generator.

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
git switch -c plan-007_2-semantic-calibration
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If git status is not clean before branch creation, stop and report.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress unless the plan explicitly allows it.
7. Do not mark this plan human_verified or finished.

Main conda environment:

```text
pdf2md
```

Repository-level commands must run using:

```bash
conda run -n pdf2md python <command>
```

This plan does NOT require backend execution. It reads existing graph JSON
files from `webui/cross_ref/data/` (the `examples-only` snapshot). No OCR
or semantic-model run required.

---

## 4. Scope, constraints, and dependencies

In scope:

1. `tools/semantic_calibration_report.py` CLI that:
   * Iterates over examples in `webui/cross_ref/data/manifest.json`.
   * For each example × semantic-backend × OCR-candidates combination
     present as a `<sem>__resolved_with__<ocr>.json` file, loads the graph.
   * Computes resolution rate per `marker_type` (resolved / total
     cross_reference edges, grouped by `marker_type`).
   * Computes overall resolution rate per combination.
   * Optionally loads a `<document_id>.adjudications.json` from Plan 008_4
     and applies `noise` decisions as FP corrections and `resolve` decisions
     as FN corrections to the counts.
   * Emits a structured JSON report
     (`semantic_calibration_report.json`) and a markdown summary table.
2. `src/pdf2md/calibration/semantic_report.py` module containing the
   report logic (pure functions, no CLI concerns) so it is testable.
3. Tests: unit tests for the report computation (given known edge counts,
   verify the per-type breakdown and the adjudication correction logic).
4. A sample run against the existing `examples-only` data, with the output
   committed as `docs/reports/semantic_calibration_baseline.md` — the
   first published calibration report for the project.

Out of scope:

1. Any change to `evaluate_semantic()` or the existing benchmark harness
   (this plan adds a new surface, it does not modify the existing one).
2. Calibration-weight generation (a future plan consumes this report).
3. Resolver or connector changes.
4. Teaching loop or viewer changes.
5. Ground-truth corpus expansion (Plan 007_1).

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan human_verified or finished.
3. No existing test may regress.
4. The report must be reproducible: given the same input graphs and
   adjudications, it must produce byte-identical JSON output (sort keys,
   deterministic ordering).
5. The CLI must work without any adjudication file (adjudications are
   optional enrichment, not a requirement).

Allowed Python dependencies:

```text
none (stdlib + pydantic already present)
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
src/pdf2md/calibration/semantic_report.py       (new)
tools/semantic_calibration_report.py            (new)
tests/test_semantic_calibration_report.py       (new)
docs/reports/semantic_calibration_baseline.md   (new)
docs/reports/semantic_calibration_baseline.json (new)
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
src/pdf2md/semantic/evaluation.py
src/pdf2md/semantic/resolver.py
src/pdf2md/semantic/graph_export.py
src/pdf2md/connectors/*
src/pdf2md/models/*
src/pdf2md/diagnostics/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*
backend/*
webui/*
tools/run_semantic_benchmark.py
```

Expected output artefacts:

```text
docs/reports/semantic_calibration_baseline.md
docs/reports/semantic_calibration_baseline.json
```

---

## 6. Agent tasks

### Task A1 — Report computation module

Title:
`src/pdf2md/calibration/semantic_report.py`

Goal:
Pure-function module that computes the per-backend × per-RefType resolution
matrix from a set of cross-reference graph files.

Files allowed:

```text
src/pdf2md/calibration/semantic_report.py
tests/test_semantic_calibration_report.py
```

Implementation requirements:

1. `load_graph(path: Path) -> dict`: load a graph JSON, return the raw dict.
2. `resolution_matrix(graphs: list[dict]) -> ReportData`: for each graph,
   iterate `edges` where `edge_kind == "cross_reference"`, group by
   `marker_type`, count resolved/total. Return a structured `ReportData`
   (dataclass or pydantic model) with:
   * `per_combo: list[ComboResult]` — one per (example, semantic_backend,
     ocr_backend) with overall and per-type rates.
   * `cross_backend_matrix: dict[str, dict[str, float]]` — aggregated
     across examples: `{marker_type: {ocr_backend: resolution_rate}}`.
3. `apply_adjudications(report: ReportData, adj: AdjudicationDocument) ->
   ReportData`: for each adjudication with `decision == "noise"`, decrement
   the total count for that marker_type (it was a false marker); for
   `decision == "resolve"`, increment the resolved count (the human found
   the target). Return corrected report.
4. `render_markdown(report: ReportData) -> str`: produce the summary table.
5. `render_json(report: ReportData) -> str`: produce deterministic JSON
   (sort_keys, indent=2).
6. Tests:
   * Build a minimal graph dict with 10 edges (5 resolved, 5 not, across
     2 marker_types). Assert `resolution_matrix` produces correct counts.
   * Build a minimal adjudication with 1 noise + 1 resolve decision.
     Assert `apply_adjudications` corrects the counts.
   * Assert `render_json` is deterministic (run twice, compare).

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_semantic_calibration_report.py -q
```

Completion evidence:
Files changed, tests run, exit codes, blockers.

Human verification required:
no

### Task A2 — CLI tool

Title:
`tools/semantic_calibration_report.py`

Goal:
CLI that discovers graph files in `webui/cross_ref/data/`, runs the report
computation, and writes the outputs.

Files allowed:

```text
tools/semantic_calibration_report.py
```

Implementation requirements:

1. Arguments:
   * `--data-dir` (default: `webui/cross_ref/data/`)
   * `--adjudications` (optional, path to an adjudications JSON)
   * `--out-dir` (required)
2. Discovery: read `manifest.json` in data-dir for examples; for each
   example, glob `<sem>__resolved_with__<ocr>.json`; also glob
   `entities_<ocr>.json` (for entity counts in the report header).
3. Run `resolution_matrix`, optionally `apply_adjudications`, then
   `render_markdown` + `render_json`.
4. Write `<out-dir>/semantic_calibration_report.{md,json}`.
5. Exit 0 on success, 2 on bad input, 3 on environment error.
6. Argparse, no third-party CLI lib.

Automated tests required:

```bash
conda run -n pdf2md python tools/semantic_calibration_report.py \
  --data-dir webui/cross_ref/data --out-dir /tmp/cal_test
test -f /tmp/cal_test/semantic_calibration_report.md && echo "OK" || echo "FAIL"
```

Completion evidence:
Files changed, CLI output, blockers.

Human verification required:
no

### Task A3 — Baseline report

Title:
Run the CLI against the existing `examples-only` data and commit the output.

Goal:
Produce the first published calibration report for the project.

Files allowed:

```text
docs/reports/semantic_calibration_baseline.md
docs/reports/semantic_calibration_baseline.json
```

Implementation requirements:

1. Run:
   ```bash
   conda run -n pdf2md python tools/semantic_calibration_report.py \
     --data-dir webui/cross_ref/data \
     --out-dir docs/reports
   mv docs/reports/semantic_calibration_report.md docs/reports/semantic_calibration_baseline.md
   mv docs/reports/semantic_calibration_report.json docs/reports/semantic_calibration_baseline.json
   ```
2. The markdown report must contain the cross-backend matrix showing
   resolution rates per marker_type per OCR backend (the table we built
   ad hoc earlier, now reproducible).
3. Commit both files.

Automated tests required:

```text
none (output is committed as a report artifact)
```

Completion evidence:
The two report files, with the cross-backend matrix visible in the markdown.

Human verification required:
no (deferred to in-product review of the report)

---

## 7. Human verification checkpoints

### Verification model

Human verification is **deferred to in-product**. The baseline report
(`docs/reports/semantic_calibration_baseline.md`) is the verification
artifact: the human reads it, confirms the numbers match expectations
from the examples-only analysis, and uses it as the evidence base for
routing decisions.

### Deferred checkpoint H1

Title:
Review the baseline calibration report against known asymmetries

Verification surface:
in_product (the published markdown report)

Pass criteria:

```text
The cross-backend matrix reproduces the known asymmetries:
  - Equation resolution: DeepSeek ~100%, MinerU high (post-006_2 fix).
  - Theorem-family: > 0% if 006_5 entities are in the snapshot
    (may still be 0% if the snapshot predates 006_5 — that is expected
    and noted, not a failure).
  - Bibliography/section/table: roughly equal across backends.
  - PaddleOCR: lowest across all types.
The report is reproducible (re-running the CLI produces identical JSON).
No previously-passing test regresses.
```

### Completion gate

```text
All A1 automated tests pass.
Full suite (pytest tests/ --ignore=tests/_legacy_temp -x) remains green.
CLI produces the baseline report without error.
No forbidden files modified.
No dependencies added.
```

When the automated gate passes, the plan advances to
`agent_complete → human_verified → finished` without blocking on H1.

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_semantic_calibration_report.py -q
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

Failure classes:

repository_defect:
Report computation wrong; counts don't match manual inspection;
adjudication correction logic inverted; non-deterministic JSON.

environment_missing:
`webui/cross_ref/data/` not populated (the examples-only data must be
present; if missing, classify as environment_missing and report).

test_expectation_wrong:
Test fixture counts don't match the computation contract.

upstream_dependency_issue:
n/a.

Failure handling:

If repository_defect: agent fixes or reports.
If environment_missing: agent reports; the human places the data.
If test_expectation_wrong: human revises.

---

## 9. Checkpoints, push policy, and hand-off

C0 Plan ready: status active; whitelist complete; tasks A1–A3; tests listed.

C1 Agent complete: all tasks attempted; tests green; CLI produces report;
baseline committed; status agent_complete.

C2 Human signs off: reviews baseline report; sets human_verified.

C3 Finished and promoted: archived; M35 appended to history.md; STATE.md
updated ("Semantic calibration" → built); next plan promoted.

Push policy:

```text
Agent may push the branch and open a draft PR.
Agent must not merge to main.
```

Hand-off after human sign-off:

1. Archive as `plans/archive/007_2-semantic-calibration.md`.
2. Append M35 to history.md.
3. Update STATE.md: "Semantic calibration" → built.
4. Promote next_plan.md to current_plan.md.
5. Record commit SHA / PR number.

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan: 007_2
Status:
Branch: plan-007_2-semantic-calibration
Commit or PR:
Files changed:
Forbidden files touched:
Tasks attempted: A1 / A2 / A3
Automated tests run / passed / failed:
Baseline report produced: yes/no
CLI exit code:
Failure classes:
Dependencies added: none expected
Blockers:
Next recommended action:
```

Reviewer checklist:

1. Only whitelisted files changed?
2. No forbidden files (evaluation.py, resolver.py, etc.) modified?
3. All tests green?
4. Baseline report contains the cross-backend matrix?
5. Report reproduces known asymmetries (equation, bibliography parity)?
6. JSON output is deterministic?
7. CLI works without adjudication file (optional enrichment)?
8. Safe to mark human_verified?

Status history:

```text
date — status — actor — note
2026-06-01 — active — human — plan drafted from full audit; grounded in
                               existing evaluate_semantic harness +
                               examples-only data
```

---

## PR_reviews

(none yet)

## Feedback

(none yet)
