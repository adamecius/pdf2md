# Plan 004_0: Project Documentation Alignment

## Status: active
## Date: 2026-05-24
## Depends on: Plans 001-003 (existing architecture stable)

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

Branch name:
plan-004-0-project-documentation-alignment

Source plan:
plans/004_0-project-documentation-alignment.md

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

- [x] project.md reflects three-layer architecture with semantic backends
- [x] ROADMAP.md has updated milestones covering Plans 004-007
- [x] README.md describes expanded scope accurately
- [x] Terminology is consistent across all documents
- [x] Existing content preserved — additions, not rewrites
- [x] All new planned work marked as "planned" (not "implemented")
- [x] Cross-references between plans and docs are consistent

---

## File whitelist

```text
project.md
ROADMAP.md
README.md
current_plan.md
run_log.md
```

## Forbidden files

```text
plans/004_0-project-documentation-alignment.md  (source, do not modify)
plans/005_0-semantic-backends-installation-smoke-tests.md
plans/006_0-semantic-layer-integration-labels.md
plans/007_0-groundtruth-evaluation-example.md
plans/008_0-visualization-web-integration.md
src/**/*.py
tests/**/*
backend/**/*
tools/**/*
docs/**/*  (out of scope for 004_0; deferred to a later docs-pass)
```

---

## PR_reviews

### PR_review #0 — plan-only pre-execution review

Verdict: pass (with notes)

Reviewer: agent (informal pre-execution review, no PR yet)
Date: 2026-05-24
Scope: review the plan content itself before any edits to project.md / ROADMAP.md / README.md.

Strengths:
- Goal is precise and bounded: documentation only, no code, no scope creep beyond Plans 004-008.
- Distinguishes terminology cleanly: extraction backend vs semantic backend, structural vs semantic layer.
- "Additions, not rewrites" rule protects existing content (the consensus + LinkedStructure + Docling export chain is already documented and stays).
- Acceptance criteria are checkable from the diff alone (no runtime tests needed for a docs plan).

Gaps to address during feedback-mode execution:

1. **Conflict with project.md §3.** project.md currently asserts:
   > "There is no PDF-type classifier or input-routing stage. Every document goes through the same visual-OCR backend ensemble; the consensus stage picks the most reliable feature extraction per BlockKind / EntityType, not the input-classification stage."

   Plan 006 introduces a profiler + router for *semantic* backend selection. These are not contradictory (profiler/router applies to semantic-layer routing, not extraction-layer routing), but the prose has to disambiguate explicitly. Recommended wording: "Extraction routing remains backend-ensemble + consensus, not classifier-based. Semantic routing (Plan 006) uses profiler signals to pick which semantic backend(s) to run, but every extraction backend still runs."

2. **CrossReferenceGraph already partly named in project.md §8 "LinkedStructure".** The LinkedStructure section already lists `caption belongs to figure or table`, `footnote marker links to footnote body`, `reference mention links to bibliography item`. The plan must reconcile: LinkedStructure (Phase 4, existing) is a *structural* layer derived from consensus; CrossReferenceGraph (Plan 006, new) is a *sidecar* on top of DoclingDocument that adds RefMarker / RefEdge / SemanticEntity for non-structural cross-references (theorem labels, citation markers, footnote anchors). Treat them as complementary, not overlapping.

3. **DoclingDocument vs Docling JSON terminology.** Plan 006 uses the noun "DoclingDocument" (the docling_core python class); the existing docs use "Docling JSON" (the on-disk JSON). Both refer to the same canonical export. Pick one consistent term per doc to avoid confusing readers.

4. **README §15 "Status" and §11 "Local acceptance programme" hard-code Plans 8-16 as the MVP path.** README currently treats Plan 16 as the MVP boundary. Plan 004_0 adds 005-008 *after* the existing MVP path. The README must clarify ordering: Plans 8-16 deliver MVP extraction + structural; Plans 005-008 deliver the semantic + visualization layer on top, post-MVP.

5. **ROADMAP.md phase structure.** The existing 8-phase structure (0-7) already covers semantic reconstruction in Phase 4 and evaluation in Phase 5. Plan 004_0's bullet "Reorder milestones to reflect dependency chain" should NOT renumber phases — add the new Plans 005-008 under existing phases (semantic → Phase 4 + new sub-phase; visualization → Phase 6/7 extension). The plan's "reorder" wording is slightly misleading; what's actually needed is *insertion*, not reordering.

6. **No semantic backend conda env / config docs exist yet.** Plan 004_0 §3.4 lists docs to write for `pdf2md.semantic.toml`, GROBID Docker, and DeepSeek-VL2 conda env, but those backends don't exist in the repo yet (Plan 005 installs them). The feedback-mode pass should mark §3.4 items as "deferred to Plan 005 README work" — do not invent config files or env recipes during the documentation alignment pass.

