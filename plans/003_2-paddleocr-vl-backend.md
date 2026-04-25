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
- Declare independent ownership boundaries and shared merge touchpoints for parallel wave `003_n`.
- Define a merge-safe sequencing protocol compatible with existing `003_1` and `003_3` tracks.

Out of scope:
- Shipping full PaddleOCR-VL extraction implementation in this phase.
- Adding heavy Paddle/PaddleOCR dependencies to baseline requirements.
- Downloading models as part of default test flow.

Parallel dependency and merge touchpoints:
- Depends on: `plans/003_rules-backend-dependency-installation-audit.md`.
- Independent owner area: `doc2md/backends/paddleocr_vl_backend.py`, `tests/test_paddleocr_vl_backend_contract.py`, `envs/paddleocr_vl.yml` (future).
- Shared merge touchpoints (coordinate with other `003_n` tracks): `backend_catalog.yaml`, `doc2md/backends/registry.py`, `scripts/run_backend.sh`, `scripts/run_many_backends.sh`, README backend setup section.

## Current known state

- `doc2md/backends/paddleocr_vl_backend.py` exists as optional stub with lazy dependency checks.
- `paddleocr_vl` is currently registered in `doc2md/backends/registry.py`.
- Shared missing-optional tests and dedicated PaddleOCR-VL contract tests already exist.
- `plans/003_1-mineru-backend.md` follows the shared contract and touches the same shared files in later milestones.
- `plans/003_3-experimental-universal-backends.md` exists and is intentionally experimental; it should not block backend-specific tracks.
- Phase 3 scaffolding artifacts now exist: `backend_catalog.yaml`, `envs/core.yml`, `envs/paddleocr_vl.yml`, `scripts/run_backend.sh`, and `scripts/run_many_backends.sh`.

## Target behavior

1. PaddleOCR-VL track can proceed independently while staying compliant with `003_rules` contract rules.
2. PaddleOCR-VL dependencies remain isolated in backend-specific environment guidance.
3. Missing dependencies produce clear optional-backend messaging.
4. Default project CLI/tests still run without PaddleOCR-VL installed.
5. Work from `003_2` can merge without blocking parallel progress in `003_1` and `003_3`.

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

Test boundary requirements (Phase 3 contract compliance):
- Default validation path (`pytest -q`) must pass without PaddleOCR/PaddleOCR-VL dependencies installed.
- PaddleOCR-VL-specific contract tests remain opt-in when they require heavy backend dependencies.
- Missing optional dependencies must raise `OptionalBackendUnavailable` with actionable environment guidance.

Scaffolding alignment requirements:
- Register backend identity in `backend_catalog.yaml` when catalog is introduced.
- Ensure compatibility with `scripts/run_backend.sh` and `scripts/run_many_backends.sh` execution contracts.

Parallel execution compatibility protocol for wave `003_n`:
- `003_2` must stay independently executable before any shared-file change lands.
- Shared-file edits should be append-only where possible and use stable key ordering for deterministic merges.
- If `003_1` and `003_2` both touch registry/catalog/scripts in the same wave, merge order is: land backend-specific file changes first, then rebase for shared-file integration.
- `003_3` remains documentation/test-guard focused and must not force dependency or registry changes required by `003_2`.

Cross-plan merge checklist:
- `003_1`: confirm backend key naming convention (`mineru`, `paddleocr_vl`) matches catalog and script selectors.
- `003_2`: avoid introducing new shared schema fields without a separate shared-rules update.
- `003_3`: keep universal-environment docs explicitly non-blocking and optional.

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

### Milestone 3 - Merge touchpoint readiness for parallel wave

Files:
- `plans/003_2-paddleocr-vl-backend.md`

Work:
Record exactly where cross-track coordination is required before implementation PRs touch shared files, including compatibility rules for `003_1` and `003_3`.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Shared-file conflict points are explicit and Phase 3 remains planning-only.

## Validation

    cd /workspace/pdf2md
    python -m doc2md --help
    pytest -q

Success signals:
- CLI help remains stable without optional backend installs.
- Baseline tests remain lightweight and green.
- `003_2` explicitly defines merge-safe behavior with `003_1` and `003_3`.

## Risks and rollback notes

- Risk: Paddle/PaddleOCR dependency stack conflicts with other backends. Mitigation: isolate via `envs/paddleocr_vl.yml`.
- Risk: backend plan drifts from shared contract. Mitigation: enforce prerequisite `003_rules` compliance checklist in this plan.
- Risk: shared-file merge churn across `003_1` and `003_2`. Mitigation: use merge sequencing and append-only key ordering rules.
- Rollback: plan-only changes are safe to revert.

## Progress

- [x] 2026-04-25 14:05 UTC: Reworked `003_2` to fully align with `003_rules` Phase 3 contract requirements.
- [x] 2026-04-25 14:07 UTC: Added explicit parallel dependency and merge touchpoints for wave `003_n`.
- [x] 2026-04-25 14:09 UTC: Added explicit test-boundary requirements to protect lightweight default test path.
- [x] 2026-04-25 14:30 UTC: Added merge-safe compatibility protocol with `003_1` and `003_3`, including a cross-plan checklist.
- [x] 2026-04-25 15:05 UTC: Executed Phase 3 scaffolding for `003_2` by adding backend catalog, environment manifests, and runner scripts with deterministic smoke coverage.
- [x] 2026-04-25 16:10 UTC: Created local `sandbox/` installation area (gitignored) and attempted isolated PaddleOCR-VL dependency install test.
- [x] 2026-04-25 16:22 UTC: Re-ran sandbox install test with proxy disabled to verify whether failures were proxy-specific.

## Surprises & Discoveries

- 2026-04-25 14:06 UTC: Prior `003_2` had contract intent but did not explicitly call out merge-touchpoint ownership, which is required for parallel execution clarity.
- 2026-04-25 14:28 UTC: Existing `003_3` remains useful but does not yet cite shared-rules coupling, so `003_2` now records non-blocking boundaries directly.
- 2026-04-25 14:58 UTC: The CLI has no direct backend selector yet, so scaffolding scripts must route through the registry for optional backends while keeping deterministic execution on the package CLI path.
- 2026-04-25 16:09 UTC: This container cannot reach package indexes due proxy tunnel 403 responses, so isolated install validation cannot complete online here.
- 2026-04-25 16:22 UTC: Retried installation without proxy variables; direct egress is blocked (`[Errno 101] Network is unreachable`), confirming installation is environment-blocked rather than package-specific.

## Decision Log

- 2026-04-25 14:05 UTC: Keep `003_2` as planning-first in Phase 3 and avoid implementation-status claims.
- 2026-04-25 14:08 UTC: Treat shared-file coordination as a first-class milestone to reduce merge churn across parallel backend tracks.
- 2026-04-25 14:29 UTC: Define explicit `003_1`/`003_2` merge order and make `003_3` non-blocking for backend-specific tracks.
- 2026-04-25 15:00 UTC: Use `paddleocr_vl` consistently for the backend catalog ID, registry name, install sandbox ID, and script selector.

## Outcomes & Retrospective

- 2026-04-25 14:09 UTC: PaddleOCR-VL subplan now explicitly satisfies `003_rules` contract sections, parallel dependency boundaries, and merge touchpoint clarity.
- 2026-04-25 14:30 UTC: `003_2` now includes concrete cross-plan execution and merge compatibility guidance for the currently existing `003_n` plans.
- 2026-04-25 15:05 UTC: `003_2` execution now includes runnable Phase 3 scaffolding and tests that validate deterministic run outputs under the canonical `runs/<document_id>/<backend_id>/document.docir.json` contract.
- 2026-04-25 16:10 UTC: Sandbox install procedure is defined and attempted, but backend package installation remains pending external network/proxy access for Phase 4 online dependency checks.
- 2026-04-25 16:22 UTC: Two-path retry (with and without proxy) confirms no reachable package index from this environment, so PaddleOCR-VL install verification must be finalized in an environment with package egress.
