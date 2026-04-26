# pdf2md Architecture

**Version**: 1.0  
**Last Updated**: April 26, 2026

## 1. Overview

pdf2md is a lightweight, extensible Python package that provides a unified interface to **benchmark different tools to analyse documents**.

**Core Goals** (from original vision):
- Support different benchmarks such as OmniDocBench
- Support different backends such as MinerU and PaddleOCR-VL
- Provide a CLI (`doc2pdf --backend <name>`) to process a single PDF into a single `.md` file
- Have an **Intermediate Representation (IR)** in the middle
- Support JSON output for variable conversion and benchmarking
- Have a second CLI (`run_benchmark`) that reads a benchmark config file to decide which benchmark and which backends/models to run
- Keep the main installation light — backends must not burden the core
- Ship with a core `.env` example
- Provide a clear installation procedure for each environment
- Make the system scalable so new environments and backends can be added easily
- The connection between each backend and the IR happens **inside** that backend’s own environment (logic is separated)

## 2. High-Level Data Flow

```
PDF Input
    │
    ▼
doc2pdf --backend mineru input.pdf --output result.md
    │
    ▼
Backend (runs in its own local virtual environment)
    │
    ▼
DocumentIR (standardized Pydantic model)
    │
    ├───► Markdown (.md)
    ├───► JSON (.json)          ← for variable conversion and benchmarking
    └───► run_benchmark CLI
```

## 3. Main Components

### 3.1 Core Package (Light)
- Only contains: CLI, IR models, converters (IR → MD/JSON), backend registry, and reporting system
- Never imports heavy ML libraries (torch, paddle, etc.)

### 3.2 Backends (Isolated Environments)
Each backend is treated as a separate pipeline of the application.

- Runs in its own local virtual environment (venv)
- Inside that environment lives:
  - The actual parser
  - Brief install instructions (`README.md`)
  - `requirements.txt`
  - The code that converts the backend’s native output into the standard `DocumentIR`

### 3.3 Benchmarks
- Driven by a YAML config file
- `run_benchmark` reads the config to know which benchmark (e.g. OmniDoc) and which backends to test
- Produces comparative scores and reports

### 3.4 Intermediate Representation (IR)
- The central contract of the system
- All backends must output the same `DocumentIR` structure
- Enables fair benchmarking and easy conversion to Markdown or JSON

## 4. Installation Strategy (Local Virtual Environments)

**Core installation** (remains light):
```bash
pip install pdf2md
```

**Each backend** (example for MinerU):
```bash
python -m venv envs/mineru
source envs/mineru/bin/activate
pip install -r envs/mineru/requirements.txt
```

The same pattern is used for PaddleOCR-VL and any future backend.

## 5. Agent Development Process (4 Phases)

The project is built following a strict agentic workflow:

- **Phase 0**: Understand target architecture + human approval
- **Phase 1**: Review existing `old_code/` (especially the IR) and produce a formal review report
- **Phase 2**: Build interconnection, logging systems, error catching, and verification logic
- **Phase 3**: Define installation logic for each backend — create local `README.md` + `requirements.txt` in each environment, make every environment fully standalone and functional. Can run in parallel with different agents per backend.
- **Phase 4**: Full integration, review, testing, correction, and consolidation of the interface between backends and main code. User validates with real PDFs.

All agents must follow the rules in `docs/AGENTS.md` and update `CURRENT_PLAN.md` after every task. A reporting system (`report.success` / `report.issues`) is used throughout.

## 6. Key Design Decisions

- **Light core** — main package stays small and fast to install
- **Isolated local environments** — each backend has its own venv with parser + install instructions
- **IR as single source of truth** — everything goes through the Intermediate Representation
- **Config-driven benchmarking** — `run_benchmark` uses a YAML file
- **Scalable** — new backends and environments can be added without touching the core
- **Logic separation** — the connection between backend and IR happens inside each backend’s environment

## 7. Non-Goals (v1)

- Docker (not needed — project is small)
- GUI
- Cloud deployment
- Training new models
- Support for non-PDF formats (future)
```

---

**File created successfully.**

You can now download it from:

**`/home/workdir/artifacts/pdf2md/docs/architecture.md`**

Would you like me to also create the other key files (`AGENTS.md`, `CURRENT_PLAN.md`, `PHASE_0_UNDERSTAND_TARGET.md`, etc.) so you have the complete obedience framework ready? Just say **"Yes, create the full framework"**.
