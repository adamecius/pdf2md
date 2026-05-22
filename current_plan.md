# Plan 7 - Local environment and toolchain preflight

Status: ready to implement after Plan 6  
Repo: `pdf2md`  
Owner: local acceptance layer  
Sequence: plan 7 of 12. It starts the post-Plan-6 local ground-truth acceptance programme.

Applies forward: the repository working protocol and environment rules in sections 0.1 and 0.2 apply to Plan 7 and all subsequent local acceptance plans, namely Plans 8 to 12.

---

## 0.1 Repository working protocol for the agent

Before implementing Plan 7, and before implementing any subsequent local acceptance plan, the agent must start from a clean, updated repository state.

Required sequence:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-7-local-preflight
```

For subsequent plans, use the corresponding branch name:

```text
plan-8-groundtruth-validation
plan-9-backend-execution-smoke
plan-10-connector-normalisation-real-output
plan-11-staged-pipeline-chain
plan-12-full-local-e2e
```

Rules:

```text
- Do not work directly on main.
- Do not start implementation before fetching and pulling the latest main.
- If git status is not clean before creating the branch, stop and report the uncommitted files.
- The branch must be created after main is updated.
- The final report must include the branch name, changed files, pytest commands run, local preflight command run, and whitelist confirmation.
```

This is a local acceptance programme, but the implementation artefacts are still repository changes and must follow the same branch discipline as the previous plans.

---

## 0.2 Conda environment protocol

The main repository environment is:

```text
pdf2md
```

All repository-level Python commands, unit tests, local preflight checks, and pipeline CLIs must run from this environment unless explicitly stated otherwise.

Required activation pattern:

```bash
conda activate pdf2md
```

or, in non-interactive scripts:

```bash
conda run -n pdf2md python <command>
```

Repository-level commands include:

```text
pytest
python tools/local_groundtruth_preflight.py
python tools/calibrate_priors.py
python tools/build_consensus.py
python tools/build_linked_structure.py
python tools/export_linked_docling.py
```

Backend work must happen in the backend's respective expected environment. Do not run backend OCR/model scripts inside the main `pdf2md` environment unless that backend is explicitly designed to do so.

Expected backend environments:

```text
mineru      -> pdf2md-mineru
paddleocr   -> pdf2md-paddleocr
deepseek    -> pdf2md-deepseek
glm         -> pdf2md-glm
```

Backend connector scripts remain lightweight and may be checked from the main `pdf2md` environment. Backend OCR/model execution belongs to the backend-specific environment.

Examples:

```bash
conda run -n pdf2md python backend/mineru/connector.py --help
conda run -n pdf2md-mineru python backend/mineru/<backend_runtime_script>.py --help

conda run -n pdf2md python backend/paddleocr/connector.py --help
conda run -n pdf2md-paddleocr python backend/paddleocr/<backend_runtime_script>.py --help
```

For Plan 7 specifically, do not execute backend OCR/model scripts. Only verify that the expected backend environments exist and that lightweight connector CLIs start from the main `pdf2md` environment.

For Plans 9 to 12, backend runtime scripts must be executed in their respective backend environments.

---

## 0. Purpose

Plan 7 does **not** run the full OCR pipeline.

Plan 7 verifies that the local machine has the expected tools, Python package surface, backend environments, backend adapter scripts, and output permissions required for the later local ground-truth acceptance plans.

It answers this question:

```text
Does this local environment correspond to the environment required by the pipeline we designed?
```

It must not pretend that missing local tools are unit-test failures. Missing `lualatex`, `latexml`, conda environments, or backend runtimes should be reported as **environment-not-ready**, not as repository test failures.

---

## 1. Long-term context

The achieved pipeline is now:

```text
backend raw output
  -> connector
  -> PageExtractionIR + EntityProposalDocument
  -> calibration priors
  -> ConsensusIR
  -> LinkedStructure
  -> Docling JSON + RAG chunks + markdown preview
