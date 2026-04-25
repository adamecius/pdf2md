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


## Backend Phase 3 scaffolding

Phase 3 now includes lightweight scaffolding for optional backend execution contracts:

- `backend_catalog.yaml` defines backend identities and environment manifests.
- `envs/core.yml`, `envs/mineru.yml`, and `envs/paddleocr_vl.yml` provide isolated environment recommendations.
- `scripts/run_backend.sh` runs a single backend into `runs/<document_id>/<backend_id>/` and writes canonical `document.docir.json` when extraction succeeds.
- `scripts/run_many_backends.sh` runs multiple backend IDs sequentially for the same input.

Example deterministic run:

```bash
scripts/run_backend.sh deterministic test_image1.pdf
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
