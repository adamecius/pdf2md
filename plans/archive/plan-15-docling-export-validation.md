# Plan 15 — Docling Export Validation

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
Overall project from approximately 80–81% toward 83–85% after successful completion.

Note:
This plan validates the existing export stack on real Plan 14 LinkedStructure outputs. It does not build a new exporter. It does not run the end-to-end pipeline. It uses the available LaTeX-derived Docling ground-truth corpus for structural comparison, without treating the corpus count as fixed.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Plan 15 of the pre-MVP implementation sequence, ending at Plan 16.

Previous plan:
Plan 14 — LinkedStructure and Cross-Page Semantic Linking

Required previous plan status:
human_verified

Next plan after completion:
Plan 16 — End-to-End Runner and MVP Corpus Evaluation

Branch name:
plan-15-docling-export-validation

---

## 1. Purpose

This plan runs and hardens the existing export stack on real Plan 14 LinkedStructure outputs.

The repository already has the export stack:

```text
src/pdf2md/export/docling.py
src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py
src/pdf2md/export/__init__.py
```

and the CLI:

```text
tools/export_linked_docling.py
```

Plan 15 must reuse this stack.

The core question is:

```text
Can the existing exporter produce structurally valid Docling JSON, RAG chunks and Markdown preview from real LinkedStructure outputs, and are those outputs comparable with the available LaTeX-derived Docling ground truth?
```

Plan 15 must prove that the existing export path works on real Plan 14 outputs, including:

```text
Docling JSON structure
body / texts / tables / pictures / groups references
self_ref integrity
children reference integrity
prov / page_no preservation where available
labels present and valid
RAG chunks with text and confidence
Markdown preview with legible content
export manifest with artefact status and sha256 values
export report with useful counts and warnings
optional docling_core validation when available
Plan 16 readiness
```

This plan does not run the full end-to-end pipeline. That is Plan 16.

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
git switch -c plan-15-docling-export-validation
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If `git status --short` is not clean before branch creation, stop and report the uncommitted files.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies.
6. Do not change ROADMAP.md progress.
7. Do not promote this plan to current_plan.md unless Plan 14 has been marked human_verified and archived.
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

This plan does not run backend model execution, connector generation, calibration, consensus generation, linking generation, or the end-to-end pipeline. It consumes artefacts already produced by earlier plans.

---

## 4. Scope, constraints and dependencies

In scope:

1. Inspect the existing export stack.
2. Run `tools/export_linked_docling.py` on real Plan 14 `linked_structure.json` output.
3. Use Plan 14 `linked_structure.json` as the primary required input.
4. Use Plan 13 `consensus_ir.json` when available.
5. Use source PDF path when available.
6. Produce Docling JSON using the existing exporter.
7. Produce RAG chunks using the existing RAG exporter by default.
8. Produce Markdown preview using the existing Markdown exporter by default.
9. Produce export report and manifest using the existing I/O path.
10. Validate Docling-like structure using repository validation.
11. Attempt optional `docling_core` validation when available.
12. Treat `docling_core_unavailable` or equivalent as a warning, not a repository defect.
13. Compare produced Docling JSON structurally against the available LaTeX-derived ground-truth `.docling.json` files.
14. Validate that RAG chunks contain text and confidence information.
15. Validate that Markdown preview contains legible content.
16. Validate export manifest artefact status and sha256 values.
17. Confirm Plan 16 readiness.

Out of scope:

1. Creating a new export architecture.
2. Running backend execution.
3. Generating new PageExtractionIR.
4. Generating new EntityProposalDocument.
5. Generating new calibration priors.
6. Generating new ConsensusIR.
7. Generating new LinkedStructure.
8. Modifying linking logic.
9. Running the end-to-end pipeline.
10. Changing ground-truth corpus files.
11. Modifying ROADMAP.md, README.md, project.md, current_plan.md or next_plan.md.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not mark this plan as human_verified or finished.
3. The agent may only mark agent_in_progress, agent_complete, human_verification_required, blocked, or superseded.
4. Human verification is required before merge to main, milestone completion, next-plan promotion, or ROADMAP.md progress updates.
5. Plan 15 must use `tools/export_linked_docling.py`.
6. Plan 15 must not create a replacement export CLI.
7. Plan 15 must not create a new export architecture.
8. Plan 15 must consume real Plan 14 `linked_structure.json` for real execution.
9. If Plan 14 `linked_structure.json` is missing, Plan 15 is blocked for real execution.
10. Synthetic fixtures may be used only for automated tests.
11. Synthetic fixtures must not be used as a substitute for real Plan 14 outputs in human verification.
12. `--linked-structure` is a single JSON file path, not a directory root.
13. `--consensus-ir` is optional in the CLI, but should be provided in human verification when Plan 13 output is available.
14. If `--consensus-ir` is omitted, the warning must be recorded and export quality may be degraded.
15. Human checkpoint H2 must run default export behaviour: do not pass `--no-rag` or `--no-markdown`.
16. The five default artefacts are expected in H2: Docling JSON, RAG chunks, Markdown preview, export report and export manifest.
17. Ground-truth comparison is structural alignment, not exact JSON diff.
18. Plan 15 must not perform end-to-end orchestration.
19. Plan 15 must not modify the ground-truth corpus.
20. Plan 15 must not claim MVP completion.

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
src/pdf2md/export/docling.py
src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py
src/pdf2md/export/__init__.py

