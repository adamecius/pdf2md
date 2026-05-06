Feedback mode: Close the previous current plan and make it status exectured. Write the new current plan:

# Current plan - after-consensus Page IR to DoclingDocument

## Goal

The previous milestone demonstrated that a DoclingDocument can be built from the LaTeX ground-truth source. The next milestone is to demonstrate that the **Page IR after consensus** contains enough information to:

1. recover semantic links;
2. preserve document reading order;
3. populate a DoclingDocument in the same architectural direction as the ground-truth Docling output;
4. warn clearly when a Docling field cannot be filled from the post-consensus object;
5. prove the after-consensus pipeline contract with at least 10 mock after-consensus IR fixtures and unit tests.

This task is about architecture and contract validation. The final DoclingDocument does not need to be fully populated, but every missing or degraded fill must be visible in a report or warning. No value should be invented to satisfy a schema.

## Current repository review

The current repository already has pieces that should be used as the starting point rather than bypassed with new isolated scripts:

- `src/pdf2md/utils/semantic_linker.py` builds semantic anchors, references and attachments from a consensus report.
- `src/pdf2md/utils/semantic_document_builder.py` turns a consensus report plus semantic links and optional media manifest into `pdf2md.semantic_document`.
- `src/pdf2md/utils/docling_adapter.py` adapts a semantic document into Docling JSON plus Docling relation/report JSON.
- `src/pdf2md/pipeline/convert.py` is still a placeholder for orchestration and can host the after-consensus pipeline entry point.
- `tests/` already contains tests for semantic linking, mock backend schema, ground-truth regressions and pipeline contracts.

The next implementation must bring the after-consensus to Docling path into the main package. It must not create another one-off root-level converter unless it is only a thin manual debugging wrapper around production code.

## Architectural decision

Add a small production layer for **after-consensus IR to Docling** and keep responsibilities separated:

```text
after-consensus Page IR
  |
  |  1. normalise input contract
  v
canonical post-consensus semantic document
  |
  |  2. derive anchors, references, relations and reading order
  v
semantic link graph
  |
  |  3. emit DoclingDocument and sidecar reports
  v
Docling JSON + relation report + fill-warning report
```

The converter must consume the consensus object as the source of truth. It may derive missing semantic information by post-processing the consensus object, but it must not demand duplicated fields upstream if those fields can be computed from existing consensus fields.

## Responsibility boundaries

### 1. Consensus IR contract normalisation

Location: `src/pdf2md/docling/consensus.py` or, if this is judged too much package growth, one module named `src/pdf2md/utils/consensus_docling.py`.

Responsibilities:

- Accept an after-consensus IR shaped like `pdf2md.semantic_document` or the current consensus report plus derived links.
- Validate the minimum fields needed for Docling construction.
- Produce a canonical internal list of blocks sorted by deterministic reading order.
- Detect repeated blocks, repeated source information and repeated semantic content.
- Preserve provenance, agreement and conflict metadata.
- Produce warnings, not failures, for missing optional fields.

It must not:

- call OCR backends;
- read PDFs;
- infer content that is not present in the consensus object;
- modify ground-truth fixture sources.

### 2. Semantic linking

Responsibilities:

- Link captions to figures and tables.
- Link equation numbers to formulas.
- Link paragraph references to anchors where enough information exists.
- Link footnote markers to footnote bodies.
- Keep unresolved references in a sidecar report.
- Use the existing `semantic_linker.py` behaviour where possible instead of duplicating it.

This layer must be able to work from text, kind/type, page index, block order, bbox and existing relations. Explicit anchor fields may be used when present, but the upstream consensus phase should not be forced to duplicate labels that can be parsed from text.

### 3. Docling emission

Responsibilities:

- Build a DoclingDocument when docling-core is available.
- Fall back to a deterministic Docling-shaped dictionary only where tests must not depend on optional Docling runtime APIs.
- Preserve body order in texts, tables, pictures and relation sidecars.
- Attach warnings for empty fills, missing media, table degradation and unresolved links.
- Reuse the existing `docling_adapter.py` where it is sufficient; extend or wrap it where the existing adapter degrades too much information.

The implementation must not silently drop semantic information. Anything that cannot be represented in Docling must be retained in the relation or warning report.

### 4. Pipeline integration

Location: `src/pdf2md/pipeline/convert.py` or a nearby module under `src/pdf2md/pipeline/`.

Add an explicit entry point such as:

```python
build_docling_from_after_consensus_ir(after_consensus_ir, *, strict=False)
```

or:

```python
convert_after_consensus_ir_to_docling(after_consensus_ir, *, strict=False)
```

The return value must be a structured result containing:

- `docling_document`: Docling export dictionary;
- `relations`: relation/anchor/reference sidecar;
- `report`: validation and fill-warning report.

This proves that the pipeline after consensus is valid without requiring OCR or TeX tooling in the unit tests.

## Required output artefacts

The implementation must create or update the following files only unless tests require a small import adjustment elsewhere under `src/`:

- `src/pdf2md/docling/__init__.py` if a new package is used;
- `src/pdf2md/docling/consensus.py` or a single equivalent module under `src/pdf2md/utils/`;
- `src/pdf2md/pipeline/convert.py` or one narrow pipeline integration module;
- `tests/test_consensus_docling.py`;
- `consensus.docling.checklist.md`;
- `current_plan.md`.

Avoid file proliferation. The preferred design is one production converter module plus one existing pipeline integration point.

## Minimum after-consensus fields

The implementation must prove that these fields are enough to generate a useful Docling output:

- document identity: `run_id`, `source_pdf` or equivalent document name;
- pages: `page_index`, `page_number` if available;
- blocks or candidate groups: stable id, kind/type, representative text, optional bbox, optional order;
- provenance: sources, source members and agreement/conflict metadata when available;
- geometry: bbox when available; missing bbox must degrade with a warning;
- media: media id or path when available; missing media for figures must degrade with a warning;
- relations, anchors and references if already derived, but not required as duplicated upstream fields if derivable from the consensus object.

Anything else belongs in post-processing unless a test proves it cannot be reconstructed from the consensus object.

## Reading order requirements

The output order must be deterministic and stable:

- sort by `page_index`;
- prefer explicit `order` or `reading_order` if present;
- otherwise sort by bbox top coordinate, then left coordinate;
- keep source order as the final stable tiebreaker;
- warn with `order_fallback_geometry:<page_index>` when geometry was needed;
- warn with `order_ambiguous:<page_index>` when neither explicit order nor useful geometry is available.

This is the minimum needed for the after-consensus structure to be comparable in quality to the order recoverable from tagged PDF plus XML witnesses.

## Warning contract

Warnings must be machine-readable strings. Required warning families:

- `empty_fill:<docling_ref>:<field>`
- `missing_text:<block_id>`
- `missing_bbox:<block_id>`
- `missing_page:<block_id>`
- `order_fallback_geometry:<page_index>`
- `order_ambiguous:<page_index>`
- `duplicate_content_suppressed:<block_id>`
- `duplicate_block_id:<block_id>`
- `unresolved_reference:<reference_id>`
- `figure_without_media:<block_id>`
- `table_structure_degraded:<block_id>`
- `formula_text_geometry_not_fused:<block_id>`
- `caption_without_target:<block_id>`

Tests may add narrower warnings, but these families must stay stable.

## Ten required mock after-consensus IR fixtures

Create at least 10 mock after-consensus IR objects inside `tests/test_consensus_docling.py` or a small test helper in the same file. Do not create large JSON fixture files unless readability becomes impossible.

Required cases:

