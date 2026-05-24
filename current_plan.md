# Plan 007_0: Semantic Layer Ground Truth & Evaluation Harness

## Status: active
## Date: 2026-05-24
## Depends on: Plan 006_0 (human_verified, archived as M21)

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

Branch name:
plan-007-0-semantic-eval

Source plan:
plans/007_0-groundtruth-evaluation-example.md

---

## 1. Goal

Ship the ground-truth and evaluation half of the semantic layer:

1. A **LaTeXML TEI → CrossReferenceGraph** ground-truth parser that
   produces a `CrossReferenceGraph` (with `backend="ground_truth"` and
   `confidence=1.0`) from a `.tex` source using the system `latexml`
   tool (LaTeXML 0.8.6 is already installed on the dev host).
2. A **semantic evaluation harness** that aligns an extracted
   `CrossReferenceGraph` to a ground-truth graph and reports
   precision/recall/F1 for marker detection plus resolution accuracy.
3. A **benchmark runner CLI** that runs the Plan 006_0 backends across
   an existing groundtruth corpus and produces a per-backend per-document
   comparison table (CSV + JSON).

Scope reductions vs. the source plan:

- New controlled `.tex` corpus (source §2.1) → **deferred to Plan 007_1**;
  Plan 007_0 reuses the existing `groundtruth/corpus/latex/` fixtures
  shipped with previous plans.
- Worked example under `examples/semantic_cross_references/` (source §4)
  → **deferred to Plan 008**; the benchmark CLI is the proof-of-life
  artefact for Plan 007_0.

## 2. Ground-truth parser

`src/pdf2md/semantic/groundtruth.py` — new module that wraps the system
`latexml` binary and parses its TEI output into a `CrossReferenceGraph`:

```python
def generate_ground_truth(
    tex_path: Path,
    output_dir: Path,
    *,
    latexml_bin: str = "latexml",
) -> CrossReferenceGraph:
    """1. Run latexml on the .tex → TEI XML in output_dir/
       2. Parse TEI: extract <ref target="..."/>, <note>, <bibl>
       3. Build CrossReferenceGraph with backend="ground_truth"
    """
```

Behaviour:

- `latexml` binary lookup is `shutil.which(latexml_bin)`. When absent the
  function raises `LatexMLUnavailableError`; the CLI catches and exits 3.
- TEI parsing reuses the existing `_REF_TYPE_TO_MARKER` mapping from
  `backend/semantic/grobid/tei_parser.py` (loaded by `importlib.util` to
  preserve the standalone-backend isolation).
- Bibliography entries map to `SemanticEntity` with
  `entity_type=BIBLIOGRAPHY`.
- Edges with `target` attributes become resolved `RefEdge`s with
  `resolution_method="grobid_tei"` (the canonical "TEI-derived" method).

## 3. Evaluation harness

`src/pdf2md/semantic/evaluation.py` — new module:

```python
@dataclass(frozen=True)
class SemanticEvalResult:
    document_id: str
    backend: str
    marker_precision: float
    marker_recall: float
    marker_f1: float
    marker_f1_by_type: dict[str, float]
    resolution_accuracy: float
    resolution_accuracy_by_type: dict[str, float]
    entity_precision: float
    entity_recall: float
    entity_f1: float
    n_markers_extracted: int
    n_markers_truth: int
    n_markers_matched: int

def evaluate_semantic(
    extracted: CrossReferenceGraph,
    ground_truth: CrossReferenceGraph,
    *,
    document_id: str,
    backend: str,
) -> SemanticEvalResult:
    ...
```

Marker alignment is content-based:

- Two markers match iff they share the same `marker_type` AND have an
  overlapping or identical `marker_text` (case-insensitive, whitespace-
  collapsed). Char offsets are NOT used directly because the regex
  backend operates on extracted text while ground truth comes from
  LaTeXML — offsets are different coordinate spaces.

Resolution accuracy:

- For each matched marker pair, if both the extracted side and the GT
  side have a resolved edge AND `target_ref` strings match (after
  normalisation to drop "#" prefixes), the resolution is counted as
  correct.

Per-type metrics:

- F1 per `RefType` is computed separately; missing types report 0.0
  with `n=0` in the underlying tally.

## 4. Benchmark runner CLI

`tools/run_semantic_benchmark.py` — argparse CLI:

```
python tools/run_semantic_benchmark.py \
    --gt-dir groundtruth/corpus/latex/ \
    --backends regex \
    --out-dir /tmp/semantic_bench
```

Behaviour:

- Discovers all `*.tex` files under `--gt-dir` (recursive).
- For each .tex: generates GT via §2, then runs each requested backend
  against the rendered text (LaTeX → plain text via a small inline
  detexer; the PDF / image path is out of scope for this plan).
- Backends are the Plan 006_0 adapters by name: `regex`, `grobid`,
  `vlm`, plus the synthetic `ensemble`. Unavailable backends are
  skipped with a warning, not an error.
