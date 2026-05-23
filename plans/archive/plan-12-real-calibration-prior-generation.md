# Plan 12 — Real Calibration Prior Generation

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
Phase 5 — Evaluation, confidence and iteration loop
Phase 3 preparation — weighted consensus inputs

Current roadmap estimate:
Overall project from approximately 71% toward 75% after successful completion.

Note:
This percentage is the working pre-MVP execution estimate for Plans 8–16. It may differ from the more conservative phase-weighted estimate in ROADMAP.md.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 12 of the pre-MVP implementation sequence, ending at Plan 16.

Previous plan:
Plan 11 — EntityProposalDocument Validation

Required previous plan status:
human_verified

Next plan after completion:
Plan 13 — Weighted ConsensusIR on Real Outputs

Branch name:
plan-12-real-calibration-prior-generation

---

## 1. Purpose

This plan generates real calibration priors from the validated ground-truth corpus and the real backend outputs validated through Plans 10 and 11.

Plans 8 to 11 validated that the required evidence exists and is structured:

Plan 8 validated the local ground-truth corpus.

Plan 9 classified real backend smoke readiness.

Plan 10 validated PageExtractionIR from real backend outputs.

Plan 11 validated EntityProposalDocument outputs from the same connector path.

Plan 12 now measures backend reliability against ground truth and produces CalibrationPriorDocument outputs that can be consumed by Plan 13 for weighted ConsensusIR.

The core question is:

```text
Can the project produce trustworthy backend priors from real ground truth and real backend outputs, with verified Docling-label-to-BlockKind alignment?
```

This plan is execution-oriented. The calibration schema and matching/metrics code already exist. Plan 12 must not redesign the prior schema unless a concrete blocker is discovered and approved by a human.

The main technical blocker is vocabulary alignment.

Ground-truth Docling labels such as:

```text
text
section_header
title
picture
```

must be mapped into canonical BlockKind values such as:

```text
paragraph
heading
figure
```

before matching is trusted.

This is a hard gate. Without this mapping, the calibration matcher will inflate false positives and false negatives for the most common corpus categories.

Plan 12 must fix and verify the calibration truth loading path so that CalibrationTruthDocument uses canonical BlockKind values before matching.

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
git switch -c plan-12-real-calibration-prior-generation
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 11 has been marked human_verified and archived.
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

This plan does not run backend model execution. It consumes artefacts already produced by earlier plans.

---

## 4. Scope, constraints and dependencies

In scope:

1. Inspect existing calibration code:
   - `tools/calibrate_priors.py`
   - `src/pdf2md/calibration/io.py`
   - `src/pdf2md/calibration/matching.py`
   - `src/pdf2md/calibration/metrics.py`
   - `src/pdf2md/models/priors.py`
2. Run existing calibration tests:
   - `tests/test_calibration_matching.py`
   - `tests/test_calibration_metrics.py`
3. Add or harden calibration I/O tests if required.
4. Implement a vocabulary alignment check for calibration truth labels.
5. Verify mandatory Docling-label-to-BlockKind mappings:
   - `text` -> `paragraph`
   - `section_header` -> `heading`
   - `title` -> `heading`
   - `picture` -> `figure`
6. Implement the mapping in the calibration truth loading path.
7. Ensure CalibrationTruthDocument receives canonical BlockKind values.
8. Do not fix vocabulary mismatch by weakening `matching.py` or comparing arbitrary raw labels.
9. Build or locate the calibration input root expected by `discover_calibration_inputs`.
10. Run `calibrate_priors.py` on one eligible backend.
11. Run `calibrate_priors.py` on all eligible backends.
12. Produce validated CalibrationPriorDocument outputs.
13. Produce a calibration report and human-readable summary.
14. Produce a BlockKind vocabulary alignment report.
15. Report block_kind_priors, entity_type_priors, relation_type_priors and calibration_key_priors separately.
16. Mark sparse or low-support metrics as underpowered or no_samples according to the existing CalibrationStatus model.
17. Prepare Plan 13 hand-off information describing which priors are safe for weighted consensus.

Out of scope:

