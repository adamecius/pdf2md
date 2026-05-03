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
- Discovers enabled backends from selected config `[backends.<name>]`.
- Tries adapter selection in `backend/<name>/` (`pdf2ir_<name>.py`, then `pdf2ir*.py`) or override env var `PDF2MD_<NAME>_PDF2IR_CMD`.
- Activates conda env `pdf2md-<backend>`.

## Validate outputs
```bash
python validate_latex_docling_groundtruth.py --root .current/latex_docling_groundtruth --batch batch_001 --verbose
```

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
