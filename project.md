# pdf2md Project Architecture

## 1. Purpose

`pdf2md` is a multi-backend document reconstruction system for complete sequential PDFs. It is not a wrapper around one OCR engine. The project collects evidence from visual OCR/layout backends, embedded/textual PDF sources, semantic backends, and source-known ground-truth corpora, then records provenance, confidence, conflicts, and unresolved relations explicitly.

The durable export target remains Docling-compatible structured output. Markdown is a preview/downstream convenience. The semantic cross-reference graph is an additive sidecar and user-facing inspection surface, not a replacement for Docling export.

For current built/partial/planned subsystem status, active work, and verification gaps, read `STATE.md`. This document intentionally describes durable architecture rather than plan sequencing.

## 2. Current architecture: two extraction/semantic layers

The running architecture now has two related but distinct paths. New agents should not assume that page-level `ConsensusIR` is the spine of every downstream feature.

### 2.1 Extraction and structural branch

```text
PDF
  -> per-backend OCR/layout extraction
  -> connector normalization
  -> PageExtractionIR
  -> CalibrationPriorDocument
  -> page-level ConsensusIR
  -> LinkedStructure / Docling export branch
```

This branch is retained for the structural Docling-export path. `ConsensusIR` is the page/block-level feature picker: it groups backend candidates, scores agreement with calibration priors, and records selected/fallback/unresolved blocks for downstream structural export.

### 2.2 Semantic cross-reference branch

```text
per-backend OCR/layout output
  -> connector entity extraction
  -> EntityProposalDocument per backend
       -> optional OCR entity merge (`merge_entity_documents`)
       -> ResolverCandidates
semantic backends (regex / GROBID / VLM)
  -> RefMarkers / semantic entities
ResolverCandidates + RefMarkers
  -> resolver
  -> CrossReferenceGraph
  -> graph_export / webui viewer / validator staging
```

The semantic resolver bridge consumes `EntityProposalDocument`-shaped candidate evidence, not page-level `ConsensusIR`. This is an intentional abstraction boundary: cross-reference resolution needs entity-level labels, normalized numbers, offsets, provenance, and candidate ids more directly than it needs block-level consensus groups.

### 2.3 Consensus layers are separate

Two consensus-like layers now exist:

1. **Page/block consensus (`ConsensusIR`)** — calibration-weighted block selection for the structural Docling branch.
2. **Semantic/entity consensus** — graph/entity-level merging for the cross-reference branch, including semantic marker graph merging and optional OCR entity candidate merging via `merge_entity_documents`.

These layers should not be conflated. A plan that changes one must state whether it affects the Docling structural branch, the semantic graph branch, or both.

## 3. Ground truth and calibration

The ground-truth corpus is a source-known measurement system:

```text
.tex source
  -> LuaLaTeX / tagged PDF where available
  -> LaTeXML XML where available
  -> semantic contracts / Docling ground-truth JSON
  -> validation reports
  -> calibration priors and regression evidence
```

Calibration is feature-specific. A backend can be strong for equations and weak for reading order, or strong for body text and weak for tables. Priors should be generated from measured success/failure against the corpus, then applied at the appropriate layer.

External dataset downloaders add opt-in corpora under `groundtruth/external/` and manifests under `groundtruth/manifest/`; they do not automatically promote third-party data into the canonical generated corpus.

## 4. Backends and connectors

Backends are isolated and interchangeable. Each backend should expose raw artifacts and connector-normalized outputs. Connector outputs may include:

- `PageExtractionIR` for page/block evidence;
- `EntityProposalDocument` for semantic candidates such as equations, figures, tables, bibliography items, section/index/glossary entries, and future theorem-family entities;
- run manifests with backend version, environment, PDF hash, and timestamp.

Adding a backend should normally require a backend descriptor, environment/install recipe, connector, smoke test, and documentation. It should not require rewriting resolver or export code.

## 5. Semantic layer

The semantic layer builds a `CrossReferenceGraph` sidecar. Inputs include:

- OCR connector entity proposals;
- optional OCR entity merge output;
- regex/GROBID/VLM semantic backend markers;
- document-class hints (`article`, `book`, `document`);
- normalized equation labels and future theorem-family labels;
- resolver candidate indexes.