1. `simple_title_paragraph`: title, section header and paragraph with clean order.
2. `geometry_order_fallback`: blocks with no explicit order, sorted by bbox.
3. `multipage_order`: body blocks across at least two pages with headers and footers excluded or marked as artefacts.
4. `equation_reference`: formula, equation number and paragraph reference resolved to the same anchor.
5. `figure_caption_missing_media`: caption links to figure, but missing media produces a warning while preserving semantic relation.
6. `table_degraded_text_only`: table block has text but no cell grid, so Docling output degrades and warns.
7. `footnote_marker_body`: paragraph marker links to footnote body.
8. `list_items_nested_or_grouped`: list items preserve grouping and order.
9. `duplicates_and_conflicts`: duplicated candidate or repeated content is suppressed once and reported; conflict metadata is preserved.
10. `empty_and_missing_fields`: missing text, missing bbox, missing page or empty media fields produce warnings without raising.

Additional cases are welcome only if they clarify behaviour. Avoid expanding the fixture surface without a reason.

## Unit test requirements

Create `tests/test_consensus_docling.py`.

The tests must verify:

- all 10 mock after-consensus IR cases pass through the after-consensus to Docling pipeline without uncaught exceptions;
- the output has deterministic text order;
- captions, figures, tables, equations and footnotes are linked through sidecar relations or anchors;
- duplicate content is not repeated in the Docling output;
- missing optional Docling fills are reported with warnings;
- unresolved references stay visible in the report;
- the converter can run without TeX tooling, OCR engines or real PDF files;
- the pipeline entry point under `src/pdf2md/pipeline/` is exercised, not only the lower-level adapter;
- if docling-core is installed, the emitted Docling dictionary validates with the DoclingDocument schema;
- if docling-core is not installed, the fallback dictionary remains deterministic and tests still validate the project contract.

## Checklist file to create

Create `consensus.docling.checklist.md`.

Purpose:

- define the fields the consensus phase must retain so that Docling generation is possible;
- keep the checklist almost empty of new demands;
- make reviewers explicitly decide whether any proposed field is truly needed upstream or can be post-processed from the consensus object;
- prevent duplicated fields and duplicated semantic information.

The checklist must include a reviewer rule:

> A field may be added to the consensus contract only if it cannot be derived by querying the consensus object, semantic linker output, media manifest or deterministic post-processing.

The checklist should classify fields as:

- required in consensus object;
- optional but useful;
- must be post-processed, not demanded upstream;
- forbidden duplicate.

Expected direction: most semantic labels, references, section hierarchy and captions should be post-processed, not demanded as duplicate consensus fields.

## Tests to run

### A1 - targeted unit tests

```bash
PYTHONPATH=src python -m pytest tests/test_consensus_docling.py -v
```

Pass condition: all 10 mock after-consensus IR cases pass.

### A2 - existing semantic tests

```bash
PYTHONPATH=src python -m pytest tests/test_semantic_linker.py tests/test_mock_backend_schema.py -v
```

Pass condition: existing semantic linking and mock schema tests still pass.

### A3 - full unit suite

```bash
PYTHONPATH=src python -m pytest -q
```

Pass condition: all tests pass, or any unrelated pre-existing failures are documented precisely.

### A4 - syntax compilation

```bash
python -m compileall src tests/test_consensus_docling.py
```

Pass condition: no syntax errors.

## Acceptance criteria

The task is complete only when:

- production code lives under `src/`, not as an isolated script;
- an after-consensus IR can be converted to Docling JSON through a pipeline-level function;
- at least 10 mock after-consensus IR edge cases are tested;
- semantic links are preserved or reported as unresolved;
- reading order is deterministic and tested;
- empty or unavailable Docling fills produce warnings;
- duplicated information is not required from the consensus phase;
- `consensus.docling.checklist.md` exists and is strict about avoiding duplicated fields;
- all targeted tests pass.

## Status

T1 - design production converter module: pending
T2 - add pipeline entry point: pending
T3 - add 10 mock after-consensus IR tests: pending
T4 - add consensus.docling.checklist.md: pending
T5 - run targeted and full tests: pending
