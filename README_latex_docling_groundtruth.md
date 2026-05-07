# LaTeX Docling Groundtruth Harness (Temporary, Local-Only)

This temporary root-level harness generates **source-known LaTeX fixtures** and local contracts, then provides a local backend runner and validator.

## Purpose
- Create deterministic LaTeX inputs for Docling-oriented checks.
- Emit source-known ground-truth IR/contracts at generation time (not guessed later).
- Run configured backends locally and normalize outputs for consensus/semantic/docling pipeline checks.

## Scripts
- `generate_latex_docling_groundtruth.py`
- `run_latex_docling_backends.sh`
- `validate_latex_docling_groundtruth.py`

## Generate fixtures
```bash
python generate_latex_docling_groundtruth.py --output-root groundtruth/corpus/latex --compile --verbose
```
If no LaTeX engine is found, `.tex` + contracts are still generated and PDF compilation is marked skipped in provenance.

## Run backends (local only)
```bash
bash run_latex_docling_backends.sh --batch batch_001 --root groundtruth/corpus/latex --config pdf2md.consensus.example.toml --verbose
```

Canonical backend names:
- `mineru`
- `paddleocr`
- `deepseek`

Alias names in config are normalised with a warning (for example `mineruo -> mineru`).

Environment names:
- `pdf2md-mineru`
- `pdf2md-paddleocr`
- `pdf2md-deepseek`

Adapter selection order:
1. Override command env var
   - `PDF2MD_MINERU_PDF2IR_CMD`
   - `PDF2MD_PADDLEOCR_PDF2IR_CMD`
   - `PDF2MD_DEEPSEEK_PDF2IR_CMD`
2. Exact canonical adapter path
   - `backend/mineru/pdf2ir_mineru.py`
   - `backend/paddleocr/pdf2ir_paddleocr.py`
   - `backend/deepseek/pdf2ir_deepseek.py`
3. Fallback to sorted `pdf2ir*.py` discovery in `backend/<name>/`.

Canonical DeepSeek adapter filename is:
- `backend/deepseek/pdf2ir_deepseek.py`

## Validate outputs
```bash
python validate_latex_docling_groundtruth.py --root groundtruth/corpus/latex --batch batch_001 --verbose
```

Before backends are run, missing backend manifests are expected and reported as warnings:
- `backend_not_run_mineru`
- `backend_not_run_paddleocr`
- `backend_not_run_deepseek`

These warnings do **not** fail ground-truth validation by themselves.

## Expected layout
Under `groundtruth/corpus/latex/<document_id>/`:
- `<document_id>.tex`
- `<document_id>.docling.json`
- `<document_id>.docling_groundtruth_meta.json`
- `meta.toml`
- optional generated harness subdirectories such as `input/`, `groundtruth/`, `backend_ir/`, `consensus/`, `docling/`, and `reports/` when local runtime stages have been materialized.

## Notes
- Local-only operational tooling; not CI.
- Generated runtime files are artifacts, not source-of-truth; canonical LaTeX ground truth lives under `groundtruth/corpus/latex/<document_id>/`.
- These root-level scripts are temporary and may be deleted later.

## Canonical pre-Docling ground truth

LaTeX source (`input/*.tex`) and compiled PDF (`input/*.pdf`) are the source of truth. `semantic_document_groundtruth.json` is a deterministic LaTeX-derived pre-Docling benchmark target produced by `latex_to_pre_docling_groundtruth.py`.

Backend semantic outputs (for example `consensus/semantic_document.json`) are compared against this pre-Docling ground truth using `compare_pre_docling_groundtruth.py` before Docling export checks. Docling export is downstream verification only.

In this benchmark phase, exact geometric coordinates are optional unless explicitly provided by source artifacts.
