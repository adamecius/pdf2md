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

## Quick validation

```bash
python -m doc2md --help
pytest -q
```

## Backend installation options

The default install is the lightweight core path. It supports the current
deterministic PDF text pipeline and does not install optional OCR or ML
backends:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

Optional backend dependencies should be installed only when you are testing that
backend. They are intentionally not listed in `requirements.txt`.

For a MinerU environment:

```bash
python3.12 -m venv .venv-mineru
source .venv-mineru/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest mineru
```

For a PaddleOCR-VL environment:

```bash
python3.12 -m venv .venv-paddleocr-vl
source .venv-paddleocr-vl/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest paddleocr paddlepaddle
```

You can validate installability without touching your active environment by
using the local install sandbox:

```bash
bash install_scripts/check_backend_installs.sh core
bash install_scripts/check_backend_installs.sh mineru
bash install_scripts/check_backend_installs.sh paddleocr_vl
```

The sandbox writes virtual environments, logs, caches, and
`sandbox/backend-installs/summary.md` under `sandbox/`, which is ignored by git.
These checks prove dependency installation and import smoke tests only; they do
not prove backend extraction quality or download backend models. More detail is
in `docs/backends.md`.