```

The next local acceptance sequence should be:

```text
Plan 7  - Environment and toolchain preflight
Plan 8  - Ground-truth corpus generation and validation
Plan 9  - Real backend execution smoke
Plan 10 - Backend output normalisation through connectors
Plan 11 - Staged pipeline chain validation
Plan 12 - Full local end-to-end corpus validation
```

Plan 7 only checks whether the machine is ready for Plans 8 to 12.

---

## 2. Scope

Plan 7 checks:

```text
Python runtime
pdf2md importability
pytest availability
core project CLIs
LaTeX tools
LuaTeX tools
LaTeXML tools
shell availability
conda or mamba availability
backend environment names
backend connector CLIs
backend adapter script presence
write permissions for local run directories
optional docling-core availability
```

Plan 7 does **not** check OCR quality, ground-truth correctness, connector output quality, consensus quality, semantic linking quality, Docling quality, or RAG quality.

---

## 3. Hard constraints

```text
- No new mandatory runtime dependencies.
- No OCR execution.
- No backend model execution.
- No LaTeX compilation.
- No LaTeXML conversion.
- No full pipeline run.
- No changes to Plans 1 to 6 contracts.
- No changes to backend wrappers.
- No changes to existing pipeline CLIs.
- No changes to README.
- Do not treat missing local tools as unit-test failures.
- Do not create unit tests for missing local executables.
- Create unit tests only for generic repository defects found while implementing the preflight tool.
```

---

## 4. File whitelist

The reviewer rejects the plan if files outside this whitelist are modified.

```text
src/pdf2md/local/__init__.py
src/pdf2md/local/preflight.py

tools/local_groundtruth_preflight.py

tests/test_local_preflight.py

tests/data/local_preflight_fixtures/expected_environment.min.json
tests/data/local_preflight_fixtures/expected_environment.full.json
```

Optional, only if the project already uses `models/__init__.py` re-exports for every local model:

```text
src/pdf2md/models/__init__.py
```

Explicit non-whitelist files:

```text
README.md
README_latex_docling_groundtruth.md
pyproject.toml
current_plan.md

src/pdf2md/models/ir.py
src/pdf2md/models/entities.py
src/pdf2md/models/priors.py
src/pdf2md/models/linked.py
src/pdf2md/models/export.py

src/pdf2md/connectors/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

src/pdf2md/backends/runner.py
src/pdf2md/cli/main.py
src/pdf2md/pipeline/convert.py

