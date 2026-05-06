# Current plan — LaTeX corpus → DoclingDocument ground truth

## Goal

Create a parser at `tools/latex_to_docling.py` that reads every LaTeX ground-truth fixture under `groundtruth/corpus/latex/<doc_id>/` and emits a **fully populated `DoclingDocument` JSON** (the Pydantic schema from `docling-core`) into the same directory.

The existing `tools/compile_latex_groundth.py` already produces two compiled witnesses per fixture: a LuaLaTeX PDF and a LaTeXML XML. This new tool treats the `.tex` source as the **authoring source of truth** and builds the richest possible DoclingDocument from it, optionally enriched with the LaTeXML XML when present.

This completes the ground-truth triad:

```
.tex (source)  ─┬─►  .pdf        (rendered witness)
                ├─►  .latexml.xml (semantic witness)
                └─►  .docling.json (fully populated DoclingDocument)
```

The `.docling.json` becomes the **reference DoclingDocument** that the OCR pipeline's reconstructed Docling outputs are validated against.

Design rules:

- Minimal validation: warn on missing or unsupported features, never fail.
- If a field can't be populated (no geometry, no page info, no media), it is left at default/empty — not invented.
- Output uses `docling-core`'s own `export_to_dict()` for canonical JSON.
- No runtime dependency on TeX tooling — the parser reads `.tex` text.


## Architecture overview

```
.tex source
  │
  ├─► LaTeX regex parser (titles, sections, paragraphs, lists,
  │   equations, tables, figures, captions, footnotes, labels, refs)
  │
  ├─► Optional LaTeXML XML enrichment (better text normalization,
  │   resolved cross-refs, bibliography entries)
  │
  └─► DoclingDocument builder (docling-core API)
        │
        ├── body tree: title → section → subsection → paragraphs/items
        ├── texts[]: title, section_header, text, formula, footnote,
        │            caption, list_item, reference
        ├── tables[]: TableData with cell grid from \tabular
        ├── pictures[]: PictureItem for \begin{figure} (no image data)
        ├── groups[]: list / ordered_list for itemize/enumerate
        └── .docling.json
```


## Mapping: LaTeX → DocItemLabel

| LaTeX construct              | DocItemLabel       | DoclingDocument API call       |
|------------------------------|--------------------|--------------------------------|
| `\title{...}`               | `title`            | `add_text(label=TITLE)`        |
| `\section{...}`             | `section_header`   | `add_text(label=SECTION_HEADER, level=1)` |
| `\subsection{...}`          | `section_header`   | `add_text(label=SECTION_HEADER, level=2)` |
| paragraph text               | `text`             | `add_text(label=TEXT)`         |
| `\begin{equation}...\end`   | `formula`          | `add_text(label=FORMULA)`      |
| `$...$` / `$$...$$`         | `formula`          | `add_text(label=FORMULA)`      |
| `\footnote{...}`            | `footnote`         | `add_text(label=FOOTNOTE)`     |
| `\caption{...}`             | `caption`          | `add_text(label=CAPTION)`      |
| `\item ...`                 | `list_item`        | `add_text(label=LIST_ITEM, enumerated=..., parent=group)` |
| `\begin{itemize}`           | (group)            | `add_group(label=GroupLabel.LIST)` |
| `\begin{enumerate}`         | (group)            | `add_group(label=GroupLabel.ORDERED_LIST)` |
| `\begin{figure}`            | `picture`          | `add_picture()`                |
| `\begin{table}`+`\tabular`  | `table`            | `add_table(data=TableData(...))` |
| `\ref{...}`                 | (inline in text)   | stored in sidecar metadata     |
| `\label{...}`               | (label registry)   | stored in sidecar metadata     |


## Sidecar file: `.docling_groundtruth_meta.json`

DoclingDocument does not natively carry LaTeX-specific provenance (labels, cross-references, anchor IDs). A sidecar JSON is emitted alongside the Docling JSON:

```json
{
  "schema_name": "pdf2md.docling_groundtruth_meta",
  "schema_version": "1.0.0",
  "document_id": "linked_sections_figures",
  "source_tex": "groundtruth/corpus/latex/linked_sections_figures/linked_sections_figures.tex",
  "labels": {"sec:overview": "#/texts/1", "eq:energy": "#/texts/5", ...},
  "references": [
    {"source_ref": "#/texts/3", "target_label": "fig:box-diagram", "resolved_ref": "#/pictures/0"}
  ],
  "footnote_anchors": [
    {"footnote_ref": "#/texts/4", "anchor_ref": "#/texts/2"}
  ],
  "caption_relations": [
    {"caption_ref": "#/texts/6", "target_ref": "#/pictures/0"}
  ],
  "warnings": []
}
```


## Whitelist

Files the agent may create, modify, or delete:

- `tools/latex_to_docling.py`
- `tests/test_latex_to_docling.py`
- `groundtruth/corpus/latex/**/*.docling.json` (generated output only)
- `groundtruth/corpus/latex/**/*.docling_groundtruth_meta.json` (generated output only)
- `current_plan.latex_to_docling.md`

Explicitly forbidden:

- editing any `groundtruth/corpus/latex/**/*.tex` source file
- editing any `groundtruth/corpus/latex/**/*.bib` source file
- editing `tools/compile_latex_groundth.py`
- editing existing tests or production code under `src/`


## Dependencies

Python packages (already installed or in pyproject.toml):

- `docling-core>=2.50` (for `DoclingDocument`, `DocItemLabel`, `GroupLabel`, `TableData`, `TableCell`)
- standard library only otherwise (re, json, argparse, pathlib, xml.etree.ElementTree)

No external system tools required.


## Tasks

### T1 — Implement the LaTeX-to-DoclingDocument parser tool