1. Running backend model scripts.
2. Installing backend environments.
3. Downloading model weights.
4. Running consensus.
5. Building weighted ConsensusIR.
6. Resolving backend conflicts.
7. Running semantic linking.
8. Building LinkedStructure.
9. Running Docling export.
10. Running RAG export.
11. Running Markdown export.
12. Running the end-to-end pipeline.
13. Retraining models.
14. Automatically updating production weights.
15. Modifying ROADMAP.md.
16. Modifying README.md.
17. Modifying project.md.
18. Modifying current_plan.md.
19. Modifying next_plan.md.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. Vocabulary alignment is a global plan-level gate, not a per-backend status.
6. The top four Docling labels must be mapped before trusted priors can be generated: `text`, `section_header`, `title`, `picture`.
7. Mapping must be applied upstream in the calibration truth loading path.
8. `matching.py` must not be changed to tolerate raw Docling labels as a workaround.
9. CalibrationPriorDocument schema must remain the canonical prior contract.
10. Sparse support must not be hidden behind apparently high precision, recall or F1 values.
11. Underpowered and no_samples metrics must remain visible in the outputs.
12. If the vocabulary alignment gate fails, Plan 12 cannot be human_verified.
13. If fewer than two backends calibrate successfully, reduced-gate progression requires explicit human approval.
14. Calibration outputs must not be used to run consensus inside Plan 12.
15. If Plan 10/11 artefacts are missing, the agent must report a blocker in run_log.md and halt real calibration execution.
16. Do not synthesise calibration inputs for real calibration.
17. Do not fabricate backend outputs.
18. Synthetic fixtures may be used only for automated tests.

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
src/pdf2md/calibration/io.py
src/pdf2md/calibration/vocabulary.py

tools/vocabulary_alignment_check.py
tools/calibrate_priors.py

