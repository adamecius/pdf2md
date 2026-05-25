# Plan 16 — End-to-End Runner and MVP Corpus Evaluation

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
Phase 5 consumer — uses evaluation and confidence outputs
MVP boundary — local end-to-end corpus execution

Current roadmap estimate:
Overall project from approximately 83–85% toward 84–86% after successful completion.

Note:
This is the MVP boundary plan. It validates that the existing staged pipeline can be run locally from input PDF or selected corpus input through final Docling, RAG, Markdown, manifest and readiness reports. It does not mean production readiness.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 16 of the pre-MVP implementation sequence.

Previous plan:
Plan 15 — Docling Export Validation

Required previous plan status:
human_verified

Next plan after completion:
Plan 17+ — Production Readiness, Packaging and Operational Hardening

Branch name:
plan-16-end-to-end-runner-mvp-corpus-evaluation

---

## 1. Purpose

This plan implements the first local MVP runner by extending the existing `src/pdf2md/pipeline/` skeleton and adding a standalone `tools/run_mvp_pipeline.py` entry point.

The repository already has pipeline stubs:

```text
src/pdf2md/pipeline/artifacts.py
src/pdf2md/pipeline/convert.py
```

Plan 16 must extend these stubs rather than bypassing them.

The repository also has a Typer CLI in:

```text
src/pdf2md/cli/main.py
```

That CLI contains a placeholder `convert` command and a working backend-running command. Plan 16 must not harden or replace the public CLI. Public CLI hardening belongs to Plan 17+.

The core question is:

```text
Can the project run a complete local MVP pipeline from one PDF, and then over a selected corpus subset, while reusing existing stage logic and producing auditable final artefacts and readiness reports?
```

The intended MVP path is:

```text
input PDF or selected corpus document
backend execution or existing backend outputs
connector / PageExtractionIR
EntityProposalDocument
CalibrationPriorDocument
ConsensusIR
LinkedStructure
Docling JSON
RAG chunks
Markdown preview
pipeline manifest
stage status
MVP corpus evaluation summary
```

Plan 16 defines MVP as a local, auditable and reproducible pipeline run. It does not claim production readiness.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

README.md is the public entry point.

PLAN_TEMPLATE.md is the standard format for executable plans.

current_plan.md is the active execution contract for agents.

next_plan.md is the next planned execution contract.

history.md records completed milestones after human verification.

run_log.md is append-only and implicitly allowed when required by agent.md.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-16-end-to-end-runner-mvp-corpus-evaluation
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan unless Plan 15 has been marked human_verified and archived.
8. Do not mark this plan human_verified or finished. Only the human reviewer may do that.
9. Append to run_log.md only when required by agent.md and only in append-only mode.

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

Backend execution is environment-sensitive. The runner may use subprocess or existing backend-runner paths for backend execution when conda environment isolation is required. Downstream stages should use module-level orchestration by default.

---

## 4. Scope, constraints and dependencies

In scope:

1. Extend existing pipeline stubs in `src/pdf2md/pipeline/artifacts.py` and `src/pdf2md/pipeline/convert.py`.
2. Add thin runner modules inside `src/pdf2md/pipeline/`.
3. Add standalone MVP runner CLI at `tools/run_mvp_pipeline.py`.
4. Reuse existing stage logic from Plans 8–15.
5. Support one-document mode with `--pdf`, `--out-dir` and optional `--work-dir`.
6. Support corpus/subset mode with `--corpus-root`, `--out-dir`, optional `--work-dir`, `--max-documents` and optional `--document-list`.
7. Reuse existing backend execution path or consume existing backend outputs.
8. Use module-level orchestration by default for connector, calibration, consensus, linking and export stages.
9. Use subprocess fallback only when environment isolation or lack of a stable module entrypoint requires it.
10. Produce machine-readable manifest and per-stage status.
11. Produce human-readable summary.
12. Produce final Docling, RAG and Markdown artefacts for successful documents.
13. Produce MVP corpus evaluation and readiness classification.
14. Keep one-document output flat.
15. Use nested per-document output layout only for corpus/subset mode.

Out of scope:

1. Public Typer CLI hardening in `src/pdf2md/cli/main.py`.
2. Redesigning backends.
3. Adding new OCR models.
4. Rewriting connector architecture.
5. Redesigning calibration.
6. Redesigning consensus.
7. Redesigning linking.
8. Redesigning export.
9. Production deployment.
10. Web app or API server.
11. Performance optimisation beyond basic reliability.
12. Modifying ROADMAP.md, README.md, project.md, current_plan.md or next_plan.md.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before declaring the MVP boundary reached.
5. The runner must reuse existing stage logic. It must not fork separate implementations of backend extraction, connector validation, calibration, consensus, linking or export.
6. Backend execution may use the existing backend runner and subprocess/environment isolation.
7. Connector, calibration, consensus, linking and export stages must use module-level orchestration by default.
8. Subprocess fallback for non-backend stages must be explicitly justified in the agent report.
9. The existing `src/pdf2md/pipeline/artifacts.py` and `src/pdf2md/pipeline/convert.py` stubs must be extended or replaced in place.
10. The runner must not modify `src/pdf2md/cli/main.py`.
11. One-document mode must support `--pdf` and `--out-dir`.
12. One-document mode must support `--work-dir`, defaulting to `<out-dir>/work` when omitted.
13. Corpus mode must support `--corpus-root`, `--out-dir`, `--work-dir`, `--max-documents`, and optionally `--document-list`.
14. Do not add `--resume` in this plan unless its behaviour is fully defined in an amended plan.
15. Safe rerun into a clean output directory is sufficient for MVP.
16. If a required stage artefact is missing, the runner must report the missing artefact and classify the failure.
17. If a backend is not ready, classify it using earlier backend readiness conventions.
18. The runner must produce a machine-readable manifest.
19. The runner must produce a human-readable summary.
20. The runner must not claim production readiness.
21. The runner must not claim MVP completion before human verification.

Allowed Python dependencies:

```text
none beyond existing repository dependencies
```

Allowed external tools:

```text
none beyond tools already required by previous plans and available local backend environments
```

Allowed environment-modifying commands:

```text
none
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these implementation and test files:

```text
src/pdf2md/pipeline/artifacts.py
src/pdf2md/pipeline/convert.py
src/pdf2md/pipeline/__init__.py
src/pdf2md/pipeline/runner.py
src/pdf2md/pipeline/reporting.py
src/pdf2md/pipeline/io.py

tools/run_mvp_pipeline.py

