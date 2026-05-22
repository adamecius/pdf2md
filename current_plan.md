# Plan 8 — Local Ground-Truth Corpus Validation plus Documentation Consistency

Status:
human_verification_required

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
Phase 1 — Ground-truth engine
Small Phase 0 exit criterion — documentation consistency

Current roadmap estimate:
Phase 1 from 82% toward 90%

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 8 of the pre-MVP implementation sequence, ending at Plan 16.

Previous plan:
Plan 7 — Local environment and toolchain preflight

Required previous plan status:
human_verified

Next plan after completion:
Plan 9 — Real Backend Smoke Readiness

Branch name:
plan-8-groundtruth-validation

---

## 1. Purpose

This plan validates that the local LaTeX-derived ground-truth corpus can be discovered, inspected, classified, and reported before any real OCR or backend execution is run.

It must verify the readiness of source-known artefacts that already exist on disk. The plan inspects `.tex` source files, `meta.toml`, Docling ground-truth JSON, compiled PDFs where present, tagged PDFs where detectable, LaTeXML XML where present, and Docling ground-truth metadata where present.

This plan is inspect-only. It does not compile LaTeX, run LuaLaTeX, run LaTeXML, generate new ground truth, run validators, run backends, run calibration, run consensus, run semantic linking, or export Docling from backend output.

It also performs a narrow documentation consistency check. That check is limited to legacy documentation, agent governance compatibility, and one README command example that still documents an obsolete validator flag.

The plan answers this question:

```text
Can the local ground-truth corpus be inspected and reported in a machine-readable way before running any backend ensemble?
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
git switch -c plan-8-groundtruth-validation
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If git status is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 7 has been marked human_verified and archived.
8. Do not mark this plan human_verified or finished. Only the human reviewer may do that.

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

Backend runtime commands must not be run in this plan.

Expected backend environments are irrelevant for Plan 8 except as already reported by Plan 7.

If Plan 7 has not passed human verification, this Plan 8 file may be reviewed, but must not be promoted to current_plan.md.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Discover local LaTeX ground-truth corpus documents.
2. Detect supported ground-truth layouts.
3. Validate required artefact presence for corpus readiness.
4. Report optional artefact presence without hiding missing optional evidence.
5. Classify each document as ready, partial, or missing_critical.
6. Write a machine-readable validation report.
7. Write a human-readable validation summary.
8. Support strict and non-strict modes.
9. Add minimal fixture corpora for ready, partial, and empty cases.
10. Perform narrow documentation consistency edits if ROADMAP.md or PLAN_TEMPLATE.md is contradicted by allowed documentation files.
11. Align README.md Section 12 with the inspect-only Plan 8 CLI by removing the obsolete `--run-validator` example flag if present.
12. Add a narrow compatibility note to agent.md if its older mode/status terminology conflicts with PLAN_TEMPLATE.md for template-based plans.

Out of scope:

1. Running LaTeX compilation.
2. Running LuaLaTeX compilation.
3. Running LaTeXML conversion.
4. Running existing ground-truth generator scripts.
5. Running existing ground-truth validator scripts.
6. Running OCR backends.
7. Running backend model scripts.
8. Running connectors on real backend output.
9. Running calibration.
10. Running consensus.
11. Running semantic linking.
12. Running Docling export from backend output.
13. Rewriting generator or validator scripts.
14. Changing ROADMAP.md.
15. Changing README.md outside Section 12.
16. Changing project.md.
17. Changing current_plan.md.
18. Changing next_plan.md.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. Missing local tools, corpus artefacts, or optional generated files must be reported as environment-not-ready or corpus-not-ready, not as unit-test failures.
6. If the plan requires an undeclared dependency or tool, the agent must stop and report a blocker.
7. If a human verification task is vague or impossible to execute, the plan must be revised before implementation continues.
8. Unit tests must not require real LaTeX, LuaLaTeX, LaTeXML, backend environments, OCR models, GPUs, or network access.

Allowed Python dependencies:

```text
none beyond existing repository dependencies
```

Allowed external tools:

```text
none
```

Allowed environment-modifying commands:

```text
none
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these implementation and test files:

