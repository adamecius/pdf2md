# Docling Groundtruth Fixtures (Phase 1)

These fixtures are **source-known LaTeX ground truth definitions** for Docling Phase 1A.

## Scope
- Full PDF -> backend -> consensus -> Docling validation is **local-only**.
- Codex/CI should **not** run backend extraction or GPU/model-heavy stages.
- `.current` generated outputs are runtime artefacts, **not source truth**.

## Local workflows
- Full local regeneration: `scripts/local_build_docling_fixtures.sh`
- Local contract validation: `scripts/local_validate_docling_fixtures.sh`

Backend commands may require explicit overrides:
- `PDF2MD_MINERU_PDF2IR_CMD`
- `PDF2MD_PADDLEOCR_PDF2IR_CMD`
- `PDF2MD_DEEPSEEK_PDF2IR_CMD`

Expected contracts define **machine-checkable constraints**, not exact final JSON dumps.


## Consensus config and backend IR layout
- Local build generates a per-document consensus TOML using `[backends.<name>]` root fields (not `[paths]`).
- Expected backend IR layout for consensus is: `<backend_root>/.current/extraction_ir/<pdf_stem>/` with `manifest.json` and `pages/`.
- Backend commands can require environment-variable command overrides if local CLI wiring differs.
