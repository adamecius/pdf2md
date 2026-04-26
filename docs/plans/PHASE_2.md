# PHASE 2 — Interconnection & Verification Logic

**Status**: Pending
**Goal**: Build the core interconnection layer, logging, error handling, and verification systems so that later phases can run reliably.

**Report Location**: None (this phase is foundational)

## Tasks

### Task 2.1 — Backend Registry
- [ ] Implement `backends/registry.py` with dynamic loading (entry points + fallback)
- [ ] Support loading backends by name (`get_backend("mineru")`)

### Task 2.2 — Logging & Error Handling
- [ ] Create `utils/logging.py` with structured logging (rich + context)
- [ ] Create centralized error catching that always logs to Reporter

### Task 2.3 — Verification Layer
- [ ] Add validation that every backend returns valid `DocumentIR`
- [ ] Add health_check() calls before running any backend

### Task 2.4 — CLI Wiring
- [ ] Connect `doc2pdf` CLI to registry + converter
- [ ] Connect `run_benchmark` CLI to config loader + reporting

**Rules for this phase**:
- No new features or business logic
- Focus only on making the system robust and observable
- After finishing: Update CURRENT_PLAN.md and commit