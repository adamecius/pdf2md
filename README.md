# doc2md

`doc2md` is a CLI-only package that converts a **single PDF** to Markdown.

Current implemented core flow:

1. profile each PDF page with structural signals,
2. route each page (`deterministic` / `hybrid` / `visual`),
3. execute the deterministic lane now,
4. normalize output through DocIR,
5. export Markdown (and optional DocIR JSON / chunks JSONL).

Hybrid and visual execution are intentionally scaffolded but not fully implemented.

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

Run on one PDF:

```bash
python -m doc2md path/to/input.pdf -o out/ -vv
```

Run an optional backend directly from the CLI:

```bash
python -m doc2md path/to/input.pdf -o out-mineru --backend mineru --emit-docir
python -m doc2md path/to/input.pdf -o out-paddle --backend paddleocr_vl --emit-docir
```

## Optional backend experiments

The default install is lightweight. Optional backends stay out of `requirements.txt`.

Use backend-specific environments in `envs/` and the backend runners:

- `scripts/run_backend.sh`
- `scripts/run_many_backends.sh`

### Install optional backend environments

Core-only environment (default):

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

MinerU environment:
Run on one PDF:

```bash
python -m doc2md path/to/input.pdf -o out/ -vv
```

## Optional backend experiments

The default install is lightweight. Optional backends stay out of `requirements.txt`.

PaddleOCR-VL environment:

```bash
python3.12 -m venv .venv-paddle
source .venv-paddle/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest paddleocr paddlepaddle
```

### Run backend commands

Run through the main CLI:

```bash
python -m doc2md path/to/input.pdf -o out-det --backend deterministic --emit-docir
python -m doc2md path/to/input.pdf -o out-mineru --backend mineru --emit-docir
python -m doc2md path/to/input.pdf -o out-paddle --backend paddleocr_vl --emit-docir
```

Run through backend runner scripts (writes under `runs/<document_id>/<backend_id>/`):

```bash
scripts/run_backend.sh deterministic path/to/input.pdf
scripts/run_backend.sh mineru path/to/input.pdf
scripts/run_backend.sh paddleocr_vl path/to/input.pdf

scripts/run_many_backends.sh path/to/input.pdf deterministic mineru paddleocr_vl
```

Each backend run emits:

- `document.docir.json` (canonical artifact)
- `document.md` (Markdown export)

Use backend-specific environments in `envs/` and the backend runners:

- `scripts/run_backend.sh`
- `scripts/run_many_backends.sh`

Installability smoke checks (isolated sandbox):

```bash
bash install_scripts/check_backend_installs.sh core
bash install_scripts/check_backend_installs.sh mineru
bash install_scripts/check_backend_installs.sh paddleocr_vl
```

These checks validate installation/import contracts only, not extraction quality.

## Validation

```bash
python -m doc2md --help
pytest -q
```