- Writes:
  - `<out-dir>/<doc>/gt_cross_references.json`
  - `<out-dir>/<doc>/<backend>_cross_references.json`
  - `<out-dir>/results.json` — all `SemanticEvalResult` entries
  - `<out-dir>/results.csv` — flat table for downstream analysis
- Exit codes: 0 success; 2 bad args; 3 if `latexml` is not on `$PATH`.

## 5. File structure (new)

```text
src/pdf2md/semantic/groundtruth.py
src/pdf2md/semantic/evaluation.py
src/pdf2md/semantic/__init__.py          (re-exports)
tools/run_semantic_benchmark.py
tests/test_semantic_groundtruth.py
tests/test_semantic_evaluation.py
tests/test_run_semantic_benchmark_cli.py
tests/data/semantic_fixtures/eval_extracted.json
tests/data/semantic_fixtures/eval_truth.json
```

## 6. Acceptance criteria

- [ ] `generate_ground_truth(...)` runs LaTeXML, parses TEI, returns a
      `CrossReferenceGraph` with `backend_versions["ground_truth"]`
      non-empty and at least one `RefMarker` on the existing
      `groundtruth/corpus/latex/linked_sections_figures/linked_sections_figures.tex`
      fixture (automated A1).
- [ ] `evaluate_semantic(...)` reports the expected
      precision/recall/F1 on the static
      `tests/data/semantic_fixtures/eval_*.json` fixtures (automated A2).
- [ ] `tools/run_semantic_benchmark.py --gt-dir <small-subset> --backends regex --out-dir <tmp>`
      exits 0 and produces `results.json` + `results.csv` with at least
      one row per (document, backend) pair (automated A3).
- [ ] When `latexml` is absent (mocked PATH), the CLI exits 3 with a
      clean `env_not_ready` message (automated A4).
- [ ] All new test files pass: `pytest tests/test_semantic_groundtruth.py
      tests/test_semantic_evaluation.py tests/test_run_semantic_benchmark_cli.py -q`
      (automated A5).
- [ ] No regressions: `pytest tests/ -q --ignore=tests/_legacy_temp -x`
      still green (automated A6).

---

## File whitelist

```text
src/pdf2md/semantic/groundtruth.py
src/pdf2md/semantic/evaluation.py
src/pdf2md/semantic/__init__.py
tools/run_semantic_benchmark.py
tests/test_semantic_groundtruth.py
tests/test_semantic_evaluation.py
tests/test_run_semantic_benchmark_cli.py
tests/data/semantic_fixtures/eval_extracted.json
tests/data/semantic_fixtures/eval_truth.json
current_plan.md
run_log.md
```

## Forbidden files

```text
src/pdf2md/semantic/base.py
src/pdf2md/semantic/regex_adapter.py
src/pdf2md/semantic/grobid_adapter.py
src/pdf2md/semantic/vlm_adapter.py
src/pdf2md/semantic/resolver.py
src/pdf2md/semantic/ensemble.py
src/pdf2md/models/**/*
src/pdf2md/pipeline/**/*
src/pdf2md/cli/**/*
src/pdf2md/connectors/**/*
src/pdf2md/calibration/**/*
src/pdf2md/consensus/**/*
src/pdf2md/linking/**/*
src/pdf2md/export/**/*
backend/**/*
project.md
ROADMAP.md
README.md
history.md
PLAN_TEMPLATE.md
agent.md
plans/**/*
docs/**/*
groundtruth/**/*
```

## Allowed dependencies

```text
pydantic, requests          (already required)
xml.etree                   (stdlib)
subprocess, shutil, pathlib (stdlib)
csv, json, dataclasses      (stdlib)
re, argparse, sys, time     (stdlib)
pytest                      (already required)
```

External system tool: **`latexml`** (LaTeXML 0.8.6, already installed at
`/usr/bin/latexml` on the dev host; no install commands run in agent
mode). The CLI gracefully exits 3 with `env_not_ready` when absent.

## Allowed environment-modifying commands

```text
none in agent mode

(LaTeXML is invoked as a read-only subprocess. The agent does not run
apt-get, cpanm, or any installer.)
```

## 7. Human verification checkpoints

### Checkpoint H1 — Ground truth on a known fixture

Command:

```bash
conda run -n pdf2md python tools/run_semantic_benchmark.py \
    --gt-dir groundtruth/corpus/latex/linked_sections_figures \
    --backends regex \
    --out-dir /tmp/semantic_bench_h1
```

Pass criteria:

```text
exit code 0
/tmp/semantic_bench_h1/results.json exists and is non-empty
/tmp/semantic_bench_h1/results.csv exists with a header + ≥1 data row
/tmp/semantic_bench_h1/<doc>/gt_cross_references.json has ≥1 marker
```

### Checkpoint H2 — Eval against synthetic fixtures (also runnable as automated)

```bash
conda run -n pdf2md pytest tests/test_semantic_evaluation.py -q
```

Pass criteria: all tests green.

---

## PR_reviews

(none yet)

## Feedback

(none yet)
