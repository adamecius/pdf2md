# Plan 14 — LinkedStructure and Cross-Page Semantic Linking

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
Phase 4 — Semantic document construction and export preparation

Current roadmap estimate:
Overall project from approximately 78% toward 80–81% after successful completion.

Note:
This plan validates and hardens the existing linking stack on real Plan 13 ConsensusIR outputs. It does not build cross-page linking from scratch. It does not perform Docling export.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 14 of the pre-MVP implementation sequence, ending at Plan 16.

Previous plan:
Plan 13 — Weighted ConsensusIR on Real Outputs

Required previous plan status:
human_verified

Next plan after completion:
Plan 15 — Docling Export Validation

Branch name:
plan-14-linkedstructure-cross-page-semantic-linking

---

## 1. Purpose

This plan runs and hardens the existing linking stack on real Plan 13 ConsensusIR outputs.

The repository already has the linking stack:

```text
src/pdf2md/linking/builder.py
src/pdf2md/linking/extract.py
src/pdf2md/linking/resolvers.py
src/pdf2md/linking/reporting.py
src/pdf2md/linking/io.py
src/pdf2md/linking/__init__.py
```

and the CLI:

```text
tools/build_linked_structure.py
```

Plan 14 must reuse this stack.

The core question is:

```text
Can the existing linker build a valid, inspectable LinkedStructure from real weighted ConsensusIR outputs, while preserving ordering, provenance, confidence, unresolved links and cross-page semantic relations?
```

Plan 14 must prove that the existing linking path works on real Plan 13 outputs, including:

```text
document reading order
section hierarchy
cross-page continuity
caption links
figure/table sequence links
footnote links
reference links
TOC links where available
provenance back to ConsensusIR
confidence and unresolved warnings
Plan 15 export readiness
```

This plan does not perform Docling export. Docling export is Plan 15.

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
git switch -c plan-14-linkedstructure-cross-page-semantic-linking
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 13 has been marked human_verified and archived.
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

This plan does not run backend model execution, consensus generation, calibration or export. It consumes artefacts already produced by earlier plans.

---

## 4. Scope, constraints and dependencies

In scope:

1. Inspect the existing linking stack.
2. Run `tools/build_linked_structure.py` on real Plan 13 ConsensusIR output.
3. Use Plan 13 `consensus_ir.json` as the primary input.
4. Use Plan 13 `reports/consensus_report.json` when available.
5. Use Plan 11 or Plan 13 entities-root when available.
6. Use Plan 12 priors-root when available.
7. Fix real-data issues inside the linking whitelist.
8. Validate `linked_structure.json`.
9. Validate `reports/linking_report.json`.
10. Confirm cross-page reading order and section hierarchy.
11. Confirm caption, footnote, reference and TOC links where evidence exists.
12. Confirm unresolved links are explicit.
13. Confirm provenance traces back to ConsensusIR.
14. Confirm Plan 15 readiness.

Out of scope:

1. Creating a new linking architecture.
2. Running backend execution.
3. Generating new PageExtractionIR.
4. Generating new EntityProposalDocument.
5. Generating new calibration priors.
6. Generating new ConsensusIR.
7. Creating embedded-text or tagged-PDF candidates.
8. Running Docling export.
9. Running Markdown export.
10. Running RAG export.
11. Running the end-to-end pipeline.
12. Modifying ROADMAP.md, README.md, project.md, current_plan.md or next_plan.md.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. Plan 14 must use `tools/build_linked_structure.py`.
6. Plan 14 must not create a replacement linking CLI.
7. Plan 14 must not create a new linking architecture.
8. Plan 14 must consume real Plan 13 ConsensusIR output for real execution.
9. If Plan 13 `consensus_ir.json` is missing, Plan 14 is blocked for real execution.
10. Synthetic fixtures may be used only for automated tests.
11. Synthetic fixtures must not be used as a substitute for real Plan 13 outputs in human verification.
12. `--consensus-ir` is a single JSON file path, not a directory root.
13. `linked_structure.json` and `reports/linking_report.json` are the expected outputs.
14. `linked_structure_report.json` is not an expected output.
15. `linked_structure_summary.txt` is not an expected output.
16. Missing entities-root or priors-root may degrade linking quality. The plan must record this explicitly instead of pretending those inputs exist.
17. Links must not be fabricated. If caption, footnote, reference or TOC links cannot be resolved, they must be marked unresolved or reported as warnings.
18. Plan 14 must not perform Docling export.

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
src/pdf2md/linking/builder.py
src/pdf2md/linking/extract.py
src/pdf2md/linking/resolvers.py
src/pdf2md/linking/reporting.py
src/pdf2md/linking/io.py
src/pdf2md/linking/__init__.py

tools/build_linked_structure.py

tests/test_linked_structure_builder.py
tests/test_build_linked_structure_cli.py
tests/test_linking_extract.py
tests/test_linking_resolvers.py
```

The agent may create test fixtures only under:

```text
tests/data/linking_fixtures/**
```

run_log.md is append-only and implicitly allowed when required by agent.md. It is not part of the implementation whitelist and must not be rewritten.

The agent may create temporary outputs only through CLI execution. These outputs must not be committed by default:

```text
<out-dir>/linked_structure.json
<out-dir>/reports/linking_report.json
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

config/backends.toml
config/*

src/pdf2md/local/*
src/pdf2md/connectors/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/export/*

tools/backend_smoke.py
tools/validate_connectors_page_ir.py
tools/validate_entity_proposals.py
tools/vocabulary_alignment_check.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/export_linked_docling.py
tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py

backend/*
groundtruth/corpus/*
```

If a defect is found in calibration, connector, consensus, export or backend execution code, the agent must stop and report a blocker. Do not modify those files under this plan without a human amendment.

Expected output artefacts, produced by `tools/build_linked_structure.py` and not committed unless a later policy explicitly allows it:

```text
<out-dir>/linked_structure.json
<out-dir>/reports/linking_report.json
```

Required output characteristics:

`linked_structure.json` must contain a valid LinkedStructure.

`reports/linking_report.json` must expose or summarise:

```text
document_id
source consensus_ir path
source consensus_report path if used
entities_root path if used
priors_root path if used
node counts
edge/link counts
unresolved link counts
low-confidence warning counts
caption link status
footnote link status
reference link status
TOC link status
figure/table sequence status
cross-page continuity status
provenance status
warnings
errors
Plan 15 readiness notes
```

LinkedStructure outcome taxonomy:

linked:
A relation or structure element was resolved with evidence.

unresolved:
A relation candidate exists but cannot be resolved confidently.

missing_input:
A useful optional input such as entities-root or priors-root is unavailable.

low_confidence:
A relation or structure decision exists but is below the configured confidence threshold.

not_applicable:
A relation type is not present in the document.

blocked:
The linker cannot proceed because required Plan 13 ConsensusIR input is missing or invalid.

Quality inspection outcome taxonomy:

ready_for_plan_15:
LinkedStructure is coherent enough to attempt Docling export.

ready_with_warnings:
LinkedStructure can proceed to Plan 15, but unresolved links or missing optional inputs must be noted.

not_ready_for_plan_15:
Ordering, hierarchy, provenance or critical relations are broken.

diagnostic_only:
Run was performed only for diagnostic purposes because real Plan 13 inputs were incomplete.

---

## 6. Agent tasks

Task A1:

Title:
Inspect and run the existing linking path on real data.

Goal:
Use the current `tools/build_linked_structure.py` and linking modules on one real Plan 13 ConsensusIR output.

Files allowed:

```text
tools/build_linked_structure.py
src/pdf2md/linking/builder.py
src/pdf2md/linking/extract.py
src/pdf2md/linking/resolvers.py
src/pdf2md/linking/reporting.py
src/pdf2md/linking/io.py
src/pdf2md/linking/__init__.py
tests/test_linked_structure_builder.py
tests/test_build_linked_structure_cli.py
tests/test_linking_extract.py
tests/test_linking_resolvers.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Inspect `tools/build_linked_structure.py`.
2. Confirm actual CLI flags:
   - `--consensus-ir`
   - `--consensus-report`
   - `--entities-root`
   - `--priors-root`
   - `--out-dir`
   - `--strict`
   - `--verbose`
   - `--low-confidence-threshold`
3. Confirm `--consensus-ir` expects a single JSON file path.
4. Inspect `src/pdf2md/linking/builder.py`.
5. Inspect `src/pdf2md/linking/extract.py`.
6. Inspect `src/pdf2md/linking/resolvers.py`.
7. Inspect `src/pdf2md/linking/reporting.py`.
8. Inspect `src/pdf2md/linking/io.py`.
9. Locate one real Plan 13 `consensus_ir.json`.
10. If real Plan 13 `consensus_ir.json` is missing, report a blocker in run_log.md and halt real execution.
11. Do not use synthetic fixtures as a substitute for real Plan 13 output.
12. Run the existing linking path on the real Plan 13 ConsensusIR output.
13. Record whether consensus_report, entities-root or priors-root were available.
14. Record what breaks, if anything.
15. Do not create new linking modules.
16. Do not create a new CLI.
17. Do not run consensus, calibration or export.

Command template:

```bash
conda run -n pdf2md python tools/build_linked_structure.py --consensus-ir <PLAN13_CONSENSUS_IR_JSON> --consensus-report <PLAN13_CONSENSUS_REPORT_JSON> --entities-root <ENTITIES_ROOT> --priors-root <PLAN12_PRIORS_ROOT> --out-dir groundtruth/runs/linked_structure_one_document --strict --verbose
```

If consensus_report, entities-root or priors-root are not available but the CLI supports omission, the agent may omit only those optional flags and must record the resulting warnings.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_linked_structure_builder.py -q
conda run -n pdf2md pytest tests/test_build_linked_structure_cli.py -q
conda run -n pdf2md pytest tests/test_linking_extract.py -q
conda run -n pdf2md pytest tests/test_linking_resolvers.py -q
```

Expected output:

```text
groundtruth/runs/linked_structure_one_document/linked_structure.json
groundtruth/runs/linked_structure_one_document/reports/linking_report.json
```

Completion evidence:
Agent must report command used, CLI flags confirmed, outputs created, missing optional inputs and failures observed.

Human verification required:
yes. Covered by H1 and H2.

Task A2:

Title:
Fix linking path for real data and add integration coverage.

Goal:
Fix failures found in A1 inside the existing linking modules and ensure real-data patterns are covered.

Files allowed:

```text
src/pdf2md/linking/builder.py
src/pdf2md/linking/extract.py
src/pdf2md/linking/resolvers.py
src/pdf2md/linking/reporting.py
src/pdf2md/linking/io.py
src/pdf2md/linking/__init__.py
tools/build_linked_structure.py
tests/test_linked_structure_builder.py
tests/test_build_linked_structure_cli.py
tests/test_linking_extract.py
tests/test_linking_resolvers.py
tests/data/linking_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Fix real-data loading issues in `linking/io.py` if needed.
2. Fix candidate extraction issues in `linking/extract.py` if real ConsensusIR patterns are not recognised.
3. Fix resolver issues in `linking/resolvers.py` if reading order, hierarchy, captions, footnotes, references, TOC links or figure/table sequences fail.
4. Fix builder orchestration issues in `linking/builder.py` if candidates are extracted but not assembled correctly.
5. Fix `reporting.py` if warnings, unresolved links or Plan 15 readiness are not inspectable.
6. Add or update integration coverage under `tests/data/linking_fixtures/**` only when needed.
7. Ensure cross-page continuity is preserved.
8. Ensure caption links are resolved only when evidence exists.
9. Ensure footnote/reference/TOC links are resolved only when evidence exists.
10. Ensure unresolved links are explicit in `linked_structure.json` or `reports/linking_report.json`.
11. Ensure missing entities-root or priors-root are reported as warnings when relevant.
12. Preserve provenance back to ConsensusIR.
13. Do not fabricate missing links.
14. Do not modify consensus, calibration, connector or export code.
15. Do not perform Docling export.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_linked_structure_builder.py -q
conda run -n pdf2md pytest tests/test_build_linked_structure_cli.py -q
conda run -n pdf2md pytest tests/test_linking_extract.py -q
conda run -n pdf2md pytest tests/test_linking_resolvers.py -q
```

Expected output:
Existing linking path works on fixtures and real Plan 13 ConsensusIR outputs, or blockers are explicitly reported.

Completion evidence:
Agent must report files changed, defects fixed, tests run and any remaining unresolved issues.

Human verification required:
yes. Covered by H2.

Task A3:

Title:
Validate LinkedStructure quality and Plan 15 readiness.

Goal:
Verify that the linked structure is coherent enough for Docling export in Plan 15.

Files allowed:

```text
src/pdf2md/linking/reporting.py
tools/build_linked_structure.py
tests/test_linked_structure_builder.py
tests/test_build_linked_structure_cli.py
tests/test_linking_extract.py
tests/test_linking_resolvers.py
tests/data/linking_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Inspect `linked_structure.json` against the source ConsensusIR.
2. Verify document-level reading order.
3. Verify section hierarchy.
4. Verify cross-page continuity.
5. Verify figure/table caption links where evidence exists.
6. Verify figure/table sequencing where evidence exists.
7. Verify footnote links where evidence exists.
8. Verify reference links where evidence exists.
9. Verify TOC links where evidence exists.
10. Verify unresolved links are explicit.
11. Verify provenance traces back to ConsensusIR.
12. Verify `reports/linking_report.json` contains useful warnings and readiness information.
13. Classify Plan 15 readiness as `ready_for_plan_15`, `ready_with_warnings`, or `not_ready_for_plan_15`.
14. Do not perform Docling export.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_linked_structure_builder.py -q
conda run -n pdf2md pytest tests/test_build_linked_structure_cli.py -q
conda run -n pdf2md pytest tests/test_linking_extract.py -q
conda run -n pdf2md pytest tests/test_linking_resolvers.py -q
```

Expected output:
Plan 15 readiness is clearly recorded in `reports/linking_report.json` or the agent report.

Completion evidence:
Agent must report quality observations and Plan 15 readiness.

Human verification required:
yes. Covered by H3.

---

## 7. Human verification checkpoints

Checkpoint H1:

Title:
Input readiness and existing CLI gate.

Purpose:
Confirm that Plan 14 has a real Plan 13 ConsensusIR file and uses the existing linking CLI.

Required environment:
pdf2md

Preconditions:
Plan 13 is human_verified.
Plan 13 produced `consensus_ir.json`.
Plan 13 produced `reports/consensus_report.json` if available.
Plan 12 priors-root and Plan 11/13 entities-root are identified if available.

Command:

```bash
conda run -n pdf2md python tools/build_linked_structure.py --help
ls -lh <PLAN13_CONSENSUS_IR_JSON>
ls -lh <PLAN13_CONSENSUS_REPORT_JSON>
```

Optional:

```bash
ls -lh <ENTITIES_ROOT>
ls -lh <PLAN12_PRIORS_ROOT>
```

Verification procedure:

1. Run the help command.
2. Confirm the CLI is `tools/build_linked_structure.py`.
3. Confirm the help output includes:
   - `--consensus-ir`
   - `--consensus-report`
   - `--entities-root`
   - `--priors-root`
   - `--out-dir`
   - `--strict`
   - `--verbose`
   - `--low-confidence-threshold`
4. Confirm `--consensus-ir` is a single JSON file path.
5. Confirm `PLAN13_CONSENSUS_IR_JSON` exists.
6. Confirm `PLAN13_CONSENSUS_IR_JSON` is from real Plan 13 output, not a test fixture.
7. Confirm consensus_report path if available.
8. Confirm entities-root and priors-root if available.
9. If real Plan 13 `consensus_ir.json` is missing, mark Plan 14 blocked for real execution.

Pass criteria:

```text
Existing CLI is used.
PLAN13_CONSENSUS_IR_JSON exists.
PLAN13_CONSENSUS_IR_JSON is a real Plan 13 artefact.
--consensus-ir is treated as a file path.
Optional input availability is recorded.
```

Fail criteria:

```text
A new linking CLI is used.
PLAN13_CONSENSUS_IR_JSON is missing.
A test fixture is used as substitute for real Plan 13 output.
--consensus-ir is treated as a directory.
Optional missing inputs are not recorded.
```

Evidence to record:

```text
Paste help output or relevant flags.
Paste PLAN13_CONSENSUS_IR_JSON path.
Paste consensus_report path if available.
Paste entities-root and priors-root availability.
Paste whether any optional inputs are missing.
```

Checkpoint H2:

Title:
One-document LinkedStructure build.

Purpose:
Confirm that the existing linking path builds valid LinkedStructure from real Plan 13 ConsensusIR.

Required environment:
pdf2md

Preconditions:
H1 passed.
Tasks A1 and A2 are complete.

Command:

```bash
conda run -n pdf2md python tools/build_linked_structure.py --consensus-ir <PLAN13_CONSENSUS_IR_JSON> --consensus-report <PLAN13_CONSENSUS_REPORT_JSON> --entities-root <ENTITIES_ROOT> --priors-root <PLAN12_PRIORS_ROOT> --out-dir groundtruth/runs/linked_structure_one_document --strict --verbose
```

If consensus_report, entities-root or priors-root are unavailable but optional in the CLI, omit only the unavailable optional flags and record the warning.

Expected output files:

```text
groundtruth/runs/linked_structure_one_document/linked_structure.json
groundtruth/runs/linked_structure_one_document/reports/linking_report.json
```

Verification procedure:

1. Replace placeholders with real Plan 13, Plan 12 and entity paths.
2. Run the command exactly as written, omitting unavailable optional flags only if needed.
3. Confirm the command exits 0.
4. Open `linked_structure.json`.
5. Confirm LinkedStructure validates.
6. Open `reports/linking_report.json`.
7. Confirm source ConsensusIR path is recorded or traceable.
8. Confirm missing optional inputs are recorded as warnings if omitted.
9. Confirm unresolved links are explicit.
10. Confirm no `linked_structure_report.json` is expected.
11. Confirm no `linked_structure_summary.txt` is expected.
12. Confirm no Docling, Markdown or RAG export artefacts are produced.

Pass criteria:

```text
linked_structure.json exists.
reports/linking_report.json exists.
LinkedStructure validates.
Real Plan 13 ConsensusIR was used.
Missing optional inputs are recorded.
Unresolved links are explicit.
No export artefacts are produced.
```

Fail criteria:

```text
linked_structure.json is missing.
reports/linking_report.json is missing.
LinkedStructure fails validation.
A test fixture is used as substitute for real Plan 13 output.
Unresolved links are hidden.
Links are fabricated without evidence.
Docling export is performed inside Plan 14.
```

Evidence to record:

```text
Paste the command.
Paste exit code.
Paste linked_structure.json path.
Paste reports/linking_report.json path.
Paste missing optional input warnings.
Paste one resolved relation if present.
Paste one unresolved relation or warning if present.
Paste confirmation that no export artefacts were produced.
```

Checkpoint H3:

Title:
Quality and Plan 15 readiness.

Purpose:
Confirm that LinkedStructure is coherent enough to attempt Docling export in Plan 15.

Required environment:
pdf2md

Preconditions:
H2 passed.
Task A3 is complete.

Command:

Manual inspection of:

```text
groundtruth/runs/linked_structure_one_document/linked_structure.json
groundtruth/runs/linked_structure_one_document/reports/linking_report.json
<PLAN13_CONSENSUS_IR_JSON>
<PLAN13_CONSENSUS_REPORT_JSON>
```

Verification procedure:

1. Open `linked_structure.json`.
2. Open `reports/linking_report.json`.
3. Open the source ConsensusIR.
4. Verify document-level reading order.
5. Verify section hierarchy.
6. Verify cross-page continuity.
7. Inspect figure/table caption links where present.
8. Inspect footnote/reference/TOC links where present.
9. Confirm unresolved links are explicit.
10. Confirm provenance traces back to ConsensusIR.
11. Confirm Plan 15 readiness is stated.
12. Confirm no export output is claimed.

Pass criteria:

```text
Document order is coherent.
Section hierarchy is plausible.
Cross-page continuity is preserved.
Caption/footnote/reference/TOC links are either plausible or explicitly unresolved.
Provenance is traceable.
Plan 15 readiness is ready_for_plan_15 or ready_with_warnings.
No export output is produced.
```

Fail criteria:

```text
Document order is incoherent.
Section hierarchy is broken.
Cross-page continuity is lost.
Links are fabricated.
Unresolved links are hidden.
Provenance is lost.
Plan 15 readiness is missing.
Docling export is performed.
```

Evidence to record:

```text
Paste linked_structure.json path.
Paste linking_report.json path.
Paste reading order assessment.
Paste section hierarchy assessment.
Paste caption/footnote/reference/TOC assessment.
Paste unresolved link summary.
Paste Plan 15 readiness.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_linked_structure_builder.py -q
conda run -n pdf2md pytest tests/test_build_linked_structure_cli.py -q
conda run -n pdf2md pytest tests/test_linking_extract.py -q
conda run -n pdf2md pytest tests/test_linking_resolvers.py -q
```

Human verification test matrix:

```text
H1 input readiness and existing CLI gate
H2 one-document LinkedStructure build
H3 quality and Plan 15 readiness
```

Plan-level statuses:

linking_ready:
Real Plan 13 ConsensusIR is available and the linker inputs are identified.

linking_blocked:
Real Plan 13 ConsensusIR is missing or invalid.

diagnostic_only:
Human permits a diagnostic run with incomplete optional inputs, but real Plan 13 ConsensusIR is still required.

Per-document linking statuses:

linked_structure_built:
LinkedStructure validates for the document.

linked_structure_failed:
Linking fails.

ready_for_plan_15:
LinkedStructure is coherent enough for Docling export validation.

ready_with_warnings:
LinkedStructure is usable for Plan 15 but unresolved links or missing optional inputs must be noted.

not_ready_for_plan_15:
Ordering, hierarchy, provenance or critical relations are broken.

Failure classes:

repository_defect:
Existing linking builder, extraction, resolver, reporting, I/O, tests or CLI integration are wrong.

missing_plan13_consensus:
Real Plan 13 `consensus_ir.json` is missing.

invalid_plan13_consensus:
Plan 13 `consensus_ir.json` exists but fails validation.

missing_optional_inputs:
consensus_report, entities-root or priors-root are unavailable.

linking_schema_failure:
LinkedStructure fails schema validation.

reading_order_failure:
Document reading order is incoherent.

section_hierarchy_failure:
Section hierarchy is broken.

relation_resolution_failure:
Captions, footnotes, references or TOC links are wrong or fabricated.

unresolved_reporting_failure:
Unresolved links are hidden.

provenance_failure:
LinkedStructure loses traceability to ConsensusIR.

scope_violation:
Plan 14 performs consensus, calibration, backend extraction, export or end-to-end work.

human_procedure_error:
Human ran the wrong command, used wrong paths or inspected stale outputs.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

Failure handling:

If failure_class is repository_defect:
The agent must fix the implementation or report a blocker.

If failure_class is missing_plan13_consensus:
Plan 14 is blocked for real execution until Plan 13 output exists.

If failure_class is invalid_plan13_consensus:
Plan 13 must be fixed or reverified.

If failure_class is missing_optional_inputs:
Proceed only if CLI supports omission and warnings are recorded.

If failure_class is linking_schema_failure:
Fix linking construction or schema usage.

If failure_class is reading_order_failure:
Fix reading-order extraction or resolver logic.

If failure_class is section_hierarchy_failure:
Fix section hierarchy resolver logic.

If failure_class is relation_resolution_failure:
Fix resolver logic or mark relation unresolved.

If failure_class is unresolved_reporting_failure:
Fix reporting before human_verified.

If failure_class is provenance_failure:
Fix provenance propagation before human_verified.

If failure_class is scope_violation:
Reject the plan output and revise.

If failure_class is human_procedure_error:
Human checkpoint must be rerun correctly.

If failure_class is test_expectation_wrong:
The plan must be revised by a human before continuing.

---

## 9. Checkpoints, push policy and hand-off

Checkpoint C0: Plan ready

Required before agent starts:

```text
status is active
Plan 13 status is human_verified or human explicitly approves drafting only
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
existing build_linked_structure.py path used
real Plan 13 consensus_ir.json used or blocker reported
linked_structure.json produced or blocker reported
reports/linking_report.json produced or blocker reported
agent report completed
status set to agent_complete or human_verification_required
```

Checkpoint C2: Human verification complete

Required before merge or milestone completion:

```text
H1 input readiness passed
H2 one-document LinkedStructure build passed
H3 quality and Plan 15 readiness completed
all expected output files produced or failures classified
Plan 15 readiness recorded
human verification report completed
status set to human_verified by a human
```

Checkpoint C3: Plan finished and promoted

Required before promotion:

```text
status is human_verified
Plan 14 is archived after completion
history.md summary is prepared or updated
Plan 15 exists as next_plan.md or approved prepared plan
Plan 15 may be promoted to current_plan.md only after Plan 14 is finished
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
plans/archive/plan-14-linkedstructure-cross-page-semantic-linking.md
```

2. Append a milestone summary to history.md.
3. Promote Plan 15 to current_plan.md.
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
Existing linking code reused:
build_linked_structure.py CLI flags confirmed:
PLAN13_CONSENSUS_IR_JSON:
PLAN13_CONSENSUS_REPORT_JSON:
ENTITIES_ROOT:
PLAN12_PRIORS_ROOT:
Optional inputs missing:
Automated tests run:
Automated tests passed:
Automated tests failed:
Failure classes:
LinkedStructure command:
Generated linked_structure.json:
Generated reports/linking_report.json:
Quality inspection result:
Plan 15 readiness:
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
Plan 13 consensus_ir:
Plan 13 consensus_report:
Entities root:
Priors root:
Commands run:
Exit codes:
Output files checked:
LinkedStructure status:
Linking report status:
Reading order assessment:
Section hierarchy assessment:
Cross-page continuity assessment:
Caption/footnote/reference/TOC assessment:
Unresolved links:
Provenance status:
Plan 15 readiness:
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
3. Was run_log.md append-only if touched?
4. Were all declared automated tests run?
5. Did any automated test fail?
6. Did the implementation reuse `tools/build_linked_structure.py`?
7. Did the implementation avoid creating a new linking CLI?
8. Did the implementation reuse existing linking modules?
9. Did the implementation use real Plan 13 `consensus_ir.json` for human verification?
10. Did the implementation avoid using synthetic fixtures as real-input substitutes?
11. Did the implementation treat `--consensus-ir` as a file path?
12. Did the implementation produce `linked_structure.json`?
13. Did the implementation produce `reports/linking_report.json`?
14. Did the implementation avoid requiring `linked_structure_report.json`?
15. Did the implementation avoid requiring `linked_structure_summary.txt`?
16. Did the implementation avoid consensus work?
17. Did the implementation avoid calibration work?
18. Did the implementation avoid backend extraction?
19. Did the implementation avoid Docling export?
20. Did LinkedStructure validate?
21. Is reading order coherent?
22. Is section hierarchy plausible?
23. Is cross-page continuity preserved?
24. Are caption/footnote/reference/TOC links plausible or explicitly unresolved?
25. Are unresolved links visible?
26. Is provenance traceable to ConsensusIR?
27. Are missing optional inputs recorded as warnings?
28. Is Plan 15 readiness clear?
29. Were generated reports left uncommitted by default?
30. Is Plan 15 clearly identified as the next plan?
31. Is it safe to mark this plan human_verified?
32. Is it safe to promote the next plan?
33. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-09 — draft — human — Plan 14 created from ROADMAP.md and PLAN_TEMPLATE.md
2026-05-09 — active — human — approved for agent execution
2026-05-09 — agent_in_progress — agent — branch created
2026-05-09 — agent_complete — agent — automated tests passed and linked structure output generated
2026-05-09 — human_verification_required — agent — awaiting human linked-structure checks
2026-05-09 — human_verified — human — all checkpoints passed
2026-05-09 — finished — human — archived and promoted
```
