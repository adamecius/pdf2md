# DeepSeek backend (local-first OCR-2)

## Purpose
DeepSeek backend converts PDFs to Markdown using a **local** DeepSeek OCR model path by default.

## Environment
- Default environment name: `pdf2md-deepseek`
- Target Python: `3.12`
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
```bash
conda activate pdf2md-deepseek
# or
source .venv-deepseek/bin/activate
```

## Local model lookup order
Normal runs resolve the model in this exact order:
1. `--model-path`
2. `PDF2MD_DEEPSEEK_MODEL`
3. `.local_models/deepseek/<safe-model-id>/`

Safe model-id directory naming replaces `/` with `__`.
Example:
`deepseek-ai/DeepSeek-OCR-2` -> `.local_models/deepseek/deepseek-ai__DeepSeek-OCR-2/`

## Explicit first-time download
Downloads are **never silent**.

If no local model is found, pass `--allow-download` explicitly:

```bash
python backend/deepseek/pdf2md_deepseek.py -i test.pdf \
  --model-id deepseek-ai/DeepSeek-OCR-2 \
  --models-dir .local_models/deepseek \
  --allow-download
```

This downloads once into `.local_models/deepseek/<safe-model-id>/` and then runs using that local path.
Future runs can omit `--allow-download` and reuse the downloaded local model.

## API policy
- Wrapper does not auto-switch to API mode.
- `--api` is explicit and currently not implemented in this wrapper.

## GPU stack guidance (CUDA 11.8)

### 1) Install Torch CUDA 11.8 wheels
```bash
python -m pip install \
  torch==2.6.0 \
  torchvision==0.21.0 \
  torchaudio==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu118
```

### 2) Install vLLM CUDA wheel
Download a matching wheel (example: `vllm-0.8.5+cu118-...whl`) and install:
```bash
python -m pip install ./vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl
```

### 3) Install flash-attn
```bash
python -m pip install flash-attn==2.7.3 --no-build-isolation --no-cache-dir
```

### 4) CUDA toolchain exports
Before building CUDA-dependent packages, point to the intended toolkit:
```bash
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
```

## NumPy rationale
`numpy==2.2.6` is pinned to avoid common compatibility issues seen with some transitive dependencies in OCR/GPU stacks.

## Troubleshooting
- **Model not found**: set `--model-path` or `PDF2MD_DEEPSEEK_MODEL`, or run once with `--allow-download`.
- **Unexpected download expectation**: downloads are explicit only; wrapper never silently downloads.
- **Wrong CUDA compiler**: run `nvcc -V` and ensure CUDA 11.8-compatible toolchain.
- **Torch cannot see GPU**: verify `torch.cuda.is_available()` in active environment.
- **flash-attn install/runtime issues**: confirm `CUDA_HOME`, `PATH`, and `LD_LIBRARY_PATH` are set to the intended toolkit.

## Git behavior
Downloaded models are local artifacts and are not committed (`.local_models/` is gitignored).