Create `tools/latex_to_docling.py`.

CLI:

```
python tools/latex_to_docling.py \
  --corpus-root groundtruth/corpus/latex \
  [--doc <doc_id>] \
  [--force] \
  [--verbose]
```

Behaviour:

- Discover fixture directories matching `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`.
- For each fixture, parse the `.tex` source and build a `DoclingDocument`.
- Save `<doc_id>.docling.json` and `<doc_id>.docling_groundtruth_meta.json` in the fixture directory.
- Process documents in sorted order.
- Never modify `.tex` sources.
- If `--force` is not passed, skip documents where `.docling.json` exists and `.tex` has not changed (hash check via `meta.toml` sha256 or file mtime).

LaTeX parser requirements:

- Parse `\title`, `\section`, `\subsection` (including starred variants).
- Parse paragraph text between structural commands.
- Parse `\begin{equation}...\end{equation}`, `$...$`, `$$...$$`.
- Parse `\begin{figure}...\end{figure}` with nested `\caption` and `\label`.
- Parse `\begin{table}...\end{table}` with nested `\begin{tabular}{spec}...\end{tabular}`, extracting cell grid.
- Parse `\begin{itemize}` and `\begin{enumerate}` with proper nesting into DoclingDocument groups.
- Parse `\footnote{...}`.
- Parse `\label{...}` and `\ref{...}` to build the sidecar label/reference map.
- Handle `\maketitle`, `\newpage` (as structural hints, not content).
- Inline math `$...$` may be left inline within paragraph text OR extracted as separate formula items — choose the strategy that best matches Docling's conventions (separate items).
- Gracefully skip unknown commands — warn, don't fail.

DoclingDocument construction:

- Use `DoclingDocument(name=doc_id)`.
- Build the body tree: title is a root child, sections are root children, subsections are children of sections, paragraphs/items are children of their enclosing section/subsection.
- Lists: create a `GroupItem` with `GroupLabel.LIST` or `GroupLabel.ORDERED_LIST`, and attach `list_item` children.
- Tables: build `TableData` with `TableCell` grid from parsed `\tabular` content.
- Figures: call `add_picture()` (no image data since these are LaTeX primitives like `\fbox`).
- Captions: call `add_text(label=CAPTION)` and use DoclingDocument's caption association.
- Export via `doc.export_to_dict()` and save as JSON with indent=2.

Warnings (non-fatal):

- `unknown_environment:<env_name>` — encountered `\begin{X}` that the parser doesn't handle.
- `missing_latexml_xml:<doc_id>` — no `.latexml.xml` found for enrichment.
- `empty_equation:<doc_id>` — equation environment with no extractable body.
- `table_parse_incomplete:<doc_id>` — tabular parsing couldn't extract full cell grid.


### T2 — Optional LaTeXML XML enrichment layer

Within the same tool, if `<doc_id>.latexml.xml` exists in the fixture directory, parse it with `xml.etree.ElementTree` to:

- Cross-check section titles and paragraph text against LaTeX parse.
- Extract resolved bibliography entries if present.
- Use LaTeXML's resolved cross-reference targets to validate the label→ref map.

This is additive enrichment only — the `.tex` parse is always the primary source. If the XML is missing or unparseable, warn and continue.


### T3 — Automated tests

Create `tests/test_latex_to_docling.py`.

Required coverage:

- **Parser unit tests**: simple title+paragraph, section hierarchy, equation extraction, table cell grid, list nesting, figure+caption, footnote, cross-references.
- **DoclingDocument validity**: parsed output can be loaded by `DoclingDocument.model_validate(json_data)`.
- **Sidecar correctness**: label→ref map resolves to valid `#/texts/N` or `#/pictures/N` JSON pointers.
- **Graceful degradation**: unknown environments produce warnings, not exceptions.
- **Hash gating**: existing output is skipped when `.tex` hasn't changed, re-generated with `--force`.
- **CLI smoke**: `--help` exits 0.

Tests must not require TeX tooling — they use inline `.tex` strings in temporary directories.


### T4 — Run against full corpus and commit outputs

tag: human (requires the agent to have run T1 on the actual corpus)

```
python tools/latex_to_docling.py --corpus-root groundtruth/corpus/latex --force --verbose
```

Verify that every fixture directory now contains:
- `<doc_id>.docling.json` — valid DoclingDocument JSON
- `<doc_id>.docling_groundtruth_meta.json` — sidecar with labels/references

Spot-check a few documents to confirm the body tree hierarchy and text content match the `.tex` source.


## Tests

### A1 — CLI help smoke test

```
python tools/latex_to_docling.py --help
```

pass: exits 0, prints usage.


### A2 — Unit test suite

```
PYTHONPATH=src python -m pytest tests/test_latex_to_docling.py -v
```

pass: all tests pass without requiring TeX installation or docling GPU models.


### A3 — Python syntax compilation

```
python -m compileall tools/latex_to_docling.py tests/test_latex_to_docling.py
```

pass: both files compile without syntax errors.


### A4 — Full corpus generation

tag: human

```
python tools/latex_to_docling.py --corpus-root groundtruth/corpus/latex --force --verbose
```

pass: all 57 corpus fixtures produce `.docling.json` and sidecar. No crashes. Warnings are acceptable for edge cases.


### A5 — DoclingDocument schema validation

tag: human (or automated if docling-core is available)

```python
from docling_core.types.doc import DoclingDocument
import json
for path in Path("groundtruth/corpus/latex").rglob("*.docling.json"):
    data = json.loads(path.read_text())
    DoclingDocument.model_validate(data)  # must not raise
```

pass: every generated `.docling.json` validates against the current `docling-core` schema.


## Status

T1: pending
T2: pending
T3: pending
T4: pending