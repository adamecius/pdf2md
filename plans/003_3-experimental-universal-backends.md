# Define an experimental universal backend environment

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

Some users will still want a single environment containing multiple optional backends. This plan defines that path as experimental, best-effort, and non-blocking for project stability.

## Scope

In scope:
- Define a best-effort universal installation profile.
- Document known conflict classes and fallback behavior.
- Define minimal smoke validation for universal setup.

Out of scope:
- Guaranteeing universal compatibility across all backends.
- Making universal setup required for contributors.

## Current known state

- Optional backends are designed to be independently installable.
- Dependency conflicts are likely when combining multiple heavy backend stacks.

## Target behavior

1. Users can attempt one universal environment with clear caveats.
2. Failure modes are documented with rollback steps.
3. Core deterministic functionality remains unaffected.

## Design and decisions

- Universal mode remains opt-in and experimental.
- Backend failures in universal mode must not prevent deterministic execution.
- Document pinned-version sets as examples, not guarantees.

## Milestones

### Milestone 1 - Universal profile documentation

Files:
- `docs/experimental-universal-backends.md`

Work:
Document setup strategy, conflict expectations, and rollback workflow.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
Core CLI behavior is unchanged.

### Milestone 2 - Universal smoke check

Files:
- `tests/test_universal_backend_import_guards.py`

Work:
Add a guard test that verifies optional backends fail gracefully and deterministic path still imports.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_universal_backend_import_guards.py

Expected result:
Import guards protect baseline behavior under partial optional dependency availability.

## Validation

    cd /workspace/pdf2md
    python -m doc2md --help

## Risks and rollback notes

- Risk: users interpret universal profile as fully supported. Mitigation: label experimental prominently.
- Risk: version drift quickly invalidates universal recipes. Mitigation: timestamp version examples and keep them optional.
- Rollback: remove universal docs/tests without affecting backend-specific tracks.

## Progress

- [ ] Not started

## Surprises & Discoveries

- None yet.

## Decision Log

- None yet.

## Outcomes & Retrospective

- To be filled during execution and at completion.
