# Calibration and factory-prior management

This document is the operator's reference for the calibration
subsystem and the three-level prior hierarchy introduced by Plan 19.
It covers:

1. What calibration produces and where the files live.
2. How `tools/calibrate_priors.py` is invoked.
3. The user → factory → uninformative fallback chain consumed by
   `consensus/io.py` at runtime.
4. **How to refresh the factory priors shipped with the package** —
   the update protocol (covers H6).
5. How to verify the post-Plan-19 invariants (H3 + H4 in
   [tests/test_bayesian_feature_picker_human_h.py](../tests/test_bayesian_feature_picker_human_h.py)).

---

## 1. What calibration produces

`tools/calibrate_priors.py` consumes a ground-truth corpus with the
layout below and produces one `CalibrationPriorDocument` JSON per
backend plus a summary report:

```text
<corpus-root>/
└── <doc-id>/
    ├── truth.json                    # CalibrationTruthDocument
    ├── <backend-a>/
    │   ├── pages/page_NNNN.json      # PageExtractionIR per page
    │   ├── entities.json             # EntityProposalDocument
    │   └── manifest.json
    └── <backend-b>/...
```

Output:

```text
<out-dir>/
├── priors/
│   ├── <backend-a>.json              # CalibrationPriorDocument
│   └── <backend-b>.json
└── reports/
    ├── calibration_report.json
    ├── calibration_summary.txt
    └── blockkind_vocabulary_alignment_report.json
```

Each prior carries calibrated per-BlockKind, per-EntityType,
per-RelationType, and per-calibration-key metrics: precision, recall,
F1, support, `calibrated_confidence`, and a `status` of `calibrated`,
`underpowered`, `no_samples`, or `uninformative`.

The consensus scorer
([src/pdf2md/consensus/scoring.py](../src/pdf2md/consensus/scoring.py))
weights `calibrated_confidence` at 0.35 per BlockKind and 0.20 per
EntityType, which makes calibration the dominant signal in the
post-Plan-19 weighting (0.55 of the 1.0 total weight).

---

## 2. Running calibration

Minimal invocation against the synthetic LaTeX corpus:

```bash
conda run -n pdf2md python tools/calibrate_priors.py \
    --root <corpus-root> \
    --out-dir .tmp/calibration_run \
    --backends paddleocr,deepseek,mineru \
    --min-samples 5
```

Useful flags:

| Flag | Effect |
|---|---|
| `--min-samples N` | Statuses become `underpowered` below this floor. |
| `--smoothing-alpha A --smoothing-beta B` | Beta-binomial smoothing for the precision estimate (default 1/1). |
| `--default-confidence X` | Confidence used for missing or `no_samples` keys (default 0.50). |
| `--skip-vocabulary-gate` | Skip the BlockKind vocabulary alignment check (only when truths already carry canonical labels). |
| `--strict` | Fail hard on invalid truths instead of skipping with a warning. |
| `--from-scratch` | **Bayesian "from-scratch" mode.** Stamps `calibration_mode="from_scratch"` in the report and in every per-backend prior file's `metadata`. Calibration is always computed from truth + backend output; this flag only records provenance. Without it, mode = `incremental`. |
| `--verbose` | Print the full JSON report to stdout. |

Inspect the result:

```bash
cat .tmp/calibration_run/reports/calibration_summary.txt
jq '.plan13_readiness.safe_for_consensus' \
    .tmp/calibration_run/reports/calibration_report.json
```

Each backend listed in `safe_for_consensus` has at least one
`calibrated` BlockKind metric and is ready for the consensus picker
to consume.

---

## 3. Prior resolution at consensus time (Plan 19)

`src/pdf2md/consensus/io.py` resolves priors **per backend** via a
three-level fallback chain when the consensus stage loads its inputs:

```text
1. user-calibrated prior at <priors-dir>/<backend>.json   (silent on success)
2. factory prior at src/pdf2md/data/factory_priors/<backend>.json
   → warning: prior_factory:<backend>
3. uninformative prior built in-memory
   (uniform default_confidence, status=UNINFORMATIVE)
   → warning: prior_uninformative:<backend>
```

The pipeline therefore always works — there is no chicken-and-egg
between calibration and consensus. Refresh user priors only when a
benchmark run materially improves on the factory priors.

The level used per backend is recorded in the consensus stage's
warnings list (`prior_factory:` / `prior_uninformative:`) and in the
prior document's own `metadata.prior_type` field (`calibrated` /
`factory` / `uninformative`).

---

## 4. Factory-prior update protocol (H6)

Factory priors ship under
[src/pdf2md/data/factory_priors/](../src/pdf2md/data/factory_priors/)
as package data declared in
[pyproject.toml](../pyproject.toml)'s
`[tool.setuptools.package-data]` section. They are loaded at runtime
via `pdf2md.models.priors.load_factory_prior()`.

**When to refresh:**

- The LaTeX benchmark corpus changes materially (new fixture
  categories, new ground-truth contracts).
