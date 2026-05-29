# Plan 11 — EntityProposalDocument Validation

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
Overall project from approximately 68% toward 71% after successful completion.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 11 of the pre-MVP implementation sequence, ending at Plan 16.

Previous plan:
Plan 10 — Connector Implementation and PageExtractionIR Validation

Required previous plan status:
human_verified

Next plan after completion:
Plan 12 — Real Calibration Prior Generation

Branch name:
plan-11-entity-proposal-document-validation

---

## 1. Purpose

This plan validates `EntityProposalDocument` outputs produced by the same connector path validated in Plan 10.

Plan 10 validates `PageExtractionIR`. Plan 11 validates the second connector output: `EntityProposalDocument`.

The connector may emit both `PageExtractionIR` and `EntityProposalDocument` in one pass. Plan 11 must not reopen connector architecture except for narrow defect fixes discovered during entity validation.

The core question is:

```text
Can the connector produce valid, traceable and semantically plausible EntityProposalDocument outputs from Plan 10 validated backend artefacts?
```

Plan 11 validates:

```text
- entity proposal schema
- EntityType values
- EntityEvidence references
- EntityProposal block references
- RelationProposal endpoints and RelationType values
- provenance
- confidence sources where present in the current schema
- empty entity outputs as explicit no_entities_produced outcomes
```

Relation validation is in scope because the repository schema already supports relation proposals, including relation types such as `CAPTION_OF`, `FOOTNOTE_ANCHOR_FOR`, `TOC_POINTS_TO`, `REFERENCE_MENTION_OF`, `SAME_ENTITY_AS`, `NEAR`, `SEQUENCE_NEXT`, and `CANDIDATE_FOR`, where those are present in the current code.

Plan 11 does not perform calibration, consensus, semantic linking, Docling export, RAG export, Markdown export, or end-to-end runner work.

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
git switch -c plan-11-entity-proposal-document-validation
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 10 has been marked human_verified and archived.
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

This plan consumes existing Plan 10 connector validation outputs. It does not execute real backends by default and does not rerun Plan 10 unless the human provides existing artefacts or explicitly approves rerun inputs.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Locate Plan 10 connector validation reports and PageExtractionIR outputs.
2. Locate EntityProposalDocument outputs produced by the same connector path.
3. Validate EntityProposalDocument structurally using the repository model/schema.
4. Validate entity proposal evidence references.
5. Validate EntityType values.
6. Validate RelationProposal endpoints and RelationType values using the current schema.
7. Validate provenance fields where the schema requires or supports them.
8. Validate confidence sources where the schema requires or supports them.
9. Record entity counts by type.
10. Record relation counts by type.
11. Classify zero-entity outputs explicitly as `no_entities_produced`.
12. Produce per-backend entity validation reports.
13. Produce a machine-readable entity validation report.
14. Produce a human-readable entity validation summary.
15. Add automated tests with fixtures or mocks that do not require real backend environments.
16. Add human checkpoints for semantic plausibility of entities and relations.
17. Prepare hand-off information for Plan 12 calibration priors.

Out of scope:

1. Reopening connector architecture.
2. Modifying connector code except for narrow defect fixes required for EntityProposalDocument validity.
3. Running backend model scripts.
4. Running PageExtractionIR validation as a Plan 11 acceptance target.
5. Inventing new EntityType or RelationType values.
6. Adding new relation semantics not present in the current schema.
7. Running calibration.
8. Running consensus.
9. Running semantic linking.
10. Running Docling export.
11. Running RAG export.
12. Running Markdown export.
13. Running the end-to-end pipeline.
14. Editing ROADMAP.md.
15. Editing README.md.
16. Editing project.md.
17. Editing current_plan.md.
18. Editing next_plan.md.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. The agent must reuse existing EntityProposalDocument schema and connector artefacts.
6. The agent must not add relation types or entity types unless the plan is explicitly amended by the human.
7. Schema failures must be recorded as `schema_failed`, with exact Pydantic or validation details in warnings/errors.
8. Evidence-reference failures covered by current schema validators must be classified as `schema_failed`, not as a separate top-level status.
9. Empty but valid EntityProposalDocument outputs must be classified as `no_entities_produced`, not silently counted as validated.
10. If Plan 10 artefacts are missing, the affected backend must be classified as `deferred_from_plan_10` or the plan must be blocked if no valid inputs exist.
11. Pydantic/schema validity alone is not enough for full semantic acceptance; human semantic plausibility checkpoints must pass for validated status to count toward the gate.

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
src/pdf2md/local/entity_proposal_validation.py

