# GLM backend (API-only)

## Purpose
GLM backend is an explicit API-based wrapper scaffold for PDF→Markdown flows.

## Environment
- Default environment name: `pdf2md-glm`

### Conda setup (default)
```bash
cd backend/glm
python setup_env.py --manager conda --env-name pdf2md-glm
```

### venv setup (alternative)
```bash
cd backend/glm
python setup_env.py --manager venv --env-name .venv-glm
```

### Activate
- Conda:
```bash
conda activate pdf2md-glm
```
- venv:
```bash
source .venv-glm/bin/activate
```

## Standard wrapper command
```bash
python backend/glm/pdf2md_glm.py -i test.pdf --api
```

## Output behavior
- Current wrapper validates inputs/credentials and exits with clear status/error messages.
- Full API call flow is intentionally not auto-executed in this smoke-safe wrapper yet.

## Local-first model policy
- Not applicable: this backend is API-only.

## API policy
- `--api` flag is required.
- API key required: `ZHIPU_API_KEY` (preferred) or `GLM_API_KEY` (alias).
- No hidden local→API switching.

## Backend-specific dependency notes
- Minimal dependency set in this repo (`requests`) because API execution is scaffold-only.

## Troubleshooting
- Missing API key error: export `ZHIPU_API_KEY` (or `GLM_API_KEY`) in shell before running.
- Missing `--api`: rerun command with explicit `--api`.