- A new backend is wired into `pdf2md.backends.toml`.
- A backend version bumps materially (e.g. MinerU 2.5 → 3.0;
  PaddleOCR-VL → PP-StructureV3).
- Production telemetry shows the existing factory priors are no
  longer representative.

**Procedure:**

```bash
# 1. Run calibration against the benchmark corpus in "from-scratch"
#    mode so the resulting priors carry calibration_mode=from_scratch.
conda run -n pdf2md python tools/calibrate_priors.py \
    --root <benchmark-corpus-root> \
    --out-dir /tmp/factory_prior_update \
    --from-scratch \
    --verbose

# 2. Sanity-check the calibration_report. Every backend you intend
#    to ship must appear in safe_for_consensus.
jq '.plan13_readiness.safe_for_consensus' \
    /tmp/factory_prior_update/reports/calibration_report.json

# 3. Copy the new priors into package data.
cp /tmp/factory_prior_update/priors/*.json \
   src/pdf2md/data/factory_priors/

# 4. Stamp metadata.prior_type = "factory" so consensus io can tell
#    factory priors apart from user priors at runtime.
conda run -n pdf2md python -c "
import json, glob
for path in glob.glob('src/pdf2md/data/factory_priors/*.json'):
    with open(path) as f:
        doc = json.load(f)
    md = doc.setdefault('metadata', {})
    md['prior_type'] = 'factory'
    md.setdefault('source', 'calibrated_against_benchmark_corpus')
    with open(path, 'w') as f:
        json.dump(doc, f, indent=2)
"

# 5. Run the factory-prior and fallback tests.
conda run -n pdf2md pytest \
    tests/test_factory_priors.py \
    tests/test_consensus_prior_fallback.py \
    tests/test_bayesian_feature_picker_human_h.py -v

# 6. Commit. Factory priors are versioned with the package — replace,
#    don't accumulate.
git add src/pdf2md/data/factory_priors/*.json
git commit -m "calibration: refresh factory priors against <corpus>"
```

**Placeholder backends.** If a backend exists in the config but has
no benchmark calibration yet (e.g. mineru pre-2026-05), ship an
uninformative placeholder:

```python
from pdf2md.models.priors import build_uninformative_prior
prior = build_uninformative_prior("mineru")
prior.metadata["prior_type"] = "factory"
prior.metadata["source"] = "uninformative_placeholder"
# write prior.model_dump_json(indent=2) to
# src/pdf2md/data/factory_priors/mineru.json
```

Consumers see a `prior_factory:mineru` warning (not
`prior_uninformative:mineru`) and the factory prior delivers a
uniform 0.50 confidence — exactly what the runtime uninformative
fallback would have produced, but with audit-able provenance.

---

## 5. Verifying the post-Plan-19 invariants (H3 + H4)

Two human-verification tests sit at
[tests/test_bayesian_feature_picker_human_h.py](../tests/test_bayesian_feature_picker_human_h.py)
and assert the two load-bearing claims of the post-Plan-19 scheme:

```bash
conda run -n pdf2md pytest \
    tests/test_bayesian_feature_picker_human_h.py -v
```

- **H3 (multi-backend calibration produces real priors)** — builds a
  three-document synthetic corpus, drives `tools/calibrate_priors.py`
  end-to-end, then asserts every backend lands in
  `plan13_readiness.safe_for_consensus`, that each prior has
  positive `support` and `status="calibrated"` on the dominant block
  kinds, and that **per-backend specialisation** survives
  calibration (a backend that's reliable on heading but not on
  paragraph must end up with a higher `calibrated_confidence` on
  heading than the other backend, and vice-versa).
- **H4 (Bayesian feature picker selects per-kind)** — calls
  `score_candidate_group()` directly with mock priors and asserts:
  - the higher-prior backend wins on a given BlockKind;
  - the picker can pick different winners for different BlockKinds
    given the **same pair of backends** (the defining feature-picker
    property);
  - a single-backend candidate with `calibrated_confidence=0` lands
    in FALLBACK rather than SINGLE_SOURCE (Plan-19 invariant);
  - the rebalanced weights give the BlockKind prior at least 0.20
    score-margin leverage on a (0.9 vs 0.1) split.

H5 (end-to-end CLI smoke on a real paper) is a human-driven manual
check — see the pipeline output under `.tmp/papers_run/` after
running `pdf2md convert papers/<paper>.pdf`.

---

## 6. See also

- [project.md §5](../project.md) — durable architecture description of
  the consensus + calibration design.
- [README.md §4](../README.md) — "Prior resolution (Plan 19)" section
  in the public README.
- [src/pdf2md/models/priors.py](../src/pdf2md/models/priors.py) —
  Pydantic contracts (`CalibrationPriorDocument`,
  `CalibrationMetric`, `CalibrationStatus.UNINFORMATIVE`,
  `build_uninformative_prior`, `load_factory_prior`).
- [src/pdf2md/consensus/scoring.py](../src/pdf2md/consensus/scoring.py)
  — the scoring weights and the selection-mode decision logic.
