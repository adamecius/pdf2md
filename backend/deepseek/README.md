# DeepSeek backend (local-first OCR-2)

## Purpose
DeepSeek backend converts PDFs to Markdown using a **local** DeepSeek OCR model path by default.

## Environment
- Default environment name: `pdf2md-deepseek`
- Target Python: `3.12`
- Target CUDA toolkit: `11.8`

### Conda setup
```bash
cd backend/deepseek
python setup_env.py --manager conda --env-name pdf2md-deepseek
```

### venv setup
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

## Local-first model policy
Model lookup order is strict:
1. `--model-path`
2. `PDF2MD_DEEPSEEK_MODEL`
3. `.local_models/deepseek/<safe-model-id>/`

Safe model-id directory naming replaces `/` with `__`.
Example:
`deepseek-ai/DeepSeek-OCR-2` -> `.local_models/deepseek/deepseek-ai__DeepSeek-OCR-2/`

## Explicit first-time download
Downloads are never silent. If no local model is found, explicitly pass `--allow-download`:

```bash
python backend/deepseek/pdf2md_deepseek.py -i test.pdf \
  --model-id deepseek-ai/DeepSeek-OCR-2 \
  --models-dir .local_models/deepseek \
  --allow-download
```

This downloads into `.local_models/deepseek/<safe-model-id>/` and then runs using that local path.
Future runs without `--allow-download` reuse the local model automatically.

## API policy
- Wrapper does not auto-switch to API mode.
- `--api` is explicit and currently not implemented in this wrapper.

## Git behavior
Downloaded models are local artifacts and are not committed (`.local_models/` is gitignored).

## Backend dependency notes
The documented working stack is based on:
- Torch CUDA 11.8 wheels
- vLLM + FlashAttention combinations compatible with CUDA 11.8
- `transformers`, `tokenizers`, and OCR-side dependencies pinned in `requirements.txt`

Use backend-specific setup guidance/scripts in this folder to install the full CUDA stack when needed.
