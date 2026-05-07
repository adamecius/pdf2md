# Plan 6 - Docling export and rich semantic RAG artefacts

Status: ready to implement after Plan 5 reviewer acceptance  
Repo: `pdf2md`  
Owner: export layer  
Sequence: plan 6 of 6. It depends on Plans 1 to 5.

---

## 0. Current repository status and adequacy

The repository is now technically ready for Plan 6.

Current achieved chain:

```text
Plan 1: implemented - PageExtractionIR and ConsensusIR
Plan 2: implemented - connectors and EntityProposalDocument
Plan 3: implemented - calibration priors
Plan 4: implemented - page-level consensus factory and ConsensusIR output
Plan 5: implemented - semantic linker and LinkedStructure output
```

Plan 5 provides the required Plan 6 input:

```text
linked_structure.json
```

validated as:

```text
pdf2md.models.linked.LinkedStructure
```

Plan 6 must consume this final linked graph and project it to downstream artefacts. It must not re-resolve footnotes, captions, TOC entries, references, section hierarchy, page numbers, or unresolved conflicts. Those decisions belong to Plan 5 and must be preserved as export provenance.

Administrative note: if `current_plan.md` still names Plan 5, update it separately only after the reviewer accepts Plan 5. The technical dependency for Plan 6 is the existence of the Plan 5 implementation, tests, CLI, and `LinkedStructure` contract.

The repository still has legacy semantic-document helpers:

```text
src/pdf2md/models/semantic_document.py
src/pdf2md/utils/semantic_document_builder.py
```

These are not the new export substrate. Plan 6 must consume `LinkedStructure`, not the legacy dict-based semantic document.

The current mandatory project dependencies are deliberately minimal:

```text
pydantic>=2
typer>=0.12
```

Therefore Plan 6 must not require `docling-core` as a mandatory dependency. It should emit Docling-compatible JSON directly. If `docling-core` is installed locally, the exporter may optionally validate emitted JSON, but CI and unit tests must not depend on it.

---

## 1. Scope and constraints

Plan 6 implements the final export layer.

It consumes Plan 5 `LinkedStructure` and produces:

```text
<out-dir>/
  docling/
    <document_id>.docling.json
  rag/
    <document_id>.rag_chunks.json
  markdown/
    <document_id>.preview.md
  reports/
    export_report.json
  export_manifest.json
```

The Docling JSON is the canonical final structured output. RAG chunks and markdown preview are derived views for downstream usability and smoke testing.

Plan 6 does not run OCR. It does not run consensus. It does not run the semantic linker. It does not modify `LinkedStructure`. It is a pure projection layer.

Hard constraints:

```text
- No new mandatory runtime dependencies.
- No OCR execution in tests.
- No conda calls in tests.
- No modification to Plan 1 IR contracts.
- No modification to Plan 2 entity or connector contracts.
- No modification to Plan 3 prior contracts.
- No modification to Plan 4 consensus contracts.
- No modification to Plan 5 linked-structure contracts.
- No modification to backend OCR wrappers.
- No modification to src/pdf2md/backends/runner.py.
- No modification to src/pdf2md/cli/main.py.
- Export must be lenient: unsupported node types and unresolved links produce warnings, not hard failures.
- Invalid linked_structure.json is fatal.
- Optional docling-core validation must be best-effort and skipped when docling-core is unavailable.
- Tests must use synthetic fixtures, not real LaTeX compilation or real OCR.
```

Out of scope:

```text
- Running backend models.
- Building PageExtractionIR.
- Building EntityProposalDocument.
- Calibrating priors.
- Page-level consensus.
- Semantic linking.
- Changing LinkedStructure in-place.
- Creating embeddings.
- Running a vector database.
```

---

## 2. File whitelist

The reviewer rejects the plan if any implementation modifies files outside this whitelist.

```text
src/pdf2md/models/__init__.py
src/pdf2md/models/export.py

src/pdf2md/export/__init__.py
src/pdf2md/export/docling.py
src/pdf2md/export/rag.py
src/pdf2md/export/markdown.py
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py

tools/export_linked_docling.py

tests/test_export_contracts.py
tests/test_docling_export.py
tests/test_rag_export.py
tests/test_markdown_export.py
tests/test_export_io_cli.py

tests/data/export_fixtures/simple_document/linked_structure.json
tests/data/export_fixtures/simple_document/consensus_ir.json

tests/data/export_fixtures/rich_document/linked_structure.json
tests/data/export_fixtures/rich_document/consensus_ir.json

tests/data/export_fixtures/unresolved_conflicts/linked_structure.json
tests/data/export_fixtures/unresolved_conflicts/consensus_ir.json
```

Explicit non-whitelist files:

```text
src/pdf2md/models/ir.py
src/pdf2md/models/entities.py
src/pdf2md/models/priors.py
src/pdf2md/models/linked.py
src/pdf2md/connectors/common.py
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/backends/runner.py
src/pdf2md/cli/main.py
src/pdf2md/pipeline/convert.py
src/pdf2md/models/semantic_document.py
src/pdf2md/utils/semantic_document_builder.py
backend/*/connector.py
backend/*/pdf2md_*.py
backend/*/pdf2ir_*.py
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
pyproject.toml
current_plan.md
```

