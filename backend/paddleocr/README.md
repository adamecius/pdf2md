# PaddleOCR backend (local OCR)

## Purpose
PaddleOCR backend rasterizes PDF pages to images and runs OCR locally, then writes Markdown text.

## Environment
- Default environment name: `pdf2md-paddleocr`

### Conda setup (default)
```bash
cd backend/paddleocr
python setup_env.py --manager conda --env-name pdf2md-paddleocr
```

### venv setup (alternative)
```bash
cd backend/paddleocr
python setup_env.py --manager venv --env-name .venv-paddleocr
```

### Activate
- Conda:
```bash
conda activate pdf2md-paddleocr
```
- venv:
```bash
source .venv-paddleocr/bin/activate
```

## Standard wrapper command
```bash
python backend/paddleocr/pdf2md_paddleocr.py -i test.pdf
```

## Output behavior
- Default output path: `test.md`.
- Optional `--json-out` writes a small manifest JSON.

## Local-first model policy
- Uses local PaddleOCR installation in active environment.
- Wrapper does not include an API mode.
- PaddleOCR may fetch OCR model assets on first run if not already cached locally by Paddle.
  - To keep fully local/offline behavior, pre-populate Paddle model cache before running in offline mode.

## API policy
- `--api` is rejected for this backend.

## Backend-specific dependency notes
- Requires `paddlepaddle`, `paddleocr`, `PyMuPDF`, and `Pillow`.
- OCR quality/speed depends on Paddle model assets and CPU/GPU capability.

## Troubleshooting
- Import errors (`paddleocr`, `fitz`, `PIL`): ensure correct env is activated and dependencies installed.
- Slow OCR: use smaller PDFs or GPU-enabled Paddle build.
- Unexpected language detection: set `--lang` explicitly.
