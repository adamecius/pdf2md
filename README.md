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