tools/export_linked_docling.py

tests/test_docling_export.py
tests/test_rag_export.py
tests/test_markdown_export.py
tests/test_export_io_cli.py
tests/test_export_contracts.py
```

The agent may create test fixtures only under:

```text
tests/data/export_fixtures/**
```

run_log.md is append-only and implicitly allowed when required by agent.md. It is not part of the implementation whitelist and must not be rewritten.

The agent may create temporary outputs only through CLI execution. These outputs must not be committed by default:

```text
<out-dir>/docling/<doc_id>.docling.json
<out-dir>/rag/<doc_id>.rag_chunks.json
<out-dir>/markdown/<doc_id>.preview.md
<out-dir>/reports/export_report.json
<out-dir>/export_manifest.json
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
src/pdf2md/linking/*

src/pdf2md/models/*

tools/backend_smoke.py
tools/validate_connectors_page_ir.py
tools/validate_entity_proposals.py
tools/vocabulary_alignment_check.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/local_groundtruth_validate.py
tools/local_groundtruth_preflight.py

backend/*
groundtruth/corpus/*
```

If a defect is found in linking, consensus, calibration, connector, backend execution or model schema code, the agent must stop and report a blocker. Do not modify those files under this plan without a human amendment.

Expected output artefacts, produced by `tools/export_linked_docling.py` and not committed unless a later policy explicitly allows it:

```text
<out-dir>/docling/<doc_id>.docling.json
<out-dir>/rag/<doc_id>.rag_chunks.json
<out-dir>/markdown/<doc_id>.preview.md
<out-dir>/reports/export_report.json
<out-dir>/export_manifest.json
```

Required output characteristics:

The produced Docling JSON must expose or preserve:

```text
document identity
body structure
texts / tables / pictures / groups where applicable
self_ref references
children references
labels
provenance where available
page_no where available
unresolved markers when requested or applicable
```

The produced RAG chunks must expose:

```text
document_id
chunk ids
text content
source references or provenance where available
confidence or quality metadata where available
warnings if any
```

The produced Markdown preview must contain legible textual content and obvious structure where available.

The export manifest must expose:

```text
document_id
source_linked_structure
source_consensus_ir when provided
source_pdf when provided
artefact paths
artefact types
artefact statuses
sha256 values for written artefacts
warnings
```

The export report must expose or summarise:

```text
document_id
Docling structural warnings
RAG chunk counts
Markdown size or content status
manifest status
warnings
errors
Plan 16 readiness notes
```

Export outcome taxonomy:

exported:
All default artefacts were written and validated structurally.

exported_with_warnings:
Artefacts were written but warnings remain, such as optional missing consensus_ir or docling_core unavailable.

structural_mismatch:
Docling-like structure fails repository validation or structural ground-truth comparison.

ground_truth_unavailable:
No matching ground-truth `.docling.json` was found for the chosen document.

blocked:
Required Plan 14 `linked_structure.json` is missing or invalid.

ready_for_plan_16:
Export outputs are coherent enough for end-to-end MVP corpus evaluation.

ready_with_warnings:
Export outputs can proceed to Plan 16, but warnings must be carried forward.

not_ready_for_plan_16:
Docling JSON, RAG, Markdown, manifest or report quality is insufficient.

---

## 6. Agent tasks

Task A1:

Title:
Inspect and run the existing export path on real data.

Goal:
Use the current `tools/export_linked_docling.py` and export modules on one real Plan 14 `linked_structure.json` output.

Files allowed:

```text
tools/export_linked_docling.py
src/pdf2md/export/docling.py
src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py
src/pdf2md/export/__init__.py
tests/test_docling_export.py
tests/test_rag_export.py
tests/test_markdown_export.py
tests/test_export_io_cli.py
tests/test_export_contracts.py
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Inspect `tools/export_linked_docling.py`.
2. Confirm actual CLI flags:
   - `--linked-structure`
   - `--consensus-ir`
   - `--source-pdf`
   - `--out-dir`
   - `--strict`
   - `--verbose`
   - `--no-rag`
   - `--no-markdown`
   - `--include-unresolved`
   - `--max-chars`
3. Confirm `--linked-structure` expects a single JSON file path.
4. Confirm `--consensus-ir` is optional.
5. Inspect `src/pdf2md/export/docling.py`.
6. Inspect `src/pdf2md/export/rag.py`.
7. Inspect `src/pdf2md/export/markdown.py`.
8. Inspect `src/pdf2md/export/io.py`.
9. Inspect `src/pdf2md/export/reporting.py`.
10. Locate one real Plan 14 `linked_structure.json`.
11. If real Plan 14 `linked_structure.json` is missing, report a blocker in run_log.md and halt real execution.
12. Do not use synthetic fixtures as a substitute for real Plan 14 output.
13. Run the existing export path on the real Plan 14 LinkedStructure output using default RAG and Markdown behaviour.
14. Provide `--consensus-ir` when a real Plan 13 ConsensusIR is available.
15. Record whether `consensus_ir_missing` or docling_core unavailable warnings appear.
16. Do not run linking, consensus, calibration or backend extraction.

Command template:

```bash
conda run -n pdf2md python tools/export_linked_docling.py --linked-structure <PLAN14_LINKED_STRUCTURE_JSON> --consensus-ir <PLAN13_CONSENSUS_IR_JSON> --source-pdf <SOURCE_PDF_PATH> --out-dir groundtruth/runs/docling_export_one_document --strict --verbose
```

If `consensus-ir` or `source-pdf` is unavailable but optional in the CLI, omit only the unavailable optional flags and record the resulting warnings.

Do not pass `--no-rag` or `--no-markdown` in this task.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_docling_export.py -q
conda run -n pdf2md pytest tests/test_rag_export.py -q
conda run -n pdf2md pytest tests/test_markdown_export.py -q
conda run -n pdf2md pytest tests/test_export_io_cli.py -q
conda run -n pdf2md pytest tests/test_export_contracts.py -q
```

Expected output:

```text
groundtruth/runs/docling_export_one_document/docling/<doc_id>.docling.json
groundtruth/runs/docling_export_one_document/rag/<doc_id>.rag_chunks.json
groundtruth/runs/docling_export_one_document/markdown/<doc_id>.preview.md
groundtruth/runs/docling_export_one_document/reports/export_report.json
groundtruth/runs/docling_export_one_document/export_manifest.json
```

Completion evidence:
Agent must report command used, CLI flags confirmed, outputs created, warnings observed and failures observed.

Human verification required:
yes. Covered by H1 and H2.

Task A2:

Title:
Compare Docling output against available ground truth and fix export issues.

Goal:
Validate the exported Docling JSON against repository contracts and the available LaTeX-derived ground-truth `.docling.json` files.

Files allowed:

```text
src/pdf2md/export/docling.py
src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py
src/pdf2md/export/__init__.py
tools/export_linked_docling.py
tests/test_docling_export.py
tests/test_rag_export.py
tests/test_markdown_export.py
tests/test_export_io_cli.py
tests/test_export_contracts.py
tests/data/export_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Use existing repository validation, including `validate_docling_like_document` where applicable.
2. Use optional `try_validate_with_docling_core` where available.
3. Treat docling_core absence as a warning, not a repository defect.
4. Compare produced Docling JSON structurally against the available matching ground-truth `.docling.json` when available.
5. Do not require exact JSON equality.
6. Verify body structure is present.
7. Verify references such as `self_ref` and `children` are valid where present.
8. Verify labels are present and valid where expected.
9. Verify provenance and page numbers where available.
10. Verify tables and pictures where present.
11. Verify unresolved content handling when applicable.
12. Fix only export-layer issues inside the whitelist.
13. Do not modify ground-truth files.
14. Do not modify linked structure, consensus, calibration or connector code.
15. Record ground_truth_unavailable when no matching ground-truth Docling file exists.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_docling_export.py -q
conda run -n pdf2md pytest tests/test_export_contracts.py -q
conda run -n pdf2md pytest tests/test_export_io_cli.py -q
```

Expected output:
Produced Docling JSON validates structurally and is meaningfully comparable to available ground truth.

Completion evidence:
Agent must report files changed, structural comparison result, docling_core status and tests run.

Human verification required:
yes. Covered by H3.

Task A3:

Title:
Validate RAG, Markdown, manifest and Plan 16 readiness.

Goal:
Verify all default export artefacts and decide whether outputs are ready for Plan 16 end-to-end evaluation.

Files allowed:

```text
src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py
src/pdf2md/export/__init__.py
tools/export_linked_docling.py
tests/test_rag_export.py
tests/test_markdown_export.py
tests/test_export_io_cli.py
tests/test_export_contracts.py
tests/data/export_fixtures/**
run_log.md append-only if required by agent.md
```

Implementation requirements:

1. Validate RAG chunks JSON.
2. Confirm RAG chunks contain text where the source document has text.
3. Confirm RAG chunks contain confidence or quality metadata where available.
4. Confirm Markdown preview is legible.
5. Confirm Markdown preview preserves obvious headings and paragraph flow where available.
6. Inspect `export_manifest.json`.
7. Confirm all written artefacts have sha256 values.
8. Confirm skipped artefacts are only skipped when explicitly disabled, not during default H2 run.
9. Inspect `reports/export_report.json`.
10. Confirm counts and warnings are coherent.
11. Classify Plan 16 readiness as `ready_for_plan_16`, `ready_with_warnings`, or `not_ready_for_plan_16`.
12. Do not run the end-to-end pipeline.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_rag_export.py -q
conda run -n pdf2md pytest tests/test_markdown_export.py -q
conda run -n pdf2md pytest tests/test_export_io_cli.py -q
conda run -n pdf2md pytest tests/test_export_contracts.py -q
```

Expected output:
All five default export artefacts are validated and Plan 16 readiness is clear.

Completion evidence:
Agent must report manifest status, RAG status, Markdown status, export report status and Plan 16 readiness.

Human verification required:
yes. Covered by H3.

---

## 7. Human verification checkpoints

Checkpoint H1:

Title:
Input readiness and existing CLI gate.

Purpose:
Confirm that Plan 15 has a real Plan 14 LinkedStructure file and uses the existing export CLI.

Required environment:
pdf2md

Preconditions:
Plan 14 is human_verified.
Plan 14 produced `linked_structure.json`.
Plan 13 produced `consensus_ir.json` if available.
Source PDF is identified if available.

Command:

```bash
conda run -n pdf2md python tools/export_linked_docling.py --help
ls -lh <PLAN14_LINKED_STRUCTURE_JSON>
```

Optional:

```bash
ls -lh <PLAN13_CONSENSUS_IR_JSON>
ls -lh <SOURCE_PDF_PATH>
```

Verification procedure:

1. Run the help command.
2. Confirm the CLI is `tools/export_linked_docling.py`.
3. Confirm the help output includes:
   - `--linked-structure`
   - `--consensus-ir`
   - `--source-pdf`
   - `--out-dir`
   - `--strict`
   - `--verbose`
   - `--no-rag`
   - `--no-markdown`
   - `--include-unresolved`
   - `--max-chars`
4. Confirm `--linked-structure` is a single JSON file path.
5. Confirm `PLAN14_LINKED_STRUCTURE_JSON` exists.
6. Confirm `PLAN14_LINKED_STRUCTURE_JSON` is from real Plan 14 output, not a test fixture.
7. Confirm consensus-ir path if available.
8. Confirm source-pdf path if available.
9. If real Plan 14 `linked_structure.json` is missing, mark Plan 15 blocked for real execution.

Pass criteria:

```text
Existing CLI is used.
PLAN14_LINKED_STRUCTURE_JSON exists.
PLAN14_LINKED_STRUCTURE_JSON is a real Plan 14 artefact.
--linked-structure is treated as a file path.
Optional input availability is recorded.
```

Fail criteria:

```text
A new export CLI is used.
PLAN14_LINKED_STRUCTURE_JSON is missing.
A test fixture is used as substitute for real Plan 14 output.
--linked-structure is treated as a directory.
Optional missing inputs are not recorded.
```

Evidence to record:

```text
Paste help output or relevant flags.
Paste PLAN14_LINKED_STRUCTURE_JSON path.
Paste consensus-ir availability.
Paste source-pdf availability.
Paste whether any optional inputs are missing.
```

Checkpoint H2:

Title:
One-document default export.

Purpose:
Confirm that the existing export path writes all default artefacts from real Plan 14 LinkedStructure.

Required environment:
pdf2md

Preconditions:
H1 passed.
Tasks A1 and A2 are complete.

Command:

```bash
conda run -n pdf2md python tools/export_linked_docling.py --linked-structure <PLAN14_LINKED_STRUCTURE_JSON> --consensus-ir <PLAN13_CONSENSUS_IR_JSON> --source-pdf <SOURCE_PDF_PATH> --out-dir groundtruth/runs/docling_export_one_document --strict --verbose
```

If consensus-ir or source-pdf are unavailable but optional in the CLI, omit only the unavailable optional flags and record the warning.

Do not pass `--no-rag` or `--no-markdown`.

Expected output files:

```text
groundtruth/runs/docling_export_one_document/docling/<doc_id>.docling.json
groundtruth/runs/docling_export_one_document/rag/<doc_id>.rag_chunks.json
groundtruth/runs/docling_export_one_document/markdown/<doc_id>.preview.md
groundtruth/runs/docling_export_one_document/reports/export_report.json
groundtruth/runs/docling_export_one_document/export_manifest.json
```

Verification procedure:

1. Replace placeholders with real Plan 14, Plan 13 and source PDF paths where available.
2. Run the command exactly as written, omitting unavailable optional flags only if needed.
3. Confirm the command exits 0.
4. Confirm the Docling JSON exists.
5. Confirm the RAG chunks JSON exists.
6. Confirm the Markdown preview exists.
7. Confirm `reports/export_report.json` exists.
8. Confirm `export_manifest.json` exists.
9. Open Docling JSON and confirm body structure and labels are present.
10. Open export report and confirm warnings are understandable.
11. Confirm `docling_core_unavailable` or equivalent is only a warning if present.
12. Confirm no end-to-end pipeline was run.

Pass criteria:

```text
Command exits 0.
All five default artefacts exist.
Docling JSON validates structurally under repository validation.
RAG chunks are produced.
Markdown preview is produced.
Export report exists.
Manifest exists and records written artefacts.
Missing optional inputs are recorded as warnings.
No end-to-end pipeline is run.
```

Fail criteria:

```text
Command exits non-zero.
Any default artefact is missing.
Docling JSON is structurally invalid.
RAG or Markdown are skipped in default run.
Manifest is missing.
Warnings are hidden.
End-to-end pipeline is run.
```

Evidence to record:

```text
Paste the command.
Paste exit code.
Paste Docling JSON path.
Paste RAG chunks path.
Paste Markdown preview path.
Paste export report path.
Paste export manifest path.
Paste warnings.
Paste confirmation that no end-to-end pipeline was run.
```

Checkpoint H3:

Title:
Ground-truth comparison, artefact quality and Plan 16 readiness.

Purpose:
Confirm that exported Docling JSON is structurally comparable to the available LaTeX-derived ground truth, and that RAG, Markdown, report and manifest are ready for Plan 16.

Required environment:
pdf2md

Preconditions:
H2 passed.
Task A3 is complete.

Command:

Manual inspection of:

```text
groundtruth/runs/docling_export_one_document/docling/<doc_id>.docling.json
groundtruth/runs/docling_export_one_document/rag/<doc_id>.rag_chunks.json
groundtruth/runs/docling_export_one_document/markdown/<doc_id>.preview.md
groundtruth/runs/docling_export_one_document/reports/export_report.json
groundtruth/runs/docling_export_one_document/export_manifest.json
<matching groundtruth/corpus/latex/**/<doc_id>.docling.json if available>
```

Optional helper commands may be used only if already present in the repository.

Verification procedure:

1. Open produced Docling JSON.
2. Locate matching ground-truth `.docling.json` if available.
3. If ground truth is available, compare structure rather than exact byte-level JSON.
4. Confirm body structure is plausible.
5. Confirm texts / tables / pictures / groups are structurally comparable where present.
6. Confirm `self_ref` and `children` references are intact where present.
7. Confirm provenance and page numbers are present where source data supports them.
8. Open RAG chunks and confirm text content exists.
9. Confirm RAG chunk confidence or quality metadata exists where available.
10. Open Markdown preview and confirm legible content.
11. Open export manifest and confirm sha256 values for written artefacts.
12. Open export report and confirm counts and warnings are coherent.
13. Classify Plan 16 readiness as `ready_for_plan_16`, `ready_with_warnings`, or `not_ready_for_plan_16`.
14. Confirm no MVP completion is claimed.

Pass criteria:

```text
Produced Docling JSON is structurally valid.
If ground truth exists, exported structure is meaningfully comparable to it.
RAG chunks contain text.
Markdown preview is legible.
Manifest records written artefacts and sha256 values.
Export report is coherent.
Plan 16 readiness is ready_for_plan_16 or ready_with_warnings.
No MVP completion is claimed.
```

Fail criteria:

```text
Produced Docling JSON is structurally invalid.
Ground-truth comparison reveals major missing structure with no diagnosis.
RAG chunks are empty despite source text.
Markdown preview is empty or unreadable.
Manifest lacks sha256 values for written artefacts.
Export report is missing or incoherent.
Plan 16 readiness is missing.
MVP completion is claimed inside Plan 15.
```

Evidence to record:

```text
Paste produced Docling JSON path.
Paste matching ground-truth path or state ground_truth_unavailable.
Paste structural comparison summary.
Paste RAG chunk summary.
Paste Markdown preview summary.
Paste manifest artefact status and sha256 summary.
Paste export report warnings.
Paste Plan 16 readiness.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_docling_export.py -q
conda run -n pdf2md pytest tests/test_rag_export.py -q
conda run -n pdf2md pytest tests/test_markdown_export.py -q
conda run -n pdf2md pytest tests/test_export_io_cli.py -q
conda run -n pdf2md pytest tests/test_export_contracts.py -q
```

Human verification test matrix:

```text
H1 input readiness and existing CLI gate
H2 one-document default export
H3 ground-truth comparison, artefact quality and Plan 16 readiness
```

Plan-level statuses:

export_ready:
Real Plan 14 LinkedStructure is available and export inputs are identified.

export_blocked:
Real Plan 14 LinkedStructure is missing or invalid.

diagnostic_only:
Human permits a diagnostic run with incomplete optional inputs, but real Plan 14 LinkedStructure is still required.

Per-document export statuses:

exported:
All default artefacts are written and structurally valid.

exported_with_warnings:
Default artefacts are written but warnings remain.

structural_mismatch:
Docling JSON is structurally invalid or not meaningfully comparable to ground truth.

ground_truth_unavailable:
No matching ground-truth `.docling.json` was found for the selected document.

ready_for_plan_16:
Export output is coherent enough for end-to-end MVP corpus evaluation.

ready_with_warnings:
Export output can proceed to Plan 16 but warnings must be carried forward.

not_ready_for_plan_16:
Docling JSON, RAG, Markdown, manifest or report quality is insufficient.

Failure classes:

repository_defect:
Existing export builder, Docling exporter, RAG exporter, Markdown exporter, reporting, I/O, tests or CLI integration are wrong.

missing_plan14_linked_structure:
Real Plan 14 `linked_structure.json` is missing.

invalid_plan14_linked_structure:
Plan 14 `linked_structure.json` exists but fails validation.

missing_optional_consensus_ir:
ConsensusIR is unavailable. Export may proceed with warning, but quality may degrade.

missing_optional_source_pdf:
Source PDF is unavailable. Export may proceed with warning if not required.

docling_structural_failure:
Produced Docling JSON fails repository structural validation.

docling_core_unavailable:
Optional docling_core validation cannot run. This is a warning, not a repository defect.

docling_core_validation_failure:
docling_core is available but rejects the document.

ground_truth_comparison_failure:
Produced Docling JSON is not structurally comparable to available ground truth and no acceptable explanation exists.

rag_export_failure:
RAG chunks are missing, empty or invalid in default export.

markdown_export_failure:
Markdown preview is missing, empty or unreadable in default export.

manifest_failure:
Export manifest is missing artefact status or sha256 values for written artefacts.

reporting_failure:
Export report is missing, incoherent or hides warnings.

scope_violation:
Plan 15 performs linking, consensus, calibration, backend extraction or end-to-end work.

human_procedure_error:
Human ran the wrong command, used wrong paths or inspected stale outputs.

test_expectation_wrong:
The test or checkpoint expectation is inconsistent with the plan or repository contract.

Failure handling:

If failure_class is repository_defect:
The agent must fix the implementation or report a blocker.

If failure_class is missing_plan14_linked_structure:
Plan 15 is blocked for real execution until Plan 14 output exists.

If failure_class is invalid_plan14_linked_structure:
Plan 14 must be fixed or reverified.

If failure_class is missing_optional_consensus_ir:
Proceed only if warning is recorded and human accepts degraded quality.

If failure_class is missing_optional_source_pdf:
Proceed only if warning is recorded.

If failure_class is docling_structural_failure:
Fix export structure before human_verified.

If failure_class is docling_core_unavailable:
Record warning and continue.

If failure_class is docling_core_validation_failure:
Classify whether the defect is repository export logic or optional validator incompatibility.

If failure_class is ground_truth_comparison_failure:
Diagnose structural mismatch and fix export logic if appropriate.

If failure_class is rag_export_failure:
Fix RAG export before human_verified unless human explicitly scopes RAG out in an amended plan.

If failure_class is markdown_export_failure:
Fix Markdown export before human_verified unless human explicitly scopes Markdown out in an amended plan.

If failure_class is manifest_failure:
Fix manifest generation before human_verified.

If failure_class is reporting_failure:
Fix export reporting before human_verified.

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
Plan 14 status is human_verified or human explicitly approves drafting only
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
existing export_linked_docling.py path used
real Plan 14 linked_structure.json used or blocker reported
all five default artefacts produced or blocker reported
agent report completed
status set to agent_complete or human_verification_required
```

