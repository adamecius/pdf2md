# Tutorial 04 — Batch processing and multi-backend consensus

**Goal.** Run the MVP pipeline over an entire directory of PDFs and
optionally combine multiple backends with calibrated consensus.

**Prerequisites.**

- Tutorials [01](01-setup-backends.md), [02](02-first-conversion.md),
  and [03](03-calibrate-priors-on-corpus.md) completed.
- A directory of PDFs (one per immediate subdirectory; the first
  `.pdf` per subdirectory is used).

---

## Step 1 — Corpus mode

Process every PDF under a root directory:

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py \
    --corpus-root /path/to/pdfs/ \
    --out-dir /tmp/corpus_run \
    --max-documents 10 \
    --backends paddleocr \
    --verbose
```

Or a curated subset (one document id per line in the txt file):

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py \
    --corpus-root /path/to/pdfs/ \
    --document-list /tmp/picks.txt \
    --out-dir /tmp/corpus_run \
    --verbose
```

---

## Step 2 — Inspect the outputs

```
/tmp/corpus_run/
├── pipeline_manifest.json               # run-level
├── pipeline_summary.txt
├── mvp_corpus_evaluation.json           # per-document pass/fail aggregate
├── mvp_corpus_summary.txt
└── documents/<doc_id>/                  # same flat layout per document
    ├── stage_status.json
    ├── docling/<doc_id>.docling.json
    ├── rag/<doc_id>.rag_chunks.json
    ├── markdown/<doc_id>.preview.md
    ├── reports/export_report.json
    └── export_manifest.json
```

Useful fields in `mvp_corpus_evaluation.json`:

- `document_results` — per-doc `passed` / `passed_with_warnings` /
  `failed` / `blocked` / `skipped`.
- `stage_bottlenecks` — which stages failed across the corpus.
- `backend_eligibility` — how many documents each backend successfully
  consumed.
- `final_export_availability` — per-doc boolean (did the export stage
  produce its 5 artefacts).
- `mvp_readiness` — `MVP_ready` / `MVP_ready_with_warnings` /
  `MVP_not_ready` / `diagnostic_only`.

---

## Step 3 — Multi-backend with calibrated consensus

Once you have priors from [Tutorial 03](03-calibrate-priors-on-corpus.md)
and >1 backend configured in `pdf2md.backends.toml`:

```bash
# Enable additional backends (e.g. mineru once magic_pdf is installed,
# deepseek once GPU + model weights are in place) in pdf2md.backends.toml.

conda run -n pdf2md python tools/run_mvp_pipeline.py \
    --pdf /path/to/your.pdf \
    --out-dir /tmp/multi_run \
    --backends paddleocr,mineru \
    --verbose
```

To pipe in calibrated priors, run consensus directly after the runner
produces the canonical layout:

```bash
conda run -n pdf2md python tools/build_consensus.py \
    --connector-root /tmp/multi_run/work/connector_canonical \
    --document-id <your_doc_stem> \
    --priors-root groundtruth/runs/calibration_priors/priors \
    --out-dir /tmp/multi_run/consensus_calibrated \
    --verbose
```

> **Note.** MVP-runner-driven prior wiring is a follow-up; for now
> invoke `tools/build_consensus.py` directly with `--priors-root`.

---

## What's next

- [`../reference/export-formats.md`](../reference/export-formats.md) —
  contract details for each output artefact.
- [`../reference/calibration-priors.md`](../reference/calibration-priors.md)
  — the durable calibration reference.
- [`../explanation/pipeline-stages.md`](../explanation/pipeline-stages.md)
  — the *why* of the staged pipeline.
- [`../how-to/troubleshoot-local-runs.md`](../how-to/troubleshoot-local-runs.md)
  — recipes for common error signatures.
