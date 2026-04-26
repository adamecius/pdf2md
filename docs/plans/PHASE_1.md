# PHASE 1 — Review Old Codebase

**Status**: Complete ✅ (April 26, 2026)

**Goal**: Review `old_code/` and extract the reusable architecture/IR decisions before implementation phases.

## Tasks

### Task 1.1 — Inventory Legacy Structure
- [x] Review `old_code/` package layout, CLI flow, backend adapters, and exporters.
- [x] Identify which subsystems already align with target architecture.

### Task 1.2 — IR Deep Dive
- [x] Analyze `old_code/doc2md/ir/*` schema, ID strategy, normalization, and serialization.
- [x] Compare IR contract against tests and downstream exporters.
- [x] Document concrete strengths, mismatches, and migration risks in the Phase 1 report.

### Task 1.3 — Formal Review Report
- [x] Write `docs/reports/PHASE_1_CODE_REVIEW.md` with findings and recommendations.

**Acceptance**: Report produced and `CURRENT_PLAN.md` updated to reflect completion.