Rationale:

Plan 6 is a pure consumer of Plans 1 to 5. If it requires changing `LinkedStructure`, the Plan 5 contract was not ready. Do not fix that in Plan 6.

---

## 3. Inputs and outputs

### 3.1 Required input: LinkedStructure

Required file:

```text
linked_structure.json
```

Must validate as:

```text
pdf2md.models.linked.LinkedStructure
```

This file is the semantic source of truth for export.

### 3.2 Optional input: ConsensusIR

Optional file:

```text
consensus_ir.json
```

Must validate as:

```text
pdf2md.models.ir.ConsensusIR
```

Purpose:

```text
- page sizes
- bbox provenance
- extra block provenance
- sanity checks against consensus block ids
```

If missing, export continues with warnings and uses page information from `LinkedStructure`.

### 3.3 Optional input: source PDF path

Optional CLI argument:

```text
--source-pdf PATH
```

Purpose:

```text
- provenance only
- no PDF parsing in Plan 6
```

### 3.4 Outputs

Canonical output layout:

```text
<out-dir>/
  docling/
    <document_id>.docling.json
  rag/
    <document_id>.rag_chunks.json
  markdown/
    <document_id>.preview.md
  reports/
    export_report.json
  export_manifest.json
```

Required validation:

```text
- export_manifest.json validates as ExportManifestDocument.
- rag_chunks.json validates as RagChunkDocument.
- docling JSON passes internal structural validation.
- markdown preview is non-empty for non-empty documents.
```

---

## 4. New schema: export manifest and RAG chunks

File:

```text
src/pdf2md/models/export.py
```

This module contains Pydantic v2 models and pure helpers. It does not define DoclingDocument itself. The Docling output is emitted as a JSON dictionary because `docling-core` is not a mandatory dependency.

All models use:

```python
ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)
```

Schema version:

```python
EXPORT_SCHEMA_VERSION = "1.0.0"
```

### 4.1 Enums

```python
class ExportArtefactType(str, Enum):
    DOCLING_JSON = "docling_json"
    RAG_CHUNKS = "rag_chunks"
    MARKDOWN_PREVIEW = "markdown_preview"
    EXPORT_REPORT = "export_report"
```

```python
class ExportStatus(str, Enum):
    WRITTEN = "written"
    WRITTEN_WITH_WARNINGS = "written_with_warnings"
    SKIPPED = "skipped"
    FAILED = "failed"
```

```python
class RagChunkType(str, Enum):
    TITLE = "title"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    EQUATION = "equation"
    FOOTNOTE = "footnote"
    REFERENCE = "reference"
    MIXED = "mixed"
    UNKNOWN = "unknown"
```

### 4.2 ExportArtefact

```python
class ExportArtefact(BaseModel):
    artefact_type: ExportArtefactType
    path: str
    status: ExportStatus
    sha256: str | None
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- path is non-empty.
- sha256, when present, is 64 lowercase hex characters.
- extra fields are forbidden.
```

### 4.3 ExportManifestDocument

```python
class ExportManifestDocument(BaseModel):
    schema_name: Literal["pdf2md.ExportManifestDocument"]
    schema_version: Literal["1.0.0"]
    document_id: str
    source_linked_structure: str
    source_consensus_ir: str | None
    source_pdf: str | None
    artefacts: list[ExportArtefact]
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- document_id is non-empty.
- source_linked_structure is non-empty.
- artefact paths are unique.
- extra fields are forbidden.
```

### 4.4 RagChunk

```python
class RagChunk(BaseModel):
    id: str
    chunk_type: RagChunkType
    title: str | None
    text: str
    node_ids: list[str]
    relation_ids: list[str]
    page_start: int | None
    page_end: int | None
    section_path: list[str]
    breadcrumbs: list[str]
    confidence: float
    metadata: dict[str, Any]
```

ID pattern:

```text
^chunk:[A-Za-z0-9_.-]+:\d+$
```

Validation:

```text
- text is non-empty.
- node_ids are non-empty.
- page_start and page_end are >= 1 when present.
- page_end >= page_start when both are present.
- confidence in [0.0, 1.0].
- extra fields are forbidden.
```

### 4.5 RagChunkDocument

```python
class RagChunkDocument(BaseModel):
    schema_name: Literal["pdf2md.RagChunkDocument"]
    schema_version: Literal["1.0.0"]
    document_id: str
    chunks: list[RagChunk]
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- document_id is non-empty.
- chunk ids are unique.
- extra fields are forbidden.
```

Helper:

```python
rag_chunk_id(document_id: str, index: int) -> str
```

Re-export from:

```text
src/pdf2md/models/__init__.py
```

Append only. Do not remove Plan 1 to Plan 5 exports.

---