tools/validate_entity_proposals.py

tests/test_entity_proposal_validation.py

tests/data/entity_proposal_validation_fixtures/valid_entities/entities.json
tests/data/entity_proposal_validation_fixtures/valid_entities/page_extraction_ir.json
tests/data/entity_proposal_validation_fixtures/no_entities/entities.json
tests/data/entity_proposal_validation_fixtures/no_entities/page_extraction_ir.json
tests/data/entity_proposal_validation_fixtures/schema_failure/entities.json
tests/data/entity_proposal_validation_fixtures/schema_failure/page_extraction_ir.json
```

The agent may modify connector code only if a narrow defect prevents valid EntityProposalDocument output from being loaded or validated. Such changes must be justified in the agent report and must not alter PageExtractionIR validation behaviour from Plan 10.

Conditionally allowed connector files:

```text
src/pdf2md/connectors/*
backend/*/connector.py
```

Conditionally allowed connector changes are limited to:

```text
- exposing already-produced EntityProposalDocument output
- preserving entity provenance
- preserving entity evidence references
- preserving relation proposals already supported by the schema
- fixing schema defects in EntityProposalDocument construction
```

Conditionally allowed connector changes must not:

```text
- rework connector architecture
- change Plan 10 PageExtractionIR acceptance semantics
- implement calibration
- implement consensus
- implement semantic linking
- implement Docling export
- implement new entity or relation types outside the current schema
- change backend execution behaviour
```

Expected output artefacts, produced by the CLI and not committed unless a later policy explicitly allows it:

```text
<out-dir>/entity_proposal_validation_report.json
<out-dir>/entity_proposal_validation_summary.txt
<out-dir>/<backend_name>/entity_proposals.json
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

src/pdf2md/local/connector_validation.py
src/pdf2md/local/backend_smoke.py
src/pdf2md/local/groundtruth.py
src/pdf2md/local/preflight.py
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

tools/validate_connectors_page_ir.py
tools/backend_smoke.py
tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py

