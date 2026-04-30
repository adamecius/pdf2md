# pdf2md

## 1) Project purpose
pdf2md converts PDFs to Markdown using multiple OCR/parser backends and later consensus.

## 2) Current stage
This repository currently provides backend wrappers and config-driven backend orchestration.

## 3) What exists now
- Core `pdf2md` package in `src/pdf2md`
- Backend wrappers under `backend/`
- Config-driven `run-backends` CLI command

## 4) What does not exist yet
- Adapters
- Normalisation
- Consensus
- Final full convert pipeline

## 5) Setup
Install the central package:

```bash
python -m pip install -e .
```

## 6) Config
Copy the example config and edit backend settings:

```bash
cp pdf2md.backends.example.toml pdf2md.backends.toml
```

Then update enabled backends, model paths, and environment variables.

## 7) Running
Run configured and enabled backends only:

```bash
pdf2md run-backends test.pdf --config pdf2md.backends.toml
```

No backend runs unless it appears in config and is enabled.

## 8) Output folder
Runs are stored under:

```text
.tmp/<run-name>/
```

## 9) Safety
- Only configured and enabled backends run.
- API backends do not run unless explicitly configured.
- Local `pdf2md.backends.toml` is gitignored.

## 10) Tests
```bash
python -m pytest -q tests/test_models_and_rendering.py tests/smoke/test_backend_clis.py tests/test_run_backends_config.py
```

## 11) Roadmap
- Add adapter for MinerU
- Normalise backend outputs
- Implement consensus
- Render final Markdown