## 5. Export architecture

Plan 6 introduces six modules.

```text
src/pdf2md/export/docling.py    # LinkedStructure -> Docling-compatible JSON
src/pdf2md/export/rag.py        # LinkedStructure -> RagChunkDocument
src/pdf2md/export/markdown.py   # LinkedStructure -> markdown preview
src/pdf2md/export/io.py         # filesystem loading/writing
src/pdf2md/export/reporting.py  # export report and manifest helpers
src/pdf2md/export/__init__.py
```

No module imports OCR backends.

No module imports legacy `semantic_document_builder`.

No module requires `docling-core`.

---

## 6. Docling exporter

File:

```text
src/pdf2md/export/docling.py
```

### 6.1 Public API

```python
@dataclass(frozen=True)
class DoclingExportSettings:
    schema_name: str = "DoclingDocument"
    schema_version: str = "1.7.0"
    include_unresolved: bool = True
    coord_origin: str = "BOTTOMLEFT"
```

```python
@dataclass(frozen=True)
class DoclingExportResult:
    document: dict[str, Any]
    warnings: list[str]
```

```python
def build_docling_document(
    *,
    linked: LinkedStructure,
    consensus: ConsensusIR | None = None,
    settings: DoclingExportSettings = DoclingExportSettings(),
) -> DoclingExportResult:
    ...
```

```python
def validate_docling_like_document(document: dict[str, Any]) -> list[str]:
    ...
```

```python
def try_validate_with_docling_core(document: dict[str, Any]) -> tuple[bool, str | None]:
    ...
```

### 6.2 Docling JSON shape

The emitter produces a Docling-compatible JSON dictionary with these top-level keys:

```text
schema_name
version
name
origin
body
groups
texts
tables
pictures
pages
key_value_items
form_items
metadata
```

Required conventions:

```text
- body.self_ref = "#/body".
- every emitted item has self_ref.
- text items live under texts.
- table items live under tables.
- figure/picture items live under pictures.
- logical hierarchy is represented through groups and body.children.
- pages are keyed by page number as strings.
- provenance is preserved in prov when linked node metadata provides page and bbox.
```

### 6.3 Node-to-Docling mapping

```text
document             -> body root
title                -> text item with label "title"
section              -> group item, plus optional heading text item
paragraph            -> text item with label "paragraph"
list                 -> group item with label "list"
list_item            -> text item with label "list_item"
table                -> table item
figure               -> picture item
caption              -> text item with label "caption"; attached through metadata or parent group when relation exists
equation             -> text item with label "formula"
footnote             -> text item with label "footnote"
page_number          -> text item with label "page_footer" or metadata.is_page_artifact = true
header               -> text item with label "page_header"
footer               -> text item with label "page_footer"
toc_entry            -> text item with label "toc_entry"
reference_section    -> group item with label "references"
reference_item       -> text item with label "reference"
bibliography_marker  -> text item with label "reference_marker"
code                 -> text item with label "code"
unknown              -> text item with label "unknown"
```

### 6.4 Relation-to-Docling projection

Use `LinkedRelation` to improve hierarchy:

```text
CONTAINS / PARENT_OF:
  determine group children.

CAPTION_OF:
  attach caption self_ref into target picture/table metadata or children.

TOC_POINTS_TO:
  preserve in metadata.links on toc_entry item.

FOOTNOTE_ANCHOR_FOR:
  preserve in metadata.links on footnote item and anchor target item.

REFERENCES:
  preserve in metadata.links on citation/source item.

FOLLOWS and sequence relations:
  preserve in metadata.relations but do not force hierarchy.
```

Unresolved conflicts:

```text
- If include_unresolved is true, unresolved nodes are emitted with metadata.status = "unresolved".
- LinkedConflict objects are preserved in document.metadata.pdf2md_conflicts.
```

### 6.5 Minimal structural validation

`validate_docling_like_document` checks:

```text
- required top-level keys exist.
- body.self_ref exists.
- all self_ref values are unique.
- all body/group children references exist.
- all page references in provenance exist in pages.
- every text/table/picture item has a label or metadata.type.
- metadata contains pdf2md provenance.
```

It returns a list of warnings, not exceptions, unless the caller is in strict CLI mode.

---

## 7. RAG exporter

File:

```text
src/pdf2md/export/rag.py
```

### 7.1 Public API

```python
@dataclass(frozen=True)
class RagExportSettings:
    max_chars: int = 1800
    overlap_chars: int = 150
    include_captions_with_targets: bool = True
    include_references: bool = True
```

```python
def build_rag_chunks(
    *,
    linked: LinkedStructure,
    settings: RagExportSettings = RagExportSettings(),
) -> RagChunkDocument:
    ...
```

### 7.2 Chunking rules

Chunking is structure-first, not arbitrary text splitting.

Rules:

