# PHASE 3 — Installation Logic & Standalone Environments

**Status**: Pending
**Goal**: For every backend, create a fully functional local virtual environment with parser, install instructions, and requirements. Make each environment standalone.

**Report Location**: None (this phase produces environments + docs)

## Tasks (can run in parallel)

### Task 3.1 — MinerU Environment
- [ ] Create `envs/mineru/` folder
- [ ] Write `README.md` with clear install steps
- [ ] Create `requirements.txt` for MinerU + IR adapter
- [ ] Implement `convert_to_ir()` inside the environment
- [ ] Make environment fully standalone and testable

### Task 3.2 — PaddleOCR-VL Environment
- [ ] Create `envs/paddleocr_vl/` folder
- [ ] Write `README.md` with clear install steps
- [ ] Create `requirements.txt`
- [ ] Implement `convert_to_ir()` inside the environment
- [ ] Make environment fully standalone and testable

### Task 3.3 — Future Backends Template
- [ ] Create a template folder `envs/new_backend_template/`
- [ ] Document the exact structure every new backend must follow

**Rules for this phase**:
- Each environment must work completely independently
- If the original backend has tests, adapt 1-2 key tests here
- After finishing all environments: Update CURRENT_PLAN.md