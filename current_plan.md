# Plan 9 — Real Backend Smoke Readiness

Status:
human_verified

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Linked ROADMAP phase:
Phase 2 — Extraction and normalisation

Current roadmap estimate:
Phase 2 from 60% toward 70%

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 9 of the pre-MVP implementation sequence, ending at Plan 16.

Previous plan:
Plan 8 — Local Ground-Truth Corpus Validation plus Documentation Consistency

Required previous plan status:
human_verified

Next plan after completion:
Plan 10 — Connector Implementation and PageExtractionIR Validation

Branch name:
plan-9-backend-smoke-readiness

---

## 1. Purpose

This plan verifies that configured real backend execution can be attempted, classified, and reported before connector normalisation begins.

Plan 9 is a smoke-readiness plan. It does not validate PageExtractionIR, EntityProposalDocument, calibration, consensus, semantic linking, or Docling export. It only checks whether configured backends can run on a real PDF input and produce smoke output artefacts.

The core question is:

```text
Can at least two configured backends run on a real PDF and produce output artefacts, while every other configured backend is classified clearly?
```

Plan 9 must wrap the repository's existing backend execution path. It must not create a parallel backend runner that diverges from the pipeline.

Where existing functions are available, the implementation must reuse them, for example:

```text
load_backend_config()
run_configured_backends()
```

If these names do not exist or differ in the current code, the agent must inspect the existing backend execution code and reuse the closest existing loader/runner. If no reusable runner exists, the agent must stop and report a blocker rather than inventing a separate execution architecture.

The agent writes code, report contracts, CLI wrapper, and mocked tests. The human reviewer runs real backend smoke checks because real execution depends on local conda environments, model weights, CUDA, external binaries, and filesystem paths.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

README.md is the public entry point.

PLAN_TEMPLATE.md is the standard format for executable plans.

current_plan.md is the active execution contract for agents.

next_plan.md is the next planned execution contract.

history.md records completed milestones after human verification.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-9-backend-smoke-readiness
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 8 has been marked human_verified and archived.
8. Do not mark this plan human_verified or finished. Only the human reviewer may do that.

Main repository environment:

```text
pdf2md
```

Repository-level commands must run using:

```bash
conda run -n pdf2md python <command>
```

or from an activated environment:

```bash
conda activate pdf2md
```

Backend runtime commands must use the configured backend environments through the existing backend runner. Typical backend environments may include:

```text
pdf2md-mineru
pdf2md-paddleocr
pdf2md-deepseek
```

This plan must not install or repair backend environments automatically.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Inspect or reuse the existing backend configuration loader.
2. Inspect or reuse the existing configured backend runner.
3. Add a smoke wrapper around existing backend execution.
4. Run all configured backends, or classify unavailable/unconfigured backends.
5. Capture command, exit code, duration, stdout snippet, stderr snippet, output directory and output files found.
6. Classify each backend into a smoke-readiness status.
7. Enforce a gate of at least two successful configured backends by default.
8. Make the gate minimum configurable with `--gate-minimum`, default `2`.
9. Provide non-strict and strict-gate behaviour.
10. Write a machine-readable smoke report.
11. Write a human-readable smoke summary.
12. Add mocked automated tests that require no backend environment, no models, no GPU and no network access.
13. Provide human verification commands for real backend execution on a real PDF.
14. Treat GLM as not_configured unless it is explicitly present and enabled in the backend config.
15. Provide `next_action` guidance for each backend result.

Out of scope:

1. Installing backend conda environments.
2. Downloading model weights.
3. Fixing CUDA, drivers, system libraries or external binaries.
4. Modifying backend implementation code.
5. Modifying backend configuration by default.
6. Creating a new backend runner that bypasses the existing backend execution path.
7. Normalising backend output to PageExtractionIR.
8. Creating or validating EntityProposalDocument.
9. Running calibration.
10. Running consensus.
11. Running semantic linking.
12. Running Docling export.
13. Editing ROADMAP.md.
14. Editing README.md.
15. Editing project.md.
16. Editing current_plan.md.
17. Editing next_plan.md.
18. Committing smoke reports as repository artefacts.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. Real backend failures must be classified as backend, environment, dependency, model, timeout, output, or configuration issues. They must not be treated as repository defects unless the wrapper or report logic is wrong.
6. The automated tests must use mocks and temporary files only.
7. The agent must not run real backends in automated tests.
8. If existing backend execution functions cannot be found, the agent must stop and report a blocker.
9. If backend config is missing or incomplete, the tool must classify the affected backends as not_configured rather than creating config by default.