```text
src/pdf2md/local/groundtruth.py

tools/local_groundtruth_validate.py

tests/test_local_groundtruth_validate.py

tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.tex
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/meta.toml
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.docling.json
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.pdf.placeholder
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.latexml.xml
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.docling_groundtruth_meta.json

tests/data/local_groundtruth_fixtures/partial_corpus/incomplete_doc/incomplete_doc.tex
tests/data/local_groundtruth_fixtures/partial_corpus/incomplete_doc/meta.toml

tests/data/local_groundtruth_fixtures/empty_corpus/.gitkeep
```

The agent may modify only these documentation files for narrow consistency edits:

```text
README_latex_docling_groundtruth.md
docs/docling_layer.md
history.md
agent.md
README.md
```

Documentation edit limits:

```text
README_latex_docling_groundtruth.md:
  Only to remove direct contradiction with ROADMAP.md or clarify the ground-truth corpus role.

docs/docling_layer.md:
  Only to mark legacy material as legacy or clarify its relationship to the current canonical Docling export path.

history.md:
  Only to add or correct completed governance milestones such as ROADMAP.md or PLAN_TEMPLATE.md if missing.

agent.md:
  Only to add a narrow compatibility note that, for plans written using PLAN_TEMPLATE.md, the PLAN_TEMPLATE.md lifecycle, checkpoints and human-verification rules supersede older status terminology where they conflict.

README.md:
  Only Section 12, only to align the `tools/local_groundtruth_validate.py` example with the Plan 8 inspect-only CLI by removing obsolete validator/generator flags such as `--run-validator`.
```

Broad rewriting, style polishing, and new architectural claims are out of scope.

The agent must not modify these files, except where explicitly allowed above:

```text
ROADMAP.md
PLAN_TEMPLATE.md
project.md
current_plan.md
next_plan.md
run_log.md
pyproject.toml

generate_latex_docling_groundtruth.py
validate_latex_docling_groundtruth.py

src/pdf2md/models/*
src/pdf2md/local/preflight.py
src/pdf2md/connectors/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

backend/*
groundtruth/corpus/*

tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py
tools/local_groundtruth_preflight.py
```

If a forbidden file must be changed, this plan is incomplete and must be revised by a human before implementation starts.

Expected output artefacts, produced by the CLI and not committed unless a later policy explicitly allows it:

```text
<out-dir>/groundtruth_validation_report.json — machine-readable corpus validation report
<out-dir>/groundtruth_validation_summary.txt — human-readable validation summary
```

Required report contract:

```text
schema_name: pdf2md.LocalGroundtruthValidationReport
schema_version: 1.0.0
generated_at: ISO 8601 timestamp
tool_name: local_groundtruth_validate
corpus_root: path inspected
corpus_ready: bool
total_documents: int
documents_ready: int
documents_partial: int
documents_missing_critical: int
documents: list of per-document entries
warnings: list of strings
metadata: dict
```

Per-document entry contract:

```text
document_id: str
document_path: str
status: ready | partial | missing_critical
artefacts: dict
required_present: list of str
required_missing: list of str
optional_present: list of str
optional_missing: list of str
warnings: list of str
metadata: dict
```

Artefact classification:

```text
Required artefacts for status ready:
- .tex source file
- meta.toml
- .docling.json

Optional artefacts, always reported:
- compiled PDF, .pdf
- tagged PDF where detectable
- LaTeXML XML, .latexml.xml or .xml
- .docling_groundtruth_meta.json
```

Status logic:

```text
ready:
  all required artefacts are present.

partial:
  .tex source exists, but one or more required artefacts are missing.

missing_critical:
  no .tex source exists for the document, the document directory is invalid, the corpus root is missing, or no documents are found.
```

Empty corpus behaviour:

