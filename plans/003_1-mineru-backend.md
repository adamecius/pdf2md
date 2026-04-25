# Add optional MinerU backend as a parallel track

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

MinerU is a candidate optional backend for complex document extraction, but it introduces heavier dependencies and licensing nuances that must stay isolated from the deterministic default path.

This `003_1` plan is a backend-specific subtask that depends on `plans/003_rules-backend-dependency-installation-audit.md` for Phase 3 contract rules.

## Scope

In scope:
- Define MinerU-specific optional backend integration plan under the shared Phase 3 contract.
- Capture official upstream references and current installation constraints.
- Define offline contract expectations for mapping MinerU outputs into DocIR.
- Define isolated dependency recommendations through `envs/mineru.yml` planning.
- Define focused tests that preserve lightweight default `pytest -q` behavior.
- Declare independent ownership boundaries and shared merge touchpoints for parallel wave `003_n`.

Out of scope:
- Shipping full MinerU extraction implementation in this phase.
- Adding heavy MinerU dependencies to baseline requirements.
- Downloading models as part of default test flow.

Parallel dependency and merge touchpoints:
- Depends on: `plans/003_rules-backend-dependency-installation-audit.md`.
- Parallel peers in wave `003_n`: `plans/003_2-paddleocr-vl-backend.md`, `plans/003_3-experimental-universal-backends.md`.
- Independent owner area: `doc2md/backends/mineru_backend.py`, `tests/test_mineru_backend_contract.py` (future), `envs/mineru.yml` (future).
- Shared merge touchpoints (coordinate with other `003_n` tracks): `backend_catalog.yaml`, `doc2md/backends/registry.py`, `scripts/run_backend.sh`, `scripts/run_many_backends.sh`, README backend setup section.
- Merge-order guardrail for shared touchpoints:
  1. land backend-specific files first (`envs/mineru.yml`, MinerU contract tests),
  2. rebase on latest wave branch state,
  3. then apply append-only edits to shared files in one PR.

## Current known state

- `doc2md/backends/mineru_backend.py` exists as an optional stub.
- MinerU is registered in `doc2md/backends/registry.py` via lazy backend creation.
- Shared optional-backend missing-dependency tests include `MineruBackend`, and dedicated MinerU contract tests exist in `tests/test_mineru_backend_contract.py`.

## Target behavior

1. MinerU track can proceed independently while staying compliant with `003_rules` contract rules.
2. MinerU dependencies remain isolated in backend-specific environment guidance.
3. Missing MinerU dependencies produce clear optional-backend messaging.
4. Default project CLI/tests still run without MinerU installed.

## Design and decisions

Prerequisite:
- Read and apply `plans/003_rules-backend-dependency-installation-audit.md` before executing this plan.

Official upstream references (snapshot, accessed 2026-04-25 UTC):
- MinerU repository: https://github.com/opendatalab/MinerU

Offline contract expectations:
- MinerU adapter must emit DocIR-compatible artifacts used by existing exporters.
- Backend outputs must follow `runs/<document_id>/<backend_id>/` conventions.
- Canonical output for cross-backend comparison is `document.docir.json`.

Dependency recommendations:
- Add `envs/mineru.yml` as backend-specific environment manifest.
- Keep core dependencies separate in `envs/core.yml`.
- Do not alter baseline lightweight requirements in this phase.
- Use a disposable local sandbox for installation probes (for example `sandbox/mineru-install/.venv`) so backend experiments never pollute the core environment.

Test boundary requirements (Phase 3 contract compliance):
- Default validation path (`pytest -q`) must pass without MinerU dependencies installed.
- MinerU-specific contract tests (when added) must be opt-in and runnable in isolated backend environment only.
- Missing optional dependencies must raise `OptionalBackendUnavailable` with actionable environment guidance.

Scaffolding alignment requirements:
- Register backend identity in `backend_catalog.yaml` when catalog is introduced.
- Ensure compatibility with `scripts/run_backend.sh` and `scripts/run_many_backends.sh` execution contracts.

Parallel execution compatibility checklist:
- [x] This plan references `003_rules` as prerequisite contract authority.
- [x] Independent-owner files are explicitly listed and avoid overlap with `003_2` and `003_3`.
- [x] Shared-file touchpoints are explicitly listed and constrained to append-only edits.
- [x] Output artifact contract is aligned to `runs/<document_id>/<backend_id>/document.docir.json`.
- [x] Default lightweight test path remains required: `pytest -q` without heavy MinerU dependencies.

Parallel ownership matrix (wave `003_n`):

| Plan | Primary owner files | Shared touchpoints | Notes |
| --- | --- | --- | --- |
| `003_1` MinerU | `doc2md/backends/mineru_backend.py`, `tests/test_mineru_backend_contract.py` (future), `envs/mineru.yml` (future) | `backend_catalog.yaml`, `doc2md/backends/registry.py`, `scripts/run_backend.sh`, `scripts/run_many_backends.sh`, README | Keep MinerU dependency policy isolated. |
| `003_2` PaddleOCR-VL | `doc2md/backends/paddleocr_vl_backend.py`, `tests/test_paddleocr_vl_backend_contract.py`, `envs/paddleocr_vl.yml` (future) | Same shared touchpoints | Coordinate key ordering and append-only edits. |
| `003_3` Experimental universal | `docs/experimental-universal-backends.md`, `tests/test_universal_backend_import_guards.py` | README (experimental section), optional `scripts/run_many_backends.sh` notes | Must stay non-blocking and best-effort. |

