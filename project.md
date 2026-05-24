# pdf2md — Project description

## 1. What it does

`pdf2md` reconstructs complete sequential PDF documents into a robust semantic representation suitable for export to Docling.

The project is aimed at scientific and technical documents, including scanned PDFs, born-digital PDFs with embedded text, mixed PDFs, LaTeX-compiled PDFs, and tagged PDFs when structural tags are available.

The output must be rich enough to reconstruct the original document, whether book, article, report, thesis, or technical note, with high fidelity. It should preserve text, equations, tables, figures, captions, footnotes, references, bibliography material, glossary or index-like sections, page sequence, headers, footers, and reading order.

The system assumes that the input is a complete document, not loose pages. The document's own structure is part of the evidence.

---

## 2. Why it is hard

A single OCR or PDF extraction backend produces an idiosyncratic interpretation of the same page. Different backends disagree on text segmentation, equation boundaries, table cells, figure crops, embedded media, structural tags, footnotes, references, and reading order.

No single backend is correct on every document or every feature.

A born-digital PDF may contain a reliable text layer but poor structural information. A scanned PDF may require OCR and layout analysis. A tagged PDF may expose useful hierarchy but still omit visual details. A LaTeX-compiled document may have source-known structure, but ordinary PDFs will not.

`pdf2md` treats each backend as evidence, not as truth. Truth is reconstructed by:

1. comparing multiple backend outputs page by page;
2. extracting geometric and media evidence independently with PyMuPDF or equivalent tools;
3. exploiting embedded text and tagged structure where available;
4. using whole-document semantic constraints such as section hierarchy, captions, references, and footnotes;
5. validating against a deterministic ground-truth corpus derived from LaTeX, LuaLaTeX/tagged PDF artefacts, and LaTeXML XML.

---

## 3. Architecture

Target pipeline:

```text
Complete sequential PDF (any class: scanned, born-digital, mixed, LaTeX, tagged)

  -> visual OCR via the configured backend ensemble
  -> per-backend PageExtractionIR
  -> EntityProposalDocument
  -> CalibrationPriorDocument (loaded, not computed inline)
  -> page-level ConsensusIR (Bayesian feature picker over backends)
  -> whole-document LinkedStructure
  -> Docling JSON
  -> validation, reports, RAG chunks, Markdown preview
```

There is no PDF-type classifier or input-routing stage. Every document
is rasterised and run through the same visual-OCR backend ensemble; the
consensus stage is responsible for picking the most reliable feature
extraction per block kind, not the input-classification stage.

The semantic stage is fed by several orthogonal sources:

- text and layout from visual OCR / layout backends (paddleocr, deepseek-ocr, mineru);
- entity proposals derived from each backend's connector output;
- calibration priors that quantify how reliable each backend is per
  BlockKind / EntityType (see §5 below).

Comparison happens at the earliest practical stage, at page-level extraction IR, and again at the semantic and Docling stages.

Docling is the canonical post-consensus export target. Markdown is a preview and downstream convenience format, not the source of truth.

---

## 4. Ground truth

The project uses a growing source-known ground-truth corpus.

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

The LaTeX source is the primary semantic source of truth. The compiled PDF supplies the rendered document. Tagged PDF and LaTeXML XML provide additional structural evidence. The generated semantic and Docling contracts provide machine-checkable targets.

From this corpus, the project derives expected blocks, labels, references, relations, captions, footnotes, equations, tables, and document structure.

The corpus is intentionally diverse: numbered and unnumbered equations, inline and display mathematics, multi-column layouts, tables of varying complexity, footnotes, bibliographies, multi-page constructs, repeated references, captions in different positions, and mixed text/image regions.

Diversity is the point. It forces the consensus and semantic stages to generalise rather than overfit one document or one backend.

---

## 5. Robust ensemble OCR and extraction

The ground-truth corpus is not only a test suite. It is the basis for robust ensemble OCR and document extraction.

Each backend is evaluated feature by feature against source-known documents. The system should learn, for example:

```text
Backend A is reliable for body text but weak on table structure.
Backend B is reliable for equations but weak on footnotes.
Backend C is reliable for captions but weak on reading order.
The embedded PDF text layer is reliable for born-digital body text but incomplete for figures.
Tagged PDF structure is useful for hierarchy but may not reflect visual layout.
LaTeXML is reliable for source-known structure but is available only for LaTeX-derived documents.
```

These observations become calibration priors. During consensus, evidence is weighted according to observed reliability, not by treating all backends equally in every situation.

