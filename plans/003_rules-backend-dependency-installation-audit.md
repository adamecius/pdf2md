# Define Phase 3 backend coordination rules and dependency audit baseline

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

Phase 3 needs one shared “rules of the game” document before parallel backend subplans continue. Without a common contract, each `003_n` track can drift on dependency policy, installation shape, output locations, and test expectations.

This plan serves as `003_rules`, the general coordination subtask for all backend-specific subtasks (`003_1` through `003_n`). It also preserves an evidence-backed audit of what exists today so Phase 4 can start minimal online installation testing from a stable baseline.

## Scope

In scope:
- Define the common Phase 3 contract that every `003_n` backend subplan must follow.
- Audit current optional dependency testing and installation artifacts for deterministic/mineru/paddleocr_vl.
- Define parallel-execution boundaries and shared merge touchpoints for backend plans.
- Define required scaffolding targets for later implementation:
  - `envs/<backend>.yml`
  - `backend_catalog.yaml`
  - `scripts/run_backend.sh`
  - `scripts/run_many_backends.sh`
  - `runs/<document_id>/<backend_id>/`
  - canonical `document.docir.json`
- Record official upstream references to seed Phase 4 dependency evaluation.

Out of scope:
- Implementing real MinerU or PaddleOCR-VL backend extraction.
- Installing heavyweight backend dependencies in this phase.
- Downloading model weights.
- Adding runtime ML packages to baseline `requirements.txt`.

## Current known state

Current backend testing:
- Registry behavior is covered in `tests/test_backends_registry.py`.
- Missing optional dependency behavior is covered in `tests/test_missing_optional_backends.py`.
- PaddleOCR-VL has focused adapter contract coverage in `tests/test_paddleocr_vl_backend_contract.py`.
- MinerU does not yet have a dedicated contract test equivalent to PaddleOCR-VL.

Current backend registration and adapter state:
- `doc2md/backends/registry.py` registers `deterministic` and `paddleocr-vl`.
- `doc2md/backends/mineru_backend.py` exists as optional stub, but is not currently registered.
- `doc2md/backends/paddleocr_vl_backend.py` includes lazy dependency checks and optional-backend error behavior.

Current installation/scaffolding state:
- No `envs/` directory currently exists.
- No `scripts/` directory currently exists.
- No `backend_catalog.yaml` currently exists.
- README and AGENTS currently describe lightweight core setup; backend-specific install workflows are not yet defined as executable project artifacts.

Official upstream references snapshot for Phase 4 preparation (accessed 2026-04-25 UTC):
- MinerU official repository: https://github.com/opendatalab/MinerU
- PaddleOCR official repository (includes PaddleOCR-VL code path): https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR installation docs: https://www.paddleocr.ai/v3.3.0/en/version3.x/installation.html
- PaddleOCR framework installation docs: https://www.paddleocr.ai/latest/en/version3.x/paddlepaddle_installation.html

## Target behavior

After Phase 3 coordination rules are accepted:

1. Every backend subplan in wave `003_n` references this `003_rules` plan and follows the same dependency + output contract.
2. Parallel tracks can execute independently with explicit merge touchpoints and minimal conflicts.
3. Default `python -m doc2md --help` and `pytest -q` remain lightweight and do not require heavy optional packages.
4. Phase 4 can begin minimal online installation testing using consistent scaffolding and upstream references.

## Design and decisions

Phase model:
- Phase 3: planning + contract definition + lightweight scaffolding preparation only.
- Phase 4: minimal online install testing for each backend in isolated environments.

Parallelization model for `003_n` tracks:
- Independent ownership per backend plan file.
- Shared touchpoints must be listed explicitly in each plan before coding starts.
- Shared files likely to conflict (registry, catalog, scripts) must use append-only edits plus stable key ordering.

Required contract for each backend plan (`003_n`):
1. Upstream references section with official URLs and access date.
2. Offline contract section stating how backend output maps to DocIR.
3. Dependency recommendation section with isolated environment strategy.
4. Test boundary section proving default pytest path stays dependency-light.
5. Scaffolding compatibility section aligned with:
   - Core: package + lightweight requirements only.
   - Backend dependencies: `envs/<backend>.yml`.
   - Backend identity: `backend_catalog.yaml`.
   - Execution: `scripts/run_backend.sh`, `scripts/run_many_backends.sh`.
   - Outputs: `runs/<document_id>/<backend_id>/`.
   - Canonical result: `document.docir.json`.

