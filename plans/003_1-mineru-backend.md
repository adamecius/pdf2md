# Add optional MinerU backend as a parallel track

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

MinerU may improve extraction quality for complex pages, but it has heavier dependencies and should not destabilize the deterministic default path.

## Scope

In scope:
- Add an optional MinerU backend adapter behind lazy imports.
- Add backend-specific setup guidance and clear runtime error messaging.
- Add focused offline-safe tests for registration and missing dependency behavior.

Out of scope:
- Enabling MinerU by default.
- Adding MinerU packages to baseline test dependencies.

## Current known state

- `doc2md/backends/mineru_backend.py` currently exists as a stub.
- Backend registry and CLI already support optional backend selection patterns.

## Target behavior

1. MinerU can be selected explicitly when installed.
2. Missing MinerU dependencies produce a clear optional-backend error with install guidance.
3. Baseline deterministic runs are unchanged when MinerU is absent.

## Design and decisions

- Keep MinerU isolated in its own module and import lazily in backend initialization.
- Keep output aligned with DocIR contracts used by exporters.
- Document a dedicated environment recommendation for MinerU installs.

## Milestones

### Milestone 1 - Adapter and lazy import integration

Files:
- `doc2md/backends/mineru_backend.py`
- `doc2md/backends/registry.py`

Work:
Implement backend contract methods and preserve lazy dependency loading.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_backends_registry.py tests/test_missing_optional_backends.py

Expected result:
Registry behavior and missing-dependency handling remain stable.

### Milestone 2 - Focused smoke test and docs

Files:
- `tests/test_mineru_backend_contract.py`
- optional small docs updates

Work:
Add focused contract tests that do not require MinerU package installation by default.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_mineru_backend_contract.py

Expected result:
Contract behavior is validated without changing default dependency requirements.

## Validation

    cd /workspace/pdf2md
    pytest -q

## Risks and rollback notes

- Risk: dependency conflicts with other backend tracks. Mitigation: dedicated environment guidance.
- Risk: accidental eager imports. Mitigation: test missing dependency path.
- Rollback: unregister MinerU backend and keep stub behavior.

## Progress

- [x] 2026-04-25: Implemented MinerU optional-backend adapter improvements with explicit missing-dependency guidance.
- [x] 2026-04-25: Wired MinerU lazy backend factory into registry so selection is explicit and startup remains dependency-light.
- [x] 2026-04-25: Added focused MinerU contract tests and validated optional-backend failure behavior offline.

## Surprises & Discoveries

- 2026-04-25: Direct MinerU imports can fail even when top-level packages are present, so runtime import checks must remain guarded and produce clear environment guidance.

## Decision Log

- 2026-04-25: Keep MinerU registration in the backend registry as a lazy factory to avoid eager optional dependency loading in default startup paths.
- 2026-04-25: Use `OptionalBackendUnavailable` for missing MinerU modules and include a dedicated-environment install hint in the error text.

## Outcomes & Retrospective

- 2026-04-25: MinerU is now explicitly selectable from the registry without changing deterministic defaults.
- 2026-04-25: Offline tests cover MinerU registration and clear missing-dependency messaging without requiring MinerU installation in baseline CI.