Checkpoint C2: Human verification complete

Required before merge or milestone completion:

```text
H1 input readiness passed
H2 one-document default export passed
H3 ground-truth comparison and Plan 16 readiness completed
all expected output files produced or failures classified
Plan 16 readiness recorded
human verification report completed
status set to human_verified by a human
```

Checkpoint C3: Plan finished and promoted

Required before promotion:

```text
status is human_verified
Plan 15 is archived after completion
history.md summary is prepared or updated
Plan 16 exists as next_plan.md or approved prepared plan
Plan 16 may be promoted to current_plan.md only after Plan 15 is finished
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
plans/archive/plan-15-docling-export-validation.md
```

2. Append a milestone summary to history.md.
3. Promote Plan 16 to current_plan.md.
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
Existing export code reused:
export_linked_docling.py CLI flags confirmed:
PLAN14_LINKED_STRUCTURE_JSON:
PLAN13_CONSENSUS_IR_JSON:
SOURCE_PDF_PATH:
Optional inputs missing:
Automated tests run:
Automated tests passed:
Automated tests failed:
Failure classes:
Export command:
Generated Docling JSON:
Generated RAG chunks:
Generated Markdown preview:
Generated export report:
Generated export manifest:
Ground-truth comparison result:
docling_core status:
Plan 16 readiness:
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
Plan 14 linked_structure:
Plan 13 consensus_ir:
Source PDF:
Commands run:
Exit codes:
Output files checked:
Docling JSON status:
RAG chunks status:
Markdown preview status:
Export report status:
Export manifest status:
Ground-truth file inspected:
Structural comparison summary:
docling_core status:
Warnings:
Plan 16 readiness:
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
6. Did the implementation reuse `tools/export_linked_docling.py`?
7. Did the implementation avoid creating a new export CLI?
8. Did the implementation reuse existing export modules?
9. Did the implementation use real Plan 14 `linked_structure.json` for human verification?
10. Did the implementation avoid using synthetic fixtures as real-input substitutes?
11. Did the implementation treat `--linked-structure` as a file path?
12. Was `--consensus-ir` provided when available?
13. If `--consensus-ir` was omitted, was the warning recorded?
14. Did H2 run default export without `--no-rag` or `--no-markdown`?
15. Did the implementation produce Docling JSON?
16. Did the implementation produce RAG chunks?
17. Did the implementation produce Markdown preview?
18. Did the implementation produce `reports/export_report.json`?
19. Did the implementation produce `export_manifest.json`?
20. Did Docling JSON validate structurally?
21. Was docling_core validation attempted when available?
22. Was docling_core absence treated as warning rather than failure?
23. Was ground-truth comparison structural, not exact JSON diff?
24. Are `self_ref` and `children` references intact where present?
25. Are labels present and valid where expected?
26. Is provenance/page_no preserved where source data supports it?
27. Do RAG chunks contain text?
28. Is Markdown preview legible?
29. Does manifest include sha256 for written artefacts?
30. Is export report coherent?
31. Did the implementation avoid linking work?
32. Did the implementation avoid consensus work?
33. Did the implementation avoid calibration work?
34. Did the implementation avoid backend extraction?
35. Did the implementation avoid end-to-end pipeline work?
36. Is Plan 16 readiness clear?
37. Were generated outputs left uncommitted by default?
38. Is Plan 16 clearly identified as the next plan?
39. Is it safe to mark this plan human_verified?
40. Is it safe to promote the next plan?
41. Is ROADMAP.md progress allowed to change?