```text
non-strict mode exits 0, writes report, sets corpus_ready=false, total_documents=0.
strict mode writes report and exits 1.
```

---

## 6. Agent tasks

Task A1:

Title:
Implement local ground-truth validation models and discovery.

Goal:
Create `src/pdf2md/local/groundtruth.py` with typed report models, corpus discovery, artefact inspection, document readiness classification, and deterministic report generation.

Files allowed:

```text
src/pdf2md/local/groundtruth.py
tests/test_local_groundtruth_validate.py
tests/data/local_groundtruth_fixtures/*
```

Implementation requirements:

1. Define Pydantic models or equivalent typed models for artefact presence, document validation entries, and the full validation report.
2. Implement `discover_corpus_documents(corpus_root: Path) -> list[Path]`.
3. Implement `inspect_document(doc_dir: Path) -> DocumentValidationEntry`.
4. Implement `build_validation_report(corpus_root: Path) -> GroundtruthValidationReport`.
5. Sort documents deterministically by document ID.
6. Detect `.tex`, `meta.toml`, `.docling.json`, `.pdf`, tagged PDF where detectable, `.latexml.xml` or `.xml`, and `.docling_groundtruth_meta.json`.
7. Classify documents as ready, partial, or missing_critical.
8. Parse `meta.toml` when present using stdlib `tomllib` on Python 3.11+.
9. Include expected features and expected counts from metadata when available.
10. Do not run LaTeX, LaTeXML, generator scripts, validator scripts, or backends.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_local_groundtruth_validate.py -q
```

Expected output:
A module importable as:

```python
from pdf2md.local.groundtruth import build_validation_report
```

Completion evidence:
Agent must report files changed, models created, discovery logic implemented, and tests run.

Human verification required:
no. Covered by H1, H2, and H3.

Task A2:

Title:
Implement local ground-truth validation CLI.

Goal:
Create `tools/local_groundtruth_validate.py` as a CLI entry point around the validation module.

Files allowed:

```text
tools/local_groundtruth_validate.py
tests/test_local_groundtruth_validate.py
```

Implementation requirements:

1. Accept `--corpus-root`, default `groundtruth/corpus/latex`.
2. Accept `--out-dir`, required.
3. Accept `--strict`.
4. Accept `--verbose`.
5. Call `build_validation_report()` and write both JSON and text summary.
6. In non-strict mode, exit 0 after writing the report even when corpus_ready is false.
7. In strict mode, exit 1 when corpus_ready is false.
8. Exit 1 for invalid CLI arguments or unexpected repository errors.
9. Print summary to stdout when `--verbose` is set.
10. Do not expose generator, compiler, validator, backend, calibration, consensus, linking, or export execution options in this plan.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_local_groundtruth_validate.py -q
```

