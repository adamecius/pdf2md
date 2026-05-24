# Tutorial 01 — Set up backends

**Goal.** Install at least one OCR backend, create its conda
environment, and wire it into `pdf2md.backends.toml` so the
pipeline can dispatch it.

**Prerequisites.**

- A working `conda` (or `mamba`) install.
- The `pdf2md` package installed in editable mode in a base env
  (`python -m pip install -e .`).
- The `pdf2md` conda environment activated or available via
  `conda run -n pdf2md ...`.

This tutorial doesn't duplicate the per-backend upstream-install
recipes — those live in each backend's README. It walks you through
which backend to pick, how the envs are organised, and how to wire
the result into the runner config.

---

## Step 1 — Pick a backend

`pdf2md` treats every backend as evidence, not as truth. You need at
least one enabled to do anything useful. Start with one; add others
later for calibrated multi-backend consensus.

| Backend | Strength | Cost / constraint | When to pick it first |
|---------|----------|-------------------|-----------------------|
| **paddleocr** | Robust visual OCR on born-digital + scanned pages; GPU support documented end-to-end. | Heavy CUDA stack on GPU; ~17× CPU→GPU speedup. | You have a CUDA GPU and want strong general OCR. |
| **mineru** | Strong on tables and complex layouts (PDF-Extract-Kit lineage). | Pulls a large model + CUDA dependency tree. | You need quality table extraction. |
| **deepseek** | Vision-LM OCR ("DeepSeek-OCR-2"). | Needs the model weights on disk + GPU. | You want VLM-style OCR and have the weights cached locally. |
| **glm** | API-based (Zhipu AI). | Requires API credentials + network. | You don't want local GPU/model bytes and accept third-party API calls. |

Per-backend deep-dive:

- [`backend/paddleocr/README.md`](../../backend/paddleocr/README.md) —
  paddle 3.0.0 cu118 + cuDNN 8 recipe and the
  `[backends.paddleocr.env]` block.
- [`backend/mineru/README.md`](../../backend/mineru/README.md)
- [`backend/deepseek/README.md`](../../backend/deepseek/README.md)
- [`backend/glm/README.md`](../../backend/glm/README.md)

---

## Step 2 — Create the backend conda env

Each backend lives in its own conda env named `pdf2md-<backend>`. The
main `pdf2md` env should not contain backend dependencies — they are
isolated by design so version conflicts (CUDA, paddle, torch) don't
poison each other.

```bash
# Pick one or more. Each takes 1–10 minutes depending on bandwidth.
python backend/paddleocr/setup_env.py --manager conda --env-name pdf2md-paddleocr
python backend/mineru/setup_env.py    --manager conda --env-name pdf2md-mineru
python backend/deepseek/setup_env.py  --manager conda --env-name pdf2md-deepseek
python backend/glm/setup_env.py       --manager conda --env-name pdf2md-glm
```

If a backend has a `setup.py` (`mineru`, `deepseek`), prefer
`python backend/<name>/setup.py` — it checks env state and installs
the additional model/CUDA deps in the right order.

---

## Step 3 — (Optional) Install the GPU runtime for paddleocr

`paddleocr` on CPU works but is slow (~10 min for a 27-page PDF). The
GPU recipe lives in [`backend/paddleocr/README.md`](../../backend/paddleocr/README.md)
under "GPU vs CPU runtime". TL;DR:

```bash
conda run -n pdf2md-paddleocr pip uninstall -y paddlepaddle
conda run -n pdf2md-paddleocr pip install --no-deps paddlepaddle-gpu==3.0.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
conda run -n pdf2md-paddleocr pip install \
    "nvidia-cudnn-cu11>=8.9,<9.0" \
    "nvidia-cublas-cu11" \
    "nvidia-cuda-nvrtc-cu11"
conda run -n pdf2md-paddleocr pip install decorator astor
```

**Pin paddle to 3.0.0.** Paddle 3.1+ has an oneDNN PIR/runtime bug that
crashes PPStructureV3 — see the per-backend README for the workaround.

---

## Step 4 — Configure `pdf2md.backends.toml`

Copy the example and enable the backends you've installed:

```bash
cp pdf2md.backends.example.toml pdf2md.backends.toml
```

Open it and flip `enabled = true` for each backend you set up.
Defaults (paths, env names) match the convention from step 2.

For paddleocr GPU, uncomment the `[backends.paddleocr.env]` block and
set `LD_LIBRARY_PATH` to the cuDNN / cuBLAS / nvrtc directories
inside your paddleocr conda env. Set `device = "gpu:0"` (or
`device = "auto"`) under `[backends.paddleocr.args]`.

---

## Step 5 — Verify

A quick smoke check against a real PDF:

```bash
DOC=linked_sections_figures
PDF="groundtruth/corpus/latex/$DOC/$DOC.pdf"  # or your own .pdf

conda run -n pdf2md python tools/backend_smoke.py \
    --input-pdf "$PDF" \
    --out-dir /tmp/backend_smoke \
    --gate-minimum 1 --verbose
```

The smoke test invokes every enabled backend on the PDF and writes
per-backend output under `/tmp/backend_smoke/`. If any backend
fails, the failing log path is printed; common error signatures and
their fixes are in
[`../how-to/troubleshoot-local-runs.md`](../how-to/troubleshoot-local-runs.md).

---

## What's next

- [Tutorial 02](02-first-conversion.md) — run the full MVP pipeline on
  one PDF and inspect the outputs.
- [Tutorial 03](03-calibrate-priors-on-corpus.md) — derive calibrated
  confidence priors against the LaTeX ground-truth corpus.
- The per-backend READMEs remain canonical for upstream-install
  details and version pinning notes.
