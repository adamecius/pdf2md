# Add optional PaddleOCR-VL backend as a parallel track

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

PaddleOCR-VL may improve visual-heavy page extraction, but it introduces heavyweight optional dependencies that must remain isolated from the deterministic baseline.

## Scope

In scope:
- Add an optional PaddleOCR-VL backend adapter behind lazy imports.
- Add backend-specific setup guidance and clear runtime error messaging.
- Add focused offline-safe tests for registration and missing dependency behavior.

Out of scope:
- Enabling PaddleOCR-VL by default.
- Adding PaddleOCR-VL packages to baseline test dependencies.

## Current known state

- `doc2md/backends/paddleocr_vl_backend.py` currently exists as a stub.
- Backend registry and CLI already support optional backend selection patterns.

## Target behavior

1. PaddleOCR-VL can be selected explicitly when installed.
2. Missing dependencies produce a clear optional-backend error with install guidance.
3. Baseline deterministic runs are unchanged when PaddleOCR-VL is absent.

## Design and decisions

- Keep PaddleOCR-VL isolated in its own module and import lazily in backend initialization.
- Keep output aligned with DocIR contracts used by exporters.
- Document a dedicated environment recommendation for PaddleOCR-VL installs.

## Milestones

### Milestone 1 - Adapter and lazy import integration

Files:
- `doc2md/backends/paddleocr_vl_backend.py`
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
- `tests/test_paddleocr_vl_backend_contract.py`
- optional small docs updates

Work:
Add focused contract tests that do not require PaddleOCR-VL package installation by default.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_paddleocr_vl_backend_contract.py

Expected result:
Contract behavior is validated without changing default dependency requirements.

## Validation

    cd /workspace/pdf2md
    pytest -q

## Risks and rollback notes

- Risk: dependency conflicts with other backend tracks. Mitigation: dedicated environment guidance.
- Risk: accidental eager imports. Mitigation: test missing dependency path.
- Rollback: unregister PaddleOCR-VL backend and keep stub behavior.

## Progress

- [ ] Not started

## Surprises & Discoveries

- None yet.

## Decision Log

- None yet.

## Outcomes & Retrospective

- To be filled during execution and at completion.
