# pdf2md Roadmap

## Purpose

This roadmap is the durable planning document for moving `pdf2md` from concept and prototype to a functional, ground-truth-calibrated PDF-to-Docling program.

The target system converts complete sequential PDF documents into Docling-compatible structured output. It supports scanned PDFs, born-digital PDFs with embedded text, mixed PDFs, LaTeX-compiled PDFs, and tagged PDFs when structural tags are available.

The project is not a simple OCR wrapper. It is a multi-backend evidence system. Each backend contributes partial evidence. The system compares, weights, links, validates, and exports that evidence into a semantic document representation.

Beyond the structural Docling output, the project's target scope
includes a built **semantic cross-reference layer** (CrossReferenceGraph sidecar) and user-facing graph/validator surfaces that still need real-data hardening. Together these form a two-branch architecture: an extraction/structural Docling branch and an entity-level semantic graph branch. The semantic branch no longer flows through page-level `ConsensusIR`; it consumes connector `EntityProposalDocument` evidence plus semantic backend markers.

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
  -> page-level ConsensusIR (structural Docling branch)
  -> whole-document LinkedStructure
  -> Docling JSON

Semantic side branch:
  per-backend EntityProposalDocument
  -> optional entity-level OCR merge
  -> ResolverCandidates + semantic backend RefMarkers
  -> CrossReferenceGraph
  -> graph export, viewer, validator staging

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
| 4b | Semantic cross-reference layer | <HUMAN: set Phase 4b %> | post-MVP | CrossReferenceGraph, resolver, semantic consensus, OCR entity merge, equation normalization, theorem matcher (fixture-only), doc-class/index/glossary work shipped; 006_5 remains |
| 5 | Evaluation, confidence, and iteration loop | 40% | 80% | Concept strong, operational loop still emerging |
| 5b | Semantic ground truth and evaluation | <HUMAN: set Phase 5b %> | post-MVP | Semantic fixtures and bench scripts exist; validator staging exists but real-data verification loop remains |
| 6 | Functional application and CLI/API | 28% | 80% | Staged tools exist, single-command program not mature |
| 7 | Production readiness | 8% | post-MVP | Barely started |
| 7b | Visualization and web deliverable | <HUMAN: set Phase 7b %> | post-MVP | Static D3 graph viewer and React/Vite validator scaffold shipped; PDF overlay/real verification workflow remain |

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

Phase 4b: Semantic cross-reference layer

Current estimate: <HUMAN: set Phase 4b %>.

Goal:

Maintain the entity-level semantic side branch that produces `CrossReferenceGraph` outputs alongside the structural Docling branch. This layer consumes connector `EntityProposalDocument` candidate evidence plus regex/GROBID/VLM semantic markers; it does not use page-level `ConsensusIR` as its spine.

Shipped / recorded in this state-sync:

```text
CrossReferenceGraph schema and graph export
semantic backend adapters and marker resolver
semantic graph consensus / merge_graphs (PR #127)
optional OCR entity candidate merge via merge_entity_documents (PR #128)
equation-number normalization, including MinerU tag conventions (PR #136)
theorem-family matcher on synthetic candidates (006_3)
document-class classifier, index detector, glossary detector (PR #124)
static cross-reference viewer data/export path
```

Remaining:

```text
Plan 006_5 connector-side theorem-family entity detector
final retain/retire decision for OCR entity consensus
long-document resolver benchmarks against real backend outputs
clear CLI integration of graph generation into the normal conversion path
```

Exit criteria:

```text
Docling JSON and cross_references.json produced from the same user-facing run
markers and edges include backend provenance and confidence
resolver classifies exact / fuzzy / backend-specific / unresolved edges
theorem-family markers resolve on real connector outputs, not only fixtures
semantic and OCR consensus layers are documented as separate mechanisms
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

Phase 5b: Semantic ground truth and evaluation

Current estimate: <HUMAN: set Phase 5b %>.

Goal:

Benchmark semantic markers, entity candidates, and resolved `CrossReferenceGraph` outputs against source-known documents. The evaluation layer should distinguish semantic backend marker quality from OCR connector candidate quality and resolver quality.

Shipped / recorded in this state-sync:

```text
semantic fixtures for resolver behavior
example-only benchmark and staging data paths
equation normalization metrics recorded in plan evidence
validator scaffold with Checkpoints / Compare / Priors routes
external dataset downloader CLI for future corpus expansion
```

Remaining:

```text
LaTeXML-derived semantic ground truth as first-class graph GT
real-data validator wiring instead of synthesized/staged comparison data
per-RefType precision/recall/F1 and resolution accuracy reports
in-product verification artifacts such as <plan_id>.verification.json
```

Exit criteria:

```text
source-known documents produce ground-truth CrossReferenceGraph files
semantic backend, OCR candidate, and resolver metrics are reported separately
validator consumes real run outputs
regressions are tracked as the corpus grows
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

Phase 7b: Visualization and web deliverable

Current estimate: <HUMAN: set Phase 7b %>.

Goal:

Ship graph and validation surfaces that make semantic resolution inspectable by users and reviewers.