Expected output:
A script runnable as:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root <path> --out-dir <path>
```

Completion evidence:
Agent must report CLI command examples, exit-code behaviour, and tests run.

Human verification required:
no. Covered by H1, H2, and H3.

Task A3:

Title:
Create fixtures and automated tests.

Goal:
Create deterministic fixtures and tests for ready, partial, and empty corpus behaviour.

Files allowed:

```text
tests/test_local_groundtruth_validate.py
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/*
tests/data/local_groundtruth_fixtures/partial_corpus/*
tests/data/local_groundtruth_fixtures/empty_corpus/*
```

Implementation requirements:

1. Create `minimal_valid_corpus/simple_doc/` with `simple_doc.tex`, `meta.toml`, and `simple_doc.docling.json`.
2. Include optional artefact examples in the minimal valid corpus where practical: `.pdf.placeholder`, `.latexml.xml`, and `.docling_groundtruth_meta.json`.
3. Create `partial_corpus/incomplete_doc/` with `incomplete_doc.tex` and `meta.toml`, but no `.docling.json`.
4. Create `empty_corpus/.gitkeep`.
5. Add tests for discovery, inspection, status classification, metadata parsing, deterministic report generation, JSON report contract, CLI non-strict mode, CLI strict mode, and output file writing.
6. Ensure all tests pass without LaTeX, LaTeXML, backend environments, GPUs, or network access.
7. Ensure empty corpus is not reported as ready.

Required tests:

```text
test_discover_finds_all_documents
test_inspect_ready_document
test_inspect_partial_document
test_empty_corpus_is_not_ready
test_report_schema_validates
test_report_is_deterministic
test_meta_toml_parsed
test_optional_artefacts_are_reported
test_cli_nonstrict_exits_zero_on_partial
test_cli_strict_exits_one_on_partial
test_cli_nonstrict_exits_zero_on_empty
test_cli_strict_exits_one_on_empty
test_cli_writes_report_and_summary
test_report_json_contract
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_local_groundtruth_validate.py -q
```

Expected output:
All Plan 8 tests pass.

Completion evidence:
Agent must report test count, pass count, and exit code.

Human verification required:
no. Covered by H1 and H2.

Task A4:

Title:
Perform narrow documentation consistency check.

Goal:
Ensure allowed documentation files do not contradict ROADMAP.md, PLAN_TEMPLATE.md, or the inspect-only Plan 8 CLI.

Files allowed:

```text
README_latex_docling_groundtruth.md
docs/docling_layer.md
history.md
agent.md
README.md
```

Implementation requirements:

1. Read each allowed documentation file and compare key claims against ROADMAP.md, project.md, PLAN_TEMPLATE.md, and this plan.
2. In `README_latex_docling_groundtruth.md`, ensure ground truth is not described as temporary if ROADMAP.md treats it as the calibration corpus.
3. In `docs/docling_layer.md`, mark legacy Docling inspection paths as legacy or clarify their relationship to the current canonical export path.
4. In `history.md`, update only if it omits already-completed roadmap governance milestones such as ROADMAP.md or PLAN_TEMPLATE.md.
5. In `agent.md`, add a narrow compatibility note if older mode, status, run_log, or review terminology conflicts with PLAN_TEMPLATE.md for template-based plans.
6. In `README.md`, edit only Section 12 to ensure the `tools/local_groundtruth_validate.py` example matches the inspect-only Plan 8 CLI and does not include `--run-validator`, generator, compiler, or validator flags.
7. Do not perform style-only edits.
8. Do not edit README.md outside Section 12.
9. Do not edit project.md, ROADMAP.md, current_plan.md, or next_plan.md.
10. If no contradictions exist, record “no contradictions found” in the agent report and make no documentation changes.

Automated tests required:

```text
none beyond the full Plan 8 test matrix
```

Expected output:
Allowed documentation files either remain unchanged with recorded justification, or contain narrow corrective edits.

Completion evidence:
Agent must report each documentation file inspected, whether it changed, and why.

Human verification required:
yes. Covered by H4.

---

## 7. Human verification checkpoints

Checkpoint H1:

Title:
Verify minimal valid fixture corpus.

Purpose:
Confirm that the validation CLI can inspect a deterministic ready corpus and write both machine-readable and human-readable reports.

Required environment:
pdf2md

Preconditions:
The repository package is installed in editable mode.
The file `tools/local_groundtruth_validate.py` exists.
The fixture directory `tests/data/local_groundtruth_fixtures/minimal_valid_corpus` exists.

Command:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root tests/data/local_groundtruth_fixtures/minimal_valid_corpus --out-dir /tmp/pdf2md_plan8_h1 --strict --verbose
```

Expected output files:

```text
/tmp/pdf2md_plan8_h1/groundtruth_validation_report.json
/tmp/pdf2md_plan8_h1/groundtruth_validation_summary.txt
```

Verification procedure:

1. Run the command exactly as written.
2. Confirm the command exits with code 0.
3. Run:

```bash
python -m json.tool /tmp/pdf2md_plan8_h1/groundtruth_validation_report.json
```

4. Open:

```text
/tmp/pdf2md_plan8_h1/groundtruth_validation_summary.txt
```

5. Confirm `schema_name` equals `pdf2md.LocalGroundtruthValidationReport`.
6. Confirm `corpus_ready` is true.
7. Confirm `total_documents` is greater than 0.
8. Confirm `documents_ready` equals `total_documents`.
9. Confirm `documents_partial` equals 0.
10. Confirm `documents_missing_critical` equals 0.
11. Confirm optional artefacts are reported in the JSON.

Pass criteria:

```text
The command exits 0.
Both expected output files exist.
The JSON report is valid JSON.
schema_name equals pdf2md.LocalGroundtruthValidationReport.
corpus_ready equals true.
total_documents > 0.
documents_ready equals total_documents.
documents_partial equals 0.
documents_missing_critical equals 0.
```

Fail criteria:

```text
The command exits non-zero.
Either expected output file is missing.
The JSON file is invalid.
corpus_ready is false.
No document is classified as ready.
Optional artefacts are not reported.
```

Evidence to record:

```text
Paste the command used.
Paste the exit code.
Paste the first 20 lines of groundtruth_validation_summary.txt.
Paste schema_name, corpus_ready, total_documents, documents_ready, documents_partial, and documents_missing_critical from the JSON report.
```

Checkpoint H2:

Title:
Verify partial and empty corpus strict and non-strict behaviour.

Purpose:
Confirm that incomplete and empty corpora are reported clearly, non-strict mode writes reports and exits 0, and strict mode exits 1.

Required environment:
pdf2md

Preconditions:
The file `tools/local_groundtruth_validate.py` exists.
The fixture directories `tests/data/local_groundtruth_fixtures/partial_corpus` and `tests/data/local_groundtruth_fixtures/empty_corpus` exist.

Command 1, partial corpus non-strict:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root tests/data/local_groundtruth_fixtures/partial_corpus --out-dir /tmp/pdf2md_plan8_h2_partial_nonstrict --verbose
```

Command 2, partial corpus strict:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root tests/data/local_groundtruth_fixtures/partial_corpus --out-dir /tmp/pdf2md_plan8_h2_partial_strict --strict --verbose
```

Command 3, empty corpus non-strict:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root tests/data/local_groundtruth_fixtures/empty_corpus --out-dir /tmp/pdf2md_plan8_h2_empty_nonstrict --verbose
```

Command 4, empty corpus strict:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root tests/data/local_groundtruth_fixtures/empty_corpus --out-dir /tmp/pdf2md_plan8_h2_empty_strict --strict --verbose
```

Expected output files:

```text
/tmp/pdf2md_plan8_h2_partial_nonstrict/groundtruth_validation_report.json
/tmp/pdf2md_plan8_h2_partial_nonstrict/groundtruth_validation_summary.txt
/tmp/pdf2md_plan8_h2_partial_strict/groundtruth_validation_report.json
/tmp/pdf2md_plan8_h2_partial_strict/groundtruth_validation_summary.txt
/tmp/pdf2md_plan8_h2_empty_nonstrict/groundtruth_validation_report.json
/tmp/pdf2md_plan8_h2_empty_nonstrict/groundtruth_validation_summary.txt
/tmp/pdf2md_plan8_h2_empty_strict/groundtruth_validation_report.json
/tmp/pdf2md_plan8_h2_empty_strict/groundtruth_validation_summary.txt
```

Verification procedure:

1. Run all four commands exactly as written.
2. Confirm Command 1 exits 0.
3. Confirm Command 2 exits 1.
4. Confirm Command 3 exits 0.
5. Confirm Command 4 exits 1.
6. Confirm all eight expected output files exist.
7. Inspect each JSON report.
8. Confirm partial corpus has `corpus_ready=false` and at least one partial document.
9. Confirm empty corpus has `corpus_ready=false` and `total_documents=0`.
10. Confirm missing required artefacts are listed in the partial corpus report.

Pass criteria:

```text
Partial non-strict exits 0.
Partial strict exits 1.
Empty non-strict exits 0.
Empty strict exits 1.
All expected reports and summaries are written.
Partial corpus has corpus_ready=false and documents_partial > 0.
Empty corpus has corpus_ready=false and total_documents=0.
Missing required artefacts are explicit.
```

Fail criteria:

```text
Any exit code differs from the expected value.
Any report or summary is missing.
Partial corpus is reported as ready.
Empty corpus is reported as ready.
Missing required artefacts are not listed.
```

Evidence to record:

```text
Paste all four commands.
Paste all four exit codes.
Paste corpus_ready, total_documents, documents_ready, documents_partial, and documents_missing_critical from all four JSON reports.
Paste one example of a missing required artefact from the partial corpus report.
```

Checkpoint H3:

Title:
Verify real local corpus inspection.

Purpose:
Confirm that the Plan 8 validation CLI can inspect the real repository ground-truth corpus without running backends, compilers, validators, or generators.

Required environment:
pdf2md

Preconditions:
Plan 7 preflight has either passed or the human has decided to proceed despite known missing local components.
The path `groundtruth/corpus/latex` exists, or its absence is expected and should be reported as corpus-not-ready.

Command:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root groundtruth/corpus/latex --out-dir groundtruth/runs/local_groundtruth_validation --verbose
```

Expected output files:

```text
groundtruth/runs/local_groundtruth_validation/groundtruth_validation_report.json
groundtruth/runs/local_groundtruth_validation/groundtruth_validation_summary.txt
```

Verification procedure:

1. Run the command exactly as written.
2. Record the exit code.
3. Confirm both expected output files exist.
4. Run:

```bash
python -m json.tool groundtruth/runs/local_groundtruth_validation/groundtruth_validation_report.json
```

5. Open:

```text
groundtruth/runs/local_groundtruth_validation/groundtruth_validation_summary.txt
```

6. Confirm the report lists each discovered document, or clearly reports corpus root missing or no documents found.
7. Confirm missing corpus artefacts are classified as corpus-not-ready, not as repository defects.
8. Confirm no backend execution, LaTeX execution, LaTeXML execution, generator execution, validator execution, calibration, consensus, linking, or export was attempted.

Pass criteria:

```text
The command writes both expected output files.
The JSON report is valid.
The report either lists discovered documents or clearly reports corpus missing or no documents found.
Missing corpus artefacts are classified.
No forbidden execution is attempted.
```

Fail criteria:

```text
No report is written.
The report is invalid JSON.
The tool crashes before writing a report in non-strict mode.
Backend or compiler execution is attempted.
Missing corpus artefacts are treated as repository defects.
```

Evidence to record:

```text
Paste the command.
Paste the exit code.
Paste the first 30 lines of the summary.
Paste corpus_ready, total_documents, documents_ready, documents_partial, and documents_missing_critical from the JSON report.
Paste any failure classes reported.
```

Checkpoint H4:

Title:
Verify documentation consistency edits.

Purpose:
Confirm that narrow documentation edits do not introduce new roadmap or architecture contradictions.

Required environment:
Any text editor or git diff tool.

Command:

```bash
git diff -- README.md README_latex_docling_groundtruth.md docs/docling_layer.md history.md agent.md
```

Verification procedure:

1. Inspect the diff for each changed documentation file.
2. Confirm each change is limited to one of:
   source-of-truth hierarchy,
   legacy Docling layer clarification,
   ground-truth corpus role,
   history update for ROADMAP.md or PLAN_TEMPLATE.md,
   PLAN_TEMPLATE.md compatibility note in agent.md,
   README.md Section 12 CLI alignment.
3. Confirm README.md changes, if any, are limited to Section 12 and remove obsolete validator/generator flags from the `tools/local_groundtruth_validate.py` example.
4. Confirm agent.md changes, if any, are limited to a compatibility note for PLAN_TEMPLATE.md-based plans.
5. Confirm there are no broad style-only rewrites.
6. Search for outdated claims:

```bash
grep -R "PDF-to-Markdown only\|scanned image PDFs only\|Docling later\|semantic_document.json is canonical\|temporary ground truth\|--run-validator" README.md README_latex_docling_groundtruth.md docs/docling_layer.md history.md agent.md
```

7. Confirm either no matches exist, or matches are explicitly marked as legacy, non-canonical, or outside the Plan 8 local_groundtruth_validate.py example.

Pass criteria:

```text
Documentation changes are narrow.
No allowed doc contradicts ROADMAP.md, project.md, PLAN_TEMPLATE.md, or the Plan 8 CLI.
Legacy paths are marked as legacy or non-canonical.
README.md changes, if any, are limited to Section 12.
README.md Section 12 no longer documents --run-validator for tools/local_groundtruth_validate.py.
agent.md has no unqualified contradiction with PLAN_TEMPLATE.md for template-based plans.
No ROADMAP.md, project.md, current_plan.md, or next_plan.md change is included.
```

Fail criteria:

```text
Documentation diff contains broad rewrites.
A doc still contradicts ROADMAP.md or PLAN_TEMPLATE.md.
README.md is changed outside Section 12.
README.md still documents --run-validator for tools/local_groundtruth_validate.py.
A canonical claim points to an obsolete path.
Forbidden documentation files are modified.
```

Evidence to record:

```text
Paste git diff --name-only.
Paste the grep command and result.
List each changed documentation file and the reason for the change.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_local_groundtruth_validate.py -q
conda run -n pdf2md pytest tests/test_local_preflight.py -q
conda run -n pdf2md pytest tests/ -q
```

Human verification test matrix:

```text
H1 minimal valid fixture corpus validation
H2 partial and empty corpus strict and non-strict validation
H3 real local corpus validation report
H4 documentation consistency diff and search
```

Failure classes:

repository_defect:
The implementation is wrong, a test fails due to logic, an output schema is invalid, or a CLI signature is broken.

environment_missing:
A required local tool, backend environment, model, credential, GPU, or system package is missing.

corpus_missing:
The corpus root does not exist.

corpus_not_ready:
The corpus exists but required artefacts are missing.

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

If failure_class is corpus_missing or corpus_not_ready:
The report must record it clearly. It does not automatically fail the repository implementation in non-strict mode.

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
Plan 7 status is human_verified or human explicitly approves drafting only
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
Plan 8 is archived after completion
history.md summary is prepared or updated
Plan 9 exists as next_plan.md or approved prepared plan
Plan 9 may be promoted to current_plan.md only after Plan 8 is finished
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
plans/archive/plan-8-groundtruth-validation.md
```

2. Append a milestone summary to history.md.
3. Promote Plan 9 to current_plan.md.
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
Corpus readiness:
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
11. Did the implementation avoid backend execution?
12. Did the implementation avoid LaTeX, LuaLaTeX and LaTeXML execution?
13. Did the implementation avoid generator and validator execution?
14. Did non-strict mode write a report even when corpus is incomplete?
15. Did strict mode fail when corpus_ready is false?
16. Did documentation edits stay narrow?
17. Were README.md edits, if any, limited to Section 12 and CLI flag alignment?
18. Was agent.md updated only with a PLAN_TEMPLATE.md compatibility note, if needed?
19. Is Plan 9 clearly identified as the next plan?
20. Is it safe to mark this plan human_verified?
21. Is it safe to promote the next plan?
22. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-09 — draft — human — Plan 8 created from ROADMAP.md and PLAN_TEMPLATE.md
2026-05-09 — active — human — approved for agent execution
2026-05-09 — agent_in_progress — agent — branch created
2026-05-09 — agent_complete — agent — automated tests passed
2026-05-09 — human_verification_required — agent — awaiting human checks
2026-05-09 — human_verified — human — all checkpoints passed
2026-05-09 — finished — human — archived and promoted
```
