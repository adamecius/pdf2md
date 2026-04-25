# doc2md

`doc2md` is an experimental PDF-to-Markdown pipeline.

This project currently targets Python 3.12 and relies on a small dependency set.

## Recommended setup (default): `.venv`

Use a local virtual environment by default. This is the simplest workflow for most contributors.

```bash
# 1) Create and activate a local virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2) Upgrade pip
python -m pip install --upgrade pip

# 3) Install runtime dependencies
pip install -r requirements.txt

# 4) Optional but recommended for local validation
pip install pytest
```

## Secondary setup (experimental): Conda runtime + pip packages

> **Status:** Secondary and experimental guidance.
> Prefer `.venv` unless you already manage Python versions with conda.

```bash
# 1) Create and activate a conda environment
conda create -n doc2md python=3.12 -y
conda activate doc2md

# 2) Upgrade pip inside the conda env
python -m pip install --upgrade pip

# 3) Install runtime dependencies
pip install -r requirements.txt

# 4) Optional but recommended for local validation
pip install pytest
```

## Notes

- `.venv` is the default recommendation for day-to-day development in this repository.
- Conda remains useful when you want conda-managed Python runtimes.
- Current dependencies are lightweight and pip-installable (`pymupdf`, `pyyaml`).
- Backend expansion is organized in phases; Phase 3 coordination rules live in `plans/003_rules-backend-dependency-installation-audit.md` and backend-specific subplans are `plans/003_1-*`, `plans/003_2-*`, etc.

## Quick validation

```bash
python -m doc2md --help
pytest -q
```