The pipeline operates as a Bayesian feature picker: at each consensus
group, the per-candidate score combines text overlap, bbox IoU, reading
order, block-kind agreement and **calibrated backend priors** (currently
0.20 + 0.10 + 0.05 + 0.10 + 0.35 + 0.20 weighting, see
[src/pdf2md/consensus/scoring.py](src/pdf2md/consensus/scoring.py)).
Low-prior block kinds for a backend correctly fall to FALLBACK or
UNRESOLVED so downstream consumers know the system was uncertain.

Priors are resolved at consensus load time via a **three-level
fallback chain** (Plan 19):

```text
user-calibrated prior on disk   (refresh via tools/calibrate_priors.py)
  -> factory prior shipped under src/pdf2md/data/factory_priors/<backend>.json
  -> uninformative prior generated at runtime
     (uniform default_confidence, status=UNINFORMATIVE)
```

The chain is deterministic and silent in the happy path; the two
fallback transitions emit warnings ``prior_factory:<backend>`` and
``prior_uninformative:<backend>`` so reports record which level was
used. The consensus pipeline therefore always works — even on a fresh
install with no calibration data — and gracefully sharpens as
ground-truth measurements accumulate.

Calibration itself is **offline**: ``tools/calibrate_priors.py`` runs
against a ground-truth corpus and writes new priors that can replace
the factory priors (or live in a user-controlled directory). The
``--from-scratch`` flag stamps ``calibration_mode="from_scratch"`` in
the output metadata so downstream consumers can see provenance. There
is no per-document online prior update inside ``run_pipeline``.

When backends agree, confidence increases. When they disagree, the system uses calibrated priors, geometry, embedded text, and document-level semantic constraints to select a candidate, defer the decision, or record an explicit conflict.

The aim is to produce an OCR and extraction result that is more robust than any individual backend.

---

## 6. Backends

Backends are isolated and interchangeable.

Each backend lives in its own execution environment when needed, typically `pdf2md-<name>`, and exposes a connector that normalises its output into repository contracts.

Backend categories include:

```text
OCR/layout backends
embedded-text PDF extraction
geometry/media extraction
tagged-PDF extraction
LaTeX/XML-derived ground-truth extraction
```

The runner contract is:

- input: PDF path plus output directory;
- output: per-page IR JSON, raw artefacts, entity proposals when available, and a run manifest with PDF hash, backend version, environment information, and timestamp.

Adding a backend should require creating its environment, connector, and backend descriptor. It should not require changing the core consensus or linking code.

---

## 7. Configuration

Configuration drives backend execution, consensus thresholds, semantic patterns, and calibration behaviour.

Typical configuration surfaces include:

- `pdf2md.backends.toml`: enabled backends, environment names, override commands, model paths;
- `pdf2md.consensus.toml`: thresholds, text similarity, IoU policy, geometry policy, relation patterns, agreement weights, and evaluation metrics.

Regex-like and threshold-like parameters should live in config. Pipeline code should not hardcode tunable scientific-document assumptions when they can be made explicit.

---

## 8. Validation strategy

Validation occurs at multiple stages.

```text
backend raw output
  -> connector output
  -> PageExtractionIR
  -> ConsensusIR
  -> LinkedStructure
  -> Docling JSON
```

For ground-truth documents, each stage can be compared with LaTeX-derived expectations.

The two most important comparison points are:

1. pre-Docling semantic validation: linked or semantic structure vs ground-truth semantic contracts;
2. post-Docling validation: Docling JSON vs LaTeX-derived Docling ground truth.

A backend run, a consensus output, a linked structure, and a Docling export are judged by the same growing corpus. The contract is the standard, not any single backend.

Failures are useful. They identify where a backend, connector, consensus rule, linker, or export projection should lose confidence or be improved.

---

## 9. End goal

The final target is a semantic Docling output of a complete scientific or technical document such that:

- every block has provenance back to backend evidence;
- every important relation is explicit or explicitly unresolved;
- captions, references, footnotes, equations, figures, tables, page numbers, and headers/footers are linked when evidence supports it;
- every conflict is recorded, not silently resolved;
- every confidence score can be traced to backend evidence, priors, and ground-truth calibration;
- the resulting Docling can round-trip to a faithful Markdown or structured representation suitable for ingestion by downstream knowledge systems.

The system is judged not on any individual backend's output, but on the robustness of the post-consensus, ground-truth-calibrated reconstruction.
