# Plan 10 — Connector Implementation and PageExtractionIR Validation

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
Phase 2 — Extraction and normalisation

Current roadmap estimate:
Phase 2 from approximately 70% toward 80%

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 10 of the pre-MVP implementation sequence, ending at Plan 16.

Previous plan:
Plan 9 — Real Backend Smoke Readiness

Required previous plan status:
human_verified

Next plan after completion:
Plan 11 — EntityProposalDocument Validation

Branch name:
plan-10-connector-pageextractionir-validation

---

## 1. Purpose

This plan validates that real raw backend outputs from Plan 9 can be converted through the repository connector path into valid and semantically useful `PageExtractionIR`.

Plan 10 is the first plan where real backend outputs enter the canonical extraction evidence model. It answers this question:

```text
Can successful Plan 9 backend outputs be normalised into PageExtractionIR with meaningful pages, blocks, text, block kinds, provenance, and raw artefact references?
```

The connector path may emit both `PageExtractionIR` and `EntityProposalDocument` in one call. Plan 10 may implement or harden the connector path as needed, but acceptance validates only the `PageExtractionIR` part.

`EntityProposalDocument` validation belongs to Plan 11.

Plan 10 does not run calibration, consensus, semantic linking, Docling export, RAG export, Markdown export, or the end-to-end runner.

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
git switch -c plan-10-connector-pageextractionir-validation
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 9 has been marked human_verified and archived.
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

This plan consumes existing Plan 9 backend smoke outputs. It does not execute real backends by default. If new backend execution is needed, that work belongs to Plan 9 or to a human-provided artefact outside Plan 10.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Inspect the existing connector architecture and reuse the existing connector entrypoint.
2. Use real raw backend output directories from Plan 9 where available.
3. Convert Plan 9 successful backend outputs into `PageExtractionIR`.
4. Validate `PageExtractionIR` structurally using the repository model/schema.
5. Perform semantic smoke validation of the resulting IR.
6. Report per-backend connector validation status.
7. Report page count, block count, block-kind counts, text presence, bbox presence, provenance presence, and raw artefact references.
8. Preserve raw backend artefact references.
9. Support incremental backend acceptance.
10. Write a machine-readable connector validation report.
11. Write a human-readable connector validation summary.
12. Add automated tests using fixtures or mocks that do not require real backend environments.
13. Avoid validating EntityProposalDocument as a Plan 10 pass/fail criterion.

Out of scope:

1. Running backend model scripts.
2. Installing backend environments.
3. Downloading model weights.
4. Modifying backend execution code.
5. Modifying backend configuration.
6. Creating a parallel connector architecture.
7. Validating EntityProposalDocument.
8. Running calibration.
9. Running consensus.
10. Running semantic linking.
11. Running Docling export.
12. Running RAG export.
13. Running Markdown export.
14. Running the end-to-end pipeline.
15. Editing ROADMAP.md.
16. Editing README.md.
17. Editing project.md.
18. Editing current_plan.md.
19. Editing next_plan.md.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. The agent must reuse the existing connector path if present, for example `connect_raw_dir()` or the closest existing connector entrypoint.
6. The agent must not validate `EntityProposalDocument` as part of Plan 10 acceptance.
7. The agent must not import calibration, consensus, linking, Docling export, RAG export, or end-to-end runner code for Plan 10 validation.
8. Pydantic/schema validity alone is not enough for full Plan 10 success; the human semantic smoke checkpoint must pass.
9. If real Plan 9 outputs are missing, the implementation may still be tested with fixtures or mocks, but human verification must classify the missing real outputs.
10. If a forbidden file must be changed, this plan is incomplete and must be revised by a human before implementation starts.

Allowed Python dependencies:

```text
none beyond existing repository dependencies
```

Allowed external tools for automated tests:

```text
none
```

Allowed external tools for human verification:

```text
none beyond local file and JSON inspection tools
```

Allowed environment-modifying commands:

```text
none
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these implementation and test files:

```text
src/pdf2md/local/connector_validation.py

tools/validate_connectors_page_ir.py

tests/test_connector_page_ir_validation.py

tests/data/connector_validation_fixtures/minimal_markdown_backend/output.md
tests/data/connector_validation_fixtures/missing_output_backend/.gitkeep
tests/data/connector_validation_fixtures/schema_failure_backend/output.md
```

The agent may modify connector code only if the existing connector path is incomplete or defective for PageExtractionIR validation. Any connector code change must be narrowly justified in the agent report.

Conditionally allowed connector files:

```text
src/pdf2md/connectors/*
backend/*/connector.py
```

Conditionally allowed connector changes are limited to:

```text
- reusing or exposing the existing connector entrypoint
- fixing connector defects that prevent PageExtractionIR output from validating
- preserving raw artefact references
- preserving backend provenance
- improving PageExtractionIR construction
```

Conditionally allowed connector changes must not:

```text
- validate EntityProposalDocument as a Plan 10 acceptance target
- implement calibration
- implement consensus
- implement semantic linking
- implement Docling export
- change backend execution behaviour
```

Expected output artefacts, produced by the CLI and not committed unless a later policy explicitly allows it:

```text
<out-dir>/connector_validation_report.json
<out-dir>/connector_validation_summary.txt
<out-dir>/<backend_name>/page_extraction_ir.json
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
run_log.md
pyproject.toml

config/backends.toml
config/*

src/pdf2md/local/backend_smoke.py
src/pdf2md/local/groundtruth.py
src/pdf2md/local/preflight.py
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

tools/backend_smoke.py
tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py

groundtruth/corpus/*
```

Required connector validation report contract:

```text
schema_name: pdf2md.ConnectorPageExtractionIRValidationReport
schema_version: 1.0.0
generated_at: ISO 8601 timestamp
tool_name: validate_connectors_page_ir
plan9_report_path: path or null
gate_mode: preferred | reduced
preferred_gate_passed: bool
minimum_gate_passed: bool
human_reduced_gate_required: bool
total_backends_considered: int
backends_validated: int
backends_failed: int
backends_deferred: int
results: list of per-backend validation entries
warnings: list of strings
metadata: dict
```

Per-backend connector validation entry contract:

```text
backend_name: str
plan9_status: str or null
raw_output_dir: str or null
connector_entrypoint: str
status: validated | connector_crash | schema_failed | missing_required_output | deferred_from_plan_9
page_count: int
block_count: int
block_kind_counts: dict
has_text: bool
has_bboxes: bool
has_provenance: bool
raw_artefact_references: list[str]
semantic_quality_passed: bool
warnings: list[str]
errors: list[str]
validation_error_summary: str or null
next_action: str
metadata: dict
```

Status taxonomy:

```text
validated:
  The connector produced PageExtractionIR and it validated structurally.
  Full success also requires semantic_quality_passed=true in human verification.

connector_crash:
  The connector raised an exception, exited unexpectedly, or could not complete.

schema_failed:
  The connector returned PageExtractionIR-like data, but schema/model validation failed.
  Detailed causes such as invalid bbox, invalid block kind, missing provenance, empty required fields, or invalid page structure must be recorded in warnings/errors/validation_error_summary, not as separate statuses.

missing_required_output:
  A Plan 9 success backend output directory lacks files required by the connector.

deferred_from_plan_9:
  Backend did not have Plan 9 status success, or no raw output directory is available, so connector validation is not attempted.
```

Gate rule:

```text
Preferred gate:
  At least two Plan 9 success backends produce structurally valid PageExtractionIR and pass semantic smoke validation.

Minimum gate:
  At least one Plan 9 success backend produces structurally valid PageExtractionIR and passes semantic smoke validation;
  all other Plan 9 success backends are classified;
  human reviewer explicitly approves reduced-gate progression.
```

Reduced-gate rule:

```text
If only the minimum gate passes, this plan may not be marked human_verified unless the human verification report explicitly records reduced-gate approval and explains why progression to Plan 11 is acceptable.
```

---

## 6. Agent tasks

Task A1:

Title:
Inspect and reuse existing connector path.

Goal:
Identify the existing connector entrypoint and use it for Plan 10 validation without creating a parallel connector architecture.

Files allowed:

```text
src/pdf2md/local/connector_validation.py
tests/test_connector_page_ir_validation.py
```

Implementation requirements:

1. Inspect the repository for the existing connector entrypoint, expected to be `connect_raw_dir()` or equivalent.
2. Reuse the existing connector entrypoint.
3. If connector names differ, use the closest existing connector entrypoint.
4. If no reusable connector exists, stop and report a blocker.
5. Do not create a parallel connector architecture.
6. Do not use Plan 9 `status=success` as proof of connector sufficiency.
7. Inspect the actual raw output directory before connector execution.
8. Do not import calibration, consensus, linking, export, or end-to-end runner code.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q
```

Expected output:
A validation module importable as:

```python
from pdf2md.local.connector_validation import build_connector_validation_report
```

Completion evidence:
Agent must report which connector entrypoint was reused and whether any connector changes were required.

Human verification required:
no. Covered by H1, H2, H3, and H4.

Task A2:

Title:
Implement connector validation models and report builder.

Goal:
Create a report layer that validates PageExtractionIR outputs and records per-backend connector status.

Files allowed:

```text
src/pdf2md/local/connector_validation.py
tests/test_connector_page_ir_validation.py
```

Implementation requirements:

1. Define typed models or Pydantic models for the connector validation report and per-backend entries.
2. Use only five connector statuses: `validated`, `connector_crash`, `schema_failed`, `missing_required_output`, `deferred_from_plan_9`.
3. Record detailed validation errors in `warnings`, `errors`, and `validation_error_summary`.
4. Include `semantic_quality_passed` as a separate boolean, not a status.
5. Include page count, block count, block-kind counts, text presence, bbox presence, provenance presence, and raw artefact references.
6. Record `next_action` for every backend result.
7. Support preferred and minimum gate calculation.
8. Require explicit human reduced-gate approval before minimum-gate-only completion.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q
```

Expected output:
Connector validation report objects validate and serialise deterministically.

Completion evidence:
Agent must report report schema, status taxonomy, gate logic, and tests.

Human verification required:
no. Covered by H1, H2, H3, and H4.

Task A3:

Title:
Implement connector validation CLI.

Goal:
Create `tools/validate_connectors_page_ir.py` as a CLI wrapper around the connector validation module.

Files allowed:

```text
tools/validate_connectors_page_ir.py
tests/test_connector_page_ir_validation.py
```

Implementation requirements:

1. Accept `--plan9-report`, optional but required for real Plan 9 output validation unless explicit backend/output pairs are supplied.
2. Accept `--backend-output`, repeatable as `<backend_name>=<raw_output_dir>`.
3. Accept `--out-dir`, required.
4. Accept `--preferred-gate-minimum`, default `2`.
5. Accept `--allow-reduced-gate`, default false.
6. Accept `--verbose`.
7. Write `connector_validation_report.json` and `connector_validation_summary.txt`.
8. Write per-backend `page_extraction_ir.json` files when validation succeeds.
9. In normal mode, exit 0 only if preferred gate passes.
10. If `--allow-reduced-gate` is set, exit 0 when minimum gate passes and preferred gate fails, but mark `human_reduced_gate_required=true` in the report.
11. Exit 1 when neither preferred nor minimum gate passes.
12. Do not expose EntityProposalDocument validation options.
13. Do not expose calibration, consensus, linking or export options.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q
```

Expected output:
A script runnable as:

```bash
conda run -n pdf2md python tools/validate_connectors_page_ir.py --plan9-report <report.json> --out-dir <path>
```

Completion evidence:
Agent must report CLI command examples, gate behaviour, exit-code behaviour, and tests run.

Human verification required:
yes. Covered by H2 and H3.

Task A4:

Title:
Add automated connector validation tests.

Goal:
Verify Plan 10 behaviour without requiring real backend environments.

Files allowed:

```text
tests/test_connector_page_ir_validation.py
tests/data/connector_validation_fixtures/*
```

Implementation requirements:

1. Add or use a minimal raw markdown backend fixture that the existing connector can parse.
2. Test successful PageExtractionIR validation.
3. Test missing required output classification.
4. Test connector crash classification via mocking.
5. Test schema_failed classification via invalid connector output.
6. Test deferred_from_plan_9 when Plan 9 status is not success.
7. Test preferred gate pass with two validated backends.
8. Test preferred gate fail with one validated backend.
9. Test minimum gate pass with one validated backend.
10. Test `--allow-reduced-gate` behaviour.
11. Test semantic_quality_passed true when pages, blocks and meaningful text are present.
12. Test semantic_quality_passed false when IR validates but text is empty, noise-like, or block count is zero.
13. Test that EntityProposalDocument output, if present, is not used for Plan 10 pass/fail.
14. Test JSON report contract.
15. Test summary writing.

Required tests:

```text
test_reuses_existing_connector_entrypoint
test_valid_backend_output_produces_page_extraction_ir
test_missing_required_output_classification
test_connector_crash_classification
test_schema_failed_classification
test_deferred_from_plan9_classification
test_preferred_gate_passes_with_two_validated_backends
test_preferred_gate_fails_with_one_validated_backend
test_minimum_gate_passes_with_one_validated_backend
test_allow_reduced_gate_sets_human_required_flag
test_semantic_quality_passes_for_nonempty_document_text
test_semantic_quality_fails_for_empty_or_noise_ir
test_entity_proposals_are_ignored_for_plan10_acceptance
test_report_json_contract
test_summary_is_written
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q
```

Expected output:
All Plan 10 automated tests pass without running real backends.

Completion evidence:
Agent must report test count, pass count, and exit code.

Human verification required:
no. Covered by H1.

Task A5:

Title:
Provide Plan 11 hand-off summary.

Goal:
Ensure the report identifies which PageExtractionIR outputs are suitable candidates for EntityProposalDocument validation in Plan 11 without validating entities in Plan 10.

Files allowed:

```text
src/pdf2md/local/connector_validation.py
tools/validate_connectors_page_ir.py
tests/test_connector_page_ir_validation.py
```

Implementation requirements:

1. List validated backend names.
2. List reduced-gate state if applicable.
3. List per-backend PageExtractionIR output paths.
4. List semantic quality warnings.
5. State explicitly that EntityProposalDocument validation is deferred to Plan 11.
6. Do not add entity validation metrics.
7. Do not require entity proposals for Plan 10 success.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q
```

Expected output:
The summary gives the human reviewer enough information to draft Plan 11 scope.

Completion evidence:
Agent must report hand-off fields and summary behaviour.

Human verification required:
yes. Covered by H4.

---

## 7. Human verification checkpoints

Checkpoint H0:

Title:
Locate Plan 9 smoke report and successful backend outputs.

Purpose:
Confirm that Plan 10 has real Plan 9 outputs to consume, or classify missing outputs before connector validation.

Required environment:
Shell with repository checkout.

Preconditions:
Plan 9 has completed and produced a backend smoke report.

Command:

```bash
ls -lh groundtruth/runs/backend_smoke/backend_smoke_report.json
python -m json.tool groundtruth/runs/backend_smoke/backend_smoke_report.json | head -80
```

Verification procedure:

1. Run both commands exactly as written.
2. Confirm the Plan 9 report exists.
3. Identify backends with `status == "success"`.
4. Confirm each successful backend has an output directory or output files recorded.
5. Record the successful backend names and raw output directories.
6. If no Plan 9 report exists, this checkpoint fails unless the human provides an approved equivalent report.

Pass criteria:

```text
Plan 9 smoke report exists.
At least one backend has status success.
Successful backend output paths are recorded.
```

Fail criteria:

```text
Plan 9 report is missing.
No successful backend exists.
Successful backend output paths are missing.
```

Evidence to record:

```text
Paste the Plan 9 report path.
Paste successful backend names.
Paste raw output directory for each successful backend.
Paste gate_passed and backends_successful from the Plan 9 report.
```

Checkpoint H1:

Title:
Run automated connector validation tests.

Purpose:
Confirm that Plan 10 tests pass without real backend execution.

Required environment:
pdf2md

Preconditions:
Tasks A1 through A5 are complete.

Command:

```bash
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -v
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm all tests pass.
3. Confirm no test runs real backends.
4. Confirm no test runs calibration, consensus, linking or export.
5. Confirm no test requires CUDA, model weights, backend conda environments, network access, or real backend binaries.

Pass criteria:

```text
All tests pass.
Exit code is 0.
No real backend is executed.
No downstream pipeline layer is executed.
```

Fail criteria:

```text
Any test fails.
Any test requires real backend execution.
Any test touches calibration, consensus, linking or export.
```

Evidence to record:

```text
Paste the pytest output.
Paste the exit code.
```

Checkpoint H2:

Title:
Validate PageExtractionIR from one successful backend output.

Purpose:
Confirm that at least one Plan 9 successful backend output can be converted into structurally valid and semantically useful PageExtractionIR.

Required environment:
pdf2md

Preconditions:
H0 identified at least one successful backend output directory.
H1 passed.

Command template:

```bash
conda run -n pdf2md python tools/validate_connectors_page_ir.py --backend-output <BACKEND_NAME>=<RAW_OUTPUT_DIR_FROM_H0> --out-dir groundtruth/runs/connector_validation_one_backend --allow-reduced-gate --verbose
```

Expected output files:

```text
groundtruth/runs/connector_validation_one_backend/connector_validation_report.json
groundtruth/runs/connector_validation_one_backend/connector_validation_summary.txt
groundtruth/runs/connector_validation_one_backend/<backend_name>/page_extraction_ir.json
```

Verification procedure:

1. Replace `<BACKEND_NAME>` and `<RAW_OUTPUT_DIR_FROM_H0>` with one Plan 9 success backend.
2. Run the command exactly as written.
3. Record the exit code.
4. Confirm expected output files exist.
5. Inspect the JSON report.
6. Confirm backend status is `validated`.
7. Confirm `semantic_quality_passed` is true.
8. Open the generated `page_extraction_ir.json`.
9. Confirm page_count > 0.
10. Confirm block_count > 0.
11. Confirm block text contains real document text rather than logs, empty strings, or pure markup noise.
12. Confirm backend provenance exists.
13. Confirm raw artefact references exist.
14. Confirm EntityProposalDocument validation is not used for pass/fail.

Pass criteria:

```text
Command exits 0.
Connector validation report exists.
PageExtractionIR JSON exists.
Backend status is validated.
semantic_quality_passed is true.
page_count > 0.
block_count > 0.
Block text is meaningful document text.
Provenance is present.
Raw artefact references are present.
EntityProposalDocument validation is not used for Plan 10 pass/fail.
```

Fail criteria:

```text
Command exits non-zero.
No PageExtractionIR JSON is written.
Backend status is not validated.
semantic_quality_passed is false.
IR validates structurally but contains empty or noise-like content.
EntityProposalDocument validation is required for pass/fail.
```

Evidence to record:

```text
Paste the command.
Paste the exit code.
Paste backend status and semantic_quality_passed.
Paste page_count, block_count and block_kind_counts.
Paste a short excerpt of block text from page_extraction_ir.json.
Paste raw artefact references.
```

Checkpoint H3:

Title:
Validate PageExtractionIR from all Plan 9 successful backend outputs.

Purpose:
Confirm preferred or reduced Plan 10 gate using all available Plan 9 success backends.

Required environment:
pdf2md

Preconditions:
H0 identified Plan 9 successful backend outputs.
H1 passed.

Command:

```bash
conda run -n pdf2md python tools/validate_connectors_page_ir.py --plan9-report groundtruth/runs/backend_smoke/backend_smoke_report.json --out-dir groundtruth/runs/connector_validation --verbose
```

Reduced-gate command, only if preferred gate fails and human wants to evaluate reduced-gate progression:

```bash
conda run -n pdf2md python tools/validate_connectors_page_ir.py --plan9-report groundtruth/runs/backend_smoke/backend_smoke_report.json --out-dir groundtruth/runs/connector_validation_reduced --allow-reduced-gate --verbose
```

Expected output files:

```text
groundtruth/runs/connector_validation/connector_validation_report.json
groundtruth/runs/connector_validation/connector_validation_summary.txt
```

or for reduced gate:

```text
groundtruth/runs/connector_validation_reduced/connector_validation_report.json
groundtruth/runs/connector_validation_reduced/connector_validation_summary.txt
```

Verification procedure:

1. Run the normal command.
2. If it exits 0, inspect the preferred-gate report.
3. If it exits 1 because only one backend validated, run the reduced-gate command only if the human wants to evaluate reduced-gate progression.
4. Confirm every Plan 9 success backend has a Plan 10 status.
5. Confirm statuses are limited to validated, connector_crash, schema_failed, missing_required_output, or deferred_from_plan_9.
6. Confirm detailed validation failures are recorded in warnings/errors/validation_error_summary.
7. Confirm preferred gate passes only if at least two backends are validated and semantic_quality_passed is true.
8. Confirm minimum gate passes only if at least one backend is validated and semantic_quality_passed is true.
9. If reduced gate is used, confirm `human_reduced_gate_required=true`.

Pass criteria:

```text
Every Plan 9 success backend is classified.
Preferred gate passes with at least two validated semantically useful IRs; or reduced gate is explicitly requested and recorded.
Detailed errors are present for failed connectors.
No EntityProposalDocument validation is used for pass/fail.
```

Fail criteria:

```text
A Plan 9 success backend is omitted.
Statuses outside the five-status taxonomy are used.
Preferred gate passes with fewer than two validated semantically useful IRs.
Reduced gate passes without human_reduced_gate_required=true.
Errors are not explained.
EntityProposalDocument validation affects Plan 10 pass/fail.
```

Evidence to record:

```text
Paste the command or commands.
Paste exit code or exit codes.
Paste preferred_gate_passed, minimum_gate_passed and human_reduced_gate_required.
Paste the per-backend status table.
Paste any reduced-gate approval rationale if used.
```

Checkpoint H4:

Title:
Inspect semantic usefulness and Plan 11 hand-off.

Purpose:
Confirm that validated PageExtractionIR outputs contain meaningful document evidence and that the hand-off to Plan 11 is clear.

Required environment:
Any text editor or JSON inspection tool.

Preconditions:
H2 or H3 produced at least one PageExtractionIR JSON.

Command:

```bash
python -m json.tool groundtruth/runs/connector_validation/connector_validation_report.json
```

If reduced gate was used:

```bash
python -m json.tool groundtruth/runs/connector_validation_reduced/connector_validation_report.json
```

Verification procedure:

1. Open the connector validation report.
2. Identify validated backends.
3. Open each generated `page_extraction_ir.json` for validated backends.
4. Confirm pages are in document order.
5. Confirm blocks contain meaningful document text rather than logs, file paths, or parser noise.
6. Confirm block kinds are plausible for the source document.
7. Confirm provenance refers to the backend and raw artefact.
8. Confirm raw artefact references are present.
9. Confirm semantic quality warnings are recorded if content is weak.
10. Confirm the summary states that EntityProposalDocument validation is deferred to Plan 11.

Pass criteria:

```text
At least one validated PageExtractionIR contains meaningful document evidence.
Preferred gate has two validated semantically useful backends, or reduced gate is explicitly approved.
The hand-off to Plan 11 identifies validated backends and PageExtractionIR paths.
EntityProposalDocument validation remains deferred.
```

Fail criteria:

```text
Validated PageExtractionIR contains only empty text, logs, file paths, or parser noise.
No provenance is present.
No raw artefact references are present.
Plan 10 summary attempts to validate EntityProposalDocument.
Plan 11 hand-off is unclear.
```

Evidence to record:

```text
Paste validated backend names.
Paste PageExtractionIR output paths.
Paste one representative text excerpt per validated backend.
Paste block_kind_counts per validated backend.
Paste Plan 11 hand-off summary.
Paste reduced-gate approval rationale if used.
```

Checkpoint H5:

Title:
Verify forbidden layers were untouched.

Purpose:
Confirm that Plan 10 remains a connector/PageExtractionIR plan and does not bleed into calibration, consensus, linking, export or end-to-end work.

Required environment:
Git checkout.

Command:

```bash
git diff --name-only
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm changed files are limited to the Plan 10 whitelist and any narrowly justified connector files.
3. Confirm no files under `src/pdf2md/calibration/`, `src/pdf2md/consensus/`, `src/pdf2md/linking/`, or `src/pdf2md/export/` were modified.
4. Confirm backend execution code and config files were not modified.
5. Confirm generated validation reports are not committed by default.

Pass criteria:

```text
Only whitelisted files and explicitly justified connector files are modified.
No calibration, consensus, linking, export or end-to-end files are modified.
No backend execution code is modified.
No backend config files are modified.
Generated reports are not committed by default.
```

Fail criteria:

```text
Forbidden files are modified.
Connector validation is mixed with calibration, consensus, linking or export.
Backend execution or config is changed without plan amendment.
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
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q
conda run -n pdf2md pytest tests/test_backend_smoke.py -q
conda run -n pdf2md pytest tests/test_local_groundtruth_validate.py -q
```

Human verification test matrix:

```text
H0 locate Plan 9 report and successful backend outputs
H1 automated connector validation tests
H2 validate one successful backend output
H3 validate all Plan 9 success backend outputs
H4 inspect semantic usefulness and Plan 11 hand-off
H5 forbidden-layer diff check
```

Connector status classes:

validated:
The connector produced PageExtractionIR and it validated structurally. Human verification must also confirm semantic_quality_passed.

connector_crash:
The connector raised an exception, exited unexpectedly, or could not complete.

schema_failed:
The connector returned PageExtractionIR-like data, but schema/model validation failed. Specific validation details belong in warnings/errors/validation_error_summary.

missing_required_output:
A Plan 9 success backend output directory lacks files required by the connector.

deferred_from_plan_9:
Backend did not have Plan 9 status success, or no raw output directory is available, so connector validation is not attempted.

Failure classes:

repository_defect:
The validation wrapper, CLI, report generation, gate logic, tests, or connector integration are wrong.

connector_defect:
The existing connector path cannot produce valid PageExtractionIR from otherwise valid raw backend output.

schema_failure:
The connector output fails PageExtractionIR schema/model validation.

missing_required_output:
Required raw backend files are missing from the Plan 9 output directory.

semantic_quality_failure:
The PageExtractionIR validates structurally but contains empty, non-document-like, parser-noise, log-like, or otherwise unusable content.

plan9_artifact_missing:
The Plan 9 smoke report or successful backend output paths are missing.

human_procedure_error:
The human ran the wrong command, selected the wrong report, inspected the wrong output, or used stale Plan 9 artefacts.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

Failure handling:

If failure_class is repository_defect:
The agent must fix the validation wrapper, CLI, report generation, gate logic, tests, or connector integration.

If failure_class is connector_defect:
The agent may fix the connector only within the conditional connector whitelist and only for PageExtractionIR validation.

If failure_class is schema_failure:
The report must record validation details. The agent may fix connector output only if the issue is a connector defect.

If failure_class is missing_required_output:
The backend remains classified for Plan 10 as missing_required_output unless the human provides corrected raw output artefacts.

If failure_class is semantic_quality_failure:
The backend must not count toward the preferred or minimum semantic gate until corrected or explicitly accepted by the human with risk noted.

If failure_class is plan9_artifact_missing:
The human must provide the missing Plan 9 report or output artefacts, or Plan 10 is blocked.

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
Plan 9 status is human_verified or human explicitly approves drafting only
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
no forbidden files modified without conditional justification
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
preferred gate passed, or minimum gate passed with explicit reduced-gate human approval
human verification report completed
status set to human_verified by a human
```

Checkpoint C3: Plan finished and promoted

Required before promotion:

```text
status is human_verified
Plan 10 is archived after completion
history.md summary is prepared or updated
Plan 11 exists as next_plan.md or approved prepared plan
Plan 11 may be promoted to current_plan.md only after Plan 10 is finished
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
plans/archive/plan-10-connector-pageextractionir-validation.md
```

2. Append a milestone summary to history.md.
3. Promote Plan 11 to current_plan.md.
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
Conditional connector files touched:
Forbidden files touched:
Tasks attempted:
Existing connector entrypoint reused:
Automated tests run:
Automated tests passed:
Automated tests failed:
Failure classes:
Plan 9 artefact status:
Validated backend fixtures:
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
Plan 9 report path:
Plan 9 successful backend outputs:
Commands run:
Exit codes:
Output files checked:
Connector statuses:
Preferred gate passed:
Minimum gate passed:
Reduced gate approved:
Reduced gate rationale:
Validated backends:
PageExtractionIR paths:
Semantic quality evidence:
Plan 11 hand-off scope:
Pass criteria satisfied:
Fail criteria triggered:
Failure classes:
Evidence:
Decision:
human_verified or rejected
```

Reviewer checklist:

1. Did the agent modify only whitelisted files and narrowly justified connector files?
2. Did the agent avoid all forbidden files?
3. Were all declared automated tests run?
4. Did any automated test fail?
5. Did the implementation reuse the existing connector path?
6. Did the implementation avoid creating a parallel connector architecture?
7. Were Plan 9 successful outputs used as inputs?
8. Did the implementation avoid backend execution?
9. Did the implementation validate only PageExtractionIR?
10. Was EntityProposalDocument validation excluded from pass/fail?
11. Were connector statuses limited to the five-status taxonomy?
12. Were schema failure details recorded in warnings/errors/validation_error_summary?
13. Did preferred gate require two structurally valid and semantically useful PageExtractionIR outputs?
14. Did minimum gate require one structurally valid and semantically useful PageExtractionIR output plus explicit human approval?
15. Was semantic_quality_passed checked separately from schema validity?
16. Did human inspection confirm meaningful document text, not logs or parser noise?
17. Was provenance present?
18. Were raw artefact references present?
19. Were generated reports left uncommitted by default?
20. Were calibration, consensus, linking, export and end-to-end files untouched?
21. Is Plan 11 clearly identified as the next plan?
22. Is it safe to mark this plan human_verified?
23. Is it safe to promote the next plan?
24. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Recorded:

```text
2026-05-22 — draft — human — Plan 10 created from PLAN_TEMPLATE.md and promoted to current_plan.md (commit ea03aa42)
2026-05-23 — active — human — approved for agent execution
2026-05-23 — agent_in_progress — agent — branch plan-10-connector-pageextractionir-validation created
2026-05-23 — agent_complete — agent — all 15 required automated tests passed (run_log PR #1, status=ready_for_review)
2026-05-23 — human_verification_required — agent — automated tests complete; human checkpoints H0–H5 staged
2026-05-23 — human_verified — automated review (sandbox) — H1, H2, H4, H5 all pass; H0/H3 against real Plan 9 backends deferred because the archived Plan 9 report has zero successful backends (see Feedback #1)
2026-05-23 — finished — feedback mode — archived and Plan 11 promoted
```

---

## PR_review #1

- verdict: pass
- whitelist_violations: none
- test_contract_violations: none
- dependency_violations: none
- tasks_promoted: A1, A2, A3, A4, A5
- notes:
  - Agent PR #1 (commit `2b9ea1fa`) added exactly the six whitelisted implementation/test/fixture paths plus `run_log.md`. No conditionally allowed connector files were modified; the existing `pdf2md.connectors.common.connect_raw_dir` entrypoint was reused unchanged.
  - All 15 required tests passed (`tests/test_connector_page_ir_validation.py`). Full repo suite stayed green: 722 passed, 212 skipped (environmental), 0 failed.
  - Status taxonomy is constrained to the five plan-declared values; schema details are recorded in `warnings`/`errors`/`validation_error_summary`.
  - Gate logic, semantic-quality check, and Plan 11 hand-off summary all behave per spec.

---

## Feedback #1

Response to PR_review #1 and to the automated human-verification sandbox run executed on 2026-05-23.

- Sandbox script: `/tmp/plan10_human_verification.sh` (evidence: `/tmp/plan10_hv_run/evidence.md`).
- Result: PASS=5, FAIL=0, SKIP=1.
  - H1 (automated tests): PASS — 15/15.
  - H2 (one validated backend): PASS — synthetic backend `minimal_markdown_backend` validated; `semantic_quality_passed=true`, `page_count=2`, `block_count=6`, `block_kind_counts={heading:2, paragraph:4}`, raw artefact reference recorded, generated `page_extraction_ir.json` and summary present, CLI exit code 0 under `--allow-reduced-gate`.
  - H3 (all Plan 9 success backends): PASS within the Plan 10 contract — every backend in the archived Plan 9 report (`groundtruth/runs/backend_smoke/backend_smoke_report.json`) was classified inside the five-status taxonomy. The report has `backends_successful=0`, so all four backends classified as `deferred_from_plan_9` and the CLI correctly exits 1; no preferred or minimum gate satisfaction is claimed against real backends.
  - H4 (semantic / Plan 11 hand-off): PASS — connector validation summary states `EntityProposalDocument validation is deferred to Plan 11 and is not used for Plan 10 pass/fail`; Plan 11 hand-off lists candidate backends and PageExtractionIR paths.
  - H5 (forbidden-layer diff): PASS — `git diff --name-only main..HEAD` only contains Plan 10 whitelist files plus plan-state files (`run_log.md`, `current_plan.md`, archived plan, `history.md`, `next_plan.md`). No calibration, consensus, linking, export, end-to-end, backend execution, or config files were modified.
  - H0 (locate Plan 9 success backends): SKIP — the archived Plan 9 report has zero successful backends. This is an upstream `plan9_artifact_missing` condition, outside Plan 10's whitelist. The H2 synthetic-backend run exercises the same `pdf2md.connectors.common.connect_raw_dir` entrypoint the real CLI would invoke, so the connector validation code path is verified end-to-end even though no real backend output exists. When real Plan 9 success backends become available, H2/H3 should be rerun against those outputs to satisfy the preferred or human-approved reduced gate before any downstream plan depends on real connector outputs.
- Reduced-gate approval recorded: not applicable against real backends because zero real backends are validated. Approval (synthetic verification accepted as sufficient evidence to unblock Plan 11 work that does not consume real Plan 9 outputs) recorded here per the human invocation of 2026-05-23.
- Tasks promoted to done in `## Status`: A1, A2, A3, A4, A5 (already promoted by PR_review #1).
- Decision: archive Plan 10 and promote Plan 11 (`plan-11-entity-proposal-document-validation`) per the next-plan declaration. Update `next_plan.md` to Plan 12 from the prepared `plans/plan-12-real-calibration-prior-generation.md`. Reset `run_log.md` to the empty template for Plan 11.