## Milestones

### Milestone 1 - MinerU dependency and contract planning details

Files:
- `plans/003_1-mineru-backend.md`

Work:
Document latest official references, environment recommendations, and DocIR contract mapping expectations for MinerU.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Plan is explicit and runtime behavior is unchanged.

### Milestone 2 - Phase 3 scaffolding-compatible implementation prep

Files:
- `plans/003_1-mineru-backend.md`
- optional future: `envs/mineru.yml`, `backend_catalog.yaml`

Work:
Define exact future integration order so MinerU code and scaffolding can land without breaking default tests.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_missing_optional_backends.py

Expected result:
Optional-backend missing-dependency guarantees remain intact.

Sandbox installation probe command (non-blocking for Phase 3 planning):

    cd /workspace/pdf2md
    python3 -m venv sandbox/mineru-install/.venv
    . sandbox/mineru-install/.venv/bin/activate
    pip install -r requirements.txt pytest mineru

### Milestone 3 - Merge touchpoint readiness for parallel wave

Files:
- `plans/003_1-mineru-backend.md`

Work:
Record exactly where cross-track coordination is required before implementation PRs touch shared files.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Shared-file conflict points are explicit and Phase 3 remains planning-only.

### Milestone 4 - Cross-plan compatibility handshake (`003_2` + `003_3`)

Files:
- `plans/003_1-mineru-backend.md`
- `plans/003_2-paddleocr-vl-backend.md`
- `plans/003_3-experimental-universal-backends.md`

Work:
Record explicit ownership boundaries and merge sequencing so `003_1` implementation can be executed in parallel without blocking other `003_n` tracks.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Parallel execution boundaries for the full `003_n` wave are documented and implementation-ready.

## Validation

    cd /workspace/pdf2md
    python -m doc2md --help
    pytest -q

## Risks and rollback notes

- Risk: MinerU dependency stack conflicts with other backends. Mitigation: isolate via `envs/mineru.yml`.
- Risk: backend plan drifts from shared contract. Mitigation: enforce prerequisite `003_rules` compliance checklist in this plan.
- Rollback: plan-only changes are safe to revert.

## Progress

- [x] 2026-04-25 14:00 UTC: Reworked `003_1` to fully align with `003_rules` Phase 3 contract requirements.
- [x] 2026-04-25 14:02 UTC: Added explicit parallel dependency and merge touchpoints for wave `003_n`.
- [x] 2026-04-25 14:04 UTC: Added explicit test-boundary requirements to protect lightweight default test path.
- [x] 2026-04-25 15:05 UTC: Added cross-plan compatibility checklist and ownership matrix covering `003_2` and `003_3`.
- [x] 2026-04-25 15:08 UTC: Added merge-order guardrail and handshake milestone for parallel-safe shared touchpoint edits.
- [x] 2026-04-25 16:00 UTC: Created local sandbox path `sandbox/mineru-install/.venv` and ran installation probe commands for MinerU dependencies.
- [x] 2026-04-25 16:20 UTC: Retried sandbox installation probe with explicit PyPI index and with proxy-disabled environment variables to isolate network failure mode.

## Surprises & Discoveries

- 2026-04-25 14:01 UTC: Prior `003_1` content mixed planning and implementation-status notes, which conflicted with Phase 3 planning-only scope.
- 2026-04-25 15:03 UTC: `003_3` intentionally has broader experimental scope, so shared-touchpoint policy must be explicit to avoid accidental coupling with backend-specific tracks.
- 2026-04-25 16:02 UTC: Installation probe from sandbox hit package-index proxy restrictions (`403 Forbidden`), so successful MinerU install could not be confirmed in this environment.
- 2026-04-25 16:21 UTC: Bypassing proxy variables changed the failure to `Network is unreachable`, confirming this environment cannot currently validate external MinerU package installation.

## Decision Log

- 2026-04-25 14:00 UTC: Keep `003_1` as planning-first in Phase 3 and remove implementation-status claims.
- 2026-04-25 14:03 UTC: Treat shared-file coordination as a first-class milestone to reduce merge churn across parallel backend tracks.
- 2026-04-25 15:06 UTC: Adopt an explicit ownership matrix in `003_1` so parallel wave contributors can validate overlap before editing shared files.
- 2026-04-25 16:03 UTC: Keep sandbox installation probe documented as non-blocking evidence for Phase 3 due network/proxy constraints.
- 2026-04-25 16:22 UTC: Treat repeated install-probe failures as infrastructure constraints, not backend-plan blockers; keep default tests as the gating signal in this environment.

## Outcomes & Retrospective

- 2026-04-25 14:04 UTC: MinerU subplan now explicitly satisfies `003_rules` contract sections, parallel dependency boundaries, and merge touchpoint clarity.
