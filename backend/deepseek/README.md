# DeepSeek backend (local-first OCR-2)

## Purpose
DeepSeek backend converts PDFs to Markdown using a **local** DeepSeek OCR model path by default.

## Environment
- Default environment name: `pdf2md-deepseek`
- Target Python: `3.12` (documented working stack uses Python 3.12.9)
- Target CUDA toolkit: `11.8`

### Conda setup (default)
```bash
cd backend/deepseek
python setup_env.py --manager conda --env-name pdf2md-deepseek
```

### venv setup (alternative)
```bash
cd backend/deepseek
python setup_env.py --manager venv --env-name .venv-deepseek
```

### Activate
- Conda:
```bash
conda activate pdf2md-deepseek
```
- venv:
```bash
source .venv-deepseek/bin/activate
```

## Standard wrapper command
```bash
python backend/deepseek/pdf2md_deepseek.py -i test.pdf
```

## Output behavior
- Default output: `test.md` (same stem as input).
- Wrapper prints resulting Markdown path on success.
- Optional `--json-out` writes a small run manifest.

## Local-first model policy
- Local model is required by default.
- Provide local model via:
  - `--model-path /path/to/local/model`
  - or `PDF2MD_DEEPSEEK_MODEL=/path/to/local/model`
- No silent model download.
- No silent API fallback.

## API policy
- Wrapper does not auto-switch to API mode.
- `--api` is explicit and currently treated as not-implemented flow in this wrapper.

## Backend-specific dependency notes
The documented working stack is:
- Python `3.12.9`
- CUDA toolkit `11.8`
- `torch==2.6.0+cu118`
- `torchvision==0.21.0`
- `torchaudio==2.6.0`
- `vLLM==0.8.5+cu118` (wheel install path)
- `flash-attn==2.7.3`
- `transformers==4.46.3`
- `tokenizers==0.20.3`
- `numpy==2.2.6`
- OCR-side deps: `PyMuPDF`, `img2pdf`, `einops`, `easydict`, `addict`, `Pillow`

`requirements.txt` in this folder intentionally captures the OCR-side Python pins (`transformers`, `tokenizers`, `numpy`, and OCR dependencies). CUDA Torch/vLLM/FlashAttention are backend-specific and often installed by explicit commands/scripts to match GPU/CUDA runtime constraints.

## Full CUDA/Torch/FlashAttention/vLLM/NumPy guidance

### Why install order matters
Recommended sequence:
1. Create/activate env.
2. Install CUDA 11.8 toolkit in env.
3. Export `CUDA_HOME`, `PATH`, `LD_LIBRARY_PATH` to env CUDA.
4. Install Torch CUDA 11.8 wheels.
5. Install vLLM CUDA 11.8 wheel.
6. Install OCR requirements with NumPy pin.
7. Install `flash-attn`.
8. Verify CUDA/Torch/NumPy/Transformers/vLLM/FlashAttention.

`flash-attn` compiles CUDA extensions; using wrong `nvcc` (e.g., system CUDA 11.5) commonly breaks installation/runtime.

### CUDA environment exports
```bash
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
```

### NumPy pin rationale
`numpy==2.2.6` avoids common incompatibilities where newer NumPy conflicts with ecosystem constraints (for example, constraints used by transitive packages such as `numba`/`mistral-common`).

### Known/expected version tension
In some one-environment OCR-2 setups, you may see warnings/conflicts between vLLM requirements and OCR repository pins for `transformers`/`tokenizers`. Follow the backend’s tested combination above unless you are intentionally revalidating a newer matrix.

## Troubleshooting
- **Model missing**: set `--model-path` or `PDF2MD_DEEPSEEK_MODEL`.
- **Wrong CUDA compiler**: run `nvcc -V`, ensure it resolves to CUDA 11.8 toolchain.
- **Torch can’t see GPU**: validate `torch.cuda.is_available()` in active env.
- **flash-attn import/build failure**: verify CUDA toolkit path/env and reinstall after fixing `CUDA_HOME`.
- **Unexpected downloads**: wrapper is local-first; do not rely on runtime pull unless you explicitly add download flow.

## Legacy snapshots
Legacy files in `backend/deepseek/legacy/` are archival backups and not required for normal setup/operation.