```text
- Title is its own chunk when present.
- Each section starts a chunk group.
- Paragraphs under the same section are merged until max_chars is reached.
- Captions are included with their figure/table target when CAPTION_OF exists.
- Tables become separate chunks.
- Figures become separate chunks with caption text when available.
- Equations become separate chunks unless short enough to remain near surrounding text.
- Footnotes become separate chunks and preserve FOOTNOTE_ANCHOR_FOR metadata.
- References become separate chunks only when include_references is true.
- Unresolved nodes are included only when they contain text and marked metadata.status = "unresolved".
```

Each chunk must preserve:

```text
node_ids
relation_ids
page_start
page_end
section_path
breadcrumbs
confidence
```

Confidence:

```text
mean confidence of included nodes and relations, clipped to [0.0, 1.0]
```

---

## 8. Markdown preview exporter

File:

```text
src/pdf2md/export/markdown.py
```

### 8.1 Public API

```python
@dataclass(frozen=True)
class MarkdownExportSettings:
    include_page_numbers: bool = False
    include_headers_footers: bool = False
    include_unresolved_warnings: bool = True
```

```python
def build_markdown_preview(
    *,
    linked: LinkedStructure,
    settings: MarkdownExportSettings = MarkdownExportSettings(),
) -> tuple[str, list[str]]:
    ...
```

### 8.2 Markdown rules

```text
title        -> "# Title"
section      -> heading level from metadata, default "##"
paragraph    -> plain paragraph
list_item    -> "- item"
equation     -> fenced math block when possible
table        -> simple markdown table placeholder if cells are unavailable
figure       -> image placeholder or "[Figure]"
caption      -> italic caption unless already attached to figure/table
footnote     -> footnote block
reference_item -> numbered/bullet reference line
toc_entry    -> plain TOC line
page_number, header, footer -> excluded by default
unknown      -> HTML comment warning plus text
```

This preview is not the canonical output. It is a human-readable smoke artefact.

---

## 9. I/O layer

File:

```text
src/pdf2md/export/io.py
```

### 9.1 Public API

```python
@dataclass(frozen=True)
class ExportLoadResult:
    linked: LinkedStructure
    consensus: ConsensusIR | None
    warnings: list[str]
```

```python
@dataclass(frozen=True)
class ExportRunResult:
    docling: dict[str, Any]
    rag_chunks: RagChunkDocument
    markdown: str
    manifest: ExportManifestDocument
    report: dict[str, Any]
    warnings: list[str]
```

```python
def load_export_inputs(
    *,
    linked_structure_path: Path,
    consensus_ir_path: Path | None = None,
    strict: bool = False,
) -> ExportLoadResult:
    ...
```

```python
def write_export_outputs(
    *,
    result: ExportRunResult,
    out_dir: Path,
) -> None:
    ...
```

```python
def build_export_run(
    *,
    linked: LinkedStructure,
    consensus: ConsensusIR | None,
    source_linked_structure: str,
    source_consensus_ir: str | None,
    source_pdf: str | None,
    docling_settings: DoclingExportSettings,
    rag_settings: RagExportSettings,
    markdown_settings: MarkdownExportSettings,
    strict: bool = False,
) -> ExportRunResult:
    ...
```

### 9.2 Lenient warnings

```text
consensus_ir_missing
invalid_consensus_ir
docling_core_unavailable
docling_core_validation_failed:<reason>
unsupported_node_type:<node_id>
unresolved_node_emitted:<node_id>
missing_page_for_node:<node_id>
rag_chunk_split:<chunk_id>
markdown_empty_node:<node_id>
```

Invalid `linked_structure.json` is fatal in both lenient and strict mode.

Invalid optional `consensus_ir.json` warns in lenient mode and raises in strict mode.

---

## 10. Reporting

File:

```text
src/pdf2md/export/reporting.py
```

Required report shape:

```json
{
  "schema_name": "pdf2md.ExportReport",
  "schema_version": "1.0.0",
  "document_id": "doc-1",
  "docling": {
    "text_count": 10,
    "table_count": 1,
    "picture_count": 1,
    "group_count": 3,
    "page_count": 2,
    "warning_count": 0
  },
  "rag": {
    "chunk_count": 5,
    "average_confidence": 0.91
  },
  "markdown": {
    "char_count": 1800,
    "warning_count": 0
  },
  "warnings": []
}
```

The report is an audit artefact.

---

## 11. CLI tool

File:

```text
tools/export_linked_docling.py
```

Required CLI:

```bash
python tools/export_linked_docling.py   --linked-structure tests/data/export_fixtures/simple_document/linked_structure.json   --consensus-ir tests/data/export_fixtures/simple_document/consensus_ir.json   --source-pdf sample.pdf   --out-dir /tmp/pdf2md_export
```

Required options:

```text
--linked-structure PATH
--consensus-ir PATH          optional
--source-pdf PATH            optional provenance only
--out-dir PATH
--strict
--verbose
--no-rag
--no-markdown
--include-unresolved
--max-chars INT              default 1800 for RAG chunks
```

Exit codes:

```text
0 = export written successfully, even if warnings exist
1 = invalid CLI arguments or strict-mode failure
```

---

## 12. Tests as milestones

Completion is certified by pytest, not by prose.

### 12.1 tests/test_export_contracts.py

Expected count: 24 tests.

Must cover:

```text
- ExportArtefactType enum values
- ExportStatus enum values
- RagChunkType enum values
- ExportArtefact validation
- ExportManifestDocument round trip
- duplicate artefact paths rejected
- RagChunk id validation
- RagChunk page range validation
- RagChunkDocument duplicate ids rejected
- rag_chunk_id factory
- JSON Schema export
```

### 12.2 tests/test_docling_export.py

Expected count: 20 tests.

Must cover:

```text
- simple LinkedStructure emits required Docling top-level keys
- body self_ref exists
- self_ref values are unique
- section nodes become groups
- paragraphs become text items
- tables become table items
- figures become picture items
- captions attach to figure/table metadata when CAPTION_OF exists
- footnote/reference relations are preserved in metadata
- unresolved conflicts are preserved in document metadata
- pages are emitted from linked nodes and/or ConsensusIR
- validate_docling_like_document catches broken child refs
- optional docling-core validation skips cleanly when unavailable
```

### 12.3 tests/test_rag_export.py

Expected count: 16 tests.

Must cover:

```text
- title chunk
- section-based chunk grouping
- max_chars split
- overlap metadata when split
- captions included with figure/table target
- tables become separate chunks
- equations become chunks
- footnotes preserve anchor metadata
- references can be included
- references can be excluded
- unresolved nodes are marked in metadata
- chunk confidence is mean of node/relation confidence
- RagChunkDocument validates
```

### 12.4 tests/test_markdown_export.py

Expected count: 14 tests.

Must cover:

```text
- title renders as H1
- section renders as heading
- paragraph renders as text
- list item renders as bullet
- equation renders as math block
- table renders as markdown placeholder or table
- figure and caption render in readable order
- footnote renders
- references render
- headers/footers/page numbers excluded by default
- unresolved warning emitted when enabled
- preview is non-empty for simple document
```

### 12.5 tests/test_export_io_cli.py

Expected count: 16 tests.

Must cover:

```text
- load_export_inputs reads LinkedStructure and ConsensusIR
- missing optional ConsensusIR warns but succeeds
- strict invalid ConsensusIR raises
- write_export_outputs writes all expected files
- export_manifest validates
- export_report contains counts
- CLI help exits zero
- CLI writes Docling JSON, RAG chunks, markdown preview, report, manifest
- CLI --no-rag skips RAG artefact
- CLI --no-markdown skips markdown artefact
- CLI strict mode fails on invalid optional input
- written Docling JSON passes internal validation
```

---

## 13. Fixtures

### 13.1 simple_document

Input:

```text
linked_structure.json
consensus_ir.json
```

Shape:

```text
document
section "Introduction"
paragraph "This is the introduction."
figure
caption "Figure 1. Example figure."
CAPTION_OF relation
```

Expected:

```text
Docling JSON with body, section group, paragraph text, picture, caption.
RAG chunks include section content and figure caption.
Markdown preview is readable.
No export conflicts.
```

### 13.2 rich_document

Shape:

```text
title
TOC entry
section hierarchy
paragraphs
table
figure
caption
equations
footnotes
references
relations from Plan 5
```

Expected:

```text
Docling groups preserve hierarchy.
RAG chunks preserve section_path and relation metadata.
Markdown preview includes all major content.
Export report has non-zero counts for text, table, picture, groups, chunks.
```

### 13.3 unresolved_conflicts

Shape:

```text
LinkedStructure includes unresolved node and LinkedConflict.
```

Expected:

```text
Docling metadata preserves conflict.
RAG chunk marks unresolved status.
Markdown preview includes unresolved warning when enabled.
Exporter does not fail in lenient mode.
```

---

## 14. Acceptance criteria

The reviewer accepts Plan 6 only when all criteria pass.

### 14.1 Plan 5 must already pass

Before implementing Plan 6, run:

```bash
pytest tests/test_linked_structure_contracts.py -q
pytest tests/test_linking_extract.py -q
pytest tests/test_linking_resolvers.py -q
pytest tests/test_linked_structure_builder.py -q
pytest tests/test_build_linked_structure_cli.py -q
```

All must pass.

### 14.2 Targeted Plan 6 tests

```bash
pytest tests/test_export_contracts.py -q
pytest tests/test_docling_export.py -q
pytest tests/test_rag_export.py -q
pytest tests/test_markdown_export.py -q
pytest tests/test_export_io_cli.py -q
```

All pass. No skip. No xfail.

### 14.3 Plans 1 to 5 still pass

