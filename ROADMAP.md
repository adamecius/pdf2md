# pdf2md Roadmap

## Purpose

This roadmap is the durable planning document for moving `pdf2md` from concept and prototype to a functional, ground-truth-calibrated PDF-to-Docling program.

The target system converts complete sequential PDF documents into Docling-compatible structured output. It supports scanned PDFs, born-digital PDFs with embedded text, mixed PDFs, LaTeX-compiled PDFs, and tagged PDFs when structural tags are available.

The project is not a simple OCR wrapper. It is a multi-backend evidence system. Each backend contributes partial evidence. The system compares, weights, links, validates, and exports that evidence into a semantic document representation.

The ground-truth corpus is central. LaTeX, LuaLaTeX/tagged-PDF artefacts, and LaTeXML XML are used to build source-known documents. These documents are used to measure backend success and failure, then calibrate feature-specific backend confidence.

---

## Source-of-Truth Hierarchy

`ROADMAP.md` is the durable product roadmap.

`project.md` is the durable architecture description.

`README.md` is the public entry point.

`current_plan.md` remains the active implementation contract for coding agents, including task scope, file whitelist, and required tests.

`history.md` records completed milestones.

---

## Current Development Estimate

The project is currently in a late prototype / early alpha stage.

Consensus estimate:

```text
Overall practical completion: 55%
Architecture-weighted completion: approximately 57 to 60%
Production-weighted completion: approximately 52%
MVP target: 84 to 86%
```

The project is past the concept stage. The architecture, core contracts, ground-truth direction, consensus direction, linked-structure direction, and Docling export direction are already present.

It is not yet a functional end-user program, because the full path from arbitrary complete PDF to Docling output is not yet mature as a single reliable command.

---

## Target Architecture

The target pipeline is:

```text
Complete sequential PDF
  - scanned PDF
  - born-digital PDF with embedded text
  - mixed PDF
  - LaTeX-compiled PDF
  - tagged PDF

  -> input classification
  -> backend extraction
  -> per-backend PageExtractionIR
  -> EntityProposalDocument
  -> CalibrationPriorDocument
  -> page-level ConsensusIR
  -> whole-document LinkedStructure
  -> Docling JSON
  -> validation, reports, RAG chunks, Markdown preview
```

The semantic stage is fed by several orthogonal sources:

```text
OCR/layout backend evidence
embedded PDF text
geometry and media extraction
tagged-PDF structure
LaTeX-derived ground-truth signal
LaTeXML XML for source-known documents
calibration priors from backend success/failure measurements
```

Docling is the canonical structured export target. Markdown is a preview and downstream convenience format, not the source of truth.

---

## Ground-Truth Strategy

The strongest ground-truth documents are built from:

```text
.tex source
  -> LuaLaTeX / LaTeX compiled PDF
  -> tagged PDF where available
  -> LaTeXML XML
  -> semantic ground-truth contracts
  -> Docling ground-truth JSON
  -> metadata and validation reports
```

The ground-truth corpus is not only a test suite. It is the basis for robust ensemble OCR and document extraction.

The intended feedback loop is:

```text
ground-truth corpus
  -> backend success/failure measurements
  -> feature-specific backend confidence
  -> weighted page-level consensus
  -> whole-document semantic linking
  -> Docling output with provenance and confidence
```

Backend trust should be feature-specific, not global. A backend may be strong for body text but weak for tables. Another may be strong for formulae but weak for reading order. Another may be strong for captions but weak for footnotes. These observations become calibration priors.

---

## Roadmap Overview

