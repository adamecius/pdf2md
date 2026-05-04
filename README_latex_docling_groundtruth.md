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
python generate_latex_docling_groundtruth.py --batch batch_001 --output-root .current/latex_docling_groundtruth --count 20 --compile --verbose
```
If no LaTeX engine is found, `.tex` + contracts are still generated and PDF compilation is marked skipped in provenance.

## Run backends (local only)
```bash
bash run_latex_docling_backends.sh --batch batch_001 --root .current/latex_docling_groundtruth --config pdf2md.consensus.example.toml --verbose
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
python validate_latex_docling_groundtruth.py --root .current/latex_docling_groundtruth --batch batch_001 --verbose
```

Before backends are run, missing backend manifests are expected and reported as warnings:
- `backend_not_run_mineru`
- `backend_not_run_paddleocr`
- `backend_not_run_deepseek`

These warnings do **not** fail ground-truth validation by themselves.

## Expected layout
Under `.current/latex_docling_groundtruth/<batch>/<document_id>/`:
- `input/` (`.tex`, optional `.pdf`)
- `groundtruth/` (`source_groundtruth_ir.json`, semantic/docling contracts, provenance)
- `backend_ir/<backend>/.current/extraction_ir/<document_id>/...`
- `consensus/` (`consensus_report.json`, links, media manifest, semantic document)
- `docling/` outputs
- `reports/` stage logs
- `local_run_manifest.json`, `validation_report.json`

## Notes
- Local-only operational tooling; not CI.
- Generated `.current` files are runtime artifacts, not source-of-truth.
- These root-level scripts are temporary and may be deleted later.

## Canonical pre-Docling ground truth

LaTeX source (`input/*.tex`) and compiled PDF (`input/*.pdf`) are the source of truth. `semantic_document_groundtruth.json` is a deterministic LaTeX-derived pre-Docling benchmark target produced by `latex_to_pre_docling_groundtruth.py`.

Backend semantic outputs (for example `consensus/semantic_document.json`) are compared against this pre-Docling ground truth using `compare_pre_docling_groundtruth.py` before Docling export checks. Docling export is downstream verification only.

In this benchmark phase, exact geometric coordinates are optional unless explicitly provided by source artifacts.

## Canonical corpus
Use `groundtruth/corpus/latex` as canonical source.

1. `python scripts/compile_corpus.py --corpus-root groundtruth/corpus/latex`
2. `python scripts/certify_corpus.py --corpus-root groundtruth/corpus/latex`
3. run derivation scripts with `--corpus-root`.