```bash
pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
pytest tests/test_connector_common.py -q
pytest tests/test_backend_connectors.py -q
pytest tests/test_prior_contracts.py -q
pytest tests/test_calibration_matching.py -q
pytest tests/test_calibration_metrics.py -q
pytest tests/test_calibrate_priors_cli.py -q
pytest tests/test_consensus_grouping.py -q
pytest tests/test_consensus_scoring.py -q
pytest tests/test_consensus_factory.py -q
pytest tests/test_build_consensus_cli.py -q
pytest tests/test_linked_structure_contracts.py -q
pytest tests/test_linking_extract.py -q
pytest tests/test_linking_resolvers.py -q
pytest tests/test_linked_structure_builder.py -q
pytest tests/test_build_linked_structure_cli.py -q
```

All pass.

### 14.4 Existing legacy tests still pass

```bash
pytest tests/test_run_backends_config.py -q
pytest tests/test_semantic_document_builder.py -q
```

Plan 6 must not break legacy compatibility tests.

### 14.5 Whole suite has no regression

```bash
pytest tests/ -q
```

Must pass with no regression.

### 14.6 Whitelist check

```bash
git diff --name-only main..HEAD
```

Must be a subset of the whitelist in section 2.

### 14.7 Smoke import

```bash
python -c "from pdf2md.export.docling import build_docling_document; from pdf2md.models.export import RagChunkDocument; print(build_docling_document.__name__, RagChunkDocument.model_json_schema()['title'])"
```

Expected output:

```text
build_docling_document RagChunkDocument
```

### 14.8 CLI smoke test

```bash
python tools/export_linked_docling.py   --linked-structure tests/data/export_fixtures/simple_document/linked_structure.json   --consensus-ir tests/data/export_fixtures/simple_document/consensus_ir.json   --out-dir /tmp/pdf2md_export_smoke
```

Then:

```bash
python -c "from pathlib import Path; import json; from pdf2md.models.export import ExportManifestDocument, RagChunkDocument; root=Path('/tmp/pdf2md_export_smoke'); ExportManifestDocument.model_validate_json((root/'export_manifest.json').read_text()); RagChunkDocument.model_validate_json(next((root/'rag').glob('*.rag_chunks.json')).read_text()); doc=json.loads(next((root/'docling').glob('*.docling.json')).read_text()); assert 'body' in doc and 'texts' in doc; print('ok')"
```

Expected output:

```text
ok
```

---

## 15. Implementation order

### A. Export contracts first

Implement only:

```text
src/pdf2md/models/export.py
src/pdf2md/models/__init__.py
tests/test_export_contracts.py
```

Run:

```bash
pytest tests/test_export_contracts.py -q
pytest tests/test_linked_structure_contracts.py -q
```

Reason:

The output manifest and RAG chunk contracts must be frozen before building exporters.

### B. Docling exporter

Implement:

```text
src/pdf2md/export/__init__.py
src/pdf2md/export/docling.py
tests/test_docling_export.py
tests/data/export_fixtures/simple_document/*
tests/data/export_fixtures/rich_document/*
tests/data/export_fixtures/unresolved_conflicts/*
```

Run:

```bash
pytest tests/test_docling_export.py -q
```

Reason:

Docling JSON is the canonical final output. It should be implemented before derived RAG and markdown artefacts.

### C. RAG exporter

Implement:

```text
src/pdf2md/export/rag.py
tests/test_rag_export.py
```

Run:

```bash
pytest tests/test_rag_export.py -q
```

Reason:

RAG chunking must consume `LinkedStructure` and should not be coupled to Docling JSON internals.

### D. Markdown preview exporter

Implement:

```text
src/pdf2md/export/markdown.py
tests/test_markdown_export.py
```

Run:

```bash
pytest tests/test_markdown_export.py -q
```

Reason:

Markdown is a human-readable smoke artefact, not the canonical output.

### E. I/O, reporting, and CLI

Implement:

```text
src/pdf2md/export/io.py
src/pdf2md/export/reporting.py
tools/export_linked_docling.py
tests/test_export_io_cli.py
```

Run:

```bash
pytest tests/test_export_io_cli.py -q
```

Reason:

The CLI should only bind together tested pure exporters.

### F. Regression pass

Run all Plan 6 targeted tests, all Plan 1 to Plan 5 tests, legacy compatibility tests, full test suite, and the whitelist check.

---

## 16. What Plan 6 must not accidentally become

Do not implement previous pipeline stages here.

Bad:

```text
"Rebuild LinkedStructure from ConsensusIR."
"Resolve footnotes or TOC targets during export."
"Change LinkedStructure nodes before emitting Docling."
"Run backend OCR."
"Run consensus."
"Call build_linked_structure internally unless explicitly requested by a later orchestration plan."
"Add docling-core as mandatory dependency."
```

Good:

```text
"Project LinkedStructure nodes to Docling JSON items."
"Preserve LinkedRelation metadata in Docling metadata."
"Emit RAG chunks with node_ids and section_path."
"Emit a markdown preview for inspection."
"Write export_manifest.json with SHA256s."
```

This is the correct level for Plan 6.

---

## 17. Practical reviewer checklist

The reviewer should ask:

