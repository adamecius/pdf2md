# PHASE 4 — Integration, Testing & User Validation

**Status**: Pending
**Goal**: Wire everything together, run full end-to-end tests, and let the user validate with real PDFs.

**Report Location**: `docs/reports/PHASE_4_INTEGRATION_REPORT.md`

## Tasks

### Task 4.1 — Full Wiring
- [ ] Connect all backends to the main CLI via registry
- [ ] Make sure `doc2pdf --backend X` works for every backend
- [ ] Make sure `run_benchmark` can use any backend from config

### Task 4.2 — End-to-End Testing
- [ ] Create integration tests that run real PDFs through each backend
- [ ] Verify IR is produced correctly
- [ ] Verify Markdown and JSON output is generated

### Task 4.3 — User Validation
- [ ] Prepare 5 diverse test PDFs (academic, scanned, table-heavy, formula-heavy, handwritten)
- [ ] Run full benchmark on them
- [ ] Let user review outputs and give feedback

### Task 4.4 — Final Polish
- [ ] Fix any issues found during user validation
- [ ] Update documentation
- [ ] Create final release checklist

**Rules for this phase**:
- All previous phases must be 100% complete
- User must approve the final outputs before marking Phase 4 as done
- After finishing: Update CURRENT_PLAN.md and commit