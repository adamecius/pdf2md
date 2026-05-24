# Tutorial 02 — Convert your first PDF

**Goal.** Run the MVP pipeline end-to-end on a single PDF and inspect
the four output artefacts (Docling JSON, Markdown preview, RAG chunks,
pipeline manifest).

**Prerequisites.**

- [Tutorial 01 — Set up backends](01-setup-backends.md) completed, with
  at least `paddleocr` enabled in `pdf2md.backends.toml`.
- The `pdf2md` conda environment activated or available via
  `conda run -n pdf2md ...`.
- A PDF to convert (a 1–5 page born-digital or scanned PDF works
  best for a first run).

---

## Step 1 — Pick a PDF

Either point at your own file, or use one of the ground-truth corpus
PDFs that ship with the repo:

```bash
DOC=linked_sections_figures
PDF="groundtruth/corpus/latex/$DOC/$DOC.pdf"
```

If the file does not exist yet, compile the corpus first:

```bash
conda run -n pdf2md python tools/compile_latex_groundth.py --doc $DOC
```

The compiled artefacts land under `groundtruth/corpus/latex/<doc>/`:

```
<doc>.tex            (source, pre-existing)
<doc>.docling.json   (groundtruth, pre-existing)
<doc>.pdf            (compiled)
<doc>.latexml.xml    (compiled)
build.log
```

---

## Step 2 — Run the MVP pipeline

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py \
    --pdf "$PDF" \
    --out-dir /tmp/my_run \
    --backends paddleocr \
    --verbose
```

This invokes every pipeline stage: backend smoke, connector
canonicalisation, entity validation, consensus, linking, and export.

**Expected:** the command exits 0 and prints a summary line per stage.

---

## Step 3 — Inspect the outputs

```
/tmp/my_run/
├── pipeline_manifest.json         # full per-stage status + MVP readiness
├── pipeline_summary.txt           # human-readable summary
├── stage_status.json
├── docling/<stem>.docling.json    # docling-core compatible
├── rag/<stem>.rag_chunks.json     # chunks for RAG indexing
├── markdown/<stem>.preview.md     # markdown preview
├── reports/export_report.json
└── export_manifest.json
```

Read the summary first:

```bash
cat /tmp/my_run/pipeline_summary.txt
```

Pick artefacts by downstream tool:

- **Search / RAG** → `rag/<stem>.rag_chunks.json` (text + confidence +
  provenance per chunk).
- **LLM prompts or human reading** → `markdown/<stem>.preview.md`.
- **Docling-compatible downstreams** (LangChain `DoclingLoader`,
  llama-index `DoclingReader`, etc.) → `docling/<stem>.docling.json`.

For the contract of each format, see
[`../reference/export-formats.md`](../reference/export-formats.md).

---

## Step 4 — Verify

```bash
# Confirm Docling JSON validates against the canonical schema
conda run -n pdf2md python -c "
import json
from pathlib import Path
data = json.loads(Path('/tmp/my_run/docling').glob('*.docling.json').__next__().read_text())
assert 'texts' in data, 'docling export missing texts'
print('docling export OK:', len(data['texts']), 'text blocks')
"
```

If the pipeline exits non-zero or an artefact is missing, the
[troubleshooting guide](../how-to/troubleshoot-local-runs.md) covers
the common causes (missing CUDA libs, LaTeX toolchain mismatches,
paddleocr output-dir quirks).

---

## What's next

- [Tutorial 03](03-calibrate-priors-on-corpus.md) — derive real
  consensus priors from a corpus by running calibration end-to-end.
- [Tutorial 04](04-batch-processing.md) — process a whole directory of
  PDFs and combine multiple backends with calibrated consensus.
