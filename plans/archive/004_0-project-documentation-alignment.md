# Plan 004_0: Project Documentation Alignment

## Status: DRAFT
## Date: 2026-05-24
## Depends on: Plans 001-003 (existing architecture stable)

---

## 1. Goal

Update all project-level documentation to reflect the full vision discussed:
structural extraction + semantic cross-reference layer + visualization deliverable.
The current docs describe only the extraction pipeline. This plan brings
ROADMAP.md, project.md, and README.md into alignment with the expanded scope
before any implementation begins.

## 2. What changed

The project scope has expanded from "PDF extraction → DoclingDocument → Markdown"
to a three-layer architecture:

```
Layer 1: Extraction    (existing, mostly implemented)
Layer 2: Structural    (DoclingDocument — existing, canonical repr)
Layer 3: Semantic      (CrossReferenceGraph — new, sidecar)
       → Visualization (interactive graph — new, user deliverable)
```

Key additions to document:

- **Semantic backends**: GROBID (articles), DeepSeek-VL2 (local VLM), regex/heuristic
- **No hardcoded routing**: Bayesian approach applies to semantic backend selection
  the same way it applies to extraction backend selection
- **CrossReferenceGraph**: sidecar schema for cross-references, citations,
  footnotes, semantic entities (theorem/definition/proof)
- **Ground truth**: LaTeXML pipeline for generating GT from .tex sources
- **Visualization**: Interactive cross-reference graph as user-facing deliverable
- **GROBID**: established project for scholarly reference resolution (TEI XML)
- **DoclingDocument confirmed**: remains canonical structural representation;
  semantic layer is additive, not a replacement

## 3. Files to update

### 3.1 project.md

Current state describes:
- Backends (extraction only)
- Runner contract
- Consensus stage
- Semantic linking (partially described)
- Docling export

Updates needed:
- [ ] Add Layer 3 (semantic) to architecture description
- [ ] Document CrossReferenceGraph as sidecar schema
- [ ] Add semantic backends section (GROBID, DeepSeek-VL2, regex)
- [ ] Clarify that `refers_to`, `caption_of`, `footnote_of` relations
      (already mentioned) are now formalized in CrossReferenceGraph
- [ ] Add semantic profiler signals (`reference_density`, `has_bibliography`, etc.)
- [ ] Document Bayesian routing for semantic backends (same principle as extraction)
- [ ] Add visualization as deliverable (not just internal tooling)
- [ ] Add LaTeXML GT pipeline to validation strategy section

### 3.2 ROADMAP.md

Current state likely describes:
- Backend gallery
- Deterministic extraction
- Consensus/comparison
- Docling export

Updates needed:
- [ ] Add semantic layer milestone after extraction stabilization
- [ ] Add GROBID integration milestone
- [ ] Add VLM semantic backend milestone
- [ ] Add GT pipeline milestone (LaTeXML)
- [ ] Add visualization/web deliverable milestone
- [ ] Reorder milestones to reflect dependency chain:
      extraction → structural → semantic → evaluation → visualization
- [ ] Mark completed milestones (profiler, router, CLI orchestration)

### 3.3 README.md

Updates needed:
- [ ] Expand project description beyond "PDF to Markdown"
- [ ] Mention three-layer architecture
- [ ] Add semantic cross-reference extraction to feature list
- [ ] Add GROBID and DeepSeek-VL2 to technology stack
- [ ] Add visualization deliverable to roadmap section
- [ ] Update architecture diagram if present

### 3.4 Configuration docs (if applicable)

- [ ] Document `pdf2md.semantic.toml` or equivalent config for semantic backends
- [ ] Document GROBID Docker setup in backend docs
- [ ] Document DeepSeek-VL2 conda env in backend docs

## 4. Principles for the rewrite

- **Don't rewrite history**: existing architecture descriptions stay, new sections
  are added. The extraction layer is not "replaced" — it's the foundation.
- **Forward-looking but honest**: describe the semantic layer as planned, not
  as if it's implemented. Use future tense or "planned" markers.
- **Consistent terminology**:
  - "extraction backend" = OCR/layout engine (MinerU, PaddleOCR, Docling)
  - "semantic backend" = cross-reference resolver (GROBID, DeepSeek-VL2, regex)
  - "structural layer" = DoclingDocument
  - "semantic layer" = CrossReferenceGraph (sidecar)
  - "visualization" = user-facing graph deliverable
- **No scope creep in docs**: only document what's in Plans 004-007.
  Don't add aspirational features beyond the four plans.

## 5. Acceptance criteria

- [ ] project.md reflects three-layer architecture with semantic backends
- [ ] ROADMAP.md has updated milestones covering Plans 004-007
- [ ] README.md describes expanded scope accurately
- [ ] Terminology is consistent across all documents
- [ ] Existing content preserved — additions, not rewrites
- [ ] All new planned work marked as "planned" (not "implemented")
- [ ] Cross-references between plans and docs are consistent