| Phase | Name | Current Estimate | Target for MVP | Status |
|---|---:|---:|---|
| 0 | Concept, vision, and architectural baseline | 90% | 95% | Strong, but some documentation remains stale |
| 1 | Ground-truth engine | 82% | 90% | Advanced prototype, not yet fully calibration-driven |
| 2 | Extraction and normalisation | 60% | 85% | Substantial progress, but not proven across all PDF classes |
| 3 | Consensus and ensemble logic | 55% | 85% | Page mechanics ahead of calibration-weighted intelligence |
| 4 | Semantic reconstruction and export | 55% | 85% | LinkedStructure and export scaffolding present, real-document validation pending |
| 5 | Evaluation, confidence, and iteration loop | 40% | 80% | Concept strong, operational loop still emerging |
| 6 | Functional application and CLI/API | 28% | 80% | Staged tools exist, single-command program not mature |
| 7 | Production readiness | 8% | post-MVP | Barely started |

Overall practical estimate: 55%.

---

## Phase 0: Concept, Vision, and Architectural Baseline

Current estimate: 90%.

Goal:

Define the durable architecture and keep repository-level documentation aligned.

Achieved:

```text
complete sequential PDF assumption
all major PDF classes included
Docling as canonical structured output
backend evidence model
ground-truth-driven calibration concept
separation between page-level consensus and whole-document linking
README.md and project.md aligned with the current architecture
```

Remaining:

```text
update README_latex_docling_groundtruth.md
rewrite or deprecate docs/docling_layer.md
update history.md with completed milestones
clarify agent.md source-of-truth hierarchy
reconcile current_plan.md and next_plan.md
```

Exit criteria:

```text
README.md, project.md, ROADMAP.md, ground-truth documentation, and agent documentation agree
legacy documentation is marked as legacy or rewritten
history.md reflects the actual completed layers
```

---

## Phase 1: Ground-Truth Engine

Current estimate: 82%.

Goal:

Make LaTeX/LuaLaTeX/tagged-PDF/LaTeXML-derived ground truth a reliable acceptance and calibration corpus.

Achieved:

```text
LaTeX-derived ground-truth concept
source-known fixture generation
semantic contracts
Docling ground-truth JSON direction
metadata sidecars
validation tooling direction
```

Remaining:

```text
formalise tagged-PDF artefacts as first-class ground truth
formalise LaTeXML XML checks as first-class ground truth
expand corpus diversity
support public arXiv-style examples where appropriate
record backend feature-level performance measurements
turn validation results into calibration priors automatically
```

Exit criteria:

```text
each corpus document has source, PDF, XML/tagged artefacts where available, semantic contract, Docling ground truth, and metadata
the corpus can be validated locally
missing artefacts are classified clearly
backend comparison against ground truth produces machine-readable metrics
```

---

## Phase 2: Extraction and Normalisation

Current estimate: 60%.

Goal:

Convert all backend outputs into comparable repository contracts.

Achieved:

```text
backend isolation concept
backend-specific environments
connector-based normalisation direction
raw artefact preservation
PageExtractionIR and EntityProposalDocument concepts
```

Remaining:

```text
normalise real MinerU output
normalise real PaddleOCR output
normalise real DeepSeek output
add or formalise born-digital embedded-text extraction
add or formalise tagged-PDF extraction
add or formalise geometry/media extraction
normalise coordinate systems
preserve backend provenance and raw artefact references
```

Exit criteria:

```text
the same PDF can produce comparable PageExtractionIR from multiple backends
all connector outputs validate against schemas
raw evidence remains traceable
born-digital, scanned, mixed, LaTeX-compiled, and tagged PDFs have defined extraction routes
```

---

## Phase 3: Consensus and Ensemble Logic

Current estimate: 55%.

Goal:

Build page-level consensus from backend evidence and feature-specific priors.

Achieved:

```text
ConsensusIR concept
page-level comparison concept
candidate grouping direction
conflict preservation
consensus factory direction
```

Remaining:

```text
run consensus on real backend outputs
use feature-specific calibration priors
include embedded-text and tagged-PDF candidates
improve conflict taxonomy
measure consensus improvement over individual backends
emit explainable confidence scores
```

Exit criteria:

```text
ConsensusIR improves over individual backends on ground-truth documents
confidence is traceable to evidence and priors
conflicts are explicit rather than hidden
consensus reports explain backend agreement and disagreement
```