7. **Plan 004_0 itself doesn't follow PLAN_TEMPLATE.md.** No whitelist, no automated test commands, no human verification checkpoints, no Status header in the template format. This is acceptable for a docs-only plan that has no executable test surface, but the promoted current_plan.md adds a whitelist + forbidden-files block to keep the protocol intact.

Tasks promoted to done: none (execution still pending).

Notes:
- Acceptance criterion "All new planned work marked as 'planned'" is non-trivial: the existing README/project.md uses present tense throughout. New additions must use future tense or explicit "Planned" prefixes.
- Configuration docs (§3.4) are out of scope for this pass per gap #6.
- docs/ updates are out of scope here (whitelist excludes docs/**) — semantic-backend operator docs belong to Plan 005's README work.

## Feedback

### Feedback #0 — execution against PR_review #0

Mode: feedback (per user instruction; user-authorised override of the
agent.md feedback-mode "no source-file edits" rule for this docs-only
plan).
Date: 2026-05-24
Branch: plan-004-0-project-documentation-alignment

Changes applied to project.md:
- §3 (Architecture): clarified that "no PDF-type classifier" applies to
  the *extraction* layer only; the *semantic* layer (planned, Plan 006)
  does use a profiler/router. This addresses PR_review #0 gap #1.
- §4 (Ground truth): added a planned LaTeXML pipeline note pointing to
  §10 and Plan 007.
- New §10 (Planned: semantic cross-reference layer and visualization):
  three-layer architecture diagram; planned semantic backends (GROBID,
  DeepSeek-VL2, regex); semantic routing via profiler signals;
  CrossReferenceGraph schema sketch; visualization deliverable; semantic
  evaluation; sequencing relative to Plans 8-16. Addresses gaps #2-#4.

Changes applied to ROADMAP.md:
- Header: added three-layer architecture paragraph mentioning Plans 004-008.
- Roadmap overview table: inserted planned phases 4b, 5b, 7b at 0% with
  post-MVP target.
- Phase 4: added "Planned extension — Phase 4b: Semantic cross-reference
  layer" with scope and exit criteria (Plans 005-006).
- Phase 5: added "Planned extension — Phase 5b: Semantic ground truth
  and evaluation" (Plan 007).
- Phase 7: added "Planned extension — Phase 7b: Visualization and web
  deliverable" (Plan 008).
- Implementation Plans section: added the Plans 004-008 sequence below
  the existing MVP sequence with the caveat that 004-008 depend on
  Plans 8-16 being stable.
- New "Plans 004-008: Semantic Layer and Visualization" section with
  one subsection per plan (purpose, roadmap phase, type, exit criteria).
- Existing Phase 0-7 numbering preserved; no renumbering. Addresses
  PR_review #0 gap #5.

Changes applied to README.md:
- §1 opener: added the three-layer architecture diagram and explicit
  "additive sidecar, not replacement" note.
- §11 (Local acceptance programme): added the post-MVP semantic +
  visualization path (Plans 004-008) under the existing MVP sequence
  with a clarifying note that 004-008 sit on top of 8-16. Addresses
  gap #4.
- §15 (Status): added "next major milestones" extension covering
  Plans 004-008.

Out-of-scope deferrals (per PR_review #0 gap #6):
- §3.4 of the source plan (`pdf2md.semantic.toml`, GROBID Docker docs,
  DeepSeek-VL2 conda env docs) was intentionally not executed in this
  pass. Those configuration files and operator docs do not exist yet;
  they belong to Plan 005's README work, which installs the semantic
  backends and produces real config surfaces.
- `docs/**` was kept on the forbidden list; semantic-backend operator
  docs are Plan 005 / Plan 006 territory, not this docs-alignment pass.

Terminology consistency check (PR_review #0 gap #3):
- "extraction backend" vs "semantic backend" — used consistently in
  project.md §10, ROADMAP.md Phase 4b, README.md §1.
- "DoclingDocument" vs "Docling JSON" — both forms appear in the
  existing docs; the new sections use "DoclingDocument JSON" when
  referring to the on-disk artefact and "DoclingDocument" when
  referring to the docling_core class. Single-form harmonisation is
  out of scope here and would require touching many existing
  paragraphs; flagged for a future docs-pass.
- "CrossReferenceGraph" (sidecar) and "LinkedStructure" (structural)
  are kept distinct in all three files. CrossReferenceGraph is
  consistently labelled "planned" and "additive".

Acceptance criteria: all 7 items checked off in §5 above.

Next recommended action:
- Human review of the three modified files.
- If accepted, commit on branch plan-004-0-project-documentation-alignment
  and open a draft PR. The PR diff should be documentation-only.
- After human verification, archive Plan 004_0 and promote Plan 005_0
  to current_plan.md.
