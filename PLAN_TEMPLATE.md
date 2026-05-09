# PLAN_TEMPLATE.md

Plan X — Short Descriptive Name

Status:
draft

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
Phase N — Phase name

Current roadmap estimate:
From X% to Y%

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan X of Y

Previous plan:
Plan X-1 — Name

Required previous plan status:
human_verified

Next plan after completion:
Plan X+1 — Name

Branch name:
plan-X-short-name

---

## 1. Purpose

Describe, in one precise paragraph, what this plan is intended to make true.

The purpose must be tied to ROADMAP.md.

Example:

This plan validates that the local LaTeX-derived ground-truth corpus can be discovered, inspected, and reported before any OCR backend is run. It ensures that required artefacts such as .tex source, compiled PDF, LaTeXML XML, Docling ground-truth JSON, and metadata are present or clearly reported as missing.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

README.md is the public entry point.

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
git switch -c plan-X-short-name
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If git status is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress unless the plan explicitly allows it.

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

Backend runtime commands must run only in their expected backend environments.

Expected backend environments, when relevant:

```text
pdf2md-mineru
pdf2md-paddleocr
pdf2md-deepseek
```

If this plan does not explicitly require backend execution, the agent must not run backend OCR or model scripts.

---

## 4. Scope, constraints, and dependencies

In scope:

1. <Concrete item>
2. <Concrete item>
3. <Concrete item>

Out of scope:

1. <Concrete item>
2. <Concrete item>
3. <Concrete item>

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. Missing local tools, models, credentials, GPUs, or backend environments must be reported as environment-not-ready, not as repository test failures.
6. If the plan requires an undeclared dependency or tool, the agent must stop and report a blocker.
7. If a human verification task is vague or impossible to execute, the plan must be revised before implementation continues.

Allowed Python dependencies:

```text
none
```

or:

```text
package-name==version
```

Allowed external tools:

```text
none
```

or:

```text
tool-name — purpose
```

Allowed environment-modifying commands:

```text
none
```

or:

```text
exact command and reason
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these files:

```text
allowed/path/one.py
allowed/path/two.py
tests/test_example.py
```

The agent must not modify these files:

```text
README.md
ROADMAP.md
project.md
current_plan.md
next_plan.md
history.md
backend/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*
```

Adjust the forbidden list for each plan.

If a forbidden file must be changed, this plan is incomplete and must be revised by a human before implementation starts.

Expected output artefacts:

```text
artefact/path/report.json — machine-readable report
artefact/path/summary.txt — human-readable summary
```

Required report contract, when this plan creates a JSON report:

```text
schema_name
schema_version
generated_at or created_at
tool_name
input_paths
status
warnings
errors
metadata
```

For document-level reports, each document entry must include:

```text
document_id
document_path
status
required_files_present
required_files_missing
warnings
metadata
```

---

## 6. Agent tasks

Each agent task must be specific, testable, and limited to the file whitelist.

Task A1:

Title:
Short task title

Goal:
Describe the concrete implementation result.

Files allowed:

```text
allowed/path/one.py
tests/test_example.py
```

Implementation requirements:

1. Requirement one
2. Requirement two
3. Requirement three

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_example.py -q
```

Expected output:
Describe expected files, functions, models, or CLI behaviour.

Completion evidence:
The agent must report files changed, tests run, exit codes, and any blockers.

Human verification required:
yes or no

Task A2:

Title:
Short task title

Goal:
...

Files allowed:

```text
...
```

Implementation requirements:

1. ...
2. ...
3. ...

Automated tests required:

```text
...
```

Expected output:
...

Completion evidence:
...

Human verification required:
yes or no

---

## 7. Human verification checkpoints

Human verification tasks must be exact. Do not write vague instructions such as "human verifies conversion".

Each human checkpoint must include:

```text
purpose
required environment
preconditions
exact command
input files
expected output files
verification procedure
pass criteria
fail criteria
evidence to record
```

Checkpoint H1:

Title:
Verify local ground-truth validation report on minimal corpus

Purpose:
Confirm that the validation CLI can inspect a local ground-truth corpus and write both machine-readable and human-readable reports.

Required environment:
pdf2md

Preconditions:
The repository package is installed in editable mode.
The file tools/local_groundtruth_validate.py exists.
The fixture directory tests/data/local_groundtruth_fixtures/minimal_valid_corpus exists.

Command:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root tests/data/local_groundtruth_fixtures/minimal_valid_corpus --out-dir /tmp/pdf2md_groundtruth_validation_test --run-validator --verbose
```

Input files:

```text
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.tex
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.pdf.placeholder
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.latexml.xml
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.docling.json
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.docling_groundtruth_meta.json
```

Expected output files:

```text
/tmp/pdf2md_groundtruth_validation_test/groundtruth_validation_report.json
/tmp/pdf2md_groundtruth_validation_test/groundtruth_validation_summary.txt
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm the command exits with code 0.
3. Run:

```bash
python -m json.tool /tmp/pdf2md_groundtruth_validation_test/groundtruth_validation_report.json
```

4. Open:

```text
/tmp/pdf2md_groundtruth_validation_test/groundtruth_validation_summary.txt
```

5. Confirm the summary lists simple_doc as ready.
6. Confirm the JSON report has schema_name equal to pdf2md.LocalGroundtruthValidationReport.
7. Confirm corpus_ready is true.

Pass criteria:

```text
The command exits 0.
Both expected output files exist.
The JSON report is valid JSON.
schema_name equals pdf2md.LocalGroundtruthValidationReport.
corpus_ready equals true.
The summary file names simple_doc and reports it as ready.
```

Fail criteria:

```text
The command exits non-zero.
Either expected output file is missing.
The JSON file is invalid.
The report does not include simple_doc.
corpus_ready is false for the minimal valid corpus.
```

Evidence to record:

```text
Paste the command used.
Paste the exit code.
Paste the first 20 lines of groundtruth_validation_summary.txt.
Paste the values of schema_name and corpus_ready from the JSON report.
```

Checkpoint H2:

Title:
Specific human checkpoint title

Purpose:
...

Required environment:
...

Preconditions:
...

Command:

```text
...
```

Input files:

```text
...
```

Expected output files:

```text
...
```

Verification procedure:

1. ...
2. ...
3. ...

Pass criteria:

```text
...
```

Fail criteria:

```text
...
```

Evidence to record:

```text
...
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_example.py -q
conda run -n pdf2md pytest tests/test_related_previous_plan.py -q
```

Human verification test matrix:

```text
Exact human command one
Exact human command two
```

Failure classes:

repository_defect:
The implementation is wrong, a test fails due to logic, an output schema is invalid, or a CLI signature is broken.

environment_missing:
A required local tool, backend environment, model, credential, GPU, or system package is missing.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

human_procedure_error:
The human ran the wrong command, used the wrong environment, or inspected the wrong file.

upstream_dependency_issue:
A third-party package or external tool changed behaviour or failed independently.

permission_or_filesystem_error:
The command cannot write, read, or access required paths.

timeout:
The command did not finish within the expected time.

Failure handling:

If failure_class is repository_defect:
The agent must fix the implementation or report a blocker.

If failure_class is environment_missing:
The human or environment owner must fix the environment, or the plan must be marked blocked.

If failure_class is test_expectation_wrong:
The plan must be revised by a human before continuing.

If failure_class is human_procedure_error:
The human task must be rerun correctly.

If failure_class is upstream_dependency_issue:
The issue must be documented, and the plan owner decides whether to pin, mock, skip as human, or block.

If failure_class is permission_or_filesystem_error:
The path, permissions, or output location must be corrected.

If failure_class is timeout:
The timeout, fixture size, or command behaviour must be reviewed.

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
next_plan.md is promoted to current_plan.md
new next_plan.md is created from PLAN_TEMPLATE.md or an approved future plan
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
plans/archive/plan-X-short-name.md
```

2. Append a milestone summary to history.md.
3. Promote next_plan.md to current_plan.md.
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
Plan:
Reviewer:
Date:
Environment:
Commands run:
Exit codes:
Output files checked:
Comparison performed:
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
6. Were all human verification checkpoints run exactly as written?
7. Were expected output files produced?
8. Were comparison criteria satisfied?
9. Was evidence recorded?
10. Are dependencies and external tools compliant with the plan?
11. Is the next plan clearly identified?
12. Is it safe to mark this plan human_verified?
13. Is it safe to promote next_plan.md to current_plan.md?
14. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-09 — draft — human — initial plan created
2026-05-09 — active — human — approved for agent execution
2026-05-09 — agent_in_progress — agent — branch created
2026-05-09 — agent_complete — agent — automated tests passed
2026-05-09 — human_verification_required — agent — awaiting human checks
2026-05-09 — human_verified — human — all checkpoints passed
2026-05-09 — finished — human — archived and promoted
```
