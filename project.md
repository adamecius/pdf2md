# pdf2md — Project description

## 1. What it does

pdf2md converts scanned, image-based scientific PDFs into a robust semantic representation suitable for export to Docling. The output must be rich enough to reconstruct the original document — book or scientific article — with high fidelity, preserving text, equations, tables, figures, captions, footnotes, references, and reading order.

## 2. Why it is hard

A single OCR backend produces an idiosyncratic interpretation of the same page. Different backends disagree on text segmentation, equation boundaries, table cells, figure crops, and reading order. None is correct on every document.

pdf2md treats each backend as evidence, not as truth. Truth is reconstructed by:

1. Linear, page-by-page consensus across multiple backends.
2. Geometric and media data extracted independently with PyMuPDF or equivalent tools.
3. Comparison against a deterministic ground truth derived from LaTeX sources.

## 3. Architecture

Pipeline:

    PDF (image)
      -> backends (each in its own conda env, exposed via a connector)
      -> per-backend extraction IR (page-local, primitive blocks)
      -> page-by-page consensus IR
      -> semantic layer (equations <-> labels, captions <-> figures,
                         refs <-> targets, footnotes <-> markers,
                         media <-> anchors)
      -> DoclingDocument
      -> validation against LaTeX-derived ground truth

The semantic stage is fed by three orthogonal sources:

- text and layout from OCR consensus,
- geometry and embedded media from PyMuPDF,
- ground-truth comparison signal from LaTeX-derived contracts.

Comparison happens at the earliest practical stage (page-level extraction IR) and again at the semantic and Docling stages. Docling is a post-consensus export target, not the first comparison layer.

## 4. Ground truth

A controlled corpus of LaTeX sources plus their compiled PDFs. The LaTeX is the source of truth. From each `.tex` we derive `semantic_document_groundtruth.json`: a linked block graph with blocks, labels, references, and relations (`caption_of`, `footnote_of`, `reference_to`, `equation_of`).

The corpus is intentionally diverse: numbered and unnumbered equations, multi-column layouts, tables of varying complexity, footnotes, bibliographies, multi-page constructs, captions in different positions. Diversity is the point — it forces the consensus and semantic stages to generalize rather than overfit one document.

## 5. Backends

Each OCR backend lives in its own conda environment (`pdf2md-<name>`) with its own connector adapter (`backend/<name>/pdf2ir_<name>.py`). The runner contract is:

- input: PDF path + output dir,
- output: per-page IR JSON + raw artifacts + run manifest with PDF hash, backend version, env lockfile hash, timestamp.

Adding a backend requires creating its env, its adapter, and a backend descriptor in the config. No core code changes.

## 6. Configuration

Two config files drive the system:

- `pdf2md.backends.toml`: enabled backends, env names, override commands, model paths.
- `pdf2md.consensus.toml`: thresholds (text similarity, IoU, geometry policy), regex patterns for equation labels, figure/table labels, footnote markers, bibliography spans, agreement weights, evaluation metrics for backend comparison.

All regex-like and threshold-like parameters live in config. Pipeline code does not hardcode them. Adding a backend or tuning the semantic linker should not require touching the core modules.

## 7. Validation strategy

Two comparison points against LaTeX ground truth:

1. Pre-Docling: `consensus/semantic_document.json` vs `groundtruth/semantic_document_groundtruth.json`.
2. Post-Docling: `docling/document.json` vs the LaTeX-derived Docling contract.

A backend run, a consensus output, and a Docling export are all judged by the same contract. The contract is the standard, not any single backend.

## 8. End goal

A semantic Docling output of a scientific document such that:

- every block has provenance back to backend evidence,
- every relation (`caption_of`, `refers_to`, `footnote_of`, `equation_of`) is explicit and resolvable,
- every conflict is recorded, not silently resolved,
- the resulting Docling can round-trip to a faithful Markdown or structured representation suitable for ingestion by downstream knowledge systems.

The system is judged not on any individual backend's output but on the robustness of the post-consensus, ground-truth-validated reconstruction.