Status history:

```text
date — status — actor — note
```

Recorded:

```text
2026-05-22 — draft — human — Plan 15 prepared in plans/plan-15-docling-export-validation.md
2026-05-23 — active — feedback — Plan 15 promoted to current_plan.md after Plan 14 archival
2026-05-23 — agent_in_progress — agent — branch plan-15-docling-export-validation created
2026-05-23 — agent_complete — agent — 90 existing export tests still pass; 10 new Plan 15 hardening tests added (run_log PR #1, status=ready_for_review)
2026-05-23 — human_verification_required — agent — automated tests + synthetic baseline complete; human checkpoints H0–H5 staged
2026-05-23 — human_verified — automated review (sandbox) — H0, H1, H2 (synthetic + REAL), H3, H4, H5 all pass; first plan where H0 was a real PASS rather than SKIP (we produced a diagnostic real Plan 14 LinkedStructure earlier on this host)
2026-05-23 — finished — feedback mode — archived and Plan 16 promoted
```

---

## PR_review #1

- verdict: pass
- whitelist_violations: none
- test_contract_violations: none
- dependency_violations: none
- tasks_promoted: A1, A2, A3
- notes:
  - Agent PR #1 (commit `a051deb8`) modified exactly four files: `src/pdf2md/export/reporting.py`, `tools/export_linked_docling.py`, `tests/test_export_io_cli.py`, and `run_log.md`. `docling.py`, `rag.py`, `markdown.py`, `io.py`, and `__init__.py` were left untouched per the plan's "no new modules / no parallel architecture" hard constraint.
  - Reporting now exposes `inspection_status` (9-value taxonomy), `inspection_notes`, `ground_truth_ref`, and `plan16_readiness` (with `end_to_end_orchestration_handed_off_by="plan_16"`); `docling_core_validation_available` is auto-detected from warnings.
  - CLI accepts `--inspection-status`, `--inspection-note`, `--ground-truth`; defaults to `diagnostic_only`; rejects unknown statuses via argparse choices.
  - Plan 15 hard constraint honoured: only the five allowed disk artefacts (docling/rag/markdown + reports/export_report.json + export_manifest.json) are written. No `export_summary.txt`, no `linking_summary.txt`.
  - 90 existing export tests still pass; 10 new Plan 15 hardening tests pass; full repo suite 811 passed / 212 skipped / 0 failed.