groundtruth/corpus/*
```

Required entity validation report contract:

```text
schema_name: pdf2md.EntityProposalDocumentValidationReport
schema_version: 1.0.0
generated_at: ISO 8601 timestamp
tool_name: validate_entity_proposals
plan10_report_path: path or null
gate_mode: preferred | reduced
preferred_gate_passed: bool
minimum_gate_passed: bool
human_reduced_gate_required: bool
total_backends_considered: int
backends_validated: int
backends_no_entities: int
backends_failed: int
backends_deferred: int
results: list of per-backend validation entries
warnings: list of strings
metadata: dict
```

Per-backend entity validation entry contract:

```text
backend_name: str
plan10_status: str or null
page_extraction_ir_path: str or null
entity_document_path: str or null
connector_entrypoint: str or null
status: validated | no_entities_produced | schema_failed | connector_crash | deferred_from_plan_10
entity_count: int
entity_type_counts: dict
relation_count: int
relation_type_counts: dict
has_evidence: bool
has_relations: bool
has_provenance: bool
has_confidence_sources: bool
semantic_plausibility_passed: bool
warnings: list[str]
errors: list[str]
validation_error_summary: str or null
next_action: str
metadata: dict
```

Status taxonomy:

```text
validated:
  EntityProposalDocument validates structurally and contains at least one entity or relation proposal with acceptable evidence/provenance quality.

no_entities_produced:
  EntityProposalDocument validates structurally but contains zero entity proposals and zero useful relation proposals.
  This is not a connector crash and is useful evidence for Plan 12 calibration.

schema_failed:
  EntityProposalDocument-like data exists, but schema/model validation fails.
  This includes invalid EntityType, invalid RelationType, invalid evidence references, invalid block ID patterns, relation endpoints that do not exist, malformed confidence source data, or other Pydantic/model errors.

connector_crash:
  The connector or validation wrapper raised an exception, exited unexpectedly, or could not load/produce the EntityProposalDocument.

deferred_from_plan_10:
  Backend did not have Plan 10 status validated, or no Plan 10 artefacts are available, so entity validation is not attempted.
```

Gate rule:

```text
Preferred gate:
  At least two Plan 10 validated backends produce EntityProposalDocument outputs with status validated and semantic_plausibility_passed=true.

Minimum gate:
  At least one Plan 10 validated backend produces EntityProposalDocument output with status validated and semantic_plausibility_passed=true;
  all other Plan 10 validated backends are classified;
  human reviewer explicitly approves reduced-gate progression.
```

No-entity rule:

```text
Backends classified as no_entities_produced do not count toward the preferred or minimum validated gate.
They also do not count as connector failures.
They must be recorded for Plan 12 calibration and later consensus weighting.
```

Reduced-gate rule:

```text
If only the minimum gate passes, this plan may not be marked human_verified unless the human verification report explicitly records reduced-gate approval and explains why progression to Plan 12 is acceptable.
```

---

## 6. Agent tasks

Task A1:

Title:
Inspect existing entity schema and connector outputs.

Goal:
Ground Plan 11 validation in the existing EntityProposalDocument, EntityType, RelationType, EntityEvidence and RelationProposal schema.

Files allowed:

```text
src/pdf2md/local/entity_proposal_validation.py
tests/test_entity_proposal_validation.py
```

Implementation requirements:

1. Inspect the repository schema for EntityProposalDocument, EntityProposal, EntityEvidence, RelationProposal, EntityType and RelationType.
2. Reuse the existing schema; do not invent new entity or relation types.
3. Inspect Plan 10 output conventions for PageExtractionIR and entity artefacts.
4. Confirm whether connector output stores entity proposals as `entities.json`, embedded connector return data, or another current path.
5. If entity artefact location is unknown, derive it from the Plan 10 validation report or connector output metadata.
6. Do not create a parallel entity schema.
7. Do not modify calibration, consensus, linking, export, or end-to-end code.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -q
```

Expected output:
A validation module importable as:

```python
from pdf2md.local.entity_proposal_validation import build_entity_proposal_validation_report
```

Completion evidence:
Agent must report which schema classes and relation types were reused.

Human verification required:
no. Covered by H1, H2, H3 and H4.

Task A2:

Title:
Implement entity validation report models and classifier.

Goal:
Create a validation layer that classifies EntityProposalDocument outputs using the five-status taxonomy.

Files allowed:

```text
src/pdf2md/local/entity_proposal_validation.py
tests/test_entity_proposal_validation.py
```

Implementation requirements:

1. Define typed models or Pydantic models for the entity validation report and per-backend entries.
2. Use only five statuses: `validated`, `no_entities_produced`, `schema_failed`, `connector_crash`, `deferred_from_plan_10`.
3. Record detailed validation errors in `warnings`, `errors`, and `validation_error_summary`.
4. Classify empty valid EntityProposalDocument outputs as `no_entities_produced`.
5. Treat Pydantic validation failures, invalid relation endpoints and invalid evidence references as `schema_failed`.
6. Include entity count, entity type counts, relation count and relation type counts.
7. Include booleans for has_evidence, has_relations, has_provenance and has_confidence_sources.
8. Include `semantic_plausibility_passed` as a separate boolean, not a status.
9. Include `next_action` for every backend result.
10. Support preferred and minimum gate calculation.
11. Require explicit human reduced-gate approval before minimum-gate-only completion.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -q
```

Expected output:
Entity validation report objects validate and serialise deterministically.

Completion evidence:
Agent must report report schema, status taxonomy, gate logic, and tests.

Human verification required:
no. Covered by H1, H2, H3 and H4.

Task A3:

Title:
Implement entity proposal validation CLI.

Goal:
Create `tools/validate_entity_proposals.py` as a CLI wrapper around the entity validation module.

Files allowed:

```text
tools/validate_entity_proposals.py
tests/test_entity_proposal_validation.py
```

Implementation requirements:

1. Accept `--plan10-report`, optional but required for real Plan 10 output validation unless explicit backend/entity pairs are supplied.
2. Accept `--backend-entities`, repeatable as `<backend_name>=<entity_document_path>`.
3. Accept `--page-ir`, repeatable as `<backend_name>=<page_extraction_ir_path>` for evidence cross-checking when needed.
4. Accept `--out-dir`, required.
5. Accept `--preferred-gate-minimum`, default `2`.
6. Accept `--allow-reduced-gate`, default false.
7. Accept `--verbose`.
8. Write `entity_proposal_validation_report.json` and `entity_proposal_validation_summary.txt`.
9. Write per-backend `entity_proposals.json` copies or normalised reports only when validation succeeds or when explicitly useful for review.
10. In normal mode, exit 0 only if preferred gate passes.
11. If `--allow-reduced-gate` is set, exit 0 when minimum gate passes and preferred gate fails, but mark `human_reduced_gate_required=true` in the report.
12. Exit 1 when neither preferred nor minimum gate passes.
13. Do not expose calibration, consensus, linking, export or end-to-end options.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -q
```

Expected output:
A script runnable as:

```bash
conda run -n pdf2md python tools/validate_entity_proposals.py --plan10-report <report.json> --out-dir <path>
```

Completion evidence:
Agent must report CLI command examples, gate behaviour, exit-code behaviour, and tests run.

Human verification required:
yes. Covered by H2 and H3.

Task A4:

Title:
Add automated entity validation tests.

Goal:
Verify Plan 11 behaviour without requiring real backend environments.

Files allowed:

```text
tests/test_entity_proposal_validation.py
tests/data/entity_proposal_validation_fixtures/*
```

Implementation requirements:

1. Add or use a valid EntityProposalDocument fixture with entities, evidence and at least one relation if supported by the current schema.
2. Add or use an empty but valid EntityProposalDocument fixture.
3. Add or use an invalid EntityProposalDocument fixture that triggers schema_failed.
4. Add or use a matching PageExtractionIR fixture for cross-checking evidence against blocks where needed.
5. Test validated status.
6. Test no_entities_produced status.
7. Test schema_failed status.
8. Test connector_crash classification by mocking.
9. Test deferred_from_plan_10 classification.
10. Test entity type counting.
11. Test relation type counting.
12. Test relation endpoints are schema-validated.
13. Test evidence references are schema-validated.
14. Test preferred gate pass with two validated backends.
15. Test preferred gate fail with one validated backend.
16. Test minimum gate pass with one validated backend.
17. Test no_entities_produced does not count as validated gate success.
18. Test `--allow-reduced-gate` behaviour.
19. Test semantic_plausibility_passed true for plausible entities/relations.
20. Test semantic_plausibility_passed false for empty, noise-like or implausible entity outputs.
21. Test JSON report contract.
22. Test summary writing.

Required tests:

```text
test_valid_entity_document_classifies_validated
test_empty_entity_document_classifies_no_entities_produced
test_invalid_entity_document_classifies_schema_failed
test_connector_crash_classification
test_deferred_from_plan10_classification
test_entity_type_counts_are_reported
test_relation_type_counts_are_reported
test_relation_endpoints_are_validated_by_schema
test_evidence_references_are_validated_by_schema
test_preferred_gate_passes_with_two_validated_backends
test_preferred_gate_fails_with_one_validated_backend
test_minimum_gate_passes_with_one_validated_backend
test_no_entities_produced_does_not_count_toward_validated_gate
test_allow_reduced_gate_sets_human_required_flag
test_semantic_plausibility_passes_for_plausible_entities
test_semantic_plausibility_fails_for_noise_or_empty_entities
test_report_json_contract
test_summary_is_written
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -q
```

Expected output:
All Plan 11 automated tests pass without running real backends.

Completion evidence:
Agent must report test count, pass count, and exit code.

Human verification required:
no. Covered by H1.

Task A5:

Title:
Provide Plan 12 calibration hand-off summary.

Goal:
Ensure the report identifies which entity outputs can contribute to real calibration priors in Plan 12.

Files allowed:

```text
src/pdf2md/local/entity_proposal_validation.py
tools/validate_entity_proposals.py
tests/test_entity_proposal_validation.py
```

Implementation requirements:

1. List validated backend names.
2. List no_entities_produced backend names.
3. List reduced-gate state if applicable.
4. List entity type counts by backend.
5. List relation type counts by backend.
6. List semantic plausibility warnings.
7. List entity output paths.
8. State explicitly that real calibration priors are deferred to Plan 12.
9. Do not compute calibration metrics.
10. Do not compare to ground truth in Plan 11.
11. Do not produce priors.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -q
```

Expected output:
The summary gives the human reviewer enough information to draft Plan 12 scope.

Completion evidence:
Agent must report hand-off fields and summary behaviour.

Human verification required:
yes. Covered by H4.

---

## 7. Human verification checkpoints

Checkpoint H0:

Title:
Locate Plan 10 connector validation outputs.

Purpose:
Confirm that Plan 11 has Plan 10 artefacts to consume.

Required environment:
Shell with repository checkout.

Preconditions:
Plan 10 has completed and produced a connector validation report.

Command:

```bash
ls -lh groundtruth/runs/connector_validation/connector_validation_report.json
python -m json.tool groundtruth/runs/connector_validation/connector_validation_report.json | head -100
```

If reduced gate was used in Plan 10:

```bash
ls -lh groundtruth/runs/connector_validation_reduced/connector_validation_report.json
python -m json.tool groundtruth/runs/connector_validation_reduced/connector_validation_report.json | head -100
```

Verification procedure:

1. Run the appropriate commands exactly as written.
2. Confirm the Plan 10 report exists.
3. Identify backends with Plan 10 status `validated`.
4. Confirm each validated backend has a PageExtractionIR output path.
5. Confirm entity artefact paths are present or can be derived from connector outputs.
6. If no Plan 10 report exists, this checkpoint fails unless the human provides an approved equivalent report.

Pass criteria:

```text
Plan 10 connector validation report exists.
At least one backend has status validated.
PageExtractionIR path exists for each validated backend.
Entity artefact path exists or can be derived for each validated backend.
```

Fail criteria:

```text
Plan 10 report is missing.
No Plan 10 validated backend exists.
PageExtractionIR paths are missing.
Entity artefacts cannot be found or derived.
```

Evidence to record:

```text
Paste the Plan 10 report path.
Paste validated backend names.
Paste PageExtractionIR path for each validated backend.
Paste entity artefact path for each validated backend if present.
Paste preferred_gate_passed, minimum_gate_passed and human_reduced_gate_required from the Plan 10 report.
```

Checkpoint H1:

Title:
Run automated entity proposal validation tests.

Purpose:
Confirm that Plan 11 tests pass without real backend execution.

Required environment:
pdf2md

Preconditions:
Tasks A1 through A5 are complete.

Command:

```bash
conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -v
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
Validate EntityProposalDocument from one Plan 10 validated backend.

Purpose:
Confirm that at least one Plan 10 validated backend output can produce valid entity proposal evidence.

Required environment:
pdf2md

Preconditions:
H0 identified at least one Plan 10 validated backend.
H1 passed.

Command template:

```bash
conda run -n pdf2md python tools/validate_entity_proposals.py --backend-entities <BACKEND_NAME>=<ENTITY_DOCUMENT_PATH_FROM_H0> --page-ir <BACKEND_NAME>=<PAGE_EXTRACTION_IR_PATH_FROM_H0> --out-dir groundtruth/runs/entity_validation_one_backend --allow-reduced-gate --verbose
```

Expected output files:

```text
groundtruth/runs/entity_validation_one_backend/entity_proposal_validation_report.json
groundtruth/runs/entity_validation_one_backend/entity_proposal_validation_summary.txt
```

Verification procedure:

1. Replace `<BACKEND_NAME>`, `<ENTITY_DOCUMENT_PATH_FROM_H0>` and `<PAGE_EXTRACTION_IR_PATH_FROM_H0>` with paths from H0.
2. Run the command exactly as written.
3. Record the exit code.
4. Confirm expected output files exist.
5. Inspect the JSON report.
6. Confirm backend status is `validated` or `no_entities_produced`.
7. If status is `validated`, confirm entity_count > 0 or relation_count > 0.
8. Confirm EntityType values are valid.
9. Confirm RelationType values are valid where relations exist.
10. Confirm relation endpoints reference existing entities where relations exist.
11. Confirm evidence references are valid where evidence exists.
12. Confirm provenance exists where required or supported by the schema.
13. Confirm semantic_plausibility_passed reflects human judgement.

Pass criteria:

```text
Command writes report and summary.
Backend is classified as validated or no_entities_produced.
If validated, entity_count > 0 or relation_count > 0.
Entity and relation schema checks pass.
Evidence/provenance checks pass where required by schema.
semantic_plausibility_passed is true for validated backends.
```

Fail criteria:

```text
No report is written.
Backend classification is absent.
Invalid EntityType or RelationType is accepted.
Invalid relation endpoints are accepted.
Invalid evidence references are accepted.
Validated backend has no meaningful entity or relation evidence.
```

Evidence to record:

```text
Paste the command.
Paste the exit code.
Paste backend status and semantic_plausibility_passed.
Paste entity_count, entity_type_counts, relation_count and relation_type_counts.
Paste one representative entity proposal.
Paste one representative relation proposal if relations exist.
```

Checkpoint H3:

Title:
Validate EntityProposalDocument from all Plan 10 validated backend outputs.

Purpose:
Confirm preferred or reduced Plan 11 gate using all available Plan 10 validated backends.

Required environment:
pdf2md

Preconditions:
H0 identified Plan 10 validated backend outputs.
H1 passed.

Command:

```bash
conda run -n pdf2md python tools/validate_entity_proposals.py --plan10-report groundtruth/runs/connector_validation/connector_validation_report.json --out-dir groundtruth/runs/entity_validation --verbose
```

Reduced-gate command, only if preferred gate fails and human wants to evaluate reduced-gate progression:

```bash
conda run -n pdf2md python tools/validate_entity_proposals.py --plan10-report groundtruth/runs/connector_validation/connector_validation_report.json --out-dir groundtruth/runs/entity_validation_reduced --allow-reduced-gate --verbose
```

If Plan 10 used reduced gate, replace `groundtruth/runs/connector_validation/connector_validation_report.json` with the approved reduced-gate Plan 10 report.

Expected output files:

```text
groundtruth/runs/entity_validation/entity_proposal_validation_report.json
groundtruth/runs/entity_validation/entity_proposal_validation_summary.txt
```

or for reduced gate:

```text
groundtruth/runs/entity_validation_reduced/entity_proposal_validation_report.json
groundtruth/runs/entity_validation_reduced/entity_proposal_validation_summary.txt
```

Verification procedure:

1. Run the normal command.
2. If it exits 0, inspect the preferred-gate report.
3. If it exits 1 because only one backend validated, run the reduced-gate command only if the human wants to evaluate reduced-gate progression.
4. Confirm every Plan 10 validated backend has a Plan 11 status.
5. Confirm statuses are limited to validated, no_entities_produced, schema_failed, connector_crash, or deferred_from_plan_10.
6. Confirm detailed validation failures are recorded in warnings/errors/validation_error_summary.
7. Confirm preferred gate passes only if at least two backends are validated and semantic_plausibility_passed is true.
8. Confirm minimum gate passes only if at least one backend is validated and semantic_plausibility_passed is true.
9. If reduced gate is used, confirm `human_reduced_gate_required=true`.
10. Confirm no_entities_produced backends are listed but do not count toward validated gate success.

Pass criteria:

```text
Every Plan 10 validated backend is classified.
Preferred gate passes with at least two validated semantically plausible entity documents; or reduced gate is explicitly requested and recorded.
Detailed errors are present for failed entity validations.
No calibration, consensus, linking, or export is run.
No_entities_produced is recorded without being treated as connector failure.
```

Fail criteria:

```text
A Plan 10 validated backend is omitted.
Statuses outside the five-status taxonomy are used.
Preferred gate passes with fewer than two validated semantically plausible entity documents.
Reduced gate passes without human_reduced_gate_required=true.
No_entities_produced counts as validated gate success.
Errors are not explained.
Calibration or consensus metrics are computed.
```

Evidence to record:

```text
Paste the command or commands.
Paste exit code or exit codes.
Paste preferred_gate_passed, minimum_gate_passed and human_reduced_gate_required.
Paste the per-backend status table.
Paste entity_type_counts and relation_type_counts for validated backends.
Paste any reduced-gate approval rationale if used.
```

Checkpoint H4:

Title:
Inspect semantic plausibility and Plan 12 hand-off.

Purpose:
Confirm that validated entity proposals are meaningful and that the hand-off to Plan 12 calibration is clear.

Required environment:
Any text editor or JSON inspection tool.

Preconditions:
H2 or H3 produced at least one entity validation report.

Command:

```bash
python -m json.tool groundtruth/runs/entity_validation/entity_proposal_validation_report.json
```

If reduced gate was used:

```bash
python -m json.tool groundtruth/runs/entity_validation_reduced/entity_proposal_validation_report.json
```

Verification procedure:

1. Open the entity validation report.
2. Identify validated backends.
3. Identify no_entities_produced backends.
4. Inspect representative entity proposals.
5. Confirm entity proposals are based on meaningful document blocks, not parser noise.
6. Confirm captions, figures, tables, equations, references, footnotes or TOC-like entities are plausible where present.
7. Confirm relations such as CAPTION_OF and NEAR are plausible where present.
8. Confirm relation endpoints point to existing entities.
9. Confirm evidence references point to valid block/source IDs according to the schema.
10. Confirm the summary states that real calibration priors are deferred to Plan 12.
11. Confirm no calibration metrics or priors are computed.

Pass criteria:

```text
At least one validated EntityProposalDocument contains meaningful entity or relation evidence, or no_entities_produced is explicitly classified and accepted by the human as expected for that backend.
Preferred gate has two validated semantically plausible backends, or reduced gate is explicitly approved.
The hand-off to Plan 12 identifies validated, no_entities_produced, failed and deferred backends.
No calibration metrics or priors are produced.
```

Fail criteria:

```text
Validated entity proposals are parser noise or meaningless.
Relations are implausible or point to non-existing entities.
Evidence references are invalid.
No_entities_produced is silently treated as success.
Plan 11 summary attempts to compute calibration priors.
Plan 12 hand-off is unclear.
```

Evidence to record:

```text
Paste validated backend names.
Paste no_entities_produced backend names.
Paste one representative entity proposal per validated backend.
Paste one representative relation proposal per validated backend if relations exist.
Paste entity_type_counts and relation_type_counts.
Paste Plan 12 hand-off summary.
Paste reduced-gate approval rationale if used.
```

Checkpoint H5:

Title:
Verify forbidden layers were untouched.

Purpose:
Confirm that Plan 11 remains an EntityProposalDocument validation plan and does not bleed into calibration, consensus, linking, export or end-to-end work.

Required environment:
Git checkout.

Command:

```bash
git diff --name-only
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm changed files are limited to the Plan 11 whitelist and any narrowly justified connector files.
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
Entity validation is mixed with calibration, consensus, linking or export.
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
conda run -n pdf2md pytest tests/test_entity_proposal_validation.py -q
conda run -n pdf2md pytest tests/test_connector_page_ir_validation.py -q
conda run -n pdf2md pytest tests/test_backend_smoke.py -q
```

Human verification test matrix:

```text
H0 locate Plan 10 outputs
H1 automated entity validation tests
H2 validate one Plan 10 validated backend
H3 validate all Plan 10 validated backends
H4 inspect semantic plausibility and Plan 12 hand-off
H5 forbidden-layer diff check
```

Entity validation status classes:

validated:
EntityProposalDocument validates structurally and contains at least one entity or relation proposal with acceptable evidence/provenance quality.

no_entities_produced:
EntityProposalDocument validates structurally but contains zero entity proposals and zero useful relation proposals. This is not a connector crash and is useful evidence for Plan 12 calibration.

schema_failed:
EntityProposalDocument-like data exists, but schema/model validation fails. Specific validation details belong in warnings/errors/validation_error_summary.

connector_crash:
The connector or validation wrapper raised an exception, exited unexpectedly, or could not load/produce the EntityProposalDocument.

deferred_from_plan_10:
Backend did not have Plan 10 status validated, or no Plan 10 artefacts are available, so entity validation is not attempted.

Failure classes:

repository_defect:
The validation wrapper, CLI, report generation, gate logic, tests, or entity validation integration are wrong.

connector_defect:
The existing connector path cannot produce valid EntityProposalDocument from otherwise valid raw backend output.

schema_failure:
The entity document fails EntityProposalDocument schema/model validation.

no_entities_produced:
The entity document is structurally valid but contains zero entity proposals and zero useful relation proposals.

semantic_plausibility_failure:
The entity document validates structurally but contains parser-noise, implausible, untraceable, or otherwise unusable entity/relation proposals.

plan10_artifact_missing:
The Plan 10 connector validation report, PageExtractionIR output, or entity artefact paths are missing.

human_procedure_error:
The human ran the wrong command, selected the wrong report, inspected the wrong output, or used stale Plan 10 artefacts.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

Failure handling:

If failure_class is repository_defect:
The agent must fix the validation wrapper, CLI, report generation, gate logic, tests, or entity validation integration.

If failure_class is connector_defect:
The agent may fix the connector only within the conditional connector whitelist and only for EntityProposalDocument validity.

If failure_class is schema_failure:
The report must record validation details. The agent may fix connector entity output only if the issue is a connector defect.

If failure_class is no_entities_produced:
The backend does not count toward the validated gate, but it is recorded for Plan 12 calibration.

If failure_class is semantic_plausibility_failure:
The backend must not count toward the preferred or minimum semantic gate until corrected or explicitly accepted by the human with risk noted.

If failure_class is plan10_artifact_missing:
The human must provide the missing Plan 10 report or output artefacts, or Plan 11 is blocked.

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
Plan 10 status is human_verified or human explicitly approves drafting only
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
Plan 11 is archived after completion
history.md summary is prepared or updated
Plan 12 exists as next_plan.md or approved prepared plan
Plan 12 may be promoted to current_plan.md only after Plan 11 is finished
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
plans/archive/plan-11-entity-proposal-document-validation.md
```

2. Append a milestone summary to history.md.
3. Promote Plan 12 to current_plan.md.
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
Schema classes reused:
Relation types reused:
Automated tests run:
Automated tests passed:
Automated tests failed:
Failure classes:
Plan 10 artefact status:
Validated entity fixtures:
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
Plan 10 report path:
Plan 10 validated backend outputs:
Commands run:
Exit codes:
Output files checked:
Entity validation statuses:
Preferred gate passed:
Minimum gate passed:
Reduced gate approved:
Reduced gate rationale:
Validated backends:
No-entity backends:
Entity type counts:
Relation type counts:
Semantic plausibility evidence:
Plan 12 hand-off scope:
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
5. Did the implementation reuse the existing EntityProposalDocument schema?
6. Did the implementation reuse the existing EntityType and RelationType enums?
7. Did the implementation avoid inventing new entity or relation types?
8. Were Plan 10 validated outputs used as inputs?
9. Did the implementation avoid backend execution?
10. Did the implementation validate only EntityProposalDocument?
11. Was PageExtractionIR used only as evidence context, not as the Plan 11 acceptance target?
12. Were calibration, consensus, linking, export and end-to-end code untouched?
13. Were entity validation statuses limited to the five-status taxonomy?
14. Were schema failure details recorded in warnings/errors/validation_error_summary?
15. Did no_entities_produced remain separate from connector failure?
16. Did no_entities_produced avoid counting toward validated gate success?
17. Were relation proposals validated where present?
18. Were relation endpoints checked by schema/model validation?
19. Were evidence references checked by schema/model validation?
20. Did preferred gate require two validated semantically plausible EntityProposalDocument outputs?
21. Did minimum gate require one validated semantically plausible EntityProposalDocument output plus explicit human approval?
22. Did human inspection confirm plausible entities and relations, not parser noise?
23. Were generated reports left uncommitted by default?
24. Is Plan 12 clearly identified as the next plan?
25. Is it safe to mark this plan human_verified?
26. Is it safe to promote the next plan?
27. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-09 — draft — human — Plan 11 created from ROADMAP.md and PLAN_TEMPLATE.md
2026-05-09 — active — human — approved for agent execution
2026-05-09 — agent_in_progress — agent — branch created
2026-05-09 — agent_complete — agent — automated tests passed
2026-05-09 — human_verification_required — agent — awaiting human entity validation checks
2026-05-09 — human_verified — human — all checkpoints passed
2026-05-09 — finished — human — archived and promoted
```