Allowed Python dependencies:

```text
none beyond existing repository dependencies
```

Allowed external tools for agent automated tests:

```text
none
```

Allowed external tools for human verification:

```text
configured backend commands executed through the existing repository backend runner
```

Allowed environment-modifying commands:

```text
none
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these implementation and test files:

```text
src/pdf2md/local/backend_smoke.py

tools/backend_smoke.py

tests/test_backend_smoke.py
```

The agent may create temporary outputs only through the smoke CLI at runtime. These outputs must not be committed by default:

```text
<out-dir>/backend_smoke_report.json
<out-dir>/backend_smoke_summary.txt
```

The agent must not modify these files unless a human explicitly revises this plan:

```text
README.md
ROADMAP.md
PLAN_TEMPLATE.md
project.md
current_plan.md
next_plan.md
history.md
agent.md
run_log.md
pyproject.toml

config/backends.toml
config/*

src/pdf2md/models/*
src/pdf2md/local/groundtruth.py
src/pdf2md/local/preflight.py
src/pdf2md/connectors/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

backend/*
groundtruth/corpus/*

tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py
```

If `config/backends.toml` does not exist or is incomplete, Plan 9 must report not_configured/config-related readiness in the smoke report. It must not modify config unless this plan is explicitly amended by the human reviewer.

If a forbidden file must be changed, this plan is incomplete and must be revised by a human before implementation starts.

Expected output artefacts, produced by the CLI and not committed unless a later policy explicitly allows it:

```text
<out-dir>/backend_smoke_report.json — machine-readable backend smoke report
<out-dir>/backend_smoke_summary.txt — human-readable backend smoke summary
```

Required report contract:

```text
schema_name: pdf2md.BackendSmokeReport
schema_version: 1.0.0
generated_at: ISO 8601 timestamp
tool_name: backend_smoke
repo_root: path
corpus_root: path or null
input_pdf: path
gate_minimum: int
gate_passed: bool
total_backends: int
backends_successful: int
backends_failed: int
backends_deferred: int
results: list of per-backend entries
warnings: list of strings
metadata: dict
```

Per-backend result contract:

```text
backend_name: str
configured: bool
enabled: bool
environment_name: str or null
command: list[str] or string or null
input_pdf: str or null
output_dir: str or null
exit_code: int or null
duration_seconds: float or null
status: success | env_not_ready | model_missing | dependency_missing | backend_crash | output_missing | timeout | not_configured
expected_output_patterns: list[str]
output_files_found: list[str]
missing_output_patterns: list[str]
stdout_snippet: str
stderr_snippet: str
failure_reason: str or null
next_action: str
metadata: dict
```

Status taxonomy:

```text
success:
  The backend command completed successfully and at least one expected output artefact was found.

env_not_ready:
  The required conda environment, command, interpreter, binary, path, or runtime shell is missing or unavailable.

model_missing:
  Model weights, checkpoints, Hugging Face cache entries, local model paths, or required downloaded assets are missing.

dependency_missing:
  Python modules, shared libraries, system libraries, OCR engines, CUDA libraries, or other dependencies are missing.

backend_crash:
  The backend command exits non-zero or raises a runtime exception that is not better classified as env_not_ready, model_missing, dependency_missing, timeout, or output_missing.

output_missing:
  The backend command exits successfully but expected output artefacts are missing.

timeout:
  The backend run exceeds the configured timeout.

not_configured:
  The backend is absent from config, disabled in config, has no command, or is present in the repository but not configured for execution.
```

Gate rule:

```text
The default gate_minimum is 2.
The gate counts only backends with status success.
A zero exit code alone is not enough for success.
Success requires at least one expected output artefact.
The smoke tool must attempt or classify all configured backends; it must not stop at the first failure.
```

GLM rule:

```text
GLM is not automatically part of the canonical backend set.
If GLM exists under backend/ but is absent from backend configuration, report it as not_configured or omit it according to the behaviour of the existing config loader.
Do not force GLM into the configured backend set in Plan 9.
```

---

## 6. Agent tasks

Task A1:

Title:
Inspect and wrap existing backend execution.

Goal:
Create `src/pdf2md/local/backend_smoke.py` that reuses the existing backend config and execution path to support smoke readiness reporting.

Files allowed:

```text
src/pdf2md/local/backend_smoke.py
tests/test_backend_smoke.py
```

Implementation requirements:

1. Inspect the repository for existing backend config loading and backend execution functions.
2. Prefer reusing existing functions such as `load_backend_config()` and `run_configured_backends()` if present.
3. If function names differ, reuse the closest existing loader and runner.
4. Do not implement a new backend execution architecture if an existing one is available.
5. If no reusable backend runner exists, stop and report a blocker.
6. Define typed models or Pydantic models for `BackendSmokeReport` and per-backend smoke results.
7. Implement smoke result classification from runner results, subprocess-like results, stdout, stderr, timeout and output artefact presence.
8. Implement deterministic sorting of backend results by backend name.
9. Include `next_action` in every backend result.
10. Do not import or modify connector, calibration, consensus, linking, or export code.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_backend_smoke.py -q
```

Expected output:
A module importable as:

```python
from pdf2md.local.backend_smoke import build_backend_smoke_report
```

Completion evidence:
Agent must report existing runner/config functions reused, models created, classification logic implemented, and tests run.

Human verification required:
no. Covered by H1, H2, and H3.

Task A2:

Title:
Implement backend smoke CLI.

Goal:
Create `tools/backend_smoke.py` as a CLI entry point around the backend smoke module.

Files allowed:

```text
tools/backend_smoke.py
tests/test_backend_smoke.py
```

Implementation requirements:

1. Accept `--corpus-root`, default `groundtruth/corpus/latex`.
2. Accept `--input-pdf`, optional but required for real backend execution unless the tool can select one from the corpus.
3. Accept `--out-dir`, required.
4. Accept `--gate-minimum`, default `2`.
5. Accept `--strict-gate`.
6. Accept `--timeout-seconds`, default `300`.
7. Accept `--verbose`.
8. Write `backend_smoke_report.json` and `backend_smoke_summary.txt`.
9. In non-strict-gate mode, write report and exit 0 even when gate_passed is false, unless there is a repository defect in the smoke wrapper itself.
10. In strict-gate mode, exit 1 when gate_passed is false.
11. Print summary to stdout when `--verbose` is set.
12. Do not expose normalisation, connector, calibration, consensus, linking, or export options.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_backend_smoke.py -q
```

Expected output:
A script runnable as:

```bash
conda run -n pdf2md python tools/backend_smoke.py --input-pdf <pdf> --out-dir <path>
```

Completion evidence:
Agent must report CLI command examples, gate behaviour, exit-code behaviour, and tests run.

Human verification required:
no. Covered by H1, H2, and H3.

Task A3:

Title:
Add mocked automated tests for classification and gate behaviour.

Goal:
Create automated tests that validate Plan 9 logic without running real backends.

Files allowed:

```text
tests/test_backend_smoke.py
```

Implementation requirements:

1. Mock the existing backend runner or subprocess-like result objects.
2. Use `tmp_path` to create temporary output files for success and output_missing cases.
3. Test `success` classification when exit code is 0 and expected output files exist.
4. Test `output_missing` when exit code is 0 but expected outputs are absent.
5. Test `env_not_ready` from missing conda environment, missing command, or executable-not-found stderr.
6. Test `model_missing` from missing checkpoint/model/cache stderr.
7. Test `dependency_missing` from ImportError, ModuleNotFoundError, shared-library, CUDA-library or system-library errors.
8. Test `backend_crash` from generic non-zero runtime failure.
9. Test `timeout` classification.
10. Test `not_configured` classification.
11. Test gate pass when at least two backends have status success.
12. Test gate fail when fewer than two backends have status success.
13. Test strict-gate exit behaviour.
14. Test JSON report contract.
15. Test summary writing.
16. Ensure no real backend, model, CUDA or network dependency is required.
17. Do not add permanent mock output fixtures unless the human reviewer amends the plan.

Required tests:

```text
test_success_requires_exit_zero_and_output_files
test_exit_zero_without_outputs_is_output_missing
test_env_not_ready_classification
test_model_missing_classification
test_dependency_missing_classification
test_backend_crash_classification
test_timeout_classification
test_not_configured_classification
test_gate_passes_with_two_successes
test_gate_fails_with_one_success
test_strict_gate_exit_one_when_gate_fails
test_nonstrict_gate_exit_zero_when_gate_fails
test_report_json_contract
test_summary_is_written
test_next_action_is_present_for_every_backend
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_backend_smoke.py -q
```

Expected output:
All Plan 9 tests pass without real backend execution.

Completion evidence:
Agent must report test count, pass count, and exit code.

Human verification required:
no. Covered by H1.

Task A4:

Title:
Produce smoke report hand-off information for Plan 10.

Goal:
Ensure the report contains enough information for a human to decide which backend outputs should be attempted first in Plan 10, without Plan 9 making connector-readiness decisions.

Files allowed:

```text
src/pdf2md/local/backend_smoke.py
tools/backend_smoke.py
tests/test_backend_smoke.py
```

Implementation requirements:

1. Include `output_files_found` for each backend.
2. Include `expected_output_patterns` and `missing_output_patterns` where the existing runner or config provides expected patterns.
3. Include `next_action` for each backend.
4. Do not add a `ready_for_connector_validation` field.
5. Do not inspect or import connector code to decide connector sufficiency.
6. Make the summary list successful backends first, followed by failed/deferred backends and their next action.
7. Clearly state that Plan 10 will decide whether the smoke outputs are sufficient for PageExtractionIR normalisation.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_backend_smoke.py -q
```

Expected output:
Reports guide the human reviewer without collapsing Plan 9 into Plan 10.

Completion evidence:
Agent must report report fields and hand-off summary behaviour.

Human verification required:
yes. Covered by H3.

---

## 7. Human verification checkpoints

Checkpoint H0:

Title:
Confirm real smoke input PDF exists.

Purpose:
Confirm that at least one real PDF exists for backend smoke execution. Do not use `.pdf.placeholder` files for real backend smoke.

Required environment:
Shell with repository checkout.

Preconditions:
Plan 8 has completed or the human has identified an approved local PDF.

Command:

```bash
find groundtruth/corpus/latex -name "*.pdf" -type f | head -5
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm at least one real `.pdf` file is listed.
3. If no PDF is listed, the human must provide an approved real PDF path or generate one outside Plan 9.
4. Confirm the selected PDF is not a `.pdf.placeholder` file.
5. Record the selected PDF path for H2 and H3.

Pass criteria:

```text
A real PDF path is available.
The selected path ends with .pdf.
The selected path does not end with .pdf.placeholder.
The selected path can be read by the local user.
```

Fail criteria:

```text
No real PDF is available.
Only .pdf.placeholder files exist.
The selected file cannot be read.
The selected file was generated by Plan 9 itself.
```

Evidence to record:

```text
Paste the command.
Paste the selected PDF path.
Paste ls -lh output for the selected PDF.
```

Checkpoint H1:

Title:
Verify mocked backend smoke tests.

Purpose:
Confirm that automated Plan 9 tests pass without real backend environments.

Required environment:
pdf2md

Preconditions:
Tasks A1, A2, A3 and A4 are complete.

Command:

```bash
conda run -n pdf2md pytest tests/test_backend_smoke.py -v
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm all tests pass.
3. Confirm no test requires CUDA, model weights, backend conda environments, network access, or real backend binaries.
4. Confirm no tests are skipped due to missing real backend dependencies.

Pass criteria:

```text
All tests pass.
Exit code is 0.
No real backend is executed.
No tests are skipped because of missing backend environments or models.
```

Fail criteria:

```text
Any test fails.
Any test requires real backend execution.
Any test depends on CUDA, models, backend conda environments or network access.
```

Evidence to record:

```text
Paste the pytest output.
Paste the exit code.
```

Checkpoint H2:

Title:
Run real backend smoke on one approved PDF.

Purpose:
Confirm that configured backends can be attempted on a real PDF and classified correctly.

Required environment:
pdf2md plus configured backend environments as available locally.

Preconditions:
H0 has selected a real PDF path.
The existing backend configuration is present or the tool can classify missing configuration as not_configured.
The agent implementation has passed H1.

Command template:

```bash
conda run -n pdf2md python tools/backend_smoke.py --corpus-root groundtruth/corpus/latex --input-pdf <SELECTED_PDF_FROM_H0> --out-dir groundtruth/runs/backend_smoke --gate-minimum 2 --verbose
```

Strict gate command:

```bash
conda run -n pdf2md python tools/backend_smoke.py --corpus-root groundtruth/corpus/latex --input-pdf <SELECTED_PDF_FROM_H0> --out-dir groundtruth/runs/backend_smoke_strict --gate-minimum 2 --strict-gate --verbose
```

Expected output files:

```text
groundtruth/runs/backend_smoke/backend_smoke_report.json
groundtruth/runs/backend_smoke/backend_smoke_summary.txt
groundtruth/runs/backend_smoke_strict/backend_smoke_report.json
groundtruth/runs/backend_smoke_strict/backend_smoke_summary.txt
```

Verification procedure:

1. Replace `<SELECTED_PDF_FROM_H0>` with the real PDF path recorded in H0.
2. Run the non-strict command.
3. Record the exit code.
4. Confirm both non-strict output files exist.
5. Run the strict-gate command.
6. Record the exit code.
7. Confirm both strict output files exist even if the strict command exits 1.
8. Inspect both JSON reports.
9. Confirm each configured backend has a status.
10. Confirm `success` appears only when exit code was 0 and output files were found.
11. Confirm `output_missing` is used for exit-code-0 runs with missing outputs.
12. Confirm failures are classified as env_not_ready, model_missing, dependency_missing, backend_crash, output_missing, timeout or not_configured.
13. Confirm GLM is not forced into the configured backend set unless config enables it.

Pass criteria:

```text
Non-strict command writes report and summary.
Strict command writes report and summary.
All configured backends are classified.
The report counts only status=success toward the gate.
Success requires output artefacts.
Failures include failure_reason and next_action.
No normalisation, connector, calibration, consensus, linking or export code is run.
```

Fail criteria:

```text
The tool crashes before writing a report.
A configured backend is omitted without classification.
Exit-code-0 with no outputs is reported as success.
Failures lack classification.
GLM is forced into the run despite not being configured.
Forbidden pipeline stages are executed.
```

Evidence to record:

```text
Paste both commands.
Paste both exit codes.
Paste gate_passed, gate_minimum, total_backends, backends_successful, backends_failed and backends_deferred from the JSON report.
Paste the per-backend status table from backend_smoke_summary.txt.
Paste next_action for each non-success backend.
```

Checkpoint H3:

Title:
Verify smoke gate and Plan 10 hand-off scope.

Purpose:
Confirm that the smoke report is sufficient for the human reviewer to define which backend outputs should be attempted first in Plan 10, without Plan 9 deciding connector readiness.

Required environment:
Any text editor or JSON inspection tool.

Preconditions:
H2 has produced a real backend smoke report.

Command:

```bash
python -m json.tool groundtruth/runs/backend_smoke/backend_smoke_report.json
```

Verification procedure:

1. Open the non-strict smoke report.
2. Count backends with `status == "success"`.
3. Confirm the count equals `backends_successful`.
4. Confirm `gate_passed` is true only if `backends_successful >= gate_minimum`.
5. Confirm each backend result includes `output_files_found`.
6. Confirm each backend result includes `next_action`.
7. Confirm the report does not include `ready_for_connector_validation`.
8. Confirm the summary states that Plan 10 will decide whether outputs are sufficient for PageExtractionIR normalisation.
9. Record the successful backend names for Plan 10 planning.

Pass criteria:

```text
Gate calculation is correct.
Every backend has status, output_files_found and next_action.
The report does not include ready_for_connector_validation.
The report gives enough evidence for the human to choose initial Plan 10 backend scope.
```

Fail criteria:

```text
Gate calculation is wrong.
A backend lacks status or next_action.
The report contains ready_for_connector_validation.
The report tries to validate PageExtractionIR or connector sufficiency.
```

Evidence to record:

```text
Paste backends_successful and gate_passed.
Paste successful backend names.
Paste the summary section that lists next actions.
Paste confirmation that ready_for_connector_validation is absent.
```

Checkpoint H4:

Title:
Verify no forbidden pipeline layers were modified.

Purpose:
Confirm that Plan 9 remains a smoke-readiness plan and does not bleed into connector, calibration, consensus, linking or export work.

Required environment:
Git checkout.

Command:

```bash
git diff --name-only
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm changed files are limited to the Plan 9 whitelist.
3. Confirm no files under `src/pdf2md/connectors/`, `src/pdf2md/calibration/`, `src/pdf2md/consensus/`, `src/pdf2md/linking/`, or `src/pdf2md/export/` were modified.
4. Confirm `config/backends.toml` was not modified unless this plan was explicitly amended by a human.
5. Confirm smoke reports are not committed by default.

Pass criteria:

```text
Only whitelisted files are modified.
No connector, calibration, consensus, linking or export files are modified.
No backend implementation files are modified.
No backend config files are modified without explicit plan amendment.
No generated smoke reports are committed by default.
```

Fail criteria:

```text
Forbidden files are modified.
Backend execution architecture is reimplemented in parallel.
Connector or PageExtractionIR logic is added.
Generated reports are committed without explicit policy.
```

Evidence to record:

```text
Paste git diff --name-only.
List each changed file and why it changed.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_backend_smoke.py -q
conda run -n pdf2md pytest tests/test_local_groundtruth_validate.py -q
conda run -n pdf2md pytest tests/test_local_preflight.py -q
```

Human verification test matrix:

```text
H0 real PDF availability
H1 mocked backend smoke tests
H2 real backend smoke on one approved PDF
H3 smoke gate and Plan 10 hand-off scope
H4 forbidden-layer diff check
```

Smoke status classes:

success:
The backend command completed successfully and at least one expected output artefact was found.

env_not_ready:
The required conda environment, command, interpreter, binary, path, or runtime shell is missing or unavailable.

model_missing:
Model weights, checkpoints, Hugging Face cache entries, local model paths, or required downloaded assets are missing.

dependency_missing:
Python modules, shared libraries, system libraries, OCR engines, CUDA libraries, or other dependencies are missing.

backend_crash:
The backend command exits non-zero or raises a runtime exception that is not better classified as env_not_ready, model_missing, dependency_missing, timeout, or output_missing.

output_missing:
The backend command exits successfully but expected output artefacts are missing.

timeout:
The backend run exceeds the configured timeout.

not_configured:
The backend is absent from config, disabled in config, has no command, or is present in the repository but not configured for execution.

Failure classes:

repository_defect:
The wrapper, CLI, report generation, classification logic, or tests are wrong.

environment_missing:
A required local environment, backend executable, system package, CUDA runtime or shell command is missing.

model_missing:
A model, checkpoint, Hugging Face cache entry, local model directory or required asset is missing.

dependency_missing:
A Python module, shared library, system library, OCR runtime or CUDA library is missing.

backend_runtime_failure:
A backend crashes for a reason not better classified as environment, dependency, model, output or timeout.

output_missing:
A backend command exits successfully but expected output artefacts are missing.

configuration_missing:
Backend config is missing, incomplete or disables a backend.

timeout:
A backend smoke run exceeds the allowed time.

human_procedure_error:
The human ran the wrong command, used the wrong PDF, used a placeholder PDF, inspected the wrong report, or used the wrong environment.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

Failure handling:

If failure_class is repository_defect:
The agent must fix the wrapper, CLI, classification, report, or tests.

If failure_class is environment_missing:
The human or environment owner must fix the environment, or the backend remains classified as env_not_ready.

If failure_class is model_missing:
The human or environment owner must install or configure model weights, or the backend remains classified as model_missing.

If failure_class is dependency_missing:
The human or environment owner must fix dependencies, or the backend remains classified as dependency_missing.

If failure_class is backend_runtime_failure:
The backend remains classified as backend_crash unless the wrapper classification is wrong.

If failure_class is output_missing:
The backend remains classified as output_missing unless the expected output pattern is wrong.

If failure_class is configuration_missing:
The backend remains not_configured unless the human amends the plan to allow config changes.

If failure_class is timeout:
The backend remains timeout unless the human increases timeout or fixes the environment.

If failure_class is human_procedure_error:
The human checkpoint must be rerun correctly.

If failure_class is test_expectation_wrong:
The plan must be revised by a human before continuing.

---

## 9. Checkpoints, push policy, and hand-off

Checkpoint C0: Plan ready

Required before agent starts:

```text
status is active
Plan 8 status is human_verified or human explicitly approves drafting only
scope is clear
file whitelist is complete
forbidden files are listed
dependencies are declared
agent tasks are listed
automated tests are listed
human verification checkpoints are listed
next plan is identified
```

Checkpoint C1: Agent implementation complete

Required before human verification:

```text
all agent tasks attempted
all required automated tests run
no forbidden files modified
no undeclared dependencies used
agent report completed
status set to agent_complete or human_verification_required
```

Checkpoint C2: Human verification complete

Required before merge or milestone completion:

```text
all human checkpoints run
all expected output files produced
all pass criteria satisfied or failures classified
human verification report completed
status set to human_verified by a human
```

Checkpoint C3: Plan finished and promoted

Required before promotion:

```text
status is human_verified
Plan 9 is archived after completion
history.md summary is prepared or updated
Plan 10 exists as next_plan.md or approved prepared plan
Plan 10 may be promoted to current_plan.md only after Plan 9 is finished
ROADMAP.md progress is updated only if explicitly approved by the human
```

Push and PR policy:

```text
The agent may push an implementation branch if the plan allows it.
The agent may open a draft PR if the plan allows it.
The agent must not merge to main.
The agent must not direct-push to main unless the human explicitly authorises it for that specific change.
```

Human verification must pass before:

```text
merging to main
marking the plan finished
promoting next_plan.md
updating ROADMAP.md progress
declaring the milestone achieved
```

Hand-off procedure after human verification:

1. Archive current_plan.md as:

```text
plans/archive/plan-9-backend-smoke-readiness.md
```

2. Append a milestone summary to history.md.
3. Promote Plan 10 to current_plan.md.
4. Create a new next_plan.md from PLAN_TEMPLATE.md or from an approved prepared plan.
5. Record the commit SHA or PR number.
6. Record the human verification evidence.
7. Confirm whether ROADMAP.md progress should change.

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan:
Status:
Branch:
Commit or PR:
Files changed:
Forbidden files touched:
Tasks attempted:
Existing runner/config functions reused:
Automated tests run:
Automated tests passed:
Automated tests failed:
Failure classes:
Environment failures:
Backend statuses from mocks:
Dependencies added:
External tools used by agent:
Output artefacts created:
Human verification still required:
Blockers:
Next recommended action:
```

Human verification report template:

```text
Plan:
Reviewer:
Date:
Environment:
Selected smoke PDF:
Commands run:
Exit codes:
Output files checked:
Backend statuses:
Gate minimum:
Gate passed:
Successful backends:
Deferred backends:
Next actions:
Pass criteria satisfied:
Fail criteria triggered:
Failure classes:
Evidence:
Decision:
human_verified or rejected
```

Reviewer checklist:

1. Did the agent modify only whitelisted files?
2. Did the agent avoid all forbidden files?
3. Were all declared automated tests run?
4. Did any automated test fail?
5. Did automated tests avoid real backend execution?
6. Did the implementation reuse the existing backend config/runner path?
7. Did the implementation avoid creating a parallel backend runner?
8. Were real backend runs performed only by the human checkpoint?
9. Was a real PDF used, not a `.pdf.placeholder`?
10. Did `success` require both exit code 0 and output artefacts?
11. Was exit-code-0 with no outputs classified as output_missing?
12. Were all configured backends classified?
13. Was GLM treated as not_configured unless config explicitly enabled it?
14. Did each backend result include status, output_files_found, failure_reason where relevant, and next_action?
15. Was `ready_for_connector_validation` absent from the report?
16. Did the report avoid PageExtractionIR and connector sufficiency decisions?
17. Did non-strict mode write reports even when the gate failed?
18. Did strict-gate mode fail when gate_passed is false?
19. Were generated reports left uncommitted by default?
20. Were connectors, calibration, consensus, linking and export files untouched?
21. Is Plan 10 clearly identified as the next plan?
22. Is it safe to mark this plan human_verified?
23. Is it safe to promote the next plan?
24. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-09 — draft — human — Plan 9 created from ROADMAP.md and PLAN_TEMPLATE.md
2026-05-09 — active — human — approved for agent execution
2026-05-09 — agent_in_progress — agent — branch created
2026-05-09 — agent_complete — agent — automated tests passed
2026-05-09 — human_verification_required — agent — awaiting human backend smoke checks
2026-05-09 — human_verified — human — all checkpoints passed
2026-05-09 — finished — human — archived and promoted
```
