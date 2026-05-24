# Docling inspection layer (legacy)

This file documents the **legacy** Docling inspection adapter under
`pdf2md._legacy.docling_adapter`, which consumes the older
`semantic_document.json` representation.

This layer is **not** part of the canonical pipeline. It is retained
only for backward-discoverability while `src/pdf2md/_legacy/` exists.

## Canonical Docling export

The canonical Docling export path is:

```text
ConsensusIR
  -> LinkedStructure  (src/pdf2md/linking/)
  -> Docling JSON     (src/pdf2md/export/docling.py)
  -> Markdown preview (src/pdf2md/export/markdown.py)
  -> RAG chunks       (src/pdf2md/export/rag.py)
```

Driver entry points:

- end-to-end:  `pdf2md convert <input.pdf> --config pdf2md.backends.toml`
- export only: `tools/export_linked_docling.py`

The pipeline orchestrator wires LinkedStructure into Docling export at
[../src/pdf2md/pipeline/orchestrator.py](../src/pdf2md/pipeline/orchestrator.py)
stage 6.

## Why the legacy adapter still exists

Tests under `tests/test_docling_adapter*.py` and
`tests/test_groundtruth_*.py` import `pdf2md._legacy.docling_adapter`
to assert backward-compatible behaviour on historical fixtures. The
adapter is scheduled for removal together with `src/pdf2md/_legacy/`
in a follow-up cleanup plan.

If you need to **use** a Docling output from new code, use the
canonical export path above. Do not extend the legacy adapter.
