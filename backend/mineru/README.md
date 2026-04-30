# MinerU backend (local-first)

## Purpose
MinerU backend converts PDFs to Markdown using a local MinerU pipeline/VLM backend.

## Environment
- Default environment name: `pdf2md-mineru`
- Python baseline: `3.12`
- Known working stack: `mineru[pipeline]==3.1.4`, `torch==2.7.0+cu126`, `torchvision==0.22.0+cu126`

### Conda setup (default)
```bash
cd backend/mineru
python setup_env.py --manager conda --env-name pdf2md-mineru
```

### venv setup (alternative)
```bash
cd backend/mineru
python setup_env.py --manager venv --env-name .venv-mineru
```

### Activate
- Conda:
```bash
conda activate pdf2md-mineru
```
- venv:
```bash
source .venv-mineru/bin/activate
```

## Standard wrapper command
```bash
python backend/mineru/pdf2md_mineru.py -i test.pdf
```

## Output behavior
- Default output path: `test.md` (same stem as input).
- Script prints the created Markdown path on success.

## Local-first model policy
- Default mode is local MinerU execution.
- Wrapper attempts local MinerU import and local API server startup.
- If MinerU is unavailable, execution fails with actionable setup guidance.

## API policy
- Remote/API mode is **explicit only** with `--api` and `--api-url`.
- No silent switch from local mode to API mode.

## Backend-specific dependency notes
- `requirements.txt` uses PyTorch CUDA 12.6 extra index and pins GPU wheels.
- `environment.yml` installs the same pinned stack into `pdf2md-mineru`.

## Troubleshooting
- `mineru` import error: activate the correct environment, then reinstall with `setup_env.py`.
- CUDA mismatch: verify installed torch wheel matches your runtime/driver.
- No output `.md`: verify input is a valid `.pdf` and backend mode supports document type.
