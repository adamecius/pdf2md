# Add optional PaddleOCR-VL backend as a parallel track

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

PaddleOCR-VL is a strong optional backend candidate for visual-heavy parsing, but it carries heavyweight optional dependencies that must remain isolated from the deterministic baseline.

This `003_2` plan is a backend-specific subtask that depends on `plans/003_rules-backend-dependency-installation-audit.md` for Phase 3 contract rules.

## Scope

In scope:
- Define PaddleOCR-VL-specific optional backend integration plan under the shared Phase 3 contract.
- Capture official upstream references and installation constraints.
- Define offline contract expectations for mapping PaddleOCR-VL outputs into DocIR.
- Define isolated dependency recommendations through `envs/paddleocr_vl.yml` planning.
- Define focused tests that preserve lightweight default `pytest -q` behavior.

Out of scope:
- Shipping full PaddleOCR-VL extraction implementation in this phase.
- Adding heavy Paddle/PaddleOCR dependencies to baseline requirements.
- Downloading models as part of default test flow.

## Current known state

- `doc2md/backends/paddleocr_vl_backend.py` exists as optional stub with lazy dependency checks.
- `paddleocr-vl` is currently registered in `doc2md/backends/registry.py`.
- Shared missing-optional tests and dedicated PaddleOCR-VL contract tests already exist.

## Target behavior

1. PaddleOCR-VL track can proceed independently while staying compliant with `003_rules` contract rules.
2. PaddleOCR-VL dependencies remain isolated in backend-specific environment guidance.
3. Missing dependencies produce clear optional-backend messaging.
4. Default project CLI/tests still run without PaddleOCR-VL installed.

## Design and decisions

Prerequisite:
- Read and apply `plans/003_rules-backend-dependency-installation-audit.md` before executing this plan.

Official upstream references (snapshot, accessed 2026-04-25 UTC):
- PaddleOCR repository (includes PaddleOCR-VL path): https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR installation docs: https://www.paddleocr.ai/v3.3.0/en/version3.x/installation.html
- PaddlePaddle installation docs: https://www.paddleocr.ai/latest/en/version3.x/paddlepaddle_installation.html

Offline contract expectations:
- PaddleOCR-VL adapter must emit DocIR-compatible artifacts used by existing exporters.
- Backend outputs must follow `runs/<document_id>/<backend_id>/` conventions.
- Canonical output for cross-backend comparison is `document.docir.json`.

Dependency recommendations:
- Add `envs/paddleocr_vl.yml` as backend-specific environment manifest.
- Keep core dependencies separate in `envs/core.yml`.
- Do not alter baseline lightweight requirements in this phase.

Scaffolding alignment requirements:
- Register backend identity in `backend_catalog.yaml` when catalog is introduced.
- Ensure compatibility with `scripts/run_backend.sh` and `scripts/run_many_backends.sh` execution contracts.

## Milestones

### Milestone 1 - PaddleOCR-VL dependency and contract planning details

Files:
- `plans/003_2-paddleocr-vl-backend.md`

Work:
Document latest official references, environment recommendations, and DocIR contract mapping expectations for PaddleOCR-VL.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Plan is explicit and runtime behavior is unchanged.

### Milestone 2 - Phase 3 scaffolding-compatible implementation prep

Files:
- `plans/003_2-paddleocr-vl-backend.md`
- optional future: `envs/paddleocr_vl.yml`, `backend_catalog.yaml`

Work:
Define exact future integration order so PaddleOCR-VL code and scaffolding can land without breaking default tests.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_paddleocr_vl_backend_contract.py

Expected result:
Optional-backend contract guarantees remain intact.

## Validation

    cd /workspace/pdf2md
    python -m doc2md --help
    pytest -q

## Risks and rollback notes

- Risk: Paddle/PaddleOCR dependency stack conflicts with other backends. Mitigation: isolate via `envs/paddleocr_vl.yml`.
- Risk: backend plan drifts from shared contract. Mitigation: enforce prerequisite `003_rules` compliance.
- Rollback: plan-only changes are safe to revert.

## Progress

- [x] 2026-04-25 13:24 UTC: Updated `003_2` to explicitly depend on shared `003_rules` Phase 3 rules.
- [x] 2026-04-25 13:26 UTC: Added upstream-reference, offline-contract, and scaffolding-alignment sections.

## Surprises & Discoveries

- 2026-04-25 13:25 UTC: Existing `003_2` content mixed planning and implementation status; this revision keeps the track aligned to Phase 3 planning requirements.

## Decision Log

- 2026-04-25 13:24 UTC: Keep `003_2` as planning-first in Phase 3; defer heavy implementation to Phase 4+.

## Outcomes & Retrospective

- 2026-04-25 13:26 UTC: PaddleOCR-VL subplan is now aligned with a common Phase 3 contract and ready for parallel coordination.
