# Docling inspection layer (experimental)

## Purpose
This layer converts `semantic_document.json` into a real DoclingDocument export for inspection, while preserving richer semantic links, provenance, conflicts, unresolved items, and degradation decisions in `docling_relations.json`.

This is **not** final canonical reconstruction.

## Input
- `semantic_document.json`

## Outputs
- `docling_document.json`
- `docling_relations.json`
- `docling_adapter_report.json`
- `docling_preview.md` (only when `--export-markdown` is requested and markdown export succeeds)

## Modes
- `inspection` (default): continue on warnings.
- `strict`: warnings/errors produce non-zero exit.

## Dependency requirement
The CLI requires real `docling` / `docling-core`.
If missing, command fails clearly.

## Why `docling_relations.json` exists
DoclingDocument is used for typed inspection/export, while sidecar data preserves semantic information not cleanly representable in Docling item APIs.

## What is mapped into DoclingDocument
- Paragraph/title/heading/caption/etc. as text when supported.
- Figures as pictures when media is present and mapping succeeds.
- Tables/formulas/footnotes may be degraded to text when type-specific APIs are unavailable.

## What stays in the sidecar
- semantic IDs and block snapshots
- docling refs and mapped types
- anchors, references, relations, conflicts
- source and selection provenance
- warnings/errors/degradation reasons

## Orphan media policy
Default: suppress unanchored figure media and warn `orphan_media_suppressed:<block_id>`.
With `--include-orphan-media`: include and warn `orphan_media_included_debug:<block_id>`.

## Caption policy
Uses `caption_of` relations; preserves fragment IDs. Multi-fragment captions emit `fragmented_caption:*` and `caption_joined_from_fragments:*` warnings.

## Formula policy
Preserves formula blocks and emits warnings for mismatched text/geometry selection, duplicate candidates, and degraded mappings.

## Table policy
If structured table construction is unavailable, degrade to text with `table_structure_degraded:*`.

## Footnote/reference policy
Footnotes are preserved; unresolved references emit `unresolved_reference:*`; unresolved footnote refs emit `footnote_marker_unresolved:*`.

## Known limitations
- No formula fusion.
- No final caption fusion.
- No full table reconstruction.
- No footnote marker-body linking.

## Examples
```bash
python -m pdf2md.utils.docling_adapter semantic_document.json --output-root out --mode inspection --export-markdown --verbose
python -m pdf2md.utils.docling_adapter semantic_document.json --output-root out --mode strict
```

## Troubleshooting
- Missing dependency: install `docling` and `docling-core`.
- Missing media warnings: verify relative paths and materialized assets.
- Strict failures: inspect `docling_adapter_report.json` warnings/errors.
- Markdown unavailable: inspect `markdown_export_unavailable:*` warning.

## Testing note
- The repository does **not** include any fake top-level `docling` package.
- Unit tests use backend injection/mocking inside test code only.
- CLI execution requires a real `docling`/`docling-core` installation.

## Upstream input gaps tracked
The adapter currently degrades gracefully and records warnings when upstream semantic inputs are incomplete for richer Docling mapping (page dimensions/provenance granularity, structured table cells, canonical fused formula objects, canonical caption objects, and explicit canonical-vs-debug media policy markers).
