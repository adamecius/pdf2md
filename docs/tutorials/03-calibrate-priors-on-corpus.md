# Tutorial 03 — Calibrate consensus priors on the LaTeX corpus

**Goal.** Run the full calibration pipeline against the LaTeX
ground-truth corpus to produce real per-backend confidence priors,
then feed those priors back into the consensus stage so it scores
using calibrated confidences instead of the 0.50 default.

**Prerequisites.**

- Tutorials [01](01-setup-backends.md) and [02](02-first-conversion.md)
  completed.
- A working LaTeX toolchain on PATH (`lualatex`, `latexmk`); see
  [Tutorial 01](01-setup-backends.md) for the discovery rules.

The pipeline is **compile a corpus subset → run the existing backends
→ calibrate priors against the groundtruth → reuse the priors in
consensus**.

---

## Step 1 — Compile the LaTeX corpus to PDFs

```bash
# Compile every corpus document:
conda run -n pdf2md python tools/compile_latex_groundth.py

# Or a single document:
conda run -n pdf2md python tools/compile_latex_groundth.py \
    --doc linked_sections_figures
```

Each compiled document lands under `groundtruth/corpus/latex/<doc>/`:

```
<doc>.tex            (source)
<doc>.docling.json   (groundtruth, pre-existing)
<doc>.pdf            (compiled)
<doc>.latexml.xml    (compiled)
build.log
```

---

## Step 2 — (Optional) Configure paddleocr for GPU

If you completed [Tutorial 01](01-setup-backends.md) with CPU paddleocr,
the calibration will still work — it's just slower. For the full
recipe (paddlepaddle-gpu 3.0.0 + cuDNN 8 + `LD_LIBRARY_PATH`), see
[`backend/paddleocr/README.md`](../../backend/paddleocr/README.md).

A working GPU `pdf2md.backends.toml` looks like:

```toml
[backends.paddleocr]
enabled = true
runner = "conda"
env_name = "pdf2md-paddleocr"
script = "backend/paddleocr/pdf2md_paddleocr.py"
extra_args = ["--keep-output"]

[backends.paddleocr.env]
LD_LIBRARY_PATH = "<env>/lib/python3.11/site-packages/nvidia/cudnn/lib:<env>/lib/python3.11/site-packages/nvidia/cublas/lib:<env>/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib"

[backends.paddleocr.args]
lang = "en"
device = "gpu:0"
```

---

## Step 3 — Run backend smoke + connector canonicalisation per corpus document

For one document:

```bash
DOC=linked_sections_figures
PDF="groundtruth/corpus/latex/$DOC/$DOC.pdf"

conda run -n pdf2md python tools/backend_smoke.py \
    --input-pdf "$PDF" \
    --out-dir groundtruth/runs/backend_smoke \
    --gate-minimum 1 --verbose

# Convert the raw PaddleOCR output into the canonical connector layout
# (per-page IR + entities.json) that consensus + linking stages expect.
conda run -n pdf2md python - <<PY
from pathlib import Path
from pdf2md.connectors.common import BackendConnectorConfig, connect_raw_dir
raw = Path("groundtruth/runs/backend_smoke/backend_runs/$DOC/raw/paddleocr")
cfg = BackendConnectorConfig(backend="paddleocr", default_backend_version=None)
connect_raw_dir(raw_dir=raw, document_id="$DOC", config=cfg,
                out_dir=Path("groundtruth/runs/connector_canonical/$DOC"))
PY
```

Repeat (or loop) for every compiled corpus document.

---

## Step 4 — Stage a calibration input root that matches the groundtruth

The calibrator (`tools/calibrate_priors.py`) expects:

```
calibration_inputs/
└── <document_id>/
    ├── truth.json                     # CalibrationTruthDocument (NOT raw .docling.json)
    └── backend_ir/
        ├── paddleocr/
        │   ├── pages/page_0001.json   # PageExtractionIR per page
        │   └── entities.json          # EntityProposalDocument
        ├── mineru/...
        └── glm/...
```

Stage it with this one-shot helper (run from the repo root):

