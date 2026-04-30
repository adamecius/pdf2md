# pdf2md Architecture Overview

## 1. Project purpose

**pdf2md** is a local-first system for converting PDF documents into Markdown for downstream consumption, especially retrieval-augmented generation (RAG) pipelines and related document analysis workflows.

The project is intended for long-form and structure-sensitive material such as books, research papers, technical reports, manuals, and other multi-page documents where layout and reading order matter.

Its distinctive architectural idea is **multi-backend extraction**: multiple independent OCR or document-understanding backends can process the same PDF, and their outputs can later be compared rather than blindly trusting a single extractor.

## 2. High-level objective

Long-term target pipeline:

```text
PDF
  -> backend extraction
  -> backend-native outputs
  -> canonical document schema
  -> consensus and validation
  -> final Markdown
  -> review flags
```

The system is being built incrementally. Early phases focus on stable execution, reproducible artefacts, and backend orchestration before full normalisation and consensus are complete.

## 3. Architectural principles

- **Local-first execution** where practical.
- **Backend dependency isolation** to avoid coupling heavy or conflicting stacks.
- **Lightweight central package** that coordinates rather than embeds all backend runtimes.
- **Explicit configuration** for backend selection and runtime behavior.
- **No hidden downloads** during normal operation.
- **No hidden API fallback** when local execution is expected.
- **Clear separation** between execution, normalisation, consensus, and rendering.
- **Preserve backend-native outputs** for auditability and future reprocessing.

## 4. Main components

### Backend wrappers
Wrapper entry points that execute external OCR/parser tools and produce raw backend outputs.

### Backend runners
Small backend-local helpers responsible for calling each backend’s official CLI or local execution path.

### Central CLI
A coordinating interface that reads configuration and launches enabled backend wrappers as subprocesses.

### Canonical models
A shared document representation used after backend-specific outputs are normalised.

### Adapters (future)
A backend-specific conversion layer that maps backend-native outputs into canonical documents.

### Consensus (future)
A comparison and validation layer that evaluates canonical outputs from multiple backends.

### Renderers
Components that transform canonical or consensus documents into Markdown.

## 5. Repository layout

Intended high-level structure:

```text
src/pdf2md/
  central package, models, CLI, renderer, config, backend orchestration

backend/
  backend-specific wrappers, setup files, and isolated execution logic

tests/
  lightweight tests that do not require heavy OCR execution

pdf2md.backends.example.toml
  example backend configuration

description.md
  project architecture overview
```

This structure is schematic and intentionally avoids listing every file.

## 6. Backend strategy

Each backend may need a different runtime environment, package set, or system dependencies. For this reason, backend dependencies are not installed into the central package by default.

Uniform wrapper invocation pattern:

```bash
python backend/<backend>/pdf2md_<backend>.py -i input.pdf
```

Wrappers should emit backend Markdown output plus optional manifests, and should preserve raw backend artefacts where applicable.

Expected backend roles:

- **MinerU**: structured document parsing with strong signals for layout, reading order, images, tables, and content lists.
- **DeepSeek**: OCR or vision-language extraction backend, local-model-first.
- **PaddleOCR**: OCR-focused backend used as an independent text extraction signal.
- **GLM**: API-only backend at this stage; not part of default local execution.

## 7. Configuration and orchestration

Backend execution is config-driven.

The central CLI should run only backends that are explicitly defined and enabled in a local configuration file.

Intended orchestration pattern:

```bash
pdf2md run-backends input.pdf --config pdf2md.backends.toml
```

A run creates an artefact folder, executes enabled backend wrappers, and records raw outputs, logs, command metadata, and status files.

## 8. Run artefact structure

Expected schematic run layout:

```text
.tmp/<run-name>/
  input/
  raw/<backend>/
    output.md
    manifest.json
    stdout.log
    stderr.log
    command.json
    status.json
  run_manifest.json
```

This structure supports traceability, auditability, and later normalisation/consensus stages.

## 9. Canonical document schema direction

The canonical model is planned around a shared document hierarchy:

- **Document** contains **Pages**.
- **Pages** contain ordered **Blocks**.

Blocks represent semantic/layout units, including:

- title
- heading
- paragraph
- table
- formula
- image
- caption
- list item
- footnote
- header
- footer
- unknown

Where available, blocks should preserve:

- text
- page number
- reading order
- bounding box
- source backend
- confidence and/or metadata
- media references

## 10. Image and media strategy

Images should eventually be extracted into a dedicated media folder and referenced in Markdown via stable placeholders such as:

```text
[image:fig_001]
```

Captions should be preserved and linked to the corresponding image whenever reliable association is available.

## 11. Normalisation strategy

Backend outputs are not expected to share a native format.

Adapters will convert backend-native outputs into the canonical schema, for example:

```text
MinerU output -> MinerU adapter -> Document
DeepSeek output -> DeepSeek adapter -> Document
PaddleOCR output -> PaddleOCR adapter -> Document
```

Normalisation is a planned milestone and may be partial during early development.

## 12. Consensus strategy

A future consensus layer will compare canonical documents from multiple backends and detect agreement/disagreement across:

- text
- reading order
- block boundaries
- page assignment
- tables
- formulas
- images
- captions

The objective is not only selecting one output but also surfacing uncertain regions for review and confidence scoring.

## 13. Rendering strategy

Rendering should operate from canonical or consensus documents, not directly from backend-native raw formats.

Markdown rendering should preserve document structure and include stable media placeholders.

## 14. Testing philosophy

Routine tests should be lightweight, deterministic, and runnable in constrained environments.

They should **not** require:

- CUDA
- internet access
- API keys
- model downloads
- full OCR execution
- heavy backend package installation

They should focus on:

- schema behavior
- Markdown rendering
- configuration parsing
- CLI help and argument validation
- command planning
- run-folder creation
- fake backend artefact handling

## 15. Current and future milestones

Current / early milestones:

- core package skeleton
- backend wrapper stabilisation
- config-driven backend orchestration
- Markdown rendering basics

Next milestones:

- define canonical schema in greater detail
- implement the first adapter (likely MinerU)
- add normalised JSON output
- compare two normalised backend outputs
- implement consensus uncertainty flags
- render final consensus Markdown

## 16. Non-goals for this architecture document

This document intentionally excludes:

- bug reports
- PR review commentary
- temporary workaround details
- backend installation troubleshooting
- historical failed approaches
- full API references
- full code-level implementation details

It is an architectural entry point for future development sessions, not an execution log.