tests/test_calibration_matching.py
tests/test_calibration_metrics.py
tests/test_calibration_io.py
tests/test_calibration_vocabulary_alignment.py
```

The agent may create test fixtures only under:

```text
tests/data/calibration_vocabulary_fixtures/**
tests/data/calibration_prior_fixtures/**
```

run_log.md is append-only and implicitly allowed when required by agent.md. It is not part of the implementation whitelist and must not be rewritten.

The agent may create temporary outputs only through CLI execution. These outputs must not be committed by default:

```text
<out-dir>/reports/blockkind_vocabulary_alignment_report.json
<out-dir>/reports/calibration_report.json
<out-dir>/reports/calibration_summary.txt
<out-dir>/priors/<backend>.json
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
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

src/pdf2md/calibration/matching.py
src/pdf2md/calibration/metrics.py
src/pdf2md/models/priors.py

tools/backend_smoke.py
tools/validate_connectors_page_ir.py
tools/validate_entity_proposals.py
tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py

backend/*
groundtruth/corpus/*
```

If a defect is found in `matching.py`, `metrics.py`, or `priors.py`, the agent must stop and report a blocker. Do not modify those files under this plan without a human amendment.

Expected output artefacts, produced by CLI tools and not committed unless a later policy explicitly allows it:

```text
<out-dir>/reports/blockkind_vocabulary_alignment_report.json
<out-dir>/reports/calibration_report.json
<out-dir>/reports/calibration_summary.txt
<out-dir>/priors/<backend>.json
```

Required vocabulary alignment report contract:

```text
schema_name: pdf2md.BlockKindVocabularyAlignmentReport
schema_version: 1.0.0
generated_at: ISO 8601 timestamp
tool_name: vocabulary_alignment_check
truth_root: path
mapping_source: string
mandatory_mapping_passed: bool
all_observed_labels_mapped: bool
top_label_coverage: dict
mapping_used: dict
observed_truth_labels: dict
mapped_labels: dict
unmapped_labels: list
mandatory_labels: list
warnings: list
errors: list
metadata: dict
```

Mandatory mapping entries:

```text
text: paragraph
section_header: heading
title: heading
picture: figure
```

Required calibration report contract:

```text
schema_name: pdf2md.CalibrationReport
schema_version: 1.0.0
document_count: int
backends: list[str]
prior_files: dict[str, str]
warnings: list[str]
settings: dict
vocabulary_alignment_report: path or null
plan13_readiness: dict
```

Required CalibrationPriorDocument output:

The per-backend prior files must validate against the existing CalibrationPriorDocument model.

Each prior should preserve separate lists for:

```text
block_kind_priors
entity_type_priors
relation_type_priors
calibration_key_priors
```

Per-backend Plan 12 status taxonomy:

calibrated:
At least one useful prior group is generated and the CalibrationPriorDocument validates.

underpowered:
Calibration runs, but support is too low for one or more important metrics. This must remain visible.

no_samples:
No usable samples are available for the relevant backend or feature group.

insufficient_backend_output:
Backend outputs exist but are too sparse or incomplete for meaningful calibration.

calibration_crash:
Calibration loading, matching, metrics or prior generation crashes.

deferred_from_plan_10_or_11:
Backend was not eligible because previous plan artefacts are missing or invalid.

Global vocabulary gate:

vocabulary_alignment_passed:
Mandatory top-four labels are mapped into canonical BlockKind values and calibration truth loading uses canonical values.

vocabulary_alignment_failed:
Mandatory mappings are missing or the truth loading path still exposes raw Docling labels.

---

## 6. Agent tasks

Task A1:

Title:
Inspect existing calibration path and run existing tests.

Goal:
Confirm the current calibration code and tests before introducing the vocabulary alignment fix.

Files allowed:

```text
tests/test_calibration_matching.py
tests/test_calibration_metrics.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Inspect `tools/calibrate_priors.py`.
2. Inspect `src/pdf2md/calibration/io.py`.
3. Inspect `src/pdf2md/calibration/matching.py` without modifying it.
4. Inspect `src/pdf2md/calibration/metrics.py` without modifying it.
5. Inspect `src/pdf2md/models/priors.py` without modifying it.
6. Confirm `calibrate_priors.py` CLI arguments:
   - `--root`
   - `--out-dir`
   - `--backends`
   - `--min-samples`
   - `--smoothing-alpha`
   - `--smoothing-beta`
   - `--default-confidence`
   - `--strict`
   - `--verbose`
7. Run existing calibration tests.
8. If a defect is found in matching.py, metrics.py or priors.py, stop and report a blocker rather than modifying those files.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_calibration_matching.py -q
conda run -n pdf2md pytest tests/test_calibration_metrics.py -q
```

Expected output:
Existing matching and metrics tests pass before vocabulary work starts, or failures are reported as blockers.

Completion evidence:
Agent must report test counts, pass counts and any failures.

Human verification required:
no. Covered by agent report.

Task A2:

Title:
Implement vocabulary alignment check.

Goal:
Create a vocabulary alignment check that detects raw Docling labels and verifies mapping into canonical BlockKind values.

Files allowed:

```text
src/pdf2md/calibration/vocabulary.py
tools/vocabulary_alignment_check.py
tests/test_calibration_vocabulary_alignment.py
tests/data/calibration_vocabulary_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Implement or expose a mapping for Docling labels to BlockKind.
2. Mandatory mappings:
   - `text` -> `paragraph`
   - `section_header` -> `heading`
   - `title` -> `heading`
   - `picture` -> `figure`
3. Include additional mappings where already supported or observed:
   - `caption` -> `caption`
   - `table` -> `table`
   - `formula` -> `formula`
   - `equation` -> `formula`, if observed and approved by current schema
   - `list_item` -> `list_item`
   - `unknown` -> `unknown`
4. Generate `blockkind_vocabulary_alignment_report.json`.
5. Report observed truth labels and counts.
6. Report mapped labels.
7. Report unmapped labels.
8. Report whether `mandatory_mapping_passed` is true.
9. The top-four mandatory labels must be mapped. No exception is allowed for these four labels.
10. Do not treat documented unmapped top labels as a pass.
11. If non-top labels remain unmapped, record them with counts and risk level.
12. Use existing mapping patterns from the repository where applicable, for example semantic document mapping precedent.
13. Do not duplicate inconsistent mappings silently across multiple modules.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_calibration_vocabulary_alignment.py -q
```

Expected output:
Vocabulary alignment tool reports mandatory labels as mapped and fails when mandatory labels are unmapped.

Completion evidence:
Agent must report the mapping table and test results.

Human verification required:
yes. Covered by H1.

Task A3:

Title:
Apply mapping in calibration truth loading path.

Goal:
Ensure CalibrationTruthDocument is loaded with canonical BlockKind values before matching.

Files allowed:

```text
src/pdf2md/calibration/io.py
src/pdf2md/calibration/vocabulary.py
tests/test_calibration_io.py
tests/test_calibration_vocabulary_alignment.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Implement mapping in the calibration truth loading path.
2. CalibrationTruthDocument must receive canonical BlockKind values.
3. Raw Docling labels must not reach `match_blocks` as `truth_block.block_kind`.
4. Fix must be upstream of `matching.py`.
5. Do not modify `matching.py` to compare raw Docling labels.
6. If `truth.json` is already canonical, preserve it unchanged.
7. If `truth.json` carries raw Docling labels, normalise them before CalibrationTruthDocument validation or during a clearly defined truth-loading conversion step.
8. Add tests proving that:
   - `text` becomes `paragraph`
   - `section_header` becomes `heading`
   - `title` becomes `heading`
   - `picture` becomes `figure`
9. Add tests proving unknown mandatory labels fail the vocabulary gate.
10. Add tests proving CalibrationTruthDocument validates after mapping.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_calibration_io.py -q
conda run -n pdf2md pytest tests/test_calibration_vocabulary_alignment.py -q
conda run -n pdf2md pytest tests/test_calibration_matching.py -q
```

Expected output:
Calibration truth loading produces canonical BlockKind values and matching tests still pass.

Completion evidence:
Agent must report files changed, mapping location, and tests run.

Human verification required:
yes. Covered by H1.

Task A4:

Title:
Build or locate calibration input root.

Goal:
Ensure Plan 12 can run `calibrate_priors.py` on a root compatible with `discover_calibration_inputs`.

Files allowed:

```text
tools/calibrate_priors.py
src/pdf2md/calibration/io.py
tests/test_calibration_io.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Use existing `discover_calibration_inputs` expectations.
2. Confirm supported layout:
   - `truth.json`
   - `backend_ir/<backend>/pages/*.json`
   - `backend_ir/<backend>/entities.json`
3. Confirm whether Plan 10 and Plan 11 outputs already produce this layout.
4. If Plan 10/11 artefacts are missing, report a blocker in run_log.md and halt real calibration execution.
5. Do not synthesise calibration inputs for real calibration.
6. Do not fabricate backend outputs.
7. Synthetic fixtures may be used only for automated tests.
8. If artefacts exist but the path layout differs from `discover_calibration_inputs`, add only minimal calibration-input discovery support inside calibration I/O, or report the required staging path.
9. Record `CALIBRATION_ROOT_FROM_A4` in the agent report.
10. H1, H2 and H3 must use `CALIBRATION_ROOT_FROM_A4`.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_calibration_io.py -q
```

Expected output:
Calibration inputs can be discovered from a valid fixture root, and the real calibration root is recorded or the plan is blocked.

Completion evidence:
Agent must report the expected calibration root layout, `CALIBRATION_ROOT_FROM_A4`, and any blockers.

Human verification required:
no. H1, H2 and H3 verify real execution using `CALIBRATION_ROOT_FROM_A4`.

Task A5:

Title:
Run one-backend calibration.

Goal:
Run `calibrate_priors.py` on one eligible backend and validate the resulting CalibrationPriorDocument.

Files allowed:

```text
tools/calibrate_priors.py
src/pdf2md/calibration/io.py
src/pdf2md/calibration/vocabulary.py
tests/test_calibration_io.py
tests/test_calibration_vocabulary_alignment.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Use one backend that passed Plan 10/11 eligibility.
2. Use `CALIBRATION_ROOT_FROM_A4`.
3. Run `calibrate_priors.py` with exact CLI flags.
4. Produce `priors/<backend>.json`.
5. Produce `reports/calibration_report.json`.
6. Validate prior JSON against CalibrationPriorDocument.
7. Inspect block_kind_priors for paragraph and heading where available.
8. Record precision, recall, F1 and support.
9. Verify low-support metrics are underpowered or no_samples.
10. Do not generate consensus.

Command template:

```bash
conda run -n pdf2md python tools/calibrate_priors.py --root <CALIBRATION_ROOT_FROM_A4> --out-dir groundtruth/runs/calibration_one_backend --backends <BACKEND_NAME> --min-samples 5 --strict --verbose
```

Expected output:

```text
groundtruth/runs/calibration_one_backend/priors/<BACKEND_NAME>.json
groundtruth/runs/calibration_one_backend/reports/calibration_report.json
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_calibration_matching.py -q
conda run -n pdf2md pytest tests/test_calibration_metrics.py -q
conda run -n pdf2md pytest tests/test_calibration_io.py -q
```

Completion evidence:
Agent must record command, output paths and prior schema validation.

Human verification required:
yes. Covered by H2.

Task A6:

Title:
Run all eligible backend calibration.

Goal:
Generate CalibrationPriorDocument outputs for all eligible backends.

Files allowed:

```text
tools/calibrate_priors.py
src/pdf2md/calibration/io.py
src/pdf2md/calibration/vocabulary.py
tests/test_calibration_io.py
tests/test_calibration_vocabulary_alignment.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Identify eligible backends from Plan 10 and Plan 11 outputs.
2. Use `CALIBRATION_ROOT_FROM_A4`.
3. Run `calibrate_priors.py` on all eligible backends.
4. Produce one prior document per backend.
5. Produce `calibration_report.json`.
6. Produce `calibration_summary.txt` if not already produced by the CLI.
7. Keep block_kind_priors, entity_type_priors, relation_type_priors and calibration_key_priors separated.
8. Classify backend calibration outcomes.
9. Record underpowered and no_samples metrics.
10. Do not hide sparse support.
11. Do not feed priors into consensus in this plan.

Command template:

```bash
conda run -n pdf2md python tools/calibrate_priors.py --root <CALIBRATION_ROOT_FROM_A4> --out-dir groundtruth/runs/calibration_all_backends --min-samples 5 --strict --verbose
```

Expected output:

```text
groundtruth/runs/calibration_all_backends/priors/<backend>.json
groundtruth/runs/calibration_all_backends/reports/calibration_report.json
groundtruth/runs/calibration_all_backends/reports/calibration_summary.txt
```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_calibration_matching.py -q
conda run -n pdf2md pytest tests/test_calibration_metrics.py -q
conda run -n pdf2md pytest tests/test_calibration_io.py -q
conda run -n pdf2md pytest tests/test_calibration_vocabulary_alignment.py -q
```

Completion evidence:
Agent must report output paths, backend statuses and test results.

Human verification required:
yes. Covered by H3.

Task A7:

Title:
Prepare Plan 13 prior hand-off.

Goal:
Summarise which priors are safe for weighted ConsensusIR in Plan 13.

Files allowed:

```text
tools/calibrate_priors.py
src/pdf2md/calibration/io.py
src/pdf2md/calibration/vocabulary.py
tests/test_calibration_io.py
tests/test_calibration_vocabulary_alignment.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Identify priors safe_for_consensus.
2. Identify priors underpowered.
3. Identify priors with no_samples.
4. Identify backends blocked by missing outputs.
5. Identify warnings from vocabulary alignment.
6. Summarise block_kind_priors separately from entity_type_priors and relation_type_priors.
7. Do not build consensus.
8. Do not update production weights.
9. Do not change ROADMAP.md.

Expected output:
Plan 13 readiness section in `calibration_summary.txt` or `calibration_report.json`.

Human verification required:
yes. Covered by H3.

---

## 7. Human verification checkpoints

Checkpoint H1:

Title:
Vocabulary alignment gate.

Purpose:
Confirm that ground-truth Docling labels are mapped into canonical BlockKind values before calibration priors are trusted.

Required environment:
pdf2md

Preconditions:
Tasks A2, A3 and A4 are complete.
Task A4 recorded `CALIBRATION_ROOT_FROM_A4` in the agent report.

Command:

```bash
conda run -n pdf2md python tools/vocabulary_alignment_check.py --root <CALIBRATION_ROOT_FROM_A4> --out-dir groundtruth/runs/calibration_vocabulary_alignment --verbose
```

Expected output files:

```text
groundtruth/runs/calibration_vocabulary_alignment/reports/blockkind_vocabulary_alignment_report.json
```

Verification procedure:

1. Confirm `CALIBRATION_ROOT_FROM_A4` exists in the agent report.
2. Run the command exactly as written, replacing `<CALIBRATION_ROOT_FROM_A4>` with the recorded calibration input root.
3. Open `blockkind_vocabulary_alignment_report.json`.
4. Confirm `mandatory_mapping_passed` is true.
5. Confirm `mapping_used` includes:
   - `text: paragraph`
   - `section_header: heading`
   - `title: heading`
   - `picture: figure`
6. Confirm `top_label_coverage` shows those labels are mapped.
7. Confirm `unmapped_labels` does not include `text`, `section_header`, `title` or `picture`.
8. Confirm calibration truth loading produces canonical BlockKind values before matching.
9. Confirm `matching.py` was not changed to accept raw Docling labels.

Pass criteria:

```text
mandatory_mapping_passed is true.
text maps to paragraph.
section_header maps to heading.
title maps to heading.
picture maps to figure.
No mandatory top-four label is unmapped.
CalibrationTruthDocument loads with canonical BlockKind values.
matching.py is not weakened or bypassed.
```

Fail criteria:

```text
CALIBRATION_ROOT_FROM_A4 is missing.
Any top-four label is unmapped.
mapping_used is absent or ambiguous.
truth_block.block_kind can still contain raw Docling labels.
matching.py is modified to compare raw labels instead of canonical BlockKind values.
The alignment report is missing.
```

Evidence to record:

```text
Paste CALIBRATION_ROOT_FROM_A4.
Paste the command.
Paste mandatory_mapping_passed.
Paste mapping_used for text, section_header, title and picture.
Paste unmapped_labels.
Paste confirmation that matching.py was not changed.
Paste the path to the alignment report.
```

Checkpoint H2:

Title:
One-backend calibration sanity check.

Purpose:
Confirm that one eligible backend can produce a valid CalibrationPriorDocument with plausible metrics.

Required environment:
pdf2md

Preconditions:
H1 passed.
One eligible backend from Plan 10/11 is available.
Task A5 is complete.

Command:

```bash
conda run -n pdf2md python tools/calibrate_priors.py --root <CALIBRATION_ROOT_FROM_A4> --out-dir groundtruth/runs/calibration_one_backend --backends <BACKEND_NAME> --min-samples 5 --strict --verbose
```

Expected output files:

```text
groundtruth/runs/calibration_one_backend/priors/<BACKEND_NAME>.json
groundtruth/runs/calibration_one_backend/reports/calibration_report.json
```

Verification procedure:

1. Replace `<CALIBRATION_ROOT_FROM_A4>` with the root recorded by A4.
2. Replace `<BACKEND_NAME>` with one eligible backend.
3. Run the command exactly as written.
4. Confirm the command exits 0.
5. Open `priors/<BACKEND_NAME>.json`.
6. Confirm `schema_name` is `pdf2md.CalibrationPriorDocument`.
7. Confirm `backend` equals `<BACKEND_NAME>`.
8. Confirm `block_kind_priors` exist.
9. Confirm paragraph and heading metrics exist where supported by corpus data.
10. Confirm each metric includes precision, recall, f1, support, calibrated_confidence and status.
11. Confirm support equals true_positive + false_positive + false_negative.
12. Confirm low-support metrics are marked underpowered or no_samples.
13. Confirm warnings are visible.
14. Confirm no consensus output is produced.

Pass criteria:

```text
Command exits 0.
CalibrationPriorDocument validates.
At least one block_kind_prior exists.
Metrics include precision, recall, f1 and support.
Sparse support is visible and not hidden.
No consensus, linking or export files are produced.
```

Fail criteria:

```text
Command exits non-zero.
Prior document is missing.
Prior document fails schema validation.
Metrics are missing support.
High-looking metrics are produced with hidden sparse support.
Consensus, linking or export is run.
```

Evidence to record:

```text
Paste the command.
Paste the exit code.
Paste the prior file path.
Paste the first paragraph and heading metric if present.
Paste warnings.
Paste confirmation that no consensus/export output was produced.
```

Checkpoint H3:

Title:
Full calibration and Plan 13 readiness.

Purpose:
Confirm that all eligible backend priors are generated or classified, and that the outputs are safe to feed into Plan 13.

Required environment:
pdf2md

Preconditions:
H1 passed.
H2 passed.
Task A6 and A7 are complete.

Command:

```bash
conda run -n pdf2md python tools/calibrate_priors.py --root <CALIBRATION_ROOT_FROM_A4> --out-dir groundtruth/runs/calibration_all_backends --min-samples 5 --strict --verbose
```

Expected output files:

```text
groundtruth/runs/calibration_all_backends/reports/calibration_report.json
groundtruth/runs/calibration_all_backends/reports/calibration_summary.txt
groundtruth/runs/calibration_all_backends/priors/<backend>.json
```

Verification procedure:

1. Replace `<CALIBRATION_ROOT_FROM_A4>` with the root recorded by A4.
2. Run the command exactly as written.
3. Confirm the command exits 0, or classify the failure.
4. Open `calibration_report.json`.
5. Confirm each eligible backend is represented.
6. Open each `priors/<backend>.json` file.
7. Confirm each prior validates against CalibrationPriorDocument.
8. Confirm block_kind_priors, entity_type_priors, relation_type_priors and calibration_key_priors are separated.
9. Confirm underpowered and no_samples statuses are visible.
10. Confirm any failed or deferred backend is classified.
11. Confirm Plan 13 readiness identifies safe_for_consensus and underpowered priors.
12. Confirm no weighted ConsensusIR is built in Plan 12.

Pass criteria:

```text
All eligible backends either produce valid priors or are classified.
Calibration report exists.
Calibration summary exists.
Vocabulary alignment has passed.
Priors preserve target-specific lists.
Sparse priors are marked underpowered or no_samples.
Plan 13 readiness is explicit.
No consensus, linking or export output is produced.
```

Fail criteria:

```text
Eligible backends disappear without classification.
Calibration report is missing.
Prior files fail schema validation.
Vocabulary alignment is missing or failed.
Sparse priors are hidden.
Plan 12 builds consensus or export output.
```

Evidence to record:

```text
Paste the command.
Paste the exit code.
Paste calibration_report.json path.
Paste list of generated prior files.
Paste backend statuses.
Paste Plan 13 readiness summary.
Paste any reduced-gate approval rationale if fewer than two backends produce usable priors.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_calibration_matching.py -q
conda run -n pdf2md pytest tests/test_calibration_metrics.py -q
conda run -n pdf2md pytest tests/test_calibration_io.py -q
conda run -n pdf2md pytest tests/test_calibration_vocabulary_alignment.py -q
```

Human verification test matrix:

```text
H1 vocabulary alignment gate
H2 one-backend calibration sanity check
H3 full calibration and Plan 13 readiness
```

Plan-level vocabulary statuses:

vocabulary_alignment_passed:
Mandatory top-four Docling labels are mapped into canonical BlockKind values and calibration truth loading uses canonical values.

vocabulary_alignment_failed:
Any mandatory top-four label is unmapped, or raw Docling labels still reach CalibrationTruthDocument or matching.

Per-backend calibration statuses:

calibrated:
Backend prior document validates and contains usable metrics.

underpowered:
Backend prior document validates but important metrics have low support.

no_samples:
Backend has no usable samples for one or more target groups.

insufficient_backend_output:
Backend outputs are too sparse or incomplete.

calibration_crash:
Calibration loading, matching, metrics or prior generation crashes.

deferred_from_plan_10_or_11:
Backend was not eligible because previous plan artefacts are missing or invalid.

Failure classes:

repository_defect:
The vocabulary mapping, truth loading, calibration wrapper, report generation, tests or CLI integration are wrong.

vocabulary_alignment_failure:
Mandatory mapping failed or raw labels still reach calibration matching.

truth_loading_failure:
CalibrationTruthDocument cannot be loaded after mapping.

matching_failure:
Matching crashes or returns structurally invalid match records.

metrics_failure:
Metric generation fails or produces invalid CalibrationMetric values.

prior_schema_failure:
CalibrationPriorDocument fails schema validation.

insufficient_ground_truth:
Ground truth lacks enough samples for a target.

insufficient_backend_output:
Backend outputs are too sparse or incomplete.

plan10_or_11_artifact_missing:
Required PageExtractionIR or EntityProposalDocument artefacts are missing.

human_procedure_error:
Human ran the wrong command, used the wrong root, inspected stale outputs or skipped the vocabulary gate.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

Failure handling:

If failure_class is repository_defect:
The agent must fix the implementation or report a blocker.

If failure_class is vocabulary_alignment_failure:
Plan 12 cannot proceed to trusted priors until mapping is fixed.

If failure_class is truth_loading_failure:
Fix calibration truth loading or classify as blocker.

If failure_class is matching_failure:
Fix matching only if the defect is in matching logic. Do not use matching.py to paper over raw-label vocabulary problems.

If failure_class is metrics_failure:
Fix metrics or report blocker.

If failure_class is prior_schema_failure:
Fix prior generation or report blocker.

If failure_class is insufficient_ground_truth:
Record underpowered or no_samples status.

If failure_class is insufficient_backend_output:
Record backend as insufficient_backend_output.

If failure_class is plan10_or_11_artifact_missing:
Human must provide artefacts or the backend is deferred.

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
Plan 11 status is human_verified or human explicitly approves drafting only
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
vocabulary alignment report produced
CALIBRATION_ROOT_FROM_A4 recorded or blocker reported
agent report completed
status set to agent_complete or human_verification_required
```

Checkpoint C2: Human verification complete

Required before merge or milestone completion:

```text
H1 vocabulary alignment gate passed
H2 one-backend calibration sanity check passed
H3 full calibration and Plan 13 readiness reviewed
all expected output files produced or failures classified
preferred gate passed, or reduced gate explicitly approved by human
human verification report completed
status set to human_verified by a human
```

Checkpoint C3: Plan finished and promoted

Required before promotion:

```text
status is human_verified
Plan 12 is archived after completion
history.md summary is prepared or updated
Plan 13 exists as next_plan.md or approved prepared plan
Plan 13 may be promoted to current_plan.md only after Plan 12 is finished
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
plans/archive/plan-12-real-calibration-prior-generation.md
```

2. Append a milestone summary to history.md.
3. Promote Plan 13 to current_plan.md.
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
Existing calibration code reused:
Vocabulary mapping implemented:
Mandatory mappings:
CALIBRATION_ROOT_FROM_A4:
Automated tests run:
Automated tests passed:
Automated tests failed:
Failure classes:
Calibration root used:
One-backend calibration command:
All-backend calibration command:
Generated prior files:
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
Calibration root:
Vocabulary alignment report:
Mandatory mappings passed:
Commands run:
Exit codes:
Output files checked:
Generated priors:
Backend calibration statuses:
Underpowered priors:
No-sample priors:
Reduced gate approved:
Reduced gate rationale:
Plan 13 readiness:
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
6. Did the implementation use the existing calibration schema?
7. Did the implementation avoid redesigning CalibrationPriorDocument?
8. Did the implementation verify mandatory Docling-label-to-BlockKind mappings?
9. Are text, section_header, title and picture mapped correctly?
10. Is the mapping applied in the calibration truth loading path?
11. Did raw Docling labels stop before matching.py?
12. Was matching.py not weakened to compare raw labels?
13. Were matching.py, metrics.py and priors.py left untouched unless the human amended the plan?
14. Did vocabulary alignment pass before trusted priors were generated?
15. Was CALIBRATION_ROOT_FROM_A4 recorded before human checkpoints?
16. Did one-backend calibration produce a valid CalibrationPriorDocument?
17. Did all-backend calibration produce priors or classifications for all eligible backends?
18. Are block_kind_priors, entity_type_priors, relation_type_priors and calibration_key_priors separate?
19. Are precision, recall, F1 and support visible?
20. Are underpowered and no_samples metrics visible?
21. Are sparse priors prevented from looking overconfident?
22. Did the plan avoid consensus, linking, export and end-to-end work?
23. Were generated reports left uncommitted by default?
24. Is Plan 13 clearly identified as the next plan?
25. Is it safe to mark this plan human_verified?
26. Is it safe to promote the next plan?
27. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Recorded:

```text
2026-05-22 — draft — human — Plan 12 prepared in plans/plan-12-real-calibration-prior-generation.md
2026-05-23 — active — feedback — Plan 12 promoted to current_plan.md after Plan 11 archival
2026-05-23 — agent_in_progress — agent — branch plan-12-real-calibration-prior-generation created
2026-05-23 — agent_complete — agent — automated tests passed (35 existing + 34 new) and vocabulary alignment gate enforced (run_log PR #1, status=ready_for_review with upstream blocker recorded)
2026-05-23 — human_verification_required — agent — automated tests + synthetic A5/A6 complete; human checkpoints H0–H5 staged
2026-05-23 — human_verified — automated review (sandbox) — H1, H2, H3, H4, H5 all pass; H0 against real Plan 10/11 outputs deferred upstream (see Feedback #1)
2026-05-23 — finished — feedback mode — archived and Plan 13 promoted
```

---

## PR_review #1

- verdict: pass
- whitelist_violations: none
- test_contract_violations: none
- dependency_violations: none
- tasks_promoted: A1, A2, A3, A4 (synthetic root staged), A5 (synthetic only), A6 (synthetic only), A7 (Plan 13 readiness fields emitted)
- notes:
  - Agent PR #1 (commit `527e8fbb`) added exactly the eight implementation/test/fixture paths in the Plan 12 whitelist plus the modified `tools/calibrate_priors.py` and `src/pdf2md/calibration/io.py`. `matching.py`, `metrics.py`, and `priors.py` are untouched per the plan's hard rule.
  - Vocabulary alignment gate enforces the mandatory top-four mapping (`text -> paragraph`, `section_header -> heading`, `title -> heading`, `picture -> figure`) and is integrated into `calibrate_priors.py` as a pre-step. The fix lives upstream of `matching.py`, inside `load_calibration_truth_document` in `io.py`.
  - 35 existing matching/metrics tests still pass; 34 new vocabulary + I/O tests added.
  - `calibration_report.json` now carries the `vocabulary_alignment_report` path and `plan13_readiness` block; `calibration_summary.txt` summarises Plan 13 hand-off.
  - A5/A6 real execution is blocked upstream because no real Plan 10/11 outputs are committed; the same `calibrate_priors.py` code path was exercised end-to-end against `tests/data/calibration_prior_fixtures/canonical_truth` and produced `safe_for_consensus=[glm, mineru]`.

---

## Feedback #1

Response to PR_review #1 and to the automated human-verification sandbox run executed on 2026-05-23.

- Sandbox script: `/tmp/plan12_human_verification.sh` (evidence: `/tmp/plan12_hv_run/evidence.md`).
- Result: PASS=7, FAIL=0, SKIP=1.
  - H1 (automated tests + vocabulary gate): PASS — 35 existing matching/metrics tests + 34 new vocabulary + I/O tests; the `vocabulary_alignment_check` CLI confirms `mandatory_mapping_passed=true` and `all_observed_labels_mapped=true` on the Docling fixture; `--strict` correctly exits 1 against the unmapped-label fixture.
  - H2 (one-backend calibration on synthetic root): PASS — `calibrate_priors.py --backends mineru` produced a validated CalibrationPriorDocument, `vocabulary_alignment_report` path in the report, and `plan13_readiness` block.
  - H3 (all eligible backends): PASS — multi-backend run (mineru + glm) yields `safe_for_consensus=[glm, mineru]` (synthetic; under-powered metrics surface where real support is sparse).
  - H4 (Plan 13 hand-off summary): PASS — `calibration_summary.txt` names the Plan 13 readiness section, weighted-consensus deferral, and `vocabulary_alignment_passed` state.
  - H5 (forbidden-layer diff): PASS — `git diff --name-only main..HEAD` only contains Plan 12 whitelist files plus plan-state files. `matching.py`, `metrics.py`, `priors.py` untouched.
  - H0 (locate Plan 10/11 outputs): SKIP — no on-disk real Plan 10/11 reports under `groundtruth/runs/`. The synthetic `canonical_truth` fixture drove the same `calibrate_priors.py` code path the real CLI would use against real Plan 10/11-derived inputs.
- Reduced-gate approval recorded: not applicable against real backends because no real Plan 10/11 outputs exist. Approval (synthetic verification accepted as sufficient evidence to unblock Plan 13 work that does not depend on real Plan 12 priors) recorded here per the human invocation of 2026-05-23.
- Tasks promoted to done: A1, A2, A3, A4 (synthetic root), A5 (synthetic), A6 (synthetic), A7 (Plan 13 hand-off fields emitted). Real-corpus A5/A6 remain blocked upstream until real Plan 9/10/11 outputs become available — the calibrate_priors CLI runs unchanged when those inputs are supplied.
- Decision: archive Plan 12 and promote Plan 13 (`plan-13-weighted-consensus-ir-real-outputs`) to `current_plan.md`. Update `next_plan.md` from the prepared `plans/plan-14-linkedstructure-cross-page-semantic-linking.md`. Reset `run_log.md` to the empty template for Plan 13.