---

## Feedback #1

Response to PR_review #1 and to the automated human-verification sandbox run executed on 2026-05-23.

- Sandbox script: `/tmp/plan15_human_verification.sh` (evidence: `/tmp/plan15_hv_run/evidence.md`).
- Result: **PASS=9, FAIL=0, SKIP=0** — the first plan in this whole chain where H0 actually PASSED rather than being SKIPped.
  - H0 (locate real Plan 14 LinkedStructure): PASS — real `linked_structure.json` was produced on this host during the parallel real-corpus chain validation (paddleocr / pp_structurev3 / paddle 3.0.0).
  - H1 (automated tests): PASS — 100 tests across 5 export test suites.
  - H2 (three synthetic scenarios + REAL): PASS — `simple_document`, `rich_document`, and `unresolved_conflicts` all produced exactly the five allowed artefacts and nothing else; the real LinkedStructure also exported cleanly through the same CLI.
  - H3 (Plan 16 hand-off + inspection): PASS — CLI accepted `--inspection-status ready_for_plan_16`, `--ground-truth`, `--inspection-note`; report includes all three fields plus `plan16_readiness.end_to_end_orchestration_handed_off_by="plan_16"`.
  - H4 (strict CLI rejection): PASS — unknown inspection status rejected via argparse (exit 1).
  - H5 (forbidden-layer diff): PASS — only whitelisted Plan 15 files + plan-state files changed. `linking/`, `consensus/`, `calibration/`, `connectors/`, backend execution, model schema files untouched.
- Reduced-gate approval recorded: not applicable — H0 actually PASSED.
- Tasks promoted to done: A1, A2, A3 (full real-data verification achieved).
- Decision: archive Plan 15 and promote Plan 16 (`plan-16-end-to-end-runner-mvp-corpus-evaluation`) to `current_plan.md`. Plan 16 is the final pre-MVP plan; `next_plan.md` is reset to a minimal placeholder noting that post-MVP planning has not yet begun. Reset `run_log.md` to the empty template for Plan 16.

