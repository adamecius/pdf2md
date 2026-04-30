# DeepSeek backend (local-first OCR-2)

## Local model lookup order
Normal runs resolve the model in this exact order:
1. `--model-path`
2. `PDF2MD_DEEPSEEK_MODEL`
3. `.local_models/deepseek/<safe-model-id>/`

Safe model-id directory naming replaces `/` with `__`:
- `deepseek-ai/DeepSeek-OCR-2` -> `.local_models/deepseek/deepseek-ai__DeepSeek-OCR-2/`

## Explicit first-time download
Downloads are **never silent**.

If the model is missing, pass `--allow-download` explicitly:

```bash
python backend/deepseek/pdf2md_deepseek.py -i test.pdf \
  --model-id deepseek-ai/DeepSeek-OCR-2 \
  --models-dir .local_models/deepseek \
  --allow-download
```

This performs an explicit Hugging Face snapshot download into:
- `.local_models/deepseek/<safe-model-id>/`

## Future runs
After the first explicit download, future runs can omit `--allow-download` and will use the local cached path automatically.

## Git behavior
Downloaded models are local artifacts and are **not committed** (`.local_models/` is gitignored).

## Quick usage
```bash
# Local model path explicitly
python backend/deepseek/pdf2md_deepseek.py -i test.pdf --model-path /path/to/model

# Or env var
PDF2MD_DEEPSEEK_MODEL=/path/to/model python backend/deepseek/pdf2md_deepseek.py -i test.pdf
```
