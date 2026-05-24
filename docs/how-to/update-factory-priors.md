# How to update factory-shipped calibration priors

Factory priors ship under [`src/pdf2md/data/factory_priors/`](../../src/pdf2md/data/factory_priors/)
and are loaded at runtime via the three-level fallback in
`pdf2md.consensus.io`. Refresh them when the benchmark corpus,
backend versions, or production telemetry make the existing priors
no longer representative.

**Reference:** the full protocol with rationale is in
[`../reference/calibration-priors.md`](../reference/calibration-priors.md) §4.

## Quick procedure

```bash
# 1. Calibrate from scratch against the benchmark corpus
conda run -n pdf2md python tools/calibrate_priors.py \
    --root <benchmark-corpus-root> \
    --out-dir /tmp/factory_prior_update \
    --from-scratch --verbose

# 2. Confirm every shipping backend is in safe_for_consensus
jq '.plan13_readiness.safe_for_consensus' \
    /tmp/factory_prior_update/reports/calibration_report.json

# 3. Copy priors into package data
cp /tmp/factory_prior_update/priors/*.json \
   src/pdf2md/data/factory_priors/

# 4. Stamp metadata.prior_type = "factory" on each file
conda run -n pdf2md python -c "
import json, glob
for path in glob.glob('src/pdf2md/data/factory_priors/*.json'):
    doc = json.load(open(path))
    md = doc.setdefault('metadata', {})
    md['prior_type'] = 'factory'
    md.setdefault('source', 'calibrated_against_benchmark_corpus')
    json.dump(doc, open(path, 'w'), indent=2)
"

# 5. Run the fallback and factory-prior tests
conda run -n pdf2md pytest \
    tests/test_factory_priors.py \
    tests/test_consensus_prior_fallback.py \
    tests/test_bayesian_feature_picker_human_h.py -v

# 6. Commit (replace, don't accumulate — these are versioned with the package)
git add src/pdf2md/data/factory_priors/*.json
git commit -m "calibration: refresh factory priors against <corpus>"
```

## Placeholder backends

A backend wired into `pdf2md.backends.toml` that has no benchmark
calibration yet ships an uninformative placeholder file. The
recipe is in
[`../reference/calibration-priors.md`](../reference/calibration-priors.md) §4
("Placeholder backends").

## See also

- [`../reference/calibration-priors.md`](../reference/calibration-priors.md)
  — full reference + the rationale behind every step above.
- [`../tutorials/03-calibrate-priors-on-corpus.md`](../tutorials/03-calibrate-priors-on-corpus.md)
  — the end-to-end calibration tutorial.
