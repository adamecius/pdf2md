# Getting started

This page gets `pdf2md` installed and converts a single PDF in five
minutes (after backend env setup, which is the long pole).

For the project overview and design rationale, see
[`../README.md`](../README.md) and [`../project.md`](../project.md).

---

## 1. Install the package

Clone the repo and install in editable mode in the `pdf2md` conda env:

```bash
git clone https://github.com/adamecius/pdf2md.git
cd pdf2md
conda create -n pdf2md python=3.12 -y
conda activate pdf2md
python -m pip install -e .
```

`requires-python` is `>=3.11,<3.14`. 3.12 is the tested/recommended
version (matches the per-backend environment defaults).

Confirm:

```bash
pdf2md --help
```

The CLI exposes `convert`, `run-pipeline`, `run-backends`, and
`datasets` subcommands.

---

## 2. Set up at least one backend

You need an OCR backend to convert a PDF. The fastest path is
`paddleocr` on CPU:

```bash
python backend/paddleocr/setup_env.py --manager conda --env-name pdf2md-paddleocr
cp pdf2md.backends.example.toml pdf2md.backends.toml
# Edit pdf2md.backends.toml: set [backends.paddleocr] enabled = true
```

For GPU paddleocr, MinerU, DeepSeek, GLM, or a comparative guide, see
[Tutorial 01 — Set up backends](tutorials/01-setup-backends.md).

---

## 3. Convert a PDF

Use one of the LaTeX corpus PDFs that ships with the repo (or any PDF
on your disk):

```bash
DOC=linked_sections_figures
PDF="groundtruth/corpus/latex/$DOC/$DOC.pdf"

# If the corpus PDF doesn't exist yet, compile it first:
conda run -n pdf2md python tools/compile_latex_groundth.py --doc $DOC

# Run the MVP pipeline end-to-end:
conda run -n pdf2md python tools/run_mvp_pipeline.py \
    --pdf "$PDF" \
    --out-dir /tmp/my_run \
    --backends paddleocr \
    --verbose
```

You'll get a four-artefact output:

```
/tmp/my_run/
├── docling/<doc>.docling.json    # canonical structured export
├── markdown/<doc>.preview.md     # human-readable preview
├── rag/<doc>.rag_chunks.json     # chunks for RAG
└── pipeline_manifest.json        # per-stage status + readiness
```

For the contract of each artefact, see
[`reference/export-formats.md`](reference/export-formats.md).

---

## 4. Where to go next

- **Learn the package** → [Tutorials](tutorials/) (01–04, in order).
- **Solve a specific task** → [How-to guides](how-to/).
- **Look up a contract** → [Reference](reference/).
- **Understand the design** → [Explanation](explanation/) +
  [`../project.md`](../project.md).

If the pipeline failed with a CUDA / paddle / LaTeX error, the
common error signatures and their fixes are in
[`how-to/troubleshoot-local-runs.md`](how-to/troubleshoot-local-runs.md).
