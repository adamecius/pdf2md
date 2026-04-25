# AGENTS.md

## Project direction

`doc2md` is an offline, modular document parsing framework.

It is not only a PDF-to-Markdown converter. Markdown is an export format, not the source of truth.

The canonical output is **DocIR JSON**. Every backend must emit, or be adapted into, DocIR. All exporters, chunkers and benchmarks must consume DocIR.

The project is optimised for:

1. robustness across many scientific books and technical PDFs
2. offline execution
3. flexible backend orchestration
4. visual model support on local hardware
5. benchmarkable and reproducible outputs
6. RAG-ready chunk generation
7. graceful degradation when one backend fails

Licence restrictions are not a design blocker for this offline research product. Still, keep heavy dependencies optional so that the core project remains easy to install and test.

## Core principle

The architecture must separate:

```text
input document
 -> profiling and media rendering
 -> routing and backend planning
 -> backend execution
 -> candidate merging
 -> DocIR
 -> exporters
 -> benchmark adapters
```

Do not couple the main pipeline to one model, one benchmark, one output format or one OCR engine.

## Canonical representation

The canonical internal and persisted representation is:

```text
*.docir.json
```

Derived outputs may include:

```text
*.md
*.myst.md
*.html
*.blocks.jsonl
*.benchmark.json
media/
```

The DocIR must preserve:

- document metadata
- pages
- body tree
- furniture tree for headers, footers and page numbers
- text blocks
- tables
- figures
- equations
- captions
- footnotes
- references
- groups and hierarchy
- page provenance
- bounding boxes or polygons
- reading order
- media references
- backend provenance
- confidence
- raw backend output references
- normalised benchmark text
- RAG chunk metadata

## Backend policy

Backends are first-class plugins. Every backend must implement the same conceptual contract:

```python
extract(input_path, options) -> DocumentIR
```

or:

```python
extract_page(page_image, page_context, options) -> PageIR
```

Heavy backends must use lazy imports and clear installation errors.

Recommended backend tiers:

### Tier 0: deterministic baseline

- PyMuPDF text extraction
- PyMuPDF page rendering
- font and text-layer profiling
- page image and crop generation

This backend is mandatory because it is fast, cheap and useful for validation.

### Tier 1: structural framework baseline

- Docling

Use Docling as an architecture reference and optional backend because its document representation, chunking and exporters are close to the desired DocIR direction.

### Tier 2: leading offline all-in-one parsers

- MinerU / MinerU2.5 / MinerU2.5-Pro where feasible
- Marker, for comparison
- olmOCR, for OCR and linearisation comparison

These are useful for book-scale and scientific-document processing.

### Tier 3: strong visual document models

- PaddleOCR-VL-1.5
- GLM-OCR
- dots.ocr
- FireRed-OCR

These should be used for difficult pages, scanned pages, bad encodings, formula-heavy pages, tables, figures and diagrams.

### Tier 4: classical OCR and table tools

- PaddleOCR PP-StructureV3
- Tesseract
- RapidTable or similar table backends

These are useful as cheap baselines and fallback components.

## Router and orchestrator policy

The router must not only choose one of deterministic, hybrid or visual. It must produce a backend plan.

Example plans:

```text
clean born-digital text page
 -> deterministic_pymupdf

born-digital page with tables and formulas
 -> deterministic_pymupdf + visual validation for tables/formulas

bad font encoding
 -> visual backend

image-only scan
 -> visual backend

diagram-heavy mathematical page
 -> deterministic text + page image + visual backend

book chapter page with reliable text
 -> deterministic text + structure normalisation

table-heavy page
 -> visual/table backend + deterministic text cross-check
```

The orchestrator must support:

- multiple candidate backends
- page-level backend selection
- document-level backend selection
- fallback on failure
- backend timeouts
- caching of rendered pages
- caching of backend outputs
- retry policy
- offline local model endpoints
- batch processing for GPUs
- partial results when some pages fail

## Candidate and merger policy

Backends may disagree. Do not overwrite evidence too early.

The pipeline should store candidate results before selecting the final one.

A future `CandidateIR` or equivalent structure should preserve:

- backend name
- backend version
- raw output path
- confidence or heuristic score
- page number
- block candidates
- table candidates
- formula candidates
- figure candidates
- failure information

The merger should select final DocIR blocks using heuristics such as:

- text-layer reliability
- visual backend confidence
- formula quality
- table structural completeness
- reading order consistency
- agreement between backends
- page-level strategy

## Benchmark policy

Default tests must be fast, offline and deterministic.

Do not run full OmniDocBench in the default test suite.

Use tiny local fixtures inspired by OmniDocBench to test:

- category mapping
- polygon to bbox conversion
- reading-order sorting
- ignore flag handling
- text, latex and html preservation
- DocIR serialisation
- Markdown export
- JSONL chunk export
- missing optional dependency errors

Full benchmarks are explicit commands, for example:

```bash
python -m benchmarks.omnidocbench.download
python -m benchmarks.omnidocbench.evaluate --backend deterministic --limit 20
python -m benchmarks.omnidocbench.evaluate --backend mineru --limit 20
python -m benchmarks.omnidocbench.evaluate --backend paddleocr_vl --limit 20
```

## Dependency policy

Core dependencies should remain minimal, but robustness is more important than absolute minimalism.

Allowed core dependencies:

- pymupdf
- pyyaml
- pydantic, if schema validation is implemented with Pydantic

Heavy dependencies must be optional extras or backend-specific installs:

- docling
- mineru
- paddleocr
- transformers
- torch
- vllm
- sglang
- huggingface_hub
- image processing packages beyond core
- benchmark-specific packages

Do not add heavy model packages to `requirements.txt`.

Prefer optional extras later:

```text
.[test]
.[bench]
.[docling]
.[mineru]
.[paddle]
.[visual]
.[all]
```

## Output policy

The CLI should eventually support:

```bash
python -m doc2md input.pdf --backend auto --output out/
python -m doc2md input.pdf --backend deterministic --output out/
python -m doc2md input.pdf --backend docling --output out/
python -m doc2md input.pdf --backend mineru --output out/
python -m doc2md input.pdf --backend paddleocr_vl --output out/
```

Every run should be able to emit:

```text
out/document.docir.json
out/document.md
out/document.blocks.jsonl
out/document.html
out/media/
out/run_manifest.json
```

## Agent roles

### Architecture agent

Preserves the overall modular architecture.

Rules:

- do not make Markdown canonical
- do not hard-code one backend
- do not make heavy dependencies mandatory
- all backends must emit DocIR or be adapted into DocIR
- benchmarks must be explicit commands, not default tests

### DocIR agent

Owns the schema.

Responsibilities:

- define models
- define stable IDs
- define serialisation
- define validation
- define normalisation fields
- preserve provenance and media references

### Backend agent

Owns backend interfaces and adapters.

Responsibilities:

- implement backend registry
- implement deterministic backend
- add optional backend wrappers
- use lazy imports
- keep raw backend output paths
- return DocIR

### Router and orchestrator agent

Owns backend planning.

Responsibilities:

- profile pages
- select backend plans
- support fallback
- support hybrid execution
- support page-level and document-level decisions
- preserve routing reasons

### Visual backend agent

Owns local GPU model integrations.

Responsibilities:

- render pages to images
- batch pages
- call local models or local endpoints
- parse model outputs
- convert outputs to DocIR
- cache model outputs
- handle model failures

### Merger agent

Owns candidate reconciliation.

Responsibilities:

- combine deterministic and visual outputs
- preserve candidate evidence
- select final blocks
- resolve reading order
- link captions and figures
- select table and formula representations

### Export agent

Owns all derived output formats.

Responsibilities:

- Markdown
- MyST Markdown
- HTML debug view
- JSONL chunks
- benchmark prediction formats
- media manifests

### Benchmark agent

Owns test and benchmark separation.

Responsibilities:

- tiny fixtures for unit tests
- optional external benchmarks
- OmniDocBench adapter
- synthetic contaminated PDF benchmark later
- report generation

## Testing rules

Default:

```bash
pytest -q
```

Must not require:

- network access
- GPUs
- OmniDocBench
- Hugging Face downloads
- PaddleOCR
- Docling
- MinerU
- visual model packages

Optional markers:

```text
benchmark
slow
external
visual
docling
mineru
paddle
gpu
```

## Final instruction to agents

When in doubt, preserve evidence and structure rather than producing a prettier Markdown file.

A slightly verbose DocIR with good provenance is better than a clean Markdown file that cannot be benchmarked, chunked or audited.
