# Docling inspection layer

Experimental inspection conversion from `semantic_document.json` to Docling-compatible JSON plus a relation sidecar.

## CLI

```bash
python -m pdf2md.utils.docling_adapter SEMANTIC_DOCUMENT_JSON \
  --output-root OUTPUT_ROOT \
  --mode inspection \
  --include-orphan-media \
  --export-markdown \
  --json-only \
  --verbose
```

## Purpose

- Provide a first-pass Docling view for inspection.
- Preserve all rich semantic provenance/conflicts/warnings in `docling_relations.json`.
- Avoid silent canonicalisation.

## Modes

- `inspection` (default): warn and continue with degradations.
- `strict`: warnings can cause non-zero exit.

## Outputs

- `docling_document.json`
- `docling_relations.json`
- `docling_adapter_report.json`
- `docling_preview.md` when markdown export is requested and available.

## Sidecar retention

The sidecar preserves semantic IDs, JSON-pointer mappings, page/bbox/source metadata, anchors, references, relations, conflicts, warnings, and unresolved issues.

## Limitations

- This layer is intentionally non-canonical.
- Some block types may be degraded to text placeholders with explicit warnings.
