# Current Status

The repository has progressed beyond a “future consensus” placeholder: it now has implemented consensus grouping, semantic linking, media materialisation, and semantic document assembly. However, the current `semantic_document.json` path is still primarily a **group-to-block projection with metadata attachment**, not full canonical fusion. This is sufficient to start a **Docling inspection adapter** now, but not to claim final canonical reconstruction quality.

## Pipeline status

Current implemented path (observed in code and tests):

- Backend IRs are generated per backend (DeepSeek/PaddleOCR/MinerU) under backend-local `.current/extraction_ir/...` trees.
- `consensus_report.py` normalises backend blocks, groups likely equivalents, computes agreement/conflicts, and emits page-level candidate groups and conflict records.
- `semantic_linker.py` derives anchors/references/attachments for equations, figures, tables, and footnotes, including unresolved references.
- `media_materializer.py` crops canonical figure media from PDF based on semantic anchors and geometry policy.
- `semantic_document_builder.py` assembles `semantic_document.json` by emitting blocks from candidate groups and enriching them with anchors/media/relations/conflicts.

What is still scaffold/diagnostic-level:

- Canonical semantic fusion (e.g., combining formula text+geometry from different sources into one decision object with explicit selected source rationale) is incomplete.
- Caption reconstruction is relation-first (`caption_of`) rather than a single canonical caption object.
- Footnote marker-to-body linkage is partial.
- Semantic validation is largely structural/hash-based and does not yet detect several content-level quality hazards.

## Repository audit

### `src/pdf2md/utils/consensus_report.py`

- Establishes canonical backend naming/aliases and config defaults for text and geometry thresholds.
- Loads backend manifests/pages with malformed/missing JSON warnings.
- Normalises backend blocks into a shared evidence shape with kind mapping, compile roles, text/bbox/comparison hashes, and provenance pointers.
- Builds candidate groups by similarity/IoU and computes agreement/conflict heuristics.

### `src/pdf2md/utils/semantic_linker.py`

- Detects equation labels (`\tag{}`, `(1.2)`, `Eq. 1.2`), figure/table labels, section references, bibliography spans, and footnote marker syntax.
- Creates equation/figure/table/footnote anchors with source-group conflict context and selection metadata.
- Adds attachments (`caption_to_figure`, `equation_number_to_equation`) and resolves references where possible.
- Preserves unresolved references explicitly.

### `src/pdf2md/utils/media_materializer.py`

- Enforces policy defaults oriented to conservative canonical media generation.
- Materialises primarily anchored figure targets; orphan images are optional and disabled by default.
- Uses geometry-status gating (`near`, `single_source`, `conflict`, missing) plus strict/non-strict exit behavior.

### `src/pdf2md/utils/semantic_document_builder.py`

- Converts candidate groups to output blocks with status/mode/warnings and provenance.
- Attaches media by `source_group_id`, anchors by `target_group_id`, and emits relations from attachments and resolved references.
- Includes stale-upstream hash checks.
- Does not yet perform deep canonical fusion across multiple groups representing one semantic object.

### `src/pdf2md/models/semantic_document.py`

- Provides a minimal schema skeleton with structural validation buckets.
- Buckets are present but semantic rule coverage is not enforced here.

### Tests inspected

- `tests/test_semantic_linker.py`: strong coverage for equation relabeling, anchor dedupe, conflict propagation, figure target scoring, and reference uniqueness.
- `tests/test_media_materializer.py`: verifies default orphan-image suppression, geometry policy behavior, table visual fallback, strict mode on missing PDF.
- `tests/test_semantic_document_builder.py`: verifies media metadata attachment, relation generation, evidence/page-artifact bucketing, hash mismatch warnings.

### Backend wrapper/IR context

- DeepSeek and PaddleOCR have explicit `pdf2ir_*` adapters that generate page-first IR, raw captures, and media snapshots.
- MinerU wrapper exists and MinerU IR artefacts are present under backend-local `.current/extraction_ir/...`.
- Generated artefacts are present under backend-local `.current/extraction_ir/Ashcroft_Mermin_sub/...`; no root `.current/consensus` was found in this checkout.

## Current strengths

- Multi-backend comparison infrastructure exists (candidate grouping, agreement signals, conflict recording).
- Provenance is preserved through evidence IDs, source backends, source group members, and conflict linkage.
- Semantic linker preserves unresolved references instead of dropping them.
- Figure media extraction policy is conservative by default (`materialize_orphan_images=False`) and tested.
- Semantic document keeps conflicts/warnings and emits cross-object relations (caption-of, refers-to, equation-number attachments).

## Current weaknesses

- Canonical semantic reconstruction remains shallow: one block per candidate group, not per fused semantic object.
- Formula fusion is not explicit across text-strong vs geometry-strong groups.
- Caption canonicalisation is incomplete; label text and descriptive text can remain fragmented across blocks.
- Footnote body detection exists, but marker-to-body resolution is weak.
- Validation misses higher-level semantic hazards (duplicate formula bodies, fragmented captions, geometry/text duplication patterns, debug media leakage).
- `description.md` still frames consensus/normalisation as future work and lags current implementation reality.

## Verification of known concerns

