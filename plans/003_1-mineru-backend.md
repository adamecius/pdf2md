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

Out of scope:
- Shipping full MinerU extraction implementation in this phase.
- Adding heavy MinerU dependencies to baseline requirements.
- Downloading models as part of default test flow.

## Current known state

- `doc2md/backends/mineru_backend.py` exists as an optional stub.
- MinerU is not registered in `doc2md/backends/registry.py` yet.
- Shared optional-backend missing-dependency tests include `MineruBackend`, but there is no dedicated MinerU contract test file yet.

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

Scaffolding alignment requirements:
- Register backend identity in `backend_catalog.yaml` when catalog is introduced.
- Ensure compatibility with `scripts/run_backend.sh` and `scripts/run_many_backends.sh` execution contracts.

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

## Validation

    cd /workspace/pdf2md
    python -m doc2md --help
    pytest -q

## Risks and rollback notes

- Risk: MinerU dependency stack conflicts with other backends. Mitigation: isolate via `envs/mineru.yml`.
- Risk: backend plan drifts from shared contract. Mitigation: enforce prerequisite `003_rules` compliance.
- Rollback: plan-only changes are safe to revert.

## Progress

- [x] 2026-04-25 13:20 UTC: Updated `003_1` to explicitly depend on shared `003_rules` Phase 3 rules.
- [x] 2026-04-25 13:22 UTC: Added upstream-reference, offline-contract, and scaffolding-alignment sections.

## Surprises & Discoveries

- 2026-04-25 13:21 UTC: Current repository lacks MinerU-specific contract tests, so shared optional-backend tests are currently the only MinerU coverage.

## Decision Log

- 2026-04-25 13:19 UTC: Keep `003_1` as planning-first in Phase 3; defer heavy implementation to Phase 4+.

## Outcomes & Retrospective

- 2026-04-25 13:22 UTC: MinerU subplan is now aligned with a common Phase 3 contract and ready for parallel coordination.
