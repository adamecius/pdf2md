# Repository Audit (2026-04-26)

## 1) Separation: agent-directed files vs code files

### Agent-directed / process files

- `AGENTS.md`
- `.agent/PLANS.md`
- `plans/*.md`
- `docs/project-consistency-audit.md`
- `docs/repo-audit.md` (this file)

These files define operating rules, phased scope, execution coordination, and audit notes.

### Product/runtime code files

- `doc2md/**/*.py`
- `scripts/*.sh`
- `install_scripts/*.sh`
- `backend_catalog.yaml`
- `envs/*.yml`
- `requirements.txt`
- `tests/**/*.py`

These files define executable behavior, contracts, and validation.

## 2) Plan compatibility with work completed

Compatibility review against completed work and the active direction (single-PDF CLI + DocIR normalization + backend contracts) is:

- `plans/001-deterministic-extraction.md`: compatible and implemented baseline.
- `plans/002-docir-offline-foundations.md`: compatible and implemented as additive foundations.
- `plans/003-backend-feasibility-and-parallel-launch.md` + `plans/003_rules-*` + `plans/003_n-*`: compatible with current scaffold-only backend expansion.
- `plans/004-backend-install-sandbox.md` and `plans/005-backend-install-verification-and-docs.md`: compatible as install-contract hardening and documentation follow-up.

Conclusion: plan lineage is coherent with the delivered structure (core deterministic pipeline + DocIR + optional backend scaffolding).

## 3) Redundancy/bloat findings and lean actions applied

Applied in this audit pass:

1. Removed legacy empty placeholders that added confusion but no behavior:
   - `doc2md/analyzer.py` (empty)
   - `doc2md/config.py` (empty)
   - `doc2md/__init__` (empty non-Python-suffixed file)
2. Reduced CLI surface that was not connected to current execution:
   - removed unused `--ocr` and `--layout` arguments from `doc2md/cli.py`.
3. Simplified README to match the actual product contract:
   - single-PDF CLI, deterministic-first + DocIR exports, optional backend install checks.

## 4) Current gap summary (what still feels “bloated”)

Some scaffolding is intentionally ahead of full implementation (for example optional backend adapters and layout/OCR registries). This is acceptable **only** if treated as contract scaffolding, not as delivered extraction capabilities.

If further lean-down is desired in a next pass, prioritize:

- collapsing duplicate historical audit docs into one canonical `docs/` status file,
- marking completed plans as archived snapshots (read-only) and adding one short index table,
- reducing duplicated setup wording across docs and README.

## 5) Recommended next step

Given your goal (manual testing soon), the next highest-value step is:

1. run deterministic/manual fixtures and record failure modes at page level,
2. validate DocIR round-trip integrity against those fixtures,
3. define acceptance checks for backend contract outputs under `runs/<document_id>/<backend_id>/document.docir.json` before adding more backend logic.

This keeps the project aligned with your stated objective: validate a stable IR contract before expanding backend implementation complexity.
