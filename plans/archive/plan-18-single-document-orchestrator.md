# Plan 18 — Single-Document Pipeline Orchestrator

Status:
finished

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
Phase 6 — Functional application and CLI/API
Phase 5 consumer — uses all staged pipeline outputs

Current roadmap estimate:
Post-MVP. No ROADMAP.md percentage change until human approval.

Note:
This plan wires the six existing pipeline stages into a single command that
takes a PDF and produces consensus-derived Docling JSON, Markdown, and RAG
chunks. All stage logic already exists and is tested. The gap is an
orchestrator that chains them with a canonical directory layout and handles
errors, partial results, and stage skipping.

This plan does NOT implement new extraction logic, new consensus algorithms,
or new export formats. It reuses the existing modules unchanged.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 18 of the post-MVP implementation sequence.

Previous plan:
Plan 17 — External Ground-Truth Dataset Downloaders

Required previous plan status:
human_verified

Next plan after completion:
Plan 19 — External Dataset Compilation and Evaluation

Branch name:
plan-18-single-document-orchestrator

---

## 1. Purpose

This plan implements a single-document pipeline orchestrator that executes the
full pdf2md pipeline from one PDF input to final exports.

The six stages already exist as independent modules and CLI tools:

```text
Stage 1 — Backend execution          backends/runner.py      (run_configured_backends)
Stage 2 — Connector (raw → IR)       connectors/common.py    (connect_raw_dir)
Stage 3 — Calibration priors         calibration/*           (build_prior_document)
Stage 4 — Consensus                  consensus/factory.py    (build_consensus_ir)
Stage 5 — Linked structure           linking/builder.py      (build_linked_structure)
Stage 6 — Export                     export/io.py            (build_export_run)
```

Each stage writes artefacts to disk and the next stage reads them. But no
orchestrator chains them. The existing `pipeline/convert.py` is a placeholder
that runs a single backend through a single adapter, bypassing consensus
entirely. The existing `tools/` scripts are standalone CLIs that must be
invoked manually in sequence.

This plan:

1. Defines the canonical run directory layout in `pipeline/artifacts.py`.
2. Implements a stage runner in `pipeline/orchestrator.py` that calls each
   stage's Python API (not subprocess) in sequence.
3. Adds a `pdf2md convert` CLI command that replaces the current placeholder.
4. Handles stage failures gracefully: reports partial results, classifies
   failures, and produces a pipeline manifest.

The core question this plan answers:

```text
Can a user run `pdf2md convert input.pdf --config pdf2md.backends.toml`
and get consensus-derived Docling JSON, Markdown, and RAG output from all
enabled backends without manually invoking six separate tools?
```

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
git switch -c plan-18-single-document-orchestrator
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If git status is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not mark this plan human_verified or finished. Only the human reviewer may do that.

Main conda environment:

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

Backend execution during human verification requires backend-specific
environments (pdf2md-mineru, pdf2md-paddleocr, etc). The orchestrator must
invoke backends using the same conda-run subprocess mechanism as the existing
`run_configured_backends`.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Canonical run directory layout definition in `pipeline/artifacts.py`.
2. Pipeline orchestrator in `pipeline/orchestrator.py` that calls stages 1–6
   via their Python API.
3. Pipeline stage status tracking and manifest generation.
4. Replacement of the placeholder `convert` command in `cli/main.py`.
5. Graceful handling of missing backends, failed stages, and partial results.
6. Unit tests using mock backends and synthetic connector outputs.

Out of scope:

1. New extraction logic or new backend wrappers.
2. New consensus algorithms or scoring changes.
3. New export formats.
4. Parallel backend execution (backends run sequentially as today).
5. Resume/checkpoint from a partial run.
6. Web or API surfaces.
7. Changes to the `run-backends` command.
8. Changes to any existing stage module's internal logic.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The orchestrator must call existing stage modules via their Python API,
   not by spawning subprocess calls to `tools/*.py`.
4. Backend execution is the one exception: it must use subprocess via
   `run_configured_backends` because backends run in separate conda environments.
5. The orchestrator must not duplicate logic from existing stage modules.
6. Stage 3 (calibration) is optional: if no priors directory is provided or
   no ground-truth is available, the consensus runs with default priors.
