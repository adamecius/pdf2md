# DeepSeek-VL2 semantic backend

DeepSeek-VL2 is a Vision-Language Model
([huggingface.co/deepseek-ai/deepseek-vl2-small](https://huggingface.co/deepseek-ai/deepseek-vl2-small))
that can look at a rendered page image and emit structured JSON. The
semantic layer uses the `small` variant (~5.6 GB, fits a single 16 GB
GPU) to detect cross-reference markers on one page at a time.

Among the three semantic backends, DeepSeek-VL2 is the most flexible
(works on any page, including scanned scientific PDFs without text
layers) and the most expensive (GPU memory + a few seconds per page).

## Install

The install kit mirrors the OCR extraction backends
(`backend/paddleocr/`, `backend/mineru/`, `backend/deepseek/`,
`backend/glm/`):

```text
backend/semantic/deepseek_vl2/
├── environment.yml      # minimal conda spec (python + pip)
├── requirements.txt     # leaf pip deps (accelerate, timm, xformers, attrdict, …)
├── setup_env.py         # bootstrap (env create only)
├── setup.py             # main installer
│                        #   - preflight (NVIDIA GPU ≥16 GB VRAM, CUDA driver ≥11.8)
│                        #   - conda or venv env create
│                        #   - torch 2.0.1 + torchvision 0.15.2 from
│                        #     https://download.pytorch.org/whl/cu118
│                        #   - constraints file pinning the upstream-tested combo
│                        #   - requirements.txt -c constraints
│                        #   - transformers==4.38.2 -c constraints
│                        #   - deepseek-vl2 @ git+… -c constraints --no-deps
│                        #   - verify imports
└── delete_env.py        # teardown
```

One-shot install (recommended):

```bash
python backend/semantic/deepseek_vl2/setup.py
```

This:

1. Runs preflight checks (GPU detected, CUDA driver ≥11.8, ≥16 GB VRAM, ≥30 GB disk).
2. Creates the `pdf2md-deepseek-vl2` conda env (Python 3.11 + pip).
3. Installs `torch==2.0.1 torchvision==0.15.2` from the cu118 PyTorch wheel index.
4. Writes a constraints file at `${CONDA_PREFIX}/share/deepseek-vl2/constraints.txt`
   pinning `torch==2.0.1`, `torchvision==0.15.2`, `transformers==4.38.2`.
5. Installs `requirements.txt` (accelerate, sentencepiece, einops, timm, xformers,
   attrdict, pillow) against the constraints file.
6. Installs `transformers==4.38.2` (also against constraints).
7. Installs `deepseek-vl2 @ git+https://github.com/deepseek-ai/DeepSeek-VL2.git`
   with `--no-deps` — the constraints file already provides every dep at the
   working pin.
8. Verifies by importing `torch`, `transformers`, and
   `deepseek_vl2.models.{DeepseekVLV2ForCausalLM, DeepseekVLV2Processor}`.

Step-by-step if you'd rather:

```bash
python backend/semantic/deepseek_vl2/setup_env.py --manager conda
python backend/semantic/deepseek_vl2/setup.py --skip-env-create
```

Useful flags (full list with `python backend/semantic/deepseek_vl2/setup.py --help`):

| Flag | Meaning |
|---|---|
| `--manager {conda,venv}` | Default `conda`. |
| `--env-name NAME` | Override the default `pdf2md-deepseek-vl2`. |
| `--python VER` | Python version (default 3.11). |
| `--skip-env-create` | Assume the env already exists. |
| `--skip-checks` | Skip the GPU/VRAM/disk preflight. |
| `--skip-verify` | Skip the post-install import check. |
| `--check-only` | Run preflight only and exit 0. |
| `--smoke-image PATH` | Also run `smoke_test.py` against this image (downloads ~5.6 GB model on first call). |

Teardown:

```bash
python backend/semantic/deepseek_vl2/delete_env.py
```

(This removes the conda env; the Hugging Face model cache at
`~/.cache/huggingface/` stays because it's shared across envs.)

### Why these exact pins?

DeepSeek-VL2's upstream package over-pins `torch==2.0.1` and
`transformers==4.38.2` in its `pyproject.toml`. Stock `transformers`
(any version from 4.45 to 4.57) does NOT register the `deepseek_vl_v2`
architecture even with `trust_remote_code=True`, so the source pkg
must be installed to load the model — and once installed, its pins
become the working combo for the env. Newer torch (≥2.4) breaks the
`xformers` extension that DeepSeek-VL2 uses at inference time; cu118
+ torch 2.0.1 is the documented working version (it's also the combo
the upstream test suite runs against).

The cu118 PyTorch wheels are forward-compatible with the host's
CUDA driver — the dev host (`nvidia-smi` reports `CUDA Version: 13.0`)
runs them fine.

## Run the smoke test

Once the env is installed, render a PDF page to PNG and run the smoke
test:

```bash
# Example: render page 1 of an arxiv paper.
pdftoppm -r 150 paper.pdf /tmp/sample_page -png -f 1 -l 1

# First run downloads the ~5.6 GB model into ~/.cache/huggingface/.
conda run -n pdf2md-deepseek-vl2 python backend/semantic/deepseek_vl2/smoke_test.py \
    --image /tmp/sample_page-01.png \
    --out-dir /tmp/vlm_smoke
```

Expected output line:

```text
deepseek-vl2 smoke: <N> markers, load=<L> ms, infer=<I> ms, out=/tmp/vlm_smoke/vlm_smoke_result.json
```

Plan 005 H2 requires `N ≥ 1`.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | success — ≥1 marker extracted |
| 1 | repository defect — no markers detected on a page that has them |
| 2 | bad argument — image not found |
| 3 | `env_not_ready` — env missing dep, model load failed, no GPU, etc. |

## Output shape

`vlm_smoke_result.json`:

```jsonc
{
  "backend": "deepseek-vl2",
  "backend_version": "deepseek-ai/deepseek-vl2-small",
  "device": "cuda",
  "input_path": "tests/data/sample_page.png",
  "load_ms": 18420.0,
  "inference_ms": 3120.0,
  "markers": [
    {"marker_type": "figure", "marker_text": "Figure 3"},
    {"marker_type": "bibliography", "marker_text": "[15]"}
  ],
  "raw_text": "{\"markers\": [...]}",
  "parse_error": null
}
```

`raw_text` is preserved even on success so prompt drift can be
audited later. `parse_error` is non-null when the model returned
unparseable output (the smoke test still exits 0 if the parsed marker
list is non-empty).

## Library use

```python
# Only valid inside the pdf2md-deepseek-vl2 env.
from backend.semantic.deepseek_vl2 import vlm_client

settings = vlm_client.VlmSettings()  # cuda + bf16 by default
model, processor = vlm_client.load_model(settings)
out = vlm_client.extract_markers(
    Path("page.png"), model=model, processor=processor, settings=settings,
)
print(out["markers"])
```

Plan 006's in-tree adapter wraps this under
`src/pdf2md/semantic/vlm_adapter.py` — it invokes
`smoke_test.py` via `conda run -n pdf2md-deepseek-vl2`, so the main
`pdf2md` env never imports torch or transformers from the VLM env.

## Limitations

- Model output is non-deterministic across hardware even at
  `temperature=0` because of CUDA kernel non-determinism. The smoke
  test does not enforce exact-marker equality; only count ≥ 1.
- Prompt is intentionally narrow (the marker-type vocabulary in
  `prompt_templates.py`). It will not detect marker types that are
  not listed. Plan 006 will expand the vocabulary.
- One page per call. Multi-page batching is Plan 006 work.
- No fallback to CPU when CUDA fails — we report `env_not_ready`
  and let the operator decide.
- The cu118 + torch 2.0.1 pin is old. If a future NVIDIA driver
  breaks these wheels, the fallback (documented in
  [plans/005_1-deepseek-vl2-rework.md](../../../plans/005_1-deepseek-vl2-rework.md))
  is either to upgrade to torch 2.4 cu121 with matching xformers, or
  to migrate the backend to a stock-transformers-supported VLM
  (Qwen2-VL / LLaVA-OneVision / InternVL2 / Phi-3.5-Vision).