```bash
conda run -n pdf2md python - <<'PY'
import json, shutil
from pathlib import Path
from pdf2md.calibration.vocabulary import normalise_truth_payload

corpus = Path("groundtruth/corpus/latex")
canonical_root = Path("groundtruth/runs/connector_canonical")
stage = Path("groundtruth/runs/calibration_inputs")

for tex_dir in sorted(corpus.iterdir()):
    docling_gt = tex_dir / f"{tex_dir.name}.docling.json"
    canonical = canonical_root / tex_dir.name
    if not docling_gt.exists() or not canonical.exists():
        continue

    target = stage / tex_dir.name
    (target / "backend_ir").mkdir(parents=True, exist_ok=True)

    raw = json.loads(docling_gt.read_text())
    truth = {
        "schema_name": "pdf2md.CalibrationTruthDocument",
        "schema_version": "1.0.0",
        "document_id": tex_dir.name,
        "blocks": [
            {
                "id": f"tb{i}",
                "block_kind": t.get("label", "text"),
                "text": t.get("text", ""),
                "page_no": (t.get("prov") or [{}])[0].get("page_no", 1),
                "metadata": {},
            }
            for i, t in enumerate(raw.get("texts", []), 1)
        ],
        "entities": [],
        "relations": [],
        "metadata": {},
    }
    (target / "truth.json").write_text(
        json.dumps(normalise_truth_payload(truth), indent=2), encoding="utf-8"
    )

    for backend_dir in canonical.iterdir():
        shutil.copytree(
            backend_dir,
            target / "backend_ir" / backend_dir.name,
            dirs_exist_ok=True,
        )
    print("staged:", tex_dir.name)
PY
```

---

## Step 5 — Run the calibration tool

```bash
conda run -n pdf2md python tools/calibrate_priors.py \
    --root groundtruth/runs/calibration_inputs \
    --out-dir groundtruth/runs/calibration_priors \
    --min-samples 3 \
    --smoothing-alpha 1.0 --smoothing-beta 1.0 \
    --default-confidence 0.5 \
    --strict --verbose
```

**Outputs:**

```
groundtruth/runs/calibration_priors/
├── priors/<backend>.json                       # CalibrationPriorDocument per backend
└── reports/
    ├── calibration_report.json                 # includes plan13_readiness
    ├── calibration_summary.txt
    └── blockkind_vocabulary_alignment_report.json
```

Each `<backend>.json` carries four metric lists:

- `block_kind_priors` — per BlockKind
- `entity_type_priors` — per EntityType
- `relation_type_priors` — per RelationType
- `calibration_key_priors` — per detector/heuristic key

Every metric carries `counts` (tp/fp/fn), `precision`, `recall`, `f1`,
`calibrated_confidence` (beta-smoothed precision), and `status` ∈
{`calibrated`, `underpowered`, `no_samples`}.

The `calibration_report.json` has a `plan13_readiness.safe_for_consensus`
list — backends listed there are calibrated enough to feed into weighted
consensus. Backends listed under `underpowered` or `no_samples` fall
back to `default_confidence = 0.5`.

For the full reference and flag list, see
[`../reference/calibration-priors.md`](../reference/calibration-priors.md).

---

## Step 6 — Feed the priors back into consensus

```bash
conda run -n pdf2md python tools/build_consensus.py \
    --connector-root groundtruth/runs/connector_canonical \
    --document-id linked_sections_figures \
    --priors-root groundtruth/runs/calibration_priors/priors \
    --out-dir groundtruth/runs/consensus_calibrated \
    --inspection-status appears_equivalent_to_best_backend \
    --inspection-note "calibrated priors from corpus" \
    --verbose
```

`reports/consensus_report.json` under the output now uses the
calibrated confidences instead of `default_confidence = 0.5` for
`agreement_score`.

---

## What's next

- [Tutorial 04](04-batch-processing.md) — batch-process a directory of
  PDFs with calibrated multi-backend consensus.
- [How-to: update factory priors](../how-to/update-factory-priors.md) —
  ship your calibration as the package's default factory priors.
- [`../reference/calibration-priors.md`](../reference/calibration-priors.md)
  — the durable reference for the calibration subsystem.
