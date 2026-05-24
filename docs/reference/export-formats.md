# Export formats

The pipeline produces three operator-visible artefacts at the export
stage: a Docling-compatible JSON document, a Markdown preview, and a
set of RAG chunks. This reference describes each format, the module
that produces it, and the format's intended consumer.

For the *why* of having multiple export formats, see
[`../explanation/pipeline-stages.md`](../explanation/pipeline-stages.md).

---

## 1. Docling JSON (canonical)

**Producer:** [`src/pdf2md/export/docling.py`](../../src/pdf2md/export/docling.py).
**File:** `<run>/docling/<doc>.docling.json`.

The canonical structured output of the pipeline. Compatible with
`docling-core` consumers (LangChain `DoclingLoader`, llama-index
`DoclingReader`, etc.).

Carries:

- Block-level content with text, label, and bounding boxes.
- Per-block provenance (`prov`) referencing back to the source PDF
  page and char span.
- Tables (with cell structure) and pictures (with metadata).
- Origin metadata (binary hash, filename, mimetype).

Docling JSON is the **canonical** export target. Markdown preview and
RAG chunks are derived from it.

### Pipeline path

```text
ConsensusIR
  → LinkedStructure                (src/pdf2md/linking/)
  → Docling JSON                   (src/pdf2md/export/docling.py)
  → Markdown preview               (src/pdf2md/export/markdown.py)
  → RAG chunks                     (src/pdf2md/export/rag.py)
```

The pipeline orchestrator wires LinkedStructure into Docling export at
[`src/pdf2md/pipeline/orchestrator.py`](../../src/pdf2md/pipeline/orchestrator.py)
stage 6.

### Driver entry points

- End-to-end: `pdf2md convert <input.pdf> --config pdf2md.backends.toml`
- Export-only: `tools/export_linked_docling.py`

---

## 2. Markdown preview

**Producer:** [`src/pdf2md/export/markdown.py`](../../src/pdf2md/export/markdown.py).
**File:** `<run>/markdown/<doc>.preview.md`.

A human-readable rendering of the Docling document. Intended for:

- LLM prompts (paste the markdown directly).
- Spot-checking the structural reconstruction.
- Documentation that doesn't need round-trip fidelity.

The preview is **not** a round-trippable source of truth — it loses
provenance and confidence metadata that the Docling JSON preserves.

---

## 3. RAG chunks

**Producer:** [`src/pdf2md/export/rag.py`](../../src/pdf2md/export/rag.py).
**File:** `<run>/rag/<doc>.rag_chunks.json`.

A list of chunks ready for RAG indexing. Each chunk carries:

- The chunk text.
- A confidence value (from consensus scoring).
- Provenance back to the source LinkedNode IDs.
- A chunk-type tag (`text`, `caption`, `mixed`, etc.).
- Optional split metadata when a long block is split across multiple
  chunks for size limits.

Use these for search/retrieval pipelines that need both text and
metadata. The `RagExportSettings` (size limits, overlap) are
configurable in `tools/run_mvp_pipeline.py`.

---

## 4. Legacy Docling adapter

`src/pdf2md/_legacy/docling_adapter.py` consumes the older
`semantic_document.json` representation. It is **not** part of the
canonical pipeline — it is retained only for backward-discoverability
while `src/pdf2md/_legacy/` exists.

Tests under `tests/test_docling_adapter*.py` and
`tests/test_groundtruth_*.py` import the legacy adapter to assert
backward-compatible behaviour on historical fixtures. The adapter is
scheduled for removal together with `src/pdf2md/_legacy/` in a
follow-up cleanup plan.

**If you need to use a Docling output from new code, use the canonical
export path above. Do not extend the legacy adapter.**

---

## See also

- [`../explanation/pipeline-stages.md`](../explanation/pipeline-stages.md)
  — how the pipeline arrives at the export stage.
- [`../../src/pdf2md/models/export.py`](../../src/pdf2md/models/export.py)
  — Pydantic contracts (`ExportArtefact`, `ExportManifestDocument`,
  `RagChunk`, `RagChunkDocument`).
- [`../../src/pdf2md/export/`](../../src/pdf2md/export/) — implementation.