Shipped / recorded in this state-sync:

```text
D3-compatible CrossReferenceGraph export
static webui/cross_ref viewer for graph JSON
viewer data staging for examples
React/Vite webui/validator scaffold with Checkpoints, Compare, and Priors routes
webui/scripts/stage-data.mjs staging pipeline
```

Remaining:

```text
wire validator to real CrossReferenceGraph and backend outputs
add persisted in-product verification evidence
PDF/page overlay and richer unresolved-reference diagnostics
package/serve workflow for non-developer users
```

Exit criteria:

```text
graph export produces valid viewer JSON from a normal run
local web surfaces render real graph data, not only synthesized fixtures
unresolved references are visually flagged
human verification is captured as machine-readable artifacts
```

---

---

## Plans 004-008 and Follow-ups: Semantic Layer and Visualization (partly shipped)

The semantic + visualization chain sits on top of the extraction +
structural MVP. Plan 004_0 is documentation alignment; Plans 005-008
delivered the initial implementation; follow-up plans now harden real-data coverage and verification.

### Plan 004_0: Project Documentation Alignment

Roadmap phase:
Phase 0 (documentation alignment for the expanded scope).

Type:
Documentation-only.

Purpose:
Bring `project.md`, `ROADMAP.md`, and `README.md` into alignment with
the three-layer architecture (extraction + structural + semantic) and
the visualization deliverable, before any semantic-layer code is written.

Exit criteria:

```text
project.md describes the three-layer architecture, semantic backends, and
  semantic routing without contradicting existing extraction-layer prose
ROADMAP.md gains Phase 4b (semantic), Phase 5b (semantic eval), and
  Phase 7b (visualization) as planned extensions
README.md describes the expanded scope and the Plans 004-008 sequence
terminology is consistent (extraction vs semantic backend; structural vs
  semantic layer; DoclingDocument vs Docling JSON)
shipped work is distinguished from remaining planned follow-ups
```

### Plan 005_0: Semantic Backends — Installation and Smoke Tests

Roadmap phase:
Phase 4b.

Type:
Backend bring-up, parallel (independent backends).

Purpose:
Install GROBID (Docker), DeepSeek-VL2 (isolated conda env), and a
regex/heuristic backend under `backend/semantic/<name>/`. Each must run
independently with no pipeline coupling.

Exit criteria:

```text
GROBID Docker container accepts a PDF and returns TEI XML with refs
DeepSeek-VL2 loads in pdf2md-deepseek-vl2 and processes one page image
regex backend detects ≥3 pattern types from sample text
each backend has a README with install instructions and a standalone smoke test
no imports from src/pdf2md/ — semantic backends are isolated at this stage
```

### Plan 006_0: Semantic Layer Integration and Label Extension

Roadmap phase:
Phase 4b.

Type:
Sequential core.

Purpose:
Integrate the three semantic backends into the `pdf2md` pipeline.
Define the `CrossReferenceGraph` schema. Add semantic profiler signals
and a Bayesian semantic router. Wire each backend into a unified
`SemanticBackend` interface.

Exit criteria:

```text
CrossReferenceGraph schema defined and JSON-serializable
profiler computes semantic signals (reference_density, has_bibliography, …)
each semantic backend wrapped in the SemanticBackend interface
deterministic resolver matches markers to DoclingDocument JSON pointers
  (exact + fuzzy + grobid_tei + unresolved)
CLI produces cross_references.json alongside DoclingDocument
ensemble mode runs multiple backends and merges results
no hardcoded paper-vs-book routing — every backend is a candidate
```

### Plan 007_0: Ground Truth, Evaluation, and Worked Example

Roadmap phase:
Phase 5b.

Type:
Sequential after Plan 006.

Purpose:
Build the LaTeXML-based ground-truth pipeline, an evaluation harness
that benchmarks semantic backends, and a worked example that runs the
full pipeline (extraction → structural → semantic → evaluation).

Exit criteria:

```text
≥4 controlled .tex documents covering diverse cross-reference patterns
LaTeXML → TEI → CrossReferenceGraph parser produces valid GT with
  confidence 1.0 and resolved targets
metrics computed per RefType per backend (precision / recall / F1,
  resolution accuracy, entity P/R/F1)
benchmark runner produces machine-readable comparison tables
worked example under examples/semantic_cross_references/ runs end-to-end
```

### Plan 008_0: Visualization and Web Integration

Roadmap phase:
Phase 7b.

Type:
Sequential after Plan 007.

Purpose:
Ship the interactive visualization as a user-facing deliverable. The
visualization is the primary user-visible outcome of the semantic
layer.

Exit criteria:

```text
graph export produces valid D3 / Cytoscape JSON from a CrossReferenceGraph
interactive graph viewer renders nodes, edges, and cross-page relationships
PDF.js + SVG page overlay shows markers and target lines
evaluation dashboard renders backend × RefType F1 heatmap
CLI: pdf2md export-graph and pdf2md serve --port N --data-dir out/
structural (Docling) and semantic (graph) views accessible together
unresolved references are visually flagged
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