| Concern | Verified / Refuted / Partly verified | Evidence | Recommended action |
|---|---|---|---|
| A. Orphan media disabled by default, but debug media manifest might leak into semantic output | **Verified** | `media_materializer` defaults `materialize_orphan_images=False`; builder attaches any media asset by `source_group_id` without checking policy/source mode, so debug manifests can be ingested as canonical output. | In builder, reject or flag assets with `media_type=image` and no anchor in canonical mode; add `mode=canonical/debug` gate and strict failure option. |
| B. Builder emits candidate-group blocks, not true canonical fusion | **Verified** | Builder iterates `candidate_groups` and emits block per group; enrichment is attachment-based. No object-level merge stage exists. | Add canonical fusion stage before block emission (entity graph -> canonical objects -> blocks). |
| C. Formula canonicalisation incomplete (text+geometry split) | **Partly verified** | Linker can relabel equation anchor using nearby equation-number group, but builder still outputs separate blocks if split persists across groups. No guaranteed single fused formula block with explicit chosen text/geometry sources. | Add formula merge rule keyed by equation anchor label/attachments and bbox proximity, with `selected_text_source` and `selected_geometry_source`. |
| D. Caption reconstruction incomplete | **Verified** | Current approach creates anchors and `caption_of` relations but does not produce a canonical caption object synthesising label + caption body across fragments. | Add caption fusion pass and dedicated caption schema fields (`label`, `caption_text`, `full_caption`). |
| E. Footnote marker-to-body resolution weak | **Partly verified** | Footnote body anchors are detected (bottom-of-page regex), marker refs extracted, but robust marker-body linking logic is limited and heuristic. | Introduce per-page footnote index resolution with geometry/order constraints and ambiguity warnings. |
| F. Validation mostly structural, misses semantic quality problems | **Verified** | Validation tracks duplicates/missing targets/unresolved refs/hash warnings; no checks for unanchored body figure/image, duplicate formula bodies, caption fragmentation, no-bbox duplicates, fallback without explicit warning, or debug-media leakage. | Implement semantic validators + strict mode toggles + warning taxonomy. |
| G. Documentation may lag implementation | **Verified** | `description.md` describes adapters/consensus as future milestones though significant implementations now exist in utils/tests. | Update architecture doc to separate “implemented now” vs “planned next” with exact artefact flow. |

## Priority TO-DO

- Create an **experimental Docling inspection adapter** that consumes `semantic_document.json` and outputs inspection artefacts only (not authoritative conversion).
- Ensure debug/orphan media cannot leak into canonical semantic output (canonical/debug mode separation, builder-side policy checks).
- Add stronger semantic validation inside `semantic_document_builder.py` (or validator module) for the listed hazard classes.
- Document canonical mode vs debug mode explicitly in code/config/docs.
- Add regression tests for Figure 1.2 media path (anchored figure vs orphan/debug assets) if current tests are not sufficient for builder ingestion cases.
- Add tests for duplicate-formula and caption-fragmentation cases.

## Recommended TO-DO

- Implement formula text/geometry fusion with explicit source selection fields.
- Implement caption reconstruction into one semantic caption object.
- Improve footnote marker-to-body linking.
- Define and enforce table structure policy (when table-as-visual fallback is acceptable).
- Add explicit backend policy by object type (e.g., figure geometry vs formula text precedence).
- Improve warnings taxonomy and strict mode behavior.
- Update architecture documentation to match current pipeline reality.

## Additional TO-DO

- Improve CLI documentation for consensus -> links -> media -> semantic build chain.
- Add run artefact cleanup/retention instructions.
- Provide schema examples for `semantic_document.json` canonical/debug variants.
- Add developer notes for backend IR expectations and required fields.
- Prefer small synthetic fixtures in tests over heavy OCR dependencies.
- Naming consistency / typo cleanup (e.g., deepseek script naming inconsistencies).

## Docling phase recommendation

Start the Docling adapter **now**, but only as an **experimental inspection adapter**.

Recommended scope now:

- consume `semantic_document.json`
- render diagnostics and visual/structural inspection outputs
- surface conflicts, unresolved references, selection modes, and warning counts prominently
- avoid “final quality” claims

Must not pretend to solve yet:

- canonical fusion of formulas/captions/footnotes
- full deduplication across backend-specific duplicates
- semantic validation completeness

Warnings the adapter should emit by default:

- unresolved references present
- blocks with `selection_mode` fallback/single-source
- media blocks with non-resolved geometry status
- potential duplicate semantic entities (formula/caption heuristics)
- evidence/debug contamination risk when media policy/source is non-canonical

## Commands run

- `pwd`
- `rg --files -g 'AGENTS.md'`
- `sed -n '1,260p' src/pdf2md/utils/consensus_report.py`
- `sed -n '1,260p' src/pdf2md/utils/semantic_linker.py`
- `sed -n '1,260p' src/pdf2md/utils/media_materializer.py`
- `sed -n '1,320p' src/pdf2md/utils/semantic_document_builder.py`
- `sed -n '1,320p' src/pdf2md/models/semantic_document.py`
- `sed -n '1,260p' tests/test_semantic_linker.py`
- `sed -n '1,260p' tests/test_media_materializer.py`
- `sed -n '1,280p' tests/test_semantic_document_builder.py`
- `sed -n '1,260p' description.md`
- `rg --files backend/deepseek backend/mineru backend/paddleocr | head -n 40`
- `sed -n '1,260p' backend/mineru/pdf2md_mineru.py`
- `sed -n '1,260p' backend/paddleocr/pdf2ir_paddleocr.py`
- `sed -n '1,260p' backend/deepseek/pdf2ir_deeepseek.py`
- `rg --files .current/consensus backend/mineru/.current/extraction_ir backend/paddleocr/.current/extraction_ir backend/deepseek/.current/extraction_ir 2>/dev/null | head -n 60`
- `rg --files .current/consensus | head -n 40`
- `rg --files .current -g 'semantic_document.json' -g 'semantic_links.json' -g 'media_manifest.json' | head -n 40`
- `python -m pytest tests/test_semantic_linker.py tests/test_media_materializer.py tests/test_semantic_document_builder.py` (failed due to missing `PYTHONPATH=src`)
- `PYTHONPATH=src python -m pytest tests/test_semantic_linker.py tests/test_media_materializer.py tests/test_semantic_document_builder.py` (passed)