backend/*/connector.py
backend/*/pdf2md_*.py
backend/*/pdf2ir_*.py

tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py
```

Rationale:

Plan 7 is an environment detector. It must not patch the pipeline. If it finds a pipeline signature bug, it should create a targeted unit test in the responsible layer, not silently alter previous contracts here.

---

## 5. Expected environment contract

Plan 7 introduces a local expectation profile.

Main repository conda environment:

```text
pdf2md
```

Default expected tools inside the `pdf2md` environment:

```text
python
pytest
latex
lualatex
latexml
```

Expected project CLIs:

```text
conda run -n pdf2md python tools/calibrate_priors.py --help
conda run -n pdf2md python tools/build_consensus.py --help
conda run -n pdf2md python tools/build_linked_structure.py --help
conda run -n pdf2md python tools/export_linked_docling.py --help
```

Expected backend connector CLIs:

```text
conda run -n pdf2md python backend/mineru/connector.py --help
conda run -n pdf2md python backend/paddleocr/connector.py --help
conda run -n pdf2md python backend/deepseek/connector.py --help
conda run -n pdf2md python backend/glm/connector.py --help
```

Expected backend environments:

```text
pdf2md-mineru
pdf2md-paddleocr
pdf2md-deepseek
pdf2md-glm
```

`glm` may be marked optional if the local setup has not yet standardised that backend. The preflight tool must support optional backend environments.

Expected adapter script presence:

```text
backend/mineru/
backend/paddleocr/
backend/deepseek/
backend/glm/

backend/*/connector.py
```

Expected output roots are writable:

```text
groundtruth/runs/local_preflight
groundtruth/runs/local_e2e
```

Optional tool:

```text
docling-core
```

`docling-core` is optional because Plan 6 deliberately does not make it a mandatory dependency.

---

## 6. New module

File:

```text
src/pdf2md/local/preflight.py
```

This module must contain pure detection logic and data models.

### 6.1 Public dataclasses or Pydantic models

Either dataclasses or Pydantic models are acceptable. Since this is a local report contract, Pydantic is preferred.

```python
class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
```

```python
class CheckSeverity(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
```

```python
class PreflightCheck(BaseModel):
    id: str
    label: str
    status: CheckStatus
    severity: CheckSeverity
    command: list[str] | None
    returncode: int | None
    stdout_snippet: str | None
    stderr_snippet: str | None
    message: str
    metadata: dict[str, Any]
```

```python
class PreflightReport(BaseModel):
    schema_name: Literal["pdf2md.LocalPreflightReport"]
    schema_version: Literal["1.0.0"]
    environment_ready: bool
    required_passed: int
    required_failed: int
    optional_passed: int
    optional_failed: int
    checks: list[PreflightCheck]
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- check ids are unique.
- required_failed == count of required checks with status fail.
- optional_failed == count of optional checks with status fail.
- environment_ready is true only when required_failed == 0.
```

---

## 7. Public API

```python
@dataclass(frozen=True)
class PreflightSettings:
    required_backends: tuple[str, ...] = ("mineru", "paddleocr", "deepseek")
    optional_backends: tuple[str, ...] = ("glm",)
    backend_env_prefix: str = "pdf2md-"
    output_roots: tuple[Path, ...] = (
        Path("groundtruth/runs/local_preflight"),
        Path("groundtruth/runs/local_e2e"),
    )
    timeout_seconds: int = 20
```

```python
def check_command_exists(command: str) -> PreflightCheck:
    ...
```

```python
def run_help_check(
    *,
    check_id: str,
    label: str,
    command: list[str],
    severity: CheckSeverity,
    timeout_seconds: int,
) -> PreflightCheck:
    ...
```

```python
def check_python_import(
    *,
    module: str,
    severity: CheckSeverity,
) -> PreflightCheck:
    ...
```

```python
def check_conda_environment(
    *,
    env_name: str,
    severity: CheckSeverity,
    timeout_seconds: int,
) -> PreflightCheck:
    ...
```

```python
def check_path_exists(
    *,
    path: Path,
    severity: CheckSeverity,
) -> PreflightCheck:
    ...
```

```python
def check_writable_directory(
    *,
    path: Path,
    severity: CheckSeverity,
) -> PreflightCheck:
    ...
```

```python
def build_preflight_report(
    *,
    settings: PreflightSettings,
    repo_root: Path,
) -> PreflightReport:
    ...
```

```python
def write_preflight_report(
    *,
    report: PreflightReport,
    out_dir: Path,
) -> Path:
    ...
```

---

## 8. Required checks

### 8.1 Python and package checks

Required inside the `pdf2md` conda environment:

```text
python executable works
pdf2md imports
pydantic imports
typer imports
pytest imports
```

Commands:

```bash
conda run -n pdf2md python -c "import pdf2md; print('pdf2md ok')"
conda run -n pdf2md python -c "import pydantic; print('pydantic ok')"
conda run -n pdf2md python -c "import typer; print('typer ok')"
conda run -n pdf2md python -c "import pytest; print('pytest ok')"
```

### 8.2 Pipeline CLI checks

Required:

```bash
conda run -n pdf2md python tools/calibrate_priors.py --help
conda run -n pdf2md python tools/build_consensus.py --help
conda run -n pdf2md python tools/build_linked_structure.py --help
conda run -n pdf2md python tools/export_linked_docling.py --help
```

These are signature checks. If one fails due to broken argument parsing or import errors, that is a repository defect.

### 8.3 LaTeX and LaTeXML checks

Required:

```bash
latex --version
lualatex --version
latexml --version
```

Optional:

```bash
latexmk --version
kpsewhich --version
```

Missing required LaTeX tools means environment-not-ready, not a unit-test failure.

### 8.4 Backend connector checks

Required backend connector help:

```bash
python backend/mineru/connector.py --help
python backend/paddleocr/connector.py --help
python backend/deepseek/connector.py --help
```

Optional:

```bash
python backend/glm/connector.py --help
```

These checks should use the current Python environment because connector files are meant to be lightweight and must not import OCR libraries.

### 8.5 Backend environment checks

Required:

```text
pdf2md-mineru
pdf2md-paddleocr
pdf2md-deepseek
```

Optional:

```text
pdf2md-glm
```

Detection should support both:

```bash
conda env list
```

and:

```bash
mamba env list
```

If neither `conda` nor `mamba` exists, report:

```text
conda_or_mamba_missing
```

as a required failure if backend environment checks are required.

Do not run backend OCR here. This is only an environment discovery step.

### 8.6 Backend adapter path checks

Required:

```text
backend/mineru/connector.py
backend/paddleocr/connector.py
backend/deepseek/connector.py
```

Optional:

```text
backend/glm/connector.py
```

For Plan 7, do not require `pdf2ir_*.py` if the current backend layer no longer depends on that exact filename. The requirement is: each backend must have a connector and a runnable backend environment. Plan 9 will test the actual backend execution command.

### 8.7 Output directory checks

Required writable directories:

```text
groundtruth/runs/local_preflight
groundtruth/runs/local_e2e
```

The preflight tool may create them if missing.

Check by writing and deleting a small `.write_test` file from the main `pdf2md` environment.

---

## 9. CLI tool

File:

```text
tools/local_groundtruth_preflight.py
```

Required CLI:

```bash
conda run -n pdf2md python tools/local_groundtruth_preflight.py \
  --repo-root . \
  --out-dir groundtruth/runs/local_preflight \
  --required-backends mineru,paddleocr,deepseek \
  --optional-backends glm \
  --verbose
```

Required options:

```text
--repo-root PATH
--out-dir PATH
--required-backends LIST       comma-separated, default mineru,paddleocr,deepseek
--optional-backends LIST       comma-separated, default glm
--backend-env-prefix TEXT      default pdf2md-
--timeout-seconds INT          default 20
--strict                       exit 1 if any required check fails
--verbose
```

Exit codes:

```text
0 = preflight report written.
1 = invalid CLI arguments or strict mode with required failures.
```

Important:

Without `--strict`, the command writes a report and exits `0` even if the environment is not ready. This allows the agent to inspect and report missing local conditions.

With `--strict`, it exits `1` when `environment_ready == false`.

Output:

```text
<out-dir>/preflight_report.json
<out-dir>/preflight_summary.txt
```

---

## 10. Report semantics

The report must distinguish:

```text
repository_defect
environment_missing
optional_missing
path_missing
permission_error
command_timeout
command_failed
```

Use `metadata.failure_class` for this.

Examples:

```json
{
  "id": "latex.lualatex.version",
  "label": "LuaLaTeX executable",
  "status": "fail",
  "severity": "required",
  "command": ["lualatex", "--version"],
  "returncode": null,
  "stdout_snippet": null,
  "stderr_snippet": "No such file or directory",
  "message": "lualatex is not available on PATH",
  "metadata": {
    "failure_class": "environment_missing"
  }
}
```

```json
{
  "id": "cli.export_linked_docling.help",
  "label": "Plan 6 export CLI help",
  "status": "fail",
  "severity": "required",
  "command": ["python", "tools/export_linked_docling.py", "--help"],
  "returncode": 1,
  "stdout_snippet": "",
  "stderr_snippet": "ImportError ...",
  "message": "Plan 6 export CLI did not start",
  "metadata": {
    "failure_class": "repository_defect"
  }
}
```

---

## 11. Tests as milestones

These are normal unit tests for the **preflight tool logic only**. They must not require LaTeX, conda, mamba, or backend environments to exist.

File:

```text
tests/test_local_preflight.py
```

Expected count: about 24 tests.

Must cover:

```text
CheckStatus enum values
CheckSeverity enum values
PreflightCheck minimal construction
PreflightReport rejects duplicate check ids
PreflightReport computes or validates required_failed
PreflightReport environment_ready false when required failures exist
command-exists check passes with mocked executable
command-exists check fails with mocked missing executable
run_help_check passes when subprocess returns 0
run_help_check fails when subprocess returns non-zero
run_help_check records timeout
python import check passes with mocked import
python import check fails with mocked import error
path_exists check passes
path_exists check fails
writable directory check creates directory
writable directory check reports permission failure
conda env parser detects expected env
mamba env parser detects expected env
missing conda and mamba reports required failure
build_preflight_report includes pipeline CLI checks
build_preflight_report includes latex checks
build_preflight_report includes backend env checks
write_preflight_report writes JSON and summary
CLI --help exits zero
CLI writes report using mocked check functions
```

No test should call real `latex`, `lualatex`, `latexml`, `conda`, `mamba`, or backend runtimes.

---

## 12. Local acceptance command

After implementation, the user or agent runs locally:

```bash
conda run -n pdf2md python tools/local_groundtruth_preflight.py \
  --repo-root . \
  --out-dir groundtruth/runs/local_preflight \
  --required-backends mineru,paddleocr,deepseek \
  --optional-backends glm \
  --verbose
```

Then inspect:

```bash
cat groundtruth/runs/local_preflight/preflight_summary.txt
```

Strict mode:

```bash
conda run -n pdf2md python tools/local_groundtruth_preflight.py \
  --repo-root . \
  --out-dir groundtruth/runs/local_preflight \
  --required-backends mineru,paddleocr,deepseek \
  --optional-backends glm \
  --strict \
  --verbose
```

---

## 13. Acceptance criteria

Plan 7 is accepted when:

### 13.1 Branch and environment protocol is followed

The implementation must start from an updated `main` branch and continue on a dedicated feature branch:

```bash
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-7-local-preflight
```

All repository-level commands must be run from the `pdf2md` conda environment.

### 13.2 Unit tests pass

```bash
conda run -n pdf2md pytest tests/test_local_preflight.py -q
```

No skip. No xfail.

### 13.3 Plans 1 to 6 still pass

At minimum:

```bash
pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
pytest tests/test_connector_common.py -q
pytest tests/test_backend_connectors.py -q
pytest tests/test_prior_contracts.py -q
pytest tests/test_calibration_matching.py -q
pytest tests/test_calibration_metrics.py -q
pytest tests/test_calibrate_priors_cli.py -q
pytest tests/test_consensus_grouping.py -q
pytest tests/test_consensus_scoring.py -q
pytest tests/test_consensus_factory.py -q
pytest tests/test_build_consensus_cli.py -q
pytest tests/test_linked_structure_contracts.py -q
pytest tests/test_linking_extract.py -q
pytest tests/test_linking_resolvers.py -q
pytest tests/test_linked_structure_builder.py -q
pytest tests/test_build_linked_structure_cli.py -q
pytest tests/test_export_contracts.py -q
pytest tests/test_docling_export.py -q
pytest tests/test_rag_export.py -q
pytest tests/test_markdown_export.py -q
pytest tests/test_export_io_cli.py -q
```

### 13.4 Whole suite has no regression

```bash
conda run -n pdf2md pytest tests/ -q
```

### 13.5 Whitelist check

```bash
git diff --name-only main..HEAD
```

Must be a subset of the Plan 7 whitelist.

### 13.6 Local preflight report is produced

Non-strict mode must write:

```text
groundtruth/runs/local_preflight/preflight_report.json
groundtruth/runs/local_preflight/preflight_summary.txt
```

even when the environment is not ready.

### 13.7 Strict mode behaves correctly

If the local environment is fully ready:

```text
--strict exits 0
```

If required tools are missing:

```text
--strict exits 1
```

---

## 14. Failure policy

Plan 7 failures are classified as follows.

### 14.1 Environment missing

Examples:

```text
lualatex missing
latexml missing
conda missing
pdf2md-mineru env missing
backend runtime not installed
```

Action:

```text
Report environment-not-ready.
Do not create a unit test.
Do not patch repository code.
```

### 14.2 Repository defect

Examples:

```text
tools/export_linked_docling.py --help fails because of ImportError
tools/build_consensus.py --help has broken signature
connector.py imports OCR-heavy modules and crashes on --help
preflight report cannot serialise
```

Action:

```text
Create or update a targeted unit test.
Fix in the responsible layer.
Rerun Plan 7 and the affected plan tests.
```

### 14.3 Optional missing

Examples:

```text
glm env missing when glm is optional
docling-core missing
latexmk missing
```

Action:

```text
Report warning.
Do not block environment_ready.
Do not create a unit test.
```

---

## 15. What Plan 7 must not accidentally become

Bad:

```text
Run LaTeX compilation.
Run LaTeXML conversion.
Run real backend OCR.
Run connectors on real backend output.
Run calibration.
Run consensus.
Run linking.
Run export.
Evaluate OCR exactitude.
Tune parameters.
Modify README.
```

Good:

```text
Check local executables exist.
Check project CLIs start.
Check lightweight connector CLIs start.
Check expected backend environments are visible.
Check output directories are writable.
Produce a clear preflight report.
```

---

## 16. Reviewer checklist

The reviewer should ask:

```text
1. Does the plan use the conversation pipeline as source of truth, not README?
2. Does it avoid running OCR or LaTeX?
3. Does it separate environment-not-ready from repository defects?
4. Does it produce a machine-readable report?
5. Does it produce a human-readable summary?
6. Does non-strict mode always write a report?
7. Does strict mode fail when required checks fail?
8. Are unit tests mocked and independent of the local machine?
9. Are Plans 1 to 6 untouched?
10. Is git diff contained inside the whitelist?
```

---

## 17. Transition to Plan 8

Plan 8 starts only when Plan 7 reports either:

```text
environment_ready = true
```

or the user explicitly decides to proceed despite known missing optional components.

Plan 8 will then validate the actual LaTeX/LuaTeX/LaTeXML ground-truth corpus generation and validation path.

---

## Status

Plan 7 declares no enumerated task IDs; its work units are the section 13
acceptance criteria. No task can be promoted to `done`: there are no task IDs
to promote, and PR_review #5 below returns `fail` on process grounds. No prior
`done` state exists, so nothing is demoted.

- implementation: present — commit `4b616302` ("implemented the plan 7")
- acceptance substance: verified green (see PR_review #5)
- tasks_promoted: none
- plan state: blocked on bookkeeping — see PR_review #5

## PR_review #5

Reviewed object: the Plan 7 implementation in commit `4b616302`. Numbered #5 as
the next integer after run_log.md PR #4. No `## PR #5` entry exists in
run_log.md — that absence is the central finding.

- verdict: fail
- whitelist_violations: none — `4b616302` touched exactly the six Plan 7
  whitelist files and nothing else.
- test_contract_violations: none — all `tests/test_local_preflight.py` tests
  executed and passed; no skips, no mis-tags.
- dependency_violations: none — `pyproject.toml` untouched; no packages or
  environment-modifying external tools installed.
- tasks_promoted: []
- notes:
  - Fail cause is process, not code: required check #2 fails — the Plan 7 work
    has no run_log.md evidence entry. run_log.md still holds PR #1–#4 (Plan 5
    linking, Plan 6 export); it was never reset for Plan 7. Review mode cannot
    write run_log.md, so this is unrepairable here.
  - Code substance passes every acceptance criterion: `pytest
    tests/test_local_preflight.py -q` → 32 passed, 0 skipped/xfail; `pytest
    tests/ -q` → 678 passed, 212 skipped, 0 failed; preflight tool reports
    `environment_ready: true` (26/26 required, 5/5 optional, 1 optional warning
    for the optional `pdf2md-glm` env); `--strict` exits 0.
  - current_plan.md is structurally non-conforming to agent.md §1: no `tasks`
    list with IDs, and it shipped without `## Status` / `## PR_reviews` /
    `## Feedback` sections. Adding task IDs is feedback mode's job.
  - history.md ends at M5 (Plan 4); Plans 5 and 6 were implemented but never
    archived, so run_log.md and history.md are out of sync with reality.
  - To clear this fail: an agent-mode session appends a PR #5 evidence entry to
    run_log.md for the Plan 7 work; review then re-issues a `pass`; feedback
    mode (`archive plan`) records the milestones and resets run_log.md.