---

## Phase 4: Semantic Reconstruction and Export

Current estimate: 55%.

Goal:

Turn page-level consensus into whole-document semantic structure and export it to Docling.

Achieved:

```text
LinkedStructure concept
whole-document semantic layer
section hierarchy direction
caption, footnote, reference, equation, figure, and table relation direction
Docling export direction
RAG and Markdown preview direction
```

Remaining:

```text
validate semantic linking on long documents
validate on noisy OCR
validate multi-page references and captions
validate glossary/index-like sections
harden table and formula representation
validate against docling_core versions
round-trip checks
preserve relation confidence and conflicts in export metadata
```

Exit criteria:

```text
LinkedStructure validates on real corpus outputs
important relations are resolved or explicitly unresolved
Docling JSON validates
export reports explain warnings and confidence
Markdown preview and RAG chunks preserve provenance and structure
```

---

## Phase 5: Evaluation, Confidence, and Iteration Loop

Current estimate: 40%.

Goal:

Close the loop between ground-truth evaluation and backend ensemble confidence.

Achieved:

```text
ground-truth-to-confidence concept
CalibrationPriorDocument concept
feature-specific trust model direction
```

Remaining:

```text
define metrics per feature
measure body text accuracy
measure table structure accuracy
measure equation detection accuracy
measure caption relation accuracy
measure footnote relation accuracy
measure reading-order accuracy
measure reference and bibliography accuracy
produce backend reliability profiles
write CalibrationPriorDocument from measured results
feed priors into consensus scoring
track regressions as corpus grows
```

Exit criteria:

```text
each backend has feature-specific confidence values
confidence values are generated from corpus evaluation
consensus uses calibration priors
reports show why one backend was trusted over another for a feature
```

---

## Phase 6: Functional Application and CLI/API

Current estimate: 28%.

Goal:

Provide a reliable user-facing program.

Target command:

```bash
pdf2md convert input.pdf --out output_dir --to docling
```

The command should:

```text
classify the PDF type
select the backend strategy
run relevant extraction paths
normalise backend outputs
build consensus
build linked structure
export Docling
write reports
write confidence metrics
handle missing environments clearly
```

Remaining:

```text
unified convert command
input classification
backend strategy selection
pipeline orchestration
structured output directory
error handling
logging
strict and non-strict modes
dry-run mode
environment diagnostics
```

Exit criteria:

```text
one command converts a complete PDF to Docling
reports confidence and conflicts
handles missing environments clearly
works on at least one scanned, one born-digital, one mixed, one LaTeX-compiled, and one tagged PDF document
```

This is the MVP boundary.

---

## Phase 7: Production Readiness

Current estimate: 8%.

Goal:

Make the program reliable outside a controlled development environment.

Remaining:

```text
packaging
installation documentation
example datasets
performance optimisation
large-document robustness
CI matrix
stable versioned reports
contribution documentation
user-facing troubleshooting
backend environment recipes
```

Exit criteria:

```text
new users can install and run the program from documentation
examples work reproducibly
large documents are handled without fragile manual steps
backend failures are recoverable and well reported
```

---

## Definition of MVP

MVP is reached when the project can do the following locally:

```text
take a complete PDF
classify its input type
run the appropriate backend ensemble
normalise backend outputs
build consensus
build linked semantic structure
export Docling JSON
compare against ground truth when available
produce confidence and conflict reports
```

MVP should be considered reached at approximately 84 to 86% completion.

The minimum MVP corpus should include:

```text
one scanned document
one born-digital embedded-text document
one mixed document
one LaTeX-compiled document
one tagged-PDF document
```

---

## Implementation Plans to MVP

The strategic roadmap is implemented through focused, human-verifiable plans using `PLAN_TEMPLATE.md`.

Each plan should be small enough to review and verify, but large enough to move the roadmap forward. `current_plan.md` remains the active execution contract. A plan is not finished until human verification passes and the hand-off procedure is completed.