The graph records resolved and unresolved references with provenance. It is exported to viewer-friendly graph JSON and consumed by the static cross-reference viewer and the React/Vite validator staging surface.

Shipped semantic-layer capabilities now include equation-number normalization, semantic graph consensus, OCR entity candidate merge wiring, document-class classification, index/glossary detectors, theorem-family resolver matching on synthetic candidates, graph export, and viewer/validator scaffolding. The theorem-family path is still incomplete on real OCR output until connector-side theorem-family entity detection is added.

## 6. Validation strategy

Validation occurs at multiple layers:

```text
backend raw output
  -> connector output
  -> PageExtractionIR / EntityProposalDocument
  -> ConsensusIR or resolver candidates
  -> LinkedStructure / CrossReferenceGraph
  -> Docling JSON / graph JSON
```

For source-known documents, the project should compare each stage with LaTeX/LaTeXML-derived expectations. Failures are not just regressions; they identify where backend priors, connector rules, resolver logic, semantic backends, or export projections should be improved.

Visual deliverables must be verified in the product surface. Future viewer/validator plans should persist machine-readable verification evidence such as `<plan_id>.verification.json`, not only prose notes.

## 7. Configuration

Configuration should drive backend execution, consensus thresholds, resolver policies, semantic backend selection, calibration behavior, and evaluation metrics. Regex-like and threshold-like scientific-document assumptions should live in config or documented fixtures when practical, not as unexplained constants.

## 8. Governance state

Canonical governance files have distinct roles:

- `ROADMAP.md` — durable product roadmap and phase estimates.
- `project.md` — durable architecture description.
- `STATE.md` — compact current state surface for subsystem status, in-flight work, next action, and known verification gaps.
- `README.md` — public entry point.
- `agent.md` — agent operating protocol.
- `PLAN_TEMPLATE.md` — canonical full plan structure and lifecycle authority.
- `PLAN_TEMPLATE_LITE.md` — abbreviated plan tier for docs/governance/small changes that still uses the same lifecycle.
- `current_plan.md` — active execution contract.
- `next_plan.md` — next planned execution contract.
- `history.md` — completed milestones.
- `run_log.md` — evidence log.

The repository uses plan promotion and archival: human-verified plans are moved to `plans/archive/`, history is appended, `STATE.md` is updated when subsystem state changes, `next_plan.md` is promoted to `current_plan.md`, and a new `next_plan.md` is created. Agents must not blank `current_plan.md` as a hand-off shortcut.

## 9. Open decisions

These decisions are intentionally visible so future plans inherit the unresolved state instead of rediscovering it.

1. **OCR entity consensus (AP8): retain or retire.** Current tree retains `merge_entity_documents` as an optional candidate-source merge for the semantic resolver. Human decision still required: keep it as an inspectable optional source, or retire it if it only mirrors the strongest OCR backend.
2. **Page-level `ConsensusIR` role.** Current documentation treats `ConsensusIR` as retained for the structural Docling-export branch, not the semantic resolver spine. Human decision still required: confirm long-term retention for Docling export or mark it deprecated.
3. **Validator data source.** The React/Vite validator staging surface exists, but currently relies on staged/synthesized backend-vs-consensus data. A future feature plan must wire it to real `CrossReferenceGraph` outputs before it is treated as a complete deliverable.
4. **Plan 006_5 gap.** The theorem-family resolver matcher is fixture-proven but real OCR data still resolves 0% theorem-family markers because connector-side theorem/definition/corollary/example/proof entity detection is not implemented. Plan 006_5 is the next feature plan.

## 10. End goal

The target system produces Docling-compatible structured output and semantic graph sidecars for complete scientific/technical PDFs such that:

- every block/entity has provenance back to backend evidence;
- important relations are resolved or explicitly unresolved;
- captions, references, footnotes, equations, figures, tables, theorem-family items, page numbers, and headers/footers are linked when evidence supports it;
- conflicts are recorded rather than silently overwritten;
- confidence can be traced to evidence, priors, resolver decisions, and ground-truth calibration;
- graph and Docling outputs can be inspected, validated, and used by downstream knowledge systems.

The project is judged by robust, auditable reconstruction across backends and documents, not by the output of any single backend.
