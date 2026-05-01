# Next plan: page-level extraction IR and consensus-ready architecture

## 1) Scope and constraints for this step
This plan is intentionally limited to planning and schema direction only.

In this step, we should **not**:
- implement MinerU, Marker, Docling, or other backend-specific adapters beyond what already exists
- implement full consensus algorithms
- add heavy dependencies
- replace or break the current backend runner

This step **must**:
- keep the current `Document -> Page -> Block` path compatible
- provide a clear migration path from current minimal schema to staged consensus architecture
- make comparison-before-semantic-compilation explicit
- make Docling a post-consensus representation/export target, not first comparison IR

## 2) Architecture principle
Comparison must happen at the earliest practical extraction stage, page by page, before whole-document semantic compilation.

Target flow:

```text
PDF
  -> backend raw outputs
  -> PageExtractionIR (page-local primitive blocks)
  -> page-level comparison and candidate matching
  -> PageConsensusIR (agreed/conflicted page blocks)
  -> semantic document compilation (whole document)
  -> rich exports (Markdown / JSON / DoclingDocument / Pandoc AST)
```

## 3) Stage 1: raw backend output preservation
Plan requirements:
- each backend run writes native outputs under `.tmp/<run-name>/raw/<backend>/`
- raw backend files are preserved (not overwritten by normalization artifacts)
- normalized and derived artifacts should be stored separately from raw files

Purpose:
- debugging backend behavior
- adapter development and replay
- provenance tracking for later consensus analysis

## 4) Stage 2: PageExtractionIR (low-level canonical extraction model)
Add or plan a low-level, page-based canonical IR used **before** semantic compilation.

Suggested concepts:
- `ExtractionDocument`
- `ExtractionPage`
- `ExtractionBlock`
- `ExtractionSpan` (optional) or optional child blocks
- `ExtractionTableRegion`
- `ExtractionImageRegion`
- `ExtractionFormulaRegion`
- `BackendRef` (or extension of `SourceRef`)

Required `ExtractionBlock` fields:
- `id`
- `backend`
- `page_number`
- `kind`
- `bbox`
- `order`
- `text`
- `children` or `spans` (optional)
- `confidence` (optional)
- `raw_ref` or `raw_path` (optional)
- `metadata` / `properties` dictionary

Design intent:
- represent primitive extraction evidence only
- preserve backend provenance at block level
- avoid early semantic commitments (e.g., section tree inference)

## 5) Stage 3: page comparison and candidate matching
Plan a page-local matching layer operating strictly on same-page objects.

Initial matching signals:
- bbox IoU and/or geometric distance
- text similarity
- compatible block kind
- reading-order proximity
- backend confidence

Output (for this stage) should be:
- candidate groups
- tentative agreed page blocks
- unresolved candidate sets

Output should **not** yet be a final semantic document.

## 6) Stage 4: PageConsensusIR
Add or plan a page-level consensus representation that preserves all candidates and provenance.

Suggested concepts:
- `BlockCandidate`
- `CandidateGroup`
- `AgreedBlock`
- `Conflict`
- `AgreementScore`

Requirements:
- each agreed block keeps links to all contributing backend candidates
- selected candidate (if any) is explicit
- agreement score and conflict details are explicit
- provenance from all participating backends is preserved

## 7) Stage 5: semantic document compilation (post-consensus)
After page consensus, compile agreed page blocks into a whole-document semantic structure.

This stage may infer:
- sections
- headings
- paragraphs
- lists
- tables
- figures
- captions
- formulas
- headers/footers/page numbers

Modeling requirement:
- support tree structure via parent/children
- support graph structure via explicit edges

Example relation types:
- `contains`
- `follows`
- `caption_of`
- `refers_to`
- `footnote_of`
- `table_continues`
- `same_as_candidate`
- `conflicts_with`

## 8) Stage 6: rich export layer
The post-consensus semantic document should be exportable to:
- Markdown
- JSON
- DoclingDocument
- Pandoc AST

Docling position in architecture:
- useful as rich representation/export target **after agreement**
- not the low-level comparison format
- not the first IR for multi-backend matching

## 9) Compatibility and migration notes
- keep current backend runner and orchestration intact
- keep existing `Document/Page/Block` compatibility while introducing new IR layers
- treat current minimal schema as stable output for current tests until migration steps are explicitly implemented
- introduce new IR and consensus artifacts in parallel before any hard cutover

## 10) Deliverables for the next implementation task (still bounded)
The next implementation task should focus on lightweight scaffolding only:
- define PageExtractionIR and PageConsensusIR data models
- define artifact path conventions for raw and derived outputs
- add serialization tests for the new planning-level models
- add documentation describing staged flow and model boundaries

It should still avoid:
- full consensus heuristics
- backend-specific deep integrations
- heavy third-party dependencies

## 11) Acceptance criteria for this planning update
- README/project description clearly reflects staged architecture and differentiator
- plan explicitly separates:
  - page extraction IR
  - page-level comparison
  - page consensus
  - semantic compilation
  - rich export
- plan clearly states comparison occurs before DoclingDocument export
- plan clearly states Docling is post-consensus, not first comparison layer
- plan avoids implementing full consensus in this step
- plan avoids adding heavy dependencies in this step
- plan keeps current backend runner intact
- plan keeps current `Document/Page/Block` compatibility unless migration is explicitly described