The final MVP path is:

```text
Plan 8  -> Plan 9  -> Plan 10 -> Plan 11 -> Plan 12
        -> Plan 13 -> Plan 14 -> Plan 15 -> Plan 16
```

### Plan 8: Local Ground-Truth Corpus Validation plus Documentation Consistency

Roadmap phase:
Phase 1, with a small Phase 0 documentation consistency exit criterion.

Type:
Sequential core.

Purpose:
Validate the local LaTeX-derived ground-truth corpus before any real backend execution. The plan also checks that the remaining narrow documentation surfaces do not contradict this roadmap.

Scope:

```text
validate corpus discovery
check .tex source presence
check compiled PDF presence
check tagged PDF where available
check LaTeXML XML presence
check Docling ground-truth JSON presence
check metadata presence
write machine-readable and human-readable validation reports
support strict and non-strict validation modes
verify README_latex_docling_groundtruth.md, docs/docling_layer.md, history.md and agent.md do not contradict ROADMAP.md
```

Exit criteria:

```text
ground-truth validation report exists
ground-truth validation summary exists
missing artefacts are classified clearly
strict and non-strict modes behave as specified
documentation consistency check passes or narrow corrections are made inside the Plan 8 whitelist
```

### Plan 9: Real Backend Smoke Readiness

Roadmap phase:
Phase 2.

Type:
Sequential core.

Purpose:
Prove that real backend execution can be attempted and that backend failures are classified correctly before connector normalisation is trusted.

Backend gate:

```text
At least two configured backends must produce successful smoke output.
All other configured backends must be classified explicitly.
```

Allowed backend classifications:

```text
success
env_not_ready
model_missing
dependency_missing
backend_crash
output_missing
not_configured
```

Exit criteria:

```text
at least two backends produce smoke outputs suitable for connector validation
all other configured backends have a recorded readiness classification
backend manifests or smoke reports are written
backend failures are not confused with repository failures
```

### Plan 10: Connector Implementation and PageExtractionIR Validation

Roadmap phase:
Phase 2.

Type:
Sequential core with incremental backend acceptance.

Purpose:
Harden the connector path so real backend outputs can be converted into validated `PageExtractionIR` evidence.

Important boundary:
The connector may emit both `PageExtractionIR` and `EntityProposalDocument`, but Plan 10 acceptance validates only the `PageExtractionIR` part.

Incremental backend rule:
A backend whose connector output validates may move forward to later plans while other backends are still being debugged, provided missing or failing backends remain documented.

Exit criteria:

```text
at least two backend outputs are converted to valid PageExtractionIR
page numbers, block kinds, text, bounding boxes, confidence where available and provenance are present
coordinate systems are normalised or explicitly documented
raw artefact references are preserved
invalid backend output produces clear validation errors
```

### Plan 11: EntityProposalDocument Validation

Roadmap phase:
Phase 2.

Type:
Sequential core.

Purpose:
Validate and harden `EntityProposalDocument` outputs from the connector path established in Plan 10.

Important boundary:
Plan 11 should use the connector output from Plan 10. It should not reopen connector implementation except for defects found during entity validation.

Exit criteria:

```text
EntityProposalDocument outputs validate where the backend provides entity evidence
entity proposals preserve provenance
caption, equation, table, figure, footnote, reference or bibliography candidates are represented where available
absence of entity proposals is reported clearly when a backend does not provide them
```

### Plan 12: Real Calibration Prior Generation

Roadmap phase:
Phase 5.

Type:
Sequential after Plans 10 and 11.

Purpose:
Run real calibration against normalised backend outputs and source-known ground truth. This plan converts observed backend success and failure into feature-specific priors.

Required checkpoint:
Before trusting calibration metrics, verify that connector `BlockKind` vocabulary matches ground-truth `TruthBlock` vocabulary, or that an explicit mapping exists.

Expected outputs:

```text
CalibrationPriorDocument
calibration_report.json
backend_feature_metrics.json or backend_feature_metrics.csv
calibration_summary.txt
```

