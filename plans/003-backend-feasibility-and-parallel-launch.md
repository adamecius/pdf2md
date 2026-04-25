# Evaluate MinerU and PaddleOCR-VL backend tracks for parallel launch

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

The repository now supports a deterministic-first baseline with optional backend stubs, but the next planning question is operational: can MinerU and PaddleOCR-VL be introduced in parallel without destabilizing the default offline path? The team also wants a realistic "experimental universal" path that can combine backends despite dependency conflicts.

This plan provides a second-pass feasibility analysis with explicit go/no-go criteria, sequencing, and integration guardrails.

## Scope

In scope:
- Evaluate backend-track feasibility for MinerU and PaddleOCR-VL under current architecture constraints.
- Define parallel-launch requirements for plan names in the `00X_n` format.
- Define environment isolation strategy and compatibility expectations.
- Define the minimum integration contract for registry, CLI, and test boundaries.
- Define acceptance criteria for an optional experimental universal setup.

Out of scope:
- Implementing MinerU or PaddleOCR-VL adapters in this plan.
- Adding new runtime ML dependencies to the deterministic path.
- Building benchmark dashboards or full quality leaderboards.

## Current known state

- Deterministic processing remains the always-available path and must remain dependency-light.
- Optional backend stubs already exist for MinerU and PaddleOCR-VL.
- The architecture already separates profiler/router/strategy work from backend implementation details.
- The repository has not yet added concrete `00X_n` implementation plans for MinerU and PaddleOCR-VL.

## Target behavior

After this plan is applied:

1. Parallel backend plans can be created and launched as `00X_n` tracks with low merge risk.
2. Backend-specific environments are the default recommendation for heavy backends.
3. The deterministic baseline remains unaffected when optional dependencies are missing.
4. The universal setup is explicitly marked experimental and validated by a small smoke test only.
5. The team has objective readiness criteria before implementation starts.

## Design and decisions

Feasibility summary:
- MinerU and PaddleOCR-VL are feasible as parallel tracks if their dependencies and tests are isolated.
- A single universal environment is technically possible but should be treated as best-effort due to likely dependency conflicts.
- The deterministic lane should never import or initialize optional backend dependencies during normal startup.

Parallel plan naming and ownership:
- Use one parent wave number and independent child tracks:
  - `003_1-mineru-backend.md`
  - `003_2-paddleocr-vl-backend.md`
- Each child track must declare a single owner, file ownership boundaries, and explicit registry/CLI integration checkpoints.

Environment strategy:
- Preferred: one environment per heavy backend plus one core deterministic environment.
- Optional: one experimental universal environment documented as unstable.
- Each backend plan must provide a reproducible install block and an explicit rollback path.

Integration contract:
- Backend adapters only implement the backend base contract and return DocIR-compatible output.
- Registry wiring is explicit and opt-in by backend name.
- CLI behavior must remain deterministic by default and must provide clear error messages for missing optional dependencies.

Test strategy:
- Each `00X_n` plan runs its own focused tests and fixture smoke checks.
- Shared integration checks run only at integration checkpoints, not on every backend-track commit.
- Default `pytest -q` remains offline and should not require backend model packages.

## Milestones

### Milestone 1 - Feasibility gate definition

Files:
- `plans/003-backend-feasibility-and-parallel-launch.md`

Work:
Define objective feasibility gates for parallel launch and universal experimental mode.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Baseline CLI behavior remains unchanged while planning guidance is clarified.

### Milestone 2 - Parallel-track implementation plan scaffolding

Files:
- `plans/003_1-mineru-backend.md`
- `plans/003_2-paddleocr-vl-backend.md`

Work:
Create independent implementation plans that satisfy the `00X_n` constraints from this feasibility analysis.

Validation:

    cd /workspace/pdf2md
    test -f plans/003_1-mineru-backend.md && test -f plans/003_2-paddleocr-vl-backend.md && echo OK

Expected result:
Both plans exist and are ready for parallel execution.

### Milestone 3 - Experimental universal plan scaffolding

Files:
- `plans/003_3-experimental-universal-backends.md`

Work:
Document a best-effort universal environment strategy with explicit failure expectations and rollback guidance.

Validation:

    cd /workspace/pdf2md
    test -f plans/003_3-experimental-universal-backends.md && echo OK

Expected result:
Universal strategy is explicit, constrained, and clearly marked experimental.

## Validation

Repository root validation commands for this plan:

    cd /workspace/pdf2md
    python -m doc2md --help

Success signals:
- Planning artifacts are present and consistent.
- Baseline CLI help remains operational.

## Risks and rollback notes

- Risk: backend-track plans drift and modify shared files concurrently. Mitigation: require integration checkpoints and ownership declarations in each `00X_n` plan.
- Risk: universal environment instability creates confusion. Mitigation: mark universal as experimental and non-blocking.
- Risk: optional dependency imports leak into default flow. Mitigation: lazy imports only and explicit runtime error messaging.
- Rollback: all changes are documentation-only and can be reverted safely without runtime impact.

## Progress

- [x] 2026-04-25: Completed second-pass feasibility analysis and documented objective launch criteria.
- [x] 2026-04-25: Drafted `003_1` and `003_2` backend implementation plans.
- [x] 2026-04-25: Drafted `003_3` experimental universal backend plan.

## Surprises & Discoveries

- 2026-04-25: Existing repository plans did not yet include concrete MinerU/PaddleOCR-VL `00X_n` files despite stub modules being present.

## Decision Log

- 2026-04-25: Approved separate-environment-first strategy for heavy backends.
- 2026-04-25: Marked universal mixed-backend setup as experimental and non-blocking.
- 2026-04-25: Required integration checkpoints for all parallel backend plans.

## Outcomes & Retrospective

- 2026-04-25: The repository now has a concrete feasibility baseline for parallel backend planning, with clear launch constraints and risk controls.