```text
1. Does Plan 6 consume LinkedStructure from Plan 5?
2. Does it avoid modifying LinkedStructure?
3. Does it emit Docling-compatible JSON?
4. Does the Docling JSON preserve node and relation provenance?
5. Does every Docling item have a stable self_ref?
6. Are unresolved conflicts preserved in metadata?
7. Are RAG chunks structure-aware rather than arbitrary text slices?
8. Does markdown preview remain a non-canonical smoke artefact?
9. Does the exporter avoid mandatory docling-core dependency?
10. Does the CLI write all expected artefacts?
11. Are Plans 1 to 5 untouched?
12. Is git diff contained inside the whitelist?
```

---

## 18. Final pipeline after Plan 6

After Plan 6 is accepted, the full intended pipeline is:

```text
backend raw output
  -> connector
  -> PageExtractionIR + EntityProposalDocument
  -> calibration priors
  -> ConsensusIR
  -> LinkedStructure
  -> Docling JSON + RAG chunks + markdown preview
```

This completes the route needed for validating the OCR pipeline against the LaTeX/Docling ground-truth corpus and for producing rich semantic files suitable for RAG.

---

## Status

- Plan 6 / PR #4: done; ready to archive after human acceptance.
- A. Export contracts first: done.
- B. Docling exporter: done.
- C. RAG exporter: done.
- D. Markdown preview exporter: done.
- E. I/O, reporting, and CLI: done.
- F. Regression pass: done.

## PR_review #3

- verdict: fail
- reviewed_commit: `50b1906c`
- plan_compliance:
    - whitelist: pass. The PR touched only Plan 6 whitelist files plus `run_log.md`, which is whitelisted by the repository agent protocol.
    - run_log_evidence: pass. `run_log.md` contains PR #3 evidence for export contracts, Docling, RAG, markdown, I/O/CLI, regression, smoke import, smoke CLI, and the environmental `main` ref limitation.
    - dependencies: pass. No new dependencies were added.
    - automated_tests: pass. All Plan 6 targeted tests, Plan 5 prerequisite tests, Plans 1-5 regression tests, legacy tests, full suite, smoke import, and CLI smoke checks passed during review. The whitelist command `git diff --name-only main..HEAD` remains environmental because this checkout has no `main` ref.
- findings:
    - F1: Docling relation projection is incomplete for `FOOTNOTE_ANCHOR_FOR`. Plan 6 requires `FOOTNOTE_ANCHOR_FOR` to be preserved in metadata on both the footnote item and the anchor target item. The implementation handles all non-caption relations by attaching metadata only to the source item, so the paragraph/anchor target does not receive the footnote link.
    - F2: RAG footnote chunks do not preserve footnote-anchor metadata. Plan 6 requires footnotes to become separate chunks and preserve `FOOTNOTE_ANCHOR_FOR` metadata. The implementation includes relation ids, but does not include the anchor target id or relation metadata in the chunk metadata.
- tests_run:
    - `pytest tests/test_export_contracts.py -q && pytest tests/test_docling_export.py -q && pytest tests/test_rag_export.py -q && pytest tests/test_markdown_export.py -q && pytest tests/test_export_io_cli.py -q` — pass
    - `pytest tests/test_linked_structure_contracts.py -q && pytest tests/test_linking_extract.py -q && pytest tests/test_linking_resolvers.py -q && pytest tests/test_linked_structure_builder.py -q && pytest tests/test_build_linked_structure_cli.py -q` — pass
    - `pytest tests/test_ir_contracts.py -q && pytest tests/test_entity_contracts.py -q && pytest tests/test_connector_common.py -q && pytest tests/test_backend_connectors.py -q && pytest tests/test_prior_contracts.py -q && pytest tests/test_calibration_matching.py -q && pytest tests/test_calibration_metrics.py -q && pytest tests/test_calibrate_priors_cli.py -q && pytest tests/test_consensus_grouping.py -q && pytest tests/test_consensus_scoring.py -q && pytest tests/test_consensus_factory.py -q && pytest tests/test_build_consensus_cli.py -q && pytest tests/test_linked_structure_contracts.py -q && pytest tests/test_linking_extract.py -q && pytest tests/test_linking_resolvers.py -q && pytest tests/test_linked_structure_builder.py -q && pytest tests/test_build_linked_structure_cli.py -q` — pass
    - `pytest tests/test_run_backends_config.py -q && pytest tests/test_semantic_document_builder.py -q && pytest tests/ -q` — pass
    - `python -c "from pdf2md.export.docling import build_docling_document; from pdf2md.models.export import RagChunkDocument; print(build_docling_document.__name__, RagChunkDocument.model_json_schema()['title'])"` — pass
    - `python tools/export_linked_docling.py --linked-structure tests/data/export_fixtures/simple_document/linked_structure.json --consensus-ir tests/data/export_fixtures/simple_document/consensus_ir.json --out-dir /tmp/pdf2md_export_smoke` — pass
    - `python -c "from pathlib import Path; import json; from pdf2md.models.export import ExportManifestDocument, RagChunkDocument; root=Path('/tmp/pdf2md_export_smoke'); ExportManifestDocument.model_validate_json((root/'export_manifest.json').read_text()); RagChunkDocument.model_validate_json(next((root/'rag').glob('*.rag_chunks.json')).read_text()); doc=json.loads(next((root/'docling').glob('*.docling.json')).read_text()); assert 'body' in doc and 'texts' in doc; print('ok')"` — pass
    - `git diff --name-only main..HEAD` — env_fail: this checkout has no `main` ref.