Scaffolding recommendations for follow-on plans:
- Add `envs/core.yml`, `envs/mineru.yml`, and `envs/paddleocr_vl.yml` in Phase 3 only as manifest scaffolding (no heavy install execution).
- Add `backend_catalog.yaml` in Phase 3 with entries for `deterministic`, `mineru`, `paddleocr_vl` only.
- Defer actual script implementation details (`run_backend.sh`, `run_many_backends.sh`) until backend selection interface and catalog schema are accepted.
- Keep backend installation instructions concise in README and detailed in `docs/backends.md` once scaffolding files exist.

## Milestones

### Milestone 1 - Confirm audit baseline and existing tests

Files:
- `doc2md/backends/registry.py`
- `doc2md/backends/mineru_backend.py`
- `doc2md/backends/paddleocr_vl_backend.py`
- `tests/test_backends_registry.py`
- `tests/test_missing_optional_backends.py`
- `tests/test_paddleocr_vl_backend_contract.py`

Work:
Reconfirm current behavior for optional dependency tests, lazy loading expectations, and registry state so all `003_n` plans begin from facts.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_backends_registry.py tests/test_missing_optional_backends.py tests/test_paddleocr_vl_backend_contract.py

Expected result:
Focused backend tests pass without installing heavy backend packages.

### Milestone 2 - Define Phase 3 general contract for all backend subtasks

Files:
- `plans/003_rules-backend-dependency-installation-audit.md`
- `AGENTS.md`
- `plans/003_1-mineru-backend.md`
- `plans/003_2-paddleocr-vl-backend.md`

Work:
Publish shared rules and update `003_1` and `003_2` to depend on this plan and include required sections for official references, offline contracts, dependency recommendations, and scaffolding alignment.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Planning changes are visible while runtime behavior remains unchanged.

### Milestone 3 - Prepare Phase 4 entry criteria

Files:
- `plans/003_rules-backend-dependency-installation-audit.md`

Work:
Record explicit readiness criteria for moving from Phase 3 planning into Phase 4 minimal online install testing.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help
    pytest -q

Expected result:
Default CLI and tests remain stable and lightweight.

## Validation

Run these commands from repository root:

    cd /workspace/pdf2md
    python -m doc2md --help
    pytest -q

Success signals:
- CLI help command succeeds.
- Default `pytest -q` succeeds without heavy backend installations.
- `003_1` and `003_2` explicitly reference and comply with this `003_rules` contract.

## Risks and rollback notes

Risk: backend plans ignore shared contract and drift.
Mitigation: require each `003_n` plan to list this plan as prerequisite and include a contract-compliance checklist.

Risk: Phase 3 accidentally expands into heavy implementation.
Mitigation: keep this phase limited to planning/scaffolding definitions and prohibit heavy package installs.

Rollback path is safe because this plan is documentation-only.

## Progress

- [x] 2026-04-25 13:05 UTC: Reframed `003_rules` from audit-only note into the general Phase 3 coordination plan.
- [x] 2026-04-25 13:10 UTC: Added official reference snapshot links for MinerU and PaddleOCR installation paths.
- [x] 2026-04-25 13:15 UTC: Added contract requirements that all `003_n` plans must follow.

## Surprises & Discoveries

- 2026-04-25 13:08 UTC: Existing plans referenced backend-specific setup guidance but did not define one shared contract file that all `003_n` tracks must follow.
- 2026-04-25 13:11 UTC: Current code already has optional-backend tests but lacks install-scaffolding artifacts (`envs/`, `scripts/`, `backend_catalog.yaml`).

## Decision Log

- 2026-04-25 13:04 UTC: Keep filename `003_rules-backend-dependency-installation-audit.md` and repurpose it as the general Phase 3 coordination rules file.
- 2026-04-25 13:12 UTC: Require official upstream links + access date in every backend subplan before implementation.
- 2026-04-25 13:14 UTC: Freeze backend scope in this wave to `deterministic`, `mineru`, and `paddleocr_vl`.

## Outcomes & Retrospective

- 2026-04-25 13:15 UTC: Phase 3 now has a single source of truth for parallel backend planning rules, dependency policy, and scaffolding targets required before Phase 4 minimal online installation testing.