7. The orchestrator must work with a single backend (SINGLE_SOURCE consensus
   mode) as well as multiple backends.

Allowed Python dependencies:

```text
none (uses only existing project dependencies: pydantic, typer)
```

Allowed external tools:

```text
conda — for backend subprocess execution (existing mechanism)
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these files:

```text
src/pdf2md/pipeline/artifacts.py
src/pdf2md/pipeline/orchestrator.py
src/pdf2md/pipeline/reporting.py
src/pdf2md/cli/main.py
tests/test_pipeline_artifacts.py
tests/test_pipeline_orchestrator.py
tests/test_pipeline_cli.py
tests/data/orchestrator_fixtures/.gitkeep
run_log.md
```

The agent must not modify these files:

```text
README.md
ROADMAP.md
project.md
current_plan.md
next_plan.md
history.md
PLAN_TEMPLATE.md
src/pdf2md/backends/runner.py
src/pdf2md/connectors/common.py
src/pdf2md/consensus/factory.py
src/pdf2md/consensus/grouping.py
src/pdf2md/consensus/scoring.py
src/pdf2md/calibration/*
src/pdf2md/linking/*
src/pdf2md/export/*
src/pdf2md/models/*
backend/*
tools/*
groundtruth/*
pyproject.toml
```

Expected output artefacts (created at runtime, not committed):

```text
<out-dir>/pipeline_manifest.json          — stage-by-stage status
<out-dir>/pipeline_summary.txt            — human-readable summary
<out-dir>/input/<filename>.pdf            — copy of input
<out-dir>/raw/<backend>/                  — raw backend outputs
<out-dir>/connector/<backend>/pages/      — PageExtractionIR JSON
<out-dir>/connector/<backend>/entities.json
<out-dir>/priors/<backend>.json           — calibration priors (if available)
<out-dir>/consensus/consensus_ir.json
<out-dir>/consensus/reports/
<out-dir>/linked/linked_structure.json
<out-dir>/linked/reports/
<out-dir>/export/docling.json
<out-dir>/export/rag_chunks.json
<out-dir>/export/preview.md
<out-dir>/export/reports/
```

Required pipeline_manifest.json contract:

```text
schema_name: pdf2md.PipelineManifest
schema_version: 1
document_id
input_pdf
backends_requested
backends_succeeded
stages:
  - name: backend_execution | connector | calibration | consensus | linking | export
    status: success | failed | skipped | not_started
    started_at
    finished_at
    duration_seconds
    output_dir
    warnings
    error (if failed)
overall_status: success | partial | failed
```

---

## 6. Agent tasks

### Task A1 — Canonical run directory layout

Title:
Define canonical directory layout in pipeline/artifacts.py

Goal:
Replace the placeholder in `pipeline/artifacts.py` with path helper functions
that define the canonical directory structure for a pipeline run.

Files allowed:

```text
src/pdf2md/pipeline/artifacts.py
tests/test_pipeline_artifacts.py
```

Implementation requirements:

1. Define a `RunLayout` dataclass or class that, given a `run_dir: Path`,
   provides properties for every subdirectory:

   ```python
   layout = RunLayout(run_dir)
   layout.input_dir        # run_dir / "input"
   layout.raw_dir          # run_dir / "raw"
   layout.raw_backend_dir(backend)  # run_dir / "raw" / backend
   layout.connector_dir    # run_dir / "connector"
   layout.connector_backend_dir(backend)  # run_dir / "connector" / backend
   layout.priors_dir       # run_dir / "priors"
   layout.consensus_dir    # run_dir / "consensus"
   layout.linked_dir       # run_dir / "linked"
   layout.export_dir       # run_dir / "export"
   layout.manifest_path    # run_dir / "pipeline_manifest.json"
   layout.summary_path     # run_dir / "pipeline_summary.txt"
   ```

2. Provide a `create_dirs()` method that creates the top-level subdirectories.

3. The layout must be compatible with the existing `run_configured_backends`
   output: backends write to `raw/<backend>/` and this layout must not
   conflict with that.

4. The connector output layout must match what `consensus/io.py`'s
   `load_consensus_inputs` expects: `<connector_root>/<backend>/pages/*.json`
   + `<backend>/entities.json`.

5. The priors layout must match what `consensus/io.py` expects:
   `<priors_root>/<backend>.json`.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_pipeline_artifacts.py -q
```

Tests must cover:
- all path properties return expected paths
- create_dirs creates the directory tree
- layout is consistent with consensus/io expectations

Expected output:
`from pdf2md.pipeline.artifacts import RunLayout` works.

Completion evidence:
Files changed, tests run, exit codes.

Human verification required:
no

---

### Task A2 — Pipeline orchestrator

Title:
Implement stage-by-stage orchestrator

Goal:
Implement `pipeline/orchestrator.py` that chains stages 1–6 using existing
module APIs, tracks per-stage status, and produces a pipeline manifest.

Files allowed:

```text
src/pdf2md/pipeline/orchestrator.py
src/pdf2md/pipeline/reporting.py
tests/test_pipeline_orchestrator.py
tests/data/orchestrator_fixtures/.gitkeep
```

Implementation requirements:

1. Define a `PipelineSettings` dataclass:

   ```python
   @dataclass
   class PipelineSettings:
       config: dict                    # backend TOML config (loaded)
       priors_dir: Path | None = None  # pre-computed priors (optional)
       force: bool = False
       dry_run: bool = False
       timeout: int | None = None
       keep_going: bool = True         # continue past backend failures
       skip_calibration: bool = False  # skip stage 3 if no truth available
       skip_export: bool = False       # stop after consensus
       verbose: bool = False
   ```

2. Implement `run_pipeline(input_pdf: Path, out_dir: Path, settings: PipelineSettings) -> PipelineResult`:

   **Stage 1 — Backend execution:**
   Call `run_configured_backends` with `work_dir=layout.run_dir`,
   `run_name="raw"` (so raw outputs land in `<out_dir>/raw/<backend>/`).
   This is the only stage that uses subprocess (conda run).
   Record which backends succeeded.

   **Stage 2 — Connector:**
   For each backend that produced raw output, call `connect_raw_dir`
   with `out_dir=layout.connector_backend_dir(backend)`.
   Use the backend-specific `BackendConnectorConfig` from
   `backend/<name>/connector.py` if available, otherwise use the
   default config from `connectors/common.py`.
   This produces `connector/<backend>/pages/*.json` and
   `connector/<backend>/entities.json`.

   **Stage 3 — Calibration (optional):**
   If `settings.priors_dir` is provided and contains `<backend>.json`
   files, copy them to `layout.priors_dir`.
   If not provided, skip this stage with status `skipped` and let
   consensus use default priors (0.5).
   Do NOT run calibration matching here — calibration is a corpus-level
   activity that must be done separately against ground truth. This stage
   only makes existing priors available to consensus.

   **Stage 4 — Consensus:**
   Call `load_consensus_inputs` with
   `connector_root=layout.connector_dir` and
   `priors_root=layout.priors_dir`.
   Call `build_consensus_ir` with the loaded inputs.
   Call `write_consensus_outputs` to `layout.consensus_dir`.

   **Stage 5 — Linked structure:**
   Call `load_linker_inputs` with the consensus IR path and
   entities/priors roots.
   Call `build_linked_structure`.
   Call `write_linker_outputs` to `layout.linked_dir`.

   **Stage 6 — Export:**
   Call `load_export_inputs` with the linked structure path.
   Call `build_export_run` with Docling, RAG, and Markdown settings.
   Call `write_export_outputs` to `layout.export_dir`.

3. Each stage must be wrapped in a try/except. On failure:
   - Record the error in the pipeline manifest.
   - If `keep_going` is True and downstream stages can't proceed,
     mark them as `not_started` (not `failed`).
   - If `keep_going` is False, stop immediately.

4. After all stages, write `pipeline_manifest.json` and
   `pipeline_summary.txt`.

5. Return a `PipelineResult` dataclass:

   ```python
   @dataclass
   class PipelineResult:
       overall_status: str             # "success" | "partial" | "failed"
       stages: list[StageStatus]
       manifest_path: Path
       consensus_ir_path: Path | None
       docling_path: Path | None
       markdown_path: Path | None
       warnings: list[str]
   ```

6. The orchestrator must handle:
   - Zero backends enabled → fail with clear message.
   - All backends fail → stage 2+ cannot proceed → overall_status "failed".
   - Some backends fail → proceed with successful ones → overall_status
     "partial" if downstream stages succeed.
   - Single backend → SINGLE_SOURCE consensus mode (already supported).
   - No priors → consensus uses default confidence 0.5 (already supported).

7. Implement `reporting.py` with:
   - `build_pipeline_summary(manifest: dict) -> str` for the text summary.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_pipeline_orchestrator.py -q
```

Tests must NOT call real backends or require conda environments. They must:
- Mock `run_configured_backends` to simulate backend success/failure and
  produce synthetic raw output (a simple markdown file).
- Test full pipeline with one mock backend → single-source consensus.
- Test full pipeline with two mock backends → multi-source consensus.
- Test partial failure: one backend fails, one succeeds → partial result.
- Test all backends fail → overall_status "failed", downstream skipped.
- Test with pre-existing priors directory → priors loaded.
- Test without priors → consensus runs with defaults.
- Test dry-run mode → no files created.
- Test that pipeline_manifest.json is valid JSON with required fields.

Test fixtures: use `tests/data/orchestrator_fixtures/` for any synthetic
connector outputs needed. Prefer generating fixtures in-test using
`pdf2md.testing.mock_backend_ir` where possible.

Expected output:
`from pdf2md.pipeline.orchestrator import run_pipeline` works.

Completion evidence:
Files changed, tests run, exit codes.

Human verification required:
no

---

### Task A3 — CLI integration

Title:
Replace placeholder convert command with pipeline orchestrator

Goal:
Replace the placeholder `convert` command in `cli/main.py` with a real
implementation that calls `run_pipeline`.

Files allowed:

```text
src/pdf2md/cli/main.py
tests/test_pipeline_cli.py
```

Implementation requirements:

1. Replace the existing `convert` command:

   ```python
   @app.command()
   def convert(
       pdf_path: Path = typer.Argument(..., help="Input PDF path."),
       config: Path = typer.Option(Path("pdf2md.backends.toml"), "--config"),
       out_dir: Path = typer.Option(None, "--out-dir", help="Output directory. Default: .tmp/<pdf-stem>/"),
       priors_dir: Path | None = typer.Option(None, "--priors-dir", help="Pre-computed calibration priors."),
       force: bool = typer.Option(False, "--force"),
       dry_run: bool = typer.Option(False, "--dry-run"),
       timeout: int | None = typer.Option(None, "--timeout"),
       keep_going: bool = typer.Option(True, "--keep-going"),
       skip_export: bool = typer.Option(False, "--skip-export"),
       verbose: bool = typer.Option(False, "--verbose"),
   ) -> None:
   ```

2. The command must:
   - Load the backend config from the TOML file.
   - Default `out_dir` to `.tmp/<pdf-stem>/` if not provided.
   - Call `run_pipeline`.
   - Print the pipeline summary to stdout.
   - Exit with code 0 on success, 1 on failure, 2 on partial.

3. The existing `run-backends` command must remain unchanged. It continues
   to work independently for users who want backend-only execution.

4. Remove the old `convert_pdf` import from cli/main.py. The placeholder
   `pipeline/convert.py` may remain as-is (it is not deleted) but the CLI
   no longer calls it.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_pipeline_cli.py -q
```

Tests must mock `run_pipeline` to avoid real backend execution. Tests must
cover:
- `pdf2md convert --help` shows all options.
- `pdf2md convert --dry-run` with mocked pipeline.
- Exit code mapping: 0 for success, 1 for failed, 2 for partial.
- Default out_dir is `.tmp/<stem>/`.

Expected output:
`pdf2md convert input.pdf --config pdf2md.backends.toml` invokes the full
pipeline.

Completion evidence:
Files changed, tests run, exit codes.

Human verification required:
yes (see checkpoint H1)

---

## 7. Human verification checkpoints

### Checkpoint H1

Title:
Verify convert command with dry-run (no backends required)

Purpose:
Confirm that the convert command parses arguments correctly and that dry-run
mode works without real backends or conda environments.

Required environment:
pdf2md

Preconditions:
The repository package is installed in editable mode.
Pipeline orchestrator is implemented.
cli/main.py has the new convert command.

Commands:

```bash
conda run -n pdf2md pdf2md convert --help
conda run -n pdf2md pdf2md convert test_visual.pdf --config pdf2md.backends.example.toml --dry-run --verbose
```

Input files:

```text
test_visual.pdf (existing in repo root)
pdf2md.backends.example.toml (existing in repo root)
```

Expected output files:

```text
none (dry-run does not create files)
```

Verification procedure:

1. Run `pdf2md convert --help`. Confirm it shows: pdf_path, --config,
   --out-dir, --priors-dir, --force, --dry-run, --timeout, --keep-going,
   --skip-export, --verbose.
2. Run the dry-run command. Confirm it prints the planned stages and
   backend list without executing anything.
3. Confirm no directories were created under `.tmp/`.

Pass criteria:

```text
Help shows all documented options.
Dry-run exits without error.
No files or directories created.
```

Fail criteria:

```text
Help is missing options.
Dry-run crashes or creates files.
```

Evidence to record:

```text
Paste stdout of --help.
Paste stdout of --dry-run.
Confirm .tmp/ was not modified.
```

---

### Checkpoint H2

Title:
Verify full pipeline with at least one real backend

Purpose:
Confirm that the orchestrator chains all six stages correctly and produces
consensus-derived final output from a real PDF.

Required environment:
pdf2md (plus at least one backend environment, e.g. pdf2md-mineru)

Preconditions:
At least one backend is configured and enabled in pdf2md.backends.toml.
The backend conda environment is functional.
The repository package is installed in editable mode.

Commands:

```bash
conda run -n pdf2md pdf2md convert test_visual.pdf \
    --config pdf2md.backends.toml \
    --out-dir /tmp/pdf2md_pipeline_test \
    --keep-going \
    --verbose
```

Input files:

```text
test_visual.pdf
pdf2md.backends.toml
```

Expected output files:

```text
/tmp/pdf2md_pipeline_test/pipeline_manifest.json
/tmp/pdf2md_pipeline_test/pipeline_summary.txt
/tmp/pdf2md_pipeline_test/input/test_visual.pdf
/tmp/pdf2md_pipeline_test/raw/<backend>/output.md
/tmp/pdf2md_pipeline_test/connector/<backend>/pages/page_0001.json
/tmp/pdf2md_pipeline_test/connector/<backend>/entities.json
/tmp/pdf2md_pipeline_test/consensus/consensus_ir.json
/tmp/pdf2md_pipeline_test/linked/linked_structure.json
/tmp/pdf2md_pipeline_test/export/docling.json
/tmp/pdf2md_pipeline_test/export/preview.md
```

Verification procedure:

1. Run the command. Record exit code.
2. Open `pipeline_manifest.json`. Verify all six stages have a status.
3. Confirm at least one backend has status `success` in stage 1.
4. Open `connector/<backend>/pages/page_0001.json`. Verify it is valid
   PageExtractionIR JSON.
5. Open `consensus/consensus_ir.json`. Verify it has `document_id`,
   `pages`, `backends` fields.
6. Open `export/docling.json`. Verify it is valid JSON.
7. Open `export/preview.md`. Verify it contains text content from the PDF.
8. Read `pipeline_summary.txt`. Verify it lists stages and outcomes.

Pass criteria:

```text
Command exits 0 (success) or 2 (partial if some backends failed).
All expected output files exist.
pipeline_manifest.json has all six stages.
consensus_ir.json lists the successful backends.
export/docling.json is valid JSON with text content.
export/preview.md is non-empty.
```

Fail criteria:

```text
Command exits 1 (total failure) when at least one backend should work.
Any expected output file is missing.
pipeline_manifest.json is malformed.
consensus_ir.json references zero backends.
```

Evidence to record:

```text
Paste exit code.
Paste pipeline_summary.txt content.
Paste first 20 lines of pipeline_manifest.json.
Paste document_id and page_count from consensus_ir.json.
Paste first 10 lines of export/preview.md.
Confirm stage statuses from manifest.
```

---

### Checkpoint H3

Title:
Verify multi-backend consensus with at least two backends

Purpose:
Confirm that when multiple backends are enabled, the consensus stage produces
multi-source agreement scores and the final output reflects merged evidence.

Required environment:
pdf2md (plus at least two backend environments)

Preconditions:
At least two backends are configured and enabled.
Both backend conda environments are functional.

Commands:

```bash
conda run -n pdf2md pdf2md convert test_visual.pdf \
    --config pdf2md.backends.toml \
    --out-dir /tmp/pdf2md_multi_test \
    --verbose
```

Verification procedure:

1. Run the command. Record exit code.
2. Open `consensus/consensus_ir.json`.
3. Verify `backends` array has at least two entries.
4. Inspect `pages[0].blocks[0]`. Verify it has:
   - `selection_mode` (expect `agreed` or `single_source`)
   - `agreement_score` > 0
   - `candidate_ids` with entries from different backends
5. Open `consensus/reports/consensus_report.json`. Verify
   `backend_summary` has entries for both backends.

Pass criteria:

```text
Consensus IR lists 2+ backends.
At least some blocks have selection_mode = "agreed".
candidate_ids reference blocks from different backends.
```

Fail criteria:

```text
Consensus IR lists only one backend when two were enabled.
All blocks are single_source despite multiple backends.
```

Evidence to record:

```text
Paste backends array from consensus_ir.json.
Paste one agreed block showing candidate_ids from different backends.
Paste backend_summary from consensus_report.json.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_pipeline_artifacts.py -q
conda run -n pdf2md pytest tests/test_pipeline_orchestrator.py -q
conda run -n pdf2md pytest tests/test_pipeline_cli.py -q
```

Human verification test matrix:

```text
pdf2md convert --help
pdf2md convert test_visual.pdf --dry-run --verbose
pdf2md convert test_visual.pdf --out-dir /tmp/pdf2md_pipeline_test --verbose
pdf2md convert test_visual.pdf --out-dir /tmp/pdf2md_multi_test --verbose (multi-backend)
```

Failure classes:

repository_defect:
The orchestrator logic is wrong, a stage call fails due to implementation
error, or the pipeline manifest schema is invalid.

environment_missing:
Backend conda environments are not configured, git is not installed, or
required system packages are absent.

backend_failure:
A backend subprocess fails. This is expected for some environments and
must be classified separately from repository defects.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan.

human_procedure_error:
The human ran the wrong command or used the wrong config.

upstream_dependency_issue:
A third-party package changed behaviour.

permission_or_filesystem_error:
The command cannot write to the output directory.

timeout:
A backend did not finish within the configured timeout.

Failure handling:

If failure_class is repository_defect:
The agent must fix the implementation or report a blocker.

If failure_class is backend_failure:
The orchestrator must handle this gracefully: record the failure, proceed
with remaining backends, and report partial results.

If failure_class is environment_missing:
The human must configure the environment. This does not block agent tests
because agent tests mock backend execution.

---

## 9. Checkpoints, push policy, and hand-off

Checkpoint C0: Plan ready

Required before agent starts:

```text
status is active
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
all pass criteria satisfied
failure classes recorded for any failures
human verification report completed
status set to human_verified by a human
```

Checkpoint C3: Plan finished and promoted

Required before promotion:

```text
status is human_verified
previous plan is archived
history.md summary is prepared or updated
next_plan.md is promoted to current_plan.md (Plan 19)
new next_plan.md is created
ROADMAP.md progress is updated only if explicitly approved by the human
```

Push and PR policy:

```text
The agent may push an implementation branch if the plan allows it.
The agent may open a draft PR if the plan allows it.
The agent must not merge to main.
The agent must not direct-push to main.
```

Hand-off procedure after human verification:

1. Archive this plan as plans/archive/plan-18-single-document-orchestrator.md.
2. Append a milestone summary to history.md.
3. Promote next_plan.md to current_plan.md (Plan 19).
4. Create new next_plan.md.
5. Record commit SHA or PR number.
6. Confirm whether ROADMAP.md progress should change.

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan: 18
Status:
Branch:
Commit or PR:
Files changed:
Forbidden files touched:
Tasks attempted:
Automated tests run:
Automated tests passed:
Automated tests failed:
Failure classes:
Environment failures:
Dependencies added:
External tools used:
Output artefacts created:
Human verification still required:
Blockers:
Next recommended action:
```

Human verification report template:

```text
Plan: 18
Reviewer:
Date:
Environment:
Backends tested:
Commands run:
Exit codes:
Output files checked:
Stage statuses:
Consensus backends:
Consensus mode (agreed/single_source):
Export files:
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
5. Were failures classified correctly?
6. Is `pipeline/artifacts.py` no longer a placeholder?
7. Does the orchestrator call stage modules via Python API (not subprocess)?
8. Is backend execution the only subprocess call?
9. Does the orchestrator handle all-backends-fail gracefully?
10. Does single-backend mode produce valid output?
11. Does multi-backend mode produce consensus with agreement scores?
12. Is the `run-backends` command unchanged?
13. Does `--dry-run` produce no side effects?
14. Is `pipeline_manifest.json` valid and complete?
15. Does `pipeline_summary.txt` accurately reflect stage outcomes?
16. Were all human verification checkpoints run exactly as written?
17. Is the next plan clearly identified?
18. Is it safe to mark this plan human_verified?
19. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-24 — draft — human — Plan 18 created for single-document orchestrator
```

---

## 11. Design notes

### Current gap illustrated

Today, processing a single document requires six manual invocations:

```bash
# 1. Run backends
pdf2md run-backends input.pdf --config pdf2md.backends.toml

# 2. Connect each backend's raw output to IR
python backend/mineru/connector.py \
    --raw-dir .tmp/input/raw/mineru --document-id input --out-dir .tmp/input/connector
python backend/paddleocr/connector.py \
    --raw-dir .tmp/input/raw/paddleocr --document-id input --out-dir .tmp/input/connector

# 3. (Optional) Copy pre-computed priors
cp calibration_output/priors/*.json .tmp/input/priors/

# 4. Build consensus
python tools/build_consensus.py \
    --connector-root .tmp/input/connector --document-id input \
    --priors-root .tmp/input/priors --out-dir .tmp/input/consensus

# 5. Build linked structure
python tools/build_linked_structure.py \
    --consensus-ir .tmp/input/consensus/consensus_ir.json \
    --entities-root .tmp/input/connector \
    --priors-root .tmp/input/priors \
    --out-dir .tmp/input/linked

# 6. Export
python tools/export_linked_docling.py \
    --linked-structure .tmp/input/linked/linked_structure.json \
    --consensus-ir .tmp/input/consensus/consensus_ir.json \
    --out-dir .tmp/input/export
```

After this plan, one command replaces all six:

```bash
pdf2md convert input.pdf --config pdf2md.backends.toml
```

### Stage 3 (calibration) clarification

Calibration priors are a **corpus-level** artefact. They are computed once by
running `tools/calibrate_priors.py` against ground-truth fixtures and the
connector output of multiple documents. The result is a set of
`priors/<backend>.json` files.

The orchestrator does NOT re-run calibration matching per document. It only
**loads** pre-existing priors if `--priors-dir` is provided. Without priors,
the consensus scoring uses default confidence (0.5) for all backends and
block kinds. This is correct single-document behaviour.

The recommended workflow is:

1. Run calibration once on the ground-truth corpus → produces `priors/`.
2. Use those priors for all subsequent `pdf2md convert` invocations via
   `--priors-dir priors/`.

### Connector dispatch

The orchestrator must detect which `BackendConnectorConfig` to use for each
backend. The approach:

1. Try to import `backend/<name>/connector.py` and call its `connect()`
   function (which already wraps `connect_raw_dir` with backend-specific
   config).
2. If no backend-specific connector exists, fall back to
   `connect_raw_dir` with default `BackendConnectorConfig`.

The existing backend connectors (`backend/mineru/connector.py`, etc.) already
handle backend-specific markdown file patterns and manifest locations.

### Exit code convention

```text
0 — all stages succeeded, all backends succeeded
1 — pipeline failed (zero backends or critical stage failure)
2 — partial success (some backends failed, but final output was produced)
```

### Relationship to existing run-backends command

The `run-backends` command remains unchanged. It is useful for:
- Running backends without downstream processing.
- Debugging backend execution independently.
- Producing raw output for manual connector/consensus invocation.

The `convert` command is a superset: it calls `run-backends` logic internally
as stage 1 and then continues through stages 2–6.

### Relationship to Plan 16 (MVP runner)

Plan 16 specified a `tools/run_mvp_pipeline.py` entry point. This plan
supersedes that approach by implementing the orchestrator directly in the
package (`pipeline/orchestrator.py`) and exposing it via the public CLI.
The `tools/` scripts remain as standalone utilities for advanced users and
debugging.