- required_follow_up:
    - Add Docling projection for `FOOTNOTE_ANCHOR_FOR` metadata to both the footnote source item and the anchor target item, with regression coverage asserting both sides.
    - Add RAG metadata for footnote anchor relations, including the anchor target node id and relation metadata, with regression coverage.


## PR_review #4

- verdict: pass
- reviewed_commit: `7856746c`
- plan_compliance:
    - whitelist: pass. The cumulative Plan 6 diff from `9c326ced..HEAD` is confined to the Plan 6 whitelist, plus `run_log.md` and `current_plan.md` review-mode updates permitted by the agent protocol. The required plan command `git diff --name-only main..HEAD` remains environmental because this checkout has no `main` ref.
    - run_log_evidence: pass. `run_log.md` contains PR #4 evidence for the Docling follow-up, RAG follow-up, regression tests, smoke checks, `git diff --check`, and the environmental `main` ref limitation.
    - dependencies: pass. No new dependencies were added, and `docling-core` remains optional/best-effort only.
    - plan_scope: pass. The implementation consumes `LinkedStructure`, does not modify Plan 1-5 contracts, does not run OCR/consensus/linking, and does not call backend or conda tooling.
    - automated_tests: pass. All Plan 6 targeted tests ran at the expected counts, Plan 5 prerequisites ran, Plans 1-5 and legacy regression tests ran, the full suite ran, smoke import and CLI smoke checks passed, and `git diff --check` passed.
- reviewer_verification:
    - Export contracts are implemented and re-exported.
    - Docling JSON emits required top-level keys, stable self refs, pages, provenance, conflicts, captions, relation metadata, and `FOOTNOTE_ANCHOR_FOR` metadata on both footnote source and anchor target items.
    - RAG chunks preserve node ids, relation ids, page ranges, section paths, breadcrumbs, confidence, unresolved metadata, captions with figure/table targets, and footnote anchor target/relation metadata.
    - Markdown preview remains a non-canonical human-readable artefact.
    - I/O, reporting, manifest SHA256 writing, and CLI smoke behaviour satisfy Plan 6.
- tests_run:
    - `pytest tests/test_export_contracts.py -q && pytest tests/test_docling_export.py -q && pytest tests/test_rag_export.py -q && pytest tests/test_markdown_export.py -q && pytest tests/test_export_io_cli.py -q` — pass
    - `pytest tests/test_linked_structure_contracts.py -q && pytest tests/test_linking_extract.py -q && pytest tests/test_linking_resolvers.py -q && pytest tests/test_linked_structure_builder.py -q && pytest tests/test_build_linked_structure_cli.py -q && pytest tests/test_ir_contracts.py -q && pytest tests/test_entity_contracts.py -q && pytest tests/test_connector_common.py -q && pytest tests/test_backend_connectors.py -q && pytest tests/test_prior_contracts.py -q && pytest tests/test_calibration_matching.py -q && pytest tests/test_calibration_metrics.py -q && pytest tests/test_calibrate_priors_cli.py -q && pytest tests/test_consensus_grouping.py -q && pytest tests/test_consensus_scoring.py -q && pytest tests/test_consensus_factory.py -q && pytest tests/test_build_consensus_cli.py -q && pytest tests/test_run_backends_config.py -q && pytest tests/test_semantic_document_builder.py -q` — pass
    - `pytest tests/ -q` — pass
    - `python -c "from pdf2md.export.docling import build_docling_document; from pdf2md.models.export import RagChunkDocument; print(build_docling_document.__name__, RagChunkDocument.model_json_schema()['title'])"` — pass
    - `python tools/export_linked_docling.py --linked-structure tests/data/export_fixtures/simple_document/linked_structure.json --consensus-ir tests/data/export_fixtures/simple_document/consensus_ir.json --out-dir /tmp/pdf2md_export_smoke` — pass
    - `python -c "from pathlib import Path; import json; from pdf2md.models.export import ExportManifestDocument, RagChunkDocument; root=Path('/tmp/pdf2md_export_smoke'); ExportManifestDocument.model_validate_json((root/'export_manifest.json').read_text()); RagChunkDocument.model_validate_json(next((root/'rag').glob('*.rag_chunks.json')).read_text()); doc=json.loads(next((root/'docling').glob('*.docling.json')).read_text()); assert 'body' in doc and 'texts' in doc; print('ok')"` — pass
    - `git diff --check` — pass
    - `git diff --name-only main..HEAD` — env_fail: this checkout has no `main` ref.
- certification: Plan 6 is fully implemented.