Exit criteria:

```text
calibrate_priors.py runs on real normalised backend outputs against ground truth
BlockKind vocabulary alignment is verified or mapped
precision, recall and F1 are reported by feature and backend
CalibrationPriorDocument validates
insufficient evidence is reported without fabricating confidence
```

### Plan 13: Weighted ConsensusIR on Real Outputs

Roadmap phase:
Phase 3.

Type:
Sequential core.

Purpose:
Use real `PageExtractionIR` evidence and real calibration priors to produce explainable weighted consensus.

Exit criteria:

```text
ConsensusIR is produced from real normalised backend outputs
calibration priors influence scoring
conflicts are explicit
consensus report explains backend agreement, disagreement and selected candidates
confidence is traceable to evidence and priors
```

### Plan 14: LinkedStructure and Cross-Page Semantic Linking

Roadmap phase:
Phase 4.

Type:
Sequential core.

Purpose:
Turn page-level consensus into whole-document semantic structure.

Exit criteria:

```text
LinkedStructure validates on real consensus outputs
sections, captions, footnotes, equations, figures, tables, references, page numbers and headers or footers are linked when evidence supports it
unresolved relations are explicit
linking report explains warnings and conflicts
```

### Plan 15: Docling Export Validation

Roadmap phase:
Phase 4.

Type:
Sequential core.

Purpose:
Export `LinkedStructure` to Docling JSON and validate the export against the repository contracts and ground truth where available.

Exit criteria:

```text
Docling JSON is produced from LinkedStructure
export preserves provenance, conflicts, warnings and relation metadata
docling_core validation is used when available
Docling output is compared with LaTeX-derived Docling ground truth where available
Markdown preview and RAG outputs are produced if in scope for the plan
```

### Plan 16: End-to-End Runner and MVP Corpus Evaluation

Roadmap phase:
Phase 6.

Type:
Sequential core.

Purpose:
Provide the first functional local pipeline runner and validate it on the minimum MVP corpus.

Internal checkpoint 16A:
One-document end-to-end runner.

Scope:

```text
input classification, profiling or routing
backend strategy selection
normalisation
consensus
semantic linking
Docling export
confidence report
conflict report
```

Input classification assignment:
Input classification belongs in Plan 16A. Earlier plans may run all available backends on controlled documents without needing a routing decision. In Plan 16A the runner must explicitly classify or profile the input as scanned, born-digital, mixed, LaTeX-compiled, tagged or unknown, and write the decision to a report.

Internal checkpoint 16B:
MVP corpus evaluation.

Minimum corpus:

```text
one scanned document
one born-digital embedded-text document
one mixed document
one LaTeX-compiled document
one tagged-PDF document
```

Split rule:
If 16A exposes major integration failures, 16B should be split into a new Plan 17 instead of forcing MVP corpus evaluation into the same plan.

Exit criteria:

```text
one command or local runner executes the full pipeline on at least one document
runner writes Docling output, confidence report and conflict report
runner classifies or profiles the input and records the routing decision
MVP corpus evaluation succeeds or is split into the next plan with documented blockers
```

### Plan 17 and Later: Production Readiness

Roadmap phase:
Phase 7.

Type:
Post-MVP, parallel where possible.

Purpose:
Prepare the program for broader use after the MVP path is validated.

Scope:

```text
packaging
installation documentation
example datasets
performance optimisation
large-document robustness
CI matrix
stable versioned reports
contribution documentation
user-facing troubleshooting
backend environment recipes
```

---

## Final Consensus Position

Recommended statement:

```text
The project is approximately 55% complete.
It is late prototype / early alpha.
Architecture and ground truth are strong.
The main remaining gap is real-backend validation, connector normalisation, calibrated consensus, and the single-command functional program.
MVP is expected around 84 to 86%, after full local end-to-end corpus validation.
```

This roadmap is the durable product roadmap. Active implementation remains governed by `current_plan.md`.