tests/test_mvp_pipeline_runner.py
tests/test_mvp_pipeline_cli.py
tests/test_mvp_pipeline_reporting.py
```

The agent may create test fixtures only under:

```text
tests/data/mvp_pipeline_fixtures/**
```

run_log.md is append-only and implicitly allowed when required by agent.md. It is not part of the implementation whitelist and must not be rewritten.

The agent may create temporary outputs only through CLI execution. These outputs must not be committed by default.

One-document mode expected output layout:

```text
<out-dir>/pipeline_manifest.json
<out-dir>/pipeline_summary.txt
<out-dir>/stage_status.json
<out-dir>/docling/<doc_id>.docling.json
<out-dir>/rag/<doc_id>.rag_chunks.json
<out-dir>/markdown/<doc_id>.preview.md
<out-dir>/reports/export_report.json
<out-dir>/export_manifest.json
```

Corpus/subset mode expected output layout:

```text
<out-dir>/pipeline_manifest.json
<out-dir>/pipeline_summary.txt
<out-dir>/mvp_corpus_evaluation.json
<out-dir>/mvp_corpus_summary.txt
<out-dir>/documents/<doc_id>/stage_status.json
<out-dir>/documents/<doc_id>/docling/<doc_id>.docling.json
<out-dir>/documents/<doc_id>/rag/<doc_id>.rag_chunks.json
<out-dir>/documents/<doc_id>/markdown/<doc_id>.preview.md
<out-dir>/documents/<doc_id>/reports/export_report.json
<out-dir>/documents/<doc_id>/export_manifest.json
```

The agent must not modify these files unless this plan is explicitly amended by the human reviewer:

```text
README.md
ROADMAP.md
PLAN_TEMPLATE.md
project.md
current_plan.md
next_plan.md
history.md
agent.md
pyproject.toml

src/pdf2md/cli/main.py

src/pdf2md/local/*
src/pdf2md/connectors/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

tools/backend_smoke.py
tools/validate_connectors_page_ir.py
tools/validate_entity_proposals.py
tools/vocabulary_alignment_check.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py
tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py

backend/*
groundtruth/corpus/*
```

If a defect is found in a stage implementation outside the pipeline whitelist, the agent must stop and report a blocker. Do not modify those files under this plan without a human amendment.

Required manifest characteristics:

```text
schema_name
schema_version
generated_at
mode: one_document | corpus_subset
input_pdf or corpus_root
out_dir
work_dir
selected_backends
documents
per-document stage statuses
final artefact paths
warnings
errors
MVP readiness
```

Stage status values:

```text
pending
running
succeeded
skipped
failed
blocked
```

Document result values:

```text
passed
passed_with_warnings
failed
blocked
skipped
```

MVP readiness values:

```text
MVP_ready
MVP_ready_with_warnings
MVP_not_ready
diagnostic_only
```

---

## 6. Agent tasks

Task A1:

Title:
Implement pipeline runner skeleton and path model.

Goal:
Extend the existing pipeline stubs and implement a thin module-level orchestration foundation.

Files allowed:

```text
src/pdf2md/pipeline/artifacts.py
src/pdf2md/pipeline/convert.py
src/pdf2md/pipeline/__init__.py
src/pdf2md/pipeline/runner.py
src/pdf2md/pipeline/reporting.py
src/pdf2md/pipeline/io.py
tools/run_mvp_pipeline.py
tests/test_mvp_pipeline_runner.py
tests/test_mvp_pipeline_cli.py
tests/test_mvp_pipeline_reporting.py
tests/data/mvp_pipeline_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Extend `src/pdf2md/pipeline/artifacts.py` with path helpers for work and output artefacts.
2. Extend `src/pdf2md/pipeline/convert.py`, including the existing `convert_pdf()` placeholder.
3. Create `src/pdf2md/pipeline/__init__.py` if missing.
4. Create `src/pdf2md/pipeline/runner.py` for orchestration logic.
5. Create `src/pdf2md/pipeline/io.py` for manifest and status read/write helpers.
6. Create `src/pdf2md/pipeline/reporting.py` for human-readable summaries.
7. Create `tools/run_mvp_pipeline.py` as the standalone MVP runner CLI.
8. Do not modify `src/pdf2md/cli/main.py`.
9. Implement stage states: pending, running, succeeded, skipped, failed, blocked.
10. Implement failure classes for stage failures.
11. Prefer module-level orchestration for non-backend stages.
12. Allow backend execution through the existing backend runner or subprocess/environment isolation when needed.
13. Do not duplicate stage internals.
14. Write tests for stage state transitions, path layout, manifest writing and CLI parsing.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_mvp_pipeline_runner.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_cli.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_reporting.py -q
```

Expected output:
Pipeline skeleton exists, path helpers are functional, runner CLI help works, and tests validate state/report contracts.

Completion evidence:
Agent must report files changed, CLI flags, manifest schema, path layout and automated test results.

Human verification required:
no. Covered by H1.

Task A2:

Title:
Implement one-document MVP runner.

Goal:
Run one real PDF through the staged local MVP path, producing final artefacts or precise blockers.

Files allowed:

```text
src/pdf2md/pipeline/artifacts.py
src/pdf2md/pipeline/convert.py
src/pdf2md/pipeline/__init__.py
src/pdf2md/pipeline/runner.py
src/pdf2md/pipeline/reporting.py
src/pdf2md/pipeline/io.py
tools/run_mvp_pipeline.py
tests/test_mvp_pipeline_runner.py
tests/test_mvp_pipeline_cli.py
tests/test_mvp_pipeline_reporting.py
tests/data/mvp_pipeline_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Support `--pdf`.
2. Support `--out-dir`.
3. Support `--work-dir`, defaulting to `<out-dir>/work` when omitted.
4. Support `--backends`.
5. Support `--strict`.
6. Support `--verbose`.
7. Do not require corpus-mode flags for one-document mode.
8. Reuse existing backend execution path or consume existing backend outputs.
9. Use module-level orchestration by default after backend execution.
10. Produce `pipeline_manifest.json`.
11. Produce `pipeline_summary.txt`.
12. Produce `stage_status.json`.
13. Produce final Docling, RAG and Markdown artefacts if the full path succeeds.
14. Record every skipped stage with reason.
15. Record every failed stage with failure class.
16. Do not hide backend or environment failures.
17. Do not claim production readiness.

Command template:

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py --pdf <INPUT_PDF> --out-dir groundtruth/runs/mvp_one_document --work-dir groundtruth/runs/mvp_one_document/work --backends <BACKEND_LIST> --strict --verbose
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_mvp_pipeline_runner.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_cli.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_reporting.py -q
```

Expected output:
One-document runner executes or reports blockers with structured status.

Completion evidence:
Agent must report command, exit behaviour, manifest path, stage status path, final artefacts or blockers.

Human verification required:
yes. Covered by H2.

Task A3:

Title:
Implement corpus/subset mode and MVP readiness reporting.

Goal:
Run the same runner over a selected MVP corpus subset and summarise pass/fail/readiness status.

Files allowed:

```text
src/pdf2md/pipeline/artifacts.py
src/pdf2md/pipeline/convert.py
src/pdf2md/pipeline/__init__.py
src/pdf2md/pipeline/runner.py
src/pdf2md/pipeline/reporting.py
src/pdf2md/pipeline/io.py
tools/run_mvp_pipeline.py
tests/test_mvp_pipeline_runner.py
tests/test_mvp_pipeline_cli.py
tests/test_mvp_pipeline_reporting.py
tests/data/mvp_pipeline_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Support `--corpus-root`.
2. Support `--out-dir`.
3. Support `--work-dir`, defaulting to `<out-dir>/work` when omitted.
4. Support `--max-documents`.
5. Support optional `--document-list`.
6. Support `--backends`.
7. Support `--strict`.
8. Support `--verbose`.
9. Run selected corpus documents.
10. Produce per-document `stage_status.json`.
11. Produce `mvp_corpus_evaluation.json`.
12. Produce `mvp_corpus_summary.txt`.
13. Classify each document as passed, passed_with_warnings, blocked, failed or skipped.
14. Report stage-level bottlenecks.
15. Report backend eligibility.
16. Report final export availability.
17. Report confidence/warning summary.
18. Do not require all documents to pass unless strict mode is enabled.
19. In strict mode, fail if any selected document fails.
20. Do not add `--resume` in this plan.

Command template:

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py --corpus-root groundtruth/corpus/latex --out-dir groundtruth/runs/mvp_corpus --work-dir groundtruth/runs/mvp_corpus/work --max-documents <N> --backends <BACKEND_LIST> --verbose
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_mvp_pipeline_runner.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_cli.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_reporting.py -q
```

Expected output:
Corpus/subset run report with per-document and aggregate status.

Completion evidence:
Agent must report selected corpus subset, document results, failures, final artefacts and MVP readiness.

Human verification required:
yes. Covered by H3.

---

## 7. Human verification checkpoints

Checkpoint H1:

Title:
Runner CLI and architecture gate.

Purpose:
Confirm that the MVP runner exists, exposes the expected CLI, extends the pipeline package, and does not modify the public Typer CLI.

Required environment:
pdf2md

Preconditions:
Plan 15 is human_verified.
Tasks A1 is complete.

Command:

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py --help
```

Verification procedure:

1. Run the help command.
2. Confirm the tool exists.
3. Confirm it supports one-document mode with `--pdf`, `--out-dir`, `--work-dir`, `--backends`, `--strict`, `--verbose`.
4. Confirm it supports corpus mode with `--corpus-root`, `--out-dir`, `--work-dir`, `--max-documents`, optional `--document-list`, `--backends`, `--strict`, `--verbose`.
5. Confirm `--work-dir` is optional and defaults to `<out-dir>/work`.
6. Confirm `--resume` is not required.
7. Confirm `src/pdf2md/cli/main.py` was not modified.
8. Confirm the agent report explains backend subprocess/environment isolation versus module-level downstream orchestration.
9. Confirm the runner does not claim production readiness.

Pass criteria:

```text
Runner CLI exists.
One-document mode is clear.
Corpus/subset mode is clear.
--work-dir behaviour is defined.
Stage reuse is documented.
src/pdf2md/cli/main.py is untouched.
No production readiness is claimed.
```

Fail criteria:

```text
Runner missing.
Flags ambiguous.
--work-dir behaviour undefined.
Public CLI modified.
Stage internals duplicated.
Production readiness claimed.
```

Evidence to record:

```text
Paste help output or relevant flags.
Paste git diff --name-only evidence for cli/main.py untouched.
Paste orchestration architecture summary.
```

Checkpoint H2:

Title:
One-document end-to-end run.

Purpose:
Confirm that one real PDF can run through the local MVP path or produce precise blockers.

Required environment:
pdf2md plus any required backend environments for selected backends.

Preconditions:
H1 passed.
Task A2 is complete.
A real input PDF is available.
Selected backends are identified.

Command:

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py --pdf <INPUT_PDF> --out-dir groundtruth/runs/mvp_one_document --work-dir groundtruth/runs/mvp_one_document/work --backends <BACKEND_LIST> --strict --verbose
```

Expected output files:

```text
groundtruth/runs/mvp_one_document/pipeline_manifest.json
groundtruth/runs/mvp_one_document/pipeline_summary.txt
groundtruth/runs/mvp_one_document/stage_status.json
```

If successful:

```text
groundtruth/runs/mvp_one_document/docling/<doc_id>.docling.json
groundtruth/runs/mvp_one_document/rag/<doc_id>.rag_chunks.json
groundtruth/runs/mvp_one_document/markdown/<doc_id>.preview.md
groundtruth/runs/mvp_one_document/reports/export_report.json
groundtruth/runs/mvp_one_document/export_manifest.json
```

Verification procedure:

1. Replace placeholders with a real PDF and backend list.
2. Run the command exactly as written.
3. Confirm command exits 0, or exits non-zero with precise blocker classification.
4. Open `pipeline_manifest.json`.
5. Open `pipeline_summary.txt`.
6. Open `stage_status.json`.
7. Confirm all stages are marked succeeded, skipped, failed or blocked.
8. If successful, confirm final Docling, RAG and Markdown artefacts exist.
9. If blocked or failed, confirm reason and failure class are explicit.
10. Confirm no stage fails silently.
11. Confirm no production readiness is claimed.

Pass criteria:

```text
Manifest exists.
Summary exists.
Stage status exists.
All stages are classified.
Final artefacts exist for successful run, or blockers are precise.
No silent failure.
No production readiness claim.
```

Fail criteria:

```text
No manifest.
No summary.
No stage status.
Unclassified failure.
Missing final artefacts without explanation.
Silent backend or environment failure.
Production readiness claimed.
```

Evidence to record:

```text
Paste command.
Paste exit code.
Paste manifest path.
Paste stage status summary.
Paste final artefact paths or blocker classification.
Paste MVP readiness status.
```

Checkpoint H3:

Title:
MVP corpus/subset run and readiness decision.

Purpose:
Confirm that the runner can process a selected corpus subset and produce an MVP readiness decision.

Required environment:
pdf2md plus any required backend environments for selected backends.

Preconditions:
H2 passed or human approved proceeding to corpus mode with documented warnings.
Task A3 is complete.
Corpus root exists.
Selected subset size is chosen by the human.

Command:

```bash
conda run -n pdf2md python tools/run_mvp_pipeline.py --corpus-root groundtruth/corpus/latex --out-dir groundtruth/runs/mvp_corpus --work-dir groundtruth/runs/mvp_corpus/work --max-documents <N> --backends <BACKEND_LIST> --verbose
```

Expected output files:

```text
groundtruth/runs/mvp_corpus/pipeline_manifest.json
groundtruth/runs/mvp_corpus/pipeline_summary.txt
groundtruth/runs/mvp_corpus/mvp_corpus_evaluation.json
groundtruth/runs/mvp_corpus/mvp_corpus_summary.txt
```

For each selected document:

```text
groundtruth/runs/mvp_corpus/documents/<doc_id>/stage_status.json
```

If a document passes:

```text
groundtruth/runs/mvp_corpus/documents/<doc_id>/docling/<doc_id>.docling.json
groundtruth/runs/mvp_corpus/documents/<doc_id>/rag/<doc_id>.rag_chunks.json
groundtruth/runs/mvp_corpus/documents/<doc_id>/markdown/<doc_id>.preview.md
groundtruth/runs/mvp_corpus/documents/<doc_id>/reports/export_report.json
groundtruth/runs/mvp_corpus/documents/<doc_id>/export_manifest.json
```

Verification procedure:

1. Run on a human-selected MVP subset.
2. Confirm `mvp_corpus_evaluation.json` exists.
3. Confirm `mvp_corpus_summary.txt` exists.
4. Confirm per-document stage statuses exist.
5. Confirm final artefacts exist for passed documents.
6. Confirm failed or blocked documents have classified reasons.
7. Confirm backend/environment issues are separated from repository defects.
8. Confirm readiness is one of `MVP_ready`, `MVP_ready_with_warnings`, `MVP_not_ready`, or `diagnostic_only`.
9. Confirm no production readiness is claimed.

Pass criteria:

```text
Corpus/subset run is auditable.
Aggregate reports exist.
Per-document statuses exist.
Final artefacts are produced for passed documents.
Failures are classified.
MVP readiness decision is explicit.
No production readiness claim.
```

Fail criteria:

```text
No aggregate report.
No per-document status.
Unclassified failures.
Final artefacts missing without reason.
Backend/environment failures hidden.
Production readiness claimed.
```

Evidence to record:

```text
Paste command.
Paste exit code.
Paste corpus subset size.
Paste documents selected.
Paste pass/warning/fail/block counts.
Paste MVP readiness decision.
Paste representative final artefact paths.
Paste blocker summary if any.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_mvp_pipeline_runner.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_cli.py -q
conda run -n pdf2md pytest tests/test_mvp_pipeline_reporting.py -q
```

Recommended fast regression checks, if available and not environment-heavy:

```bash
conda run -n pdf2md pytest tests/test_export_io_cli.py -q
conda run -n pdf2md pytest tests/test_build_linked_structure_cli.py -q
conda run -n pdf2md pytest tests/test_build_consensus_cli.py -q
```

Human verification test matrix:

```text
H1 runner CLI and architecture gate
H2 one-document end-to-end run
H3 MVP corpus/subset run and readiness decision
```

Failure classes:

missing_input:
Required input PDF, corpus document, or stage artefact is missing.

backend_not_ready:
Selected backend environment, model or dependency is unavailable.

backend_failed:
Backend execution failed after starting.

connector_failed:
Connector or PageExtractionIR stage failed.

entity_validation_failed:
EntityProposalDocument stage failed.

calibration_failed:
Calibration prior stage failed.

consensus_failed:
ConsensusIR stage failed.

linking_failed:
LinkedStructure stage failed.

export_failed:
Docling/RAG/Markdown export stage failed.

manifest_failed:
Manifest or stage status output is missing or invalid.

reporting_failed:
Pipeline summary or corpus evaluation report is missing or invalid.

environment_missing:
Required conda environment, model, credential or system dependency is missing.

scope_violation:
Plan 16 modifies forbidden stage internals, public CLI, roadmap or docs.

human_procedure_error:
Human ran the wrong command, used wrong paths or inspected stale outputs.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

Failure handling:

If failure_class is missing_input:
Provide the input or mark the document blocked.

If failure_class is backend_not_ready:
Record backend status and proceed only if human approves reduced backend coverage.

If failure_class is backend_failed:
Classify as backend/environment failure unless evidence shows repository orchestration defect.

If failure_class is connector_failed, entity_validation_failed, calibration_failed, consensus_failed, linking_failed or export_failed:
Do not modify forbidden stage internals. Report blocker unless a human amends the plan.

If failure_class is manifest_failed or reporting_failed:
Fix pipeline reporting inside the whitelist.

If failure_class is environment_missing:
Human or environment owner must fix the environment, or the run remains diagnostic.

If failure_class is scope_violation:
Reject the plan output and revise.

If failure_class is human_procedure_error:
Human checkpoint must be rerun correctly.

If failure_class is test_expectation_wrong:
The plan must be revised by a human before continuing.

MVP readiness statuses:

MVP_ready:
Selected corpus subset completes the full path and final artefacts validate.

MVP_ready_with_warnings:
Pipeline completes with documented warnings or deferred backends, but outputs are usable.

MVP_not_ready:
Pipeline cannot complete the selected subset, or failures are unclassified.

diagnostic_only:
Pipeline run is only diagnostic because prerequisites or environments are incomplete.

---

## 9. Checkpoints, push policy and hand-off

Checkpoint C0: Plan ready

Required before agent starts:

```text
status is active
Plan 15 status is human_verified or human explicitly approves drafting only
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
no forbidden files modified without human amendment
no undeclared dependencies used
existing pipeline stubs extended
src/pdf2md/cli/main.py untouched
runner CLI created
one-document mode implemented
corpus/subset mode implemented
manifest/report outputs generated or blockers recorded
agent report completed
status set to agent_complete or human_verification_required
```

Checkpoint C2: Human verification complete

Required before merge or milestone completion:

```text
H1 runner CLI and architecture gate completed
H2 one-document run completed
H3 corpus/subset run completed
all expected output files produced or failures classified
MVP readiness decision made by human
human verification report completed
status set to human_verified by a human
```

Checkpoint C3: Plan finished and promoted

Required before promotion:

```text
status is human_verified
Plan 16 is archived after completion
history.md summary is prepared or updated
pre-MVP sequence completion is recorded only with human approval
Plan 17+ production readiness plan is prepared if desired
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
declaring the MVP boundary reached
preparing production readiness work
updating ROADMAP.md progress
```

Hand-off procedure after human verification:

1. Archive current_plan.md as:

```text
plans/archive/plan-16-end-to-end-runner-mvp-corpus-evaluation.md
```

2. Append a milestone summary to history.md.
3. Record MVP readiness decision.
4. Record commit SHA or PR number.
5. Record human verification evidence.
6. Confirm whether ROADMAP.md progress should change.
7. Prepare Plan 17+ production readiness plan only if explicitly requested.

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
Pipeline stubs extended:
src/pdf2md/cli/main.py touched: yes/no
Runner command:
One-document command:
Corpus/subset command:
Work dir behaviour:
Backend orchestration method:
Downstream module-level orchestration summary:
Documents processed:
Documents passed:
Documents passed with warnings:
Documents failed:
Documents blocked:
Failure classes:
Final Docling outputs:
Final RAG outputs:
Final Markdown outputs:
Manifest path:
Corpus evaluation path:
MVP readiness:
Automated tests run:
Automated tests passed:
Automated tests failed:
Blockers:
Next recommended action:
```

Human verification report template:

```text
Plan:
Reviewer:
Date:
Environment:
Commands run:
Input PDF:
Corpus root:
Documents selected:
Backends selected:
Work dirs:
Exit codes:
Manifest checked:
Per-document status checked:
Final artefacts checked:
Failures classified:
Warnings accepted:
MVP readiness decision:
Production readiness claimed: yes/no
Evidence:
Decision:
human_verified or rejected
```

Reviewer checklist:

1. Did the agent modify only whitelisted files?
2. Did the agent avoid all forbidden files?
3. Was run_log.md append-only if touched?
4. Was `src/pdf2md/cli/main.py` untouched?
5. Were existing pipeline stubs extended rather than ignored?
6. Did the runner avoid duplicating stage internals?
7. Did backend execution use existing backend runner or justified environment-isolated execution?
8. Did downstream stages use module-level orchestration by default?
9. Were subprocess fallbacks justified?
10. Did one-document mode support `--pdf` and `--out-dir`?
11. Was `--work-dir` supported or defaulted to `<out-dir>/work`?
12. Did corpus mode support `--corpus-root` and `--max-documents`?
13. Was `--resume` avoided or explicitly absent?
14. Did one-document mode keep a flat output layout?
15. Did corpus mode use nested per-document layout?
16. Did the runner produce `pipeline_manifest.json`?
17. Did the runner produce `pipeline_summary.txt`?
18. Did the runner produce `stage_status.json`?
19. Did passed documents produce Docling JSON?
20. Did passed documents produce RAG chunks?
21. Did passed documents produce Markdown preview?
22. Were failures classified?
23. Were skipped stages explained?
24. Were backend/environment issues separated from repository defects?
25. Was MVP readiness explicit?
26. Was production readiness not claimed?
27. Were all automated tests run?
28. Did any automated test fail?
29. Were human checkpoints H1, H2 and H3 completed?
30. Is it safe to mark the pre-MVP sequence complete?
31. Is it safe to prepare Plan 17+ production readiness?
32. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-09 — draft — human — Plan 16 created from ROADMAP.md and PLAN_TEMPLATE.md
2026-05-09 — active — human — approved for agent execution
2026-05-09 — agent_in_progress — agent — branch created
2026-05-09 — agent_complete — agent — automated tests passed and MVP runner generated reports
2026-05-09 — human_verification_required — agent — awaiting human MVP checks
2026-05-09 — human_verified — human — all checkpoints passed
2026-05-09 — finished — human — archived and pre-MVP sequence closed
```
