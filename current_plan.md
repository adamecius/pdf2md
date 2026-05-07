# Plan 2 - Backend connectors and document-level entity proposals

Status: draft, ready to implement after Plan 1  
Repo: `pdf2md`  
Owner: connector layer  
Sequence: this is plan 2 of 6. It depends on Plan 1 and blocks Plans 3 to 6.

---

## 0. Scope and constraints

This plan introduces the connector layer.

A connector is a thin, backend-local adapter that reads one backend's raw output and emits:

1. `PageExtractionIR` files, one per page, using the Plan 1 schema.
2. A document-level `EntityProposalDocument`, containing entities and relation proposals detected from that backend's own output.

This plan does not run OCR. It does not modify backend wrappers. It does not perform consensus. It does not calibrate backend priors. It does not build the final linked document structure. It only normalises backend evidence into the contracts needed by the later pipeline.

The key design correction is this:

`PageExtractionIR` remains page-local evidence. Document-level entity proposals must not be hidden inside `PageExtractionIR.metadata`, because that would make them opaque to consensus and calibration. They get their own explicit schema.

Hard constraints:

```text
- No new runtime dependencies.
- No OCR execution in tests.
- No conda calls in tests.
- No modification to backend OCR wrappers.
- No modification to src/pdf2md/backends/runner.py.
- No modification to src/pdf2md/cli/main.py.
- No modification to Plan 1 IR contracts unless a reviewer explicitly opens Plan 1 again.
- Connector behaviour must be lenient: missing manifest, missing bbox, missing page size, or missing native structure produces warnings, not hard failure.
- Only truly invalid caller state fails hard: non-existent raw_dir, invalid output path, or schema-invalid object construction.
```

Out of scope:

```text
- Ground-truth calibration.
- Consensus scoring.
- Bayesian priors.
- Page-to-page semantic disambiguation.
- Final linked structure.
- Docling export.
- Changes to existing backend CLI behaviour.
```

---

## 1. Why this plan exists

Plan 1 gives the system a stable page-level evidence contract. Plan 2 makes every backend capable of producing that evidence in a comparable way.

The connector also adds document-level proposals, but only as proposals:

```text
section candidate
TOC entry candidate
page number candidate
footnote candidate
equation candidate
caption candidate
figure/table candidate
reference section candidate
reference item candidate
possible caption_of relation
possible toc_points_to relation
```

These are not final semantic decisions. They are backend-specific hypotheses with evidence and confidence. Plan 3 calibrates their confidence against ground truth. Plan 4 consumes them during consensus. Plan 5 decides document-level links.

This separation prevents the page-local consensus layer from being forced to decide things it cannot know yet. For example, a short numeric block can be a footnote marker, a page number, an equation number, or part of a reference. The connector records proposals and evidence. It does not force a final interpretation.

---

## 2. File whitelist

The reviewer rejects the plan if any implementation modifies files outside this whitelist.

```text
src/pdf2md/models/__init__.py
src/pdf2md/models/entities.py

src/pdf2md/connectors/__init__.py
src/pdf2md/connectors/common.py

backend/deepseek/connector.py
backend/glm/connector.py
backend/mineru/connector.py
backend/paddleocr/connector.py

tests/test_entity_contracts.py
tests/test_connector_common.py
tests/test_backend_connectors.py

tests/data/connector_fixtures/simple_markdown/output.md
tests/data/connector_fixtures/simple_markdown/manifest.json
tests/data/connector_fixtures/semantic_markdown/output.md
tests/data/connector_fixtures/semantic_markdown/manifest.json
tests/data/connector_fixtures/empty_markdown/output.md
tests/data/connector_fixtures/empty_markdown/manifest.json
```

Explicit non-whitelist files:

```text
src/pdf2md/models/ir.py
src/pdf2md/backends/runner.py
src/pdf2md/cli/main.py
src/pdf2md/pipeline/convert.py
pdf2md.backends.example.toml
backend/*/pdf2md_*.py
backend/*/pdf2ir_*.py
current_plan.md
pyproject.toml
```

Why this whitelist is strict:

Plan 2 is a post-processing layer over raw backend artifacts. The existing backend runner already handles backend execution, command planning, raw output directories, and run manifests. Changing it here would couple connector work with runner work and make review harder.

---

## 3. Output layout

Each backend connector writes into an explicit output directory supplied by the caller. No global runner integration happens in this plan.

Canonical output layout:

```text
<out-dir>/<backend>/
  manifest.json
  pages/
    page_0001.json
    page_0002.json
    ...
  entities.json
```

Where:

```text
pages/page_0001.json  = PageExtractionIR
entities.json         = EntityProposalDocument
manifest.json         = connector execution manifest, not a Pydantic domain object
```

The connector manifest is intentionally simple:

```json
{
  "schema_name": "pdf2md.ConnectorManifest",
  "schema_version": "1.0.0",
  "document_id": "doc_001",
  "backend": "mineru",
  "backend_version": null,
  "raw_dir": "...",
  "page_count": 3,
  "page_ir_files": ["pages/page_0001.json"],
  "entity_file": "entities.json",
  "warnings": [],
  "created_at": "2026-05-07T00:00:00Z"
}
```

No test should depend on exact wall-clock equality. Tests only assert that `created_at` exists and is non-empty.

---

## 4. New schema: EntityProposalDocument

File:

```text
src/pdf2md/models/entities.py
```

This module contains only Pydantic v2 models and pure id factories. No I/O.

All models use:

```python
ConfigDict(extra="forbid", frozen=False, populate_by_name=True)
```

The schema version for this file is:

```python
ENTITY_SCHEMA_VERSION = "1.0.0"
```

### 4.1 Enums

```python
class EntityType(str, Enum):
    DOCUMENT_TITLE = "document_title"
    SECTION = "section"
    TOC_ENTRY = "toc_entry"
    PAGE_NUMBER = "page_number"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    EQUATION = "equation"
    FIGURE = "figure"
    TABLE = "table"
    CAPTION = "caption"
    REFERENCE_SECTION = "reference_section"
    REFERENCE_ITEM = "reference_item"
    BIBLIOGRAPHY_MARKER = "bibliography_marker"
    UNKNOWN = "unknown"
```

```python
class RelationType(str, Enum):
    CAPTION_OF = "caption_of"
    FOOTNOTE_ANCHOR_FOR = "footnote_anchor_for"
    TOC_POINTS_TO = "toc_points_to"
    REFERENCE_MENTION_OF = "reference_mention_of"
    SAME_ENTITY_AS = "same_entity_as"
    NEAR = "near"
    SEQUENCE_NEXT = "sequence_next"
    CANDIDATE_FOR = "candidate_for"
```

```python
class EvidenceKind(str, Enum):
    BLOCK_TEXT = "block_text"
    BBOX = "bbox"
    REGEX = "regex"
    POSITION = "position"
    READING_ORDER = "reading_order"
    MARKDOWN_SYNTAX = "markdown_syntax"
    BACKEND_NATIVE_TYPE = "backend_native_type"
    RAW_ARTIFACT = "raw_artifact"
    DOCUMENT_CONTEXT = "document_context"
```

```python
class ConfidenceSource(str, Enum):
    HEURISTIC = "heuristic"
    CALIBRATED = "calibrated"
    MANUAL = "manual"
    UNKNOWN = "unknown"
```

Plan 2 uses `heuristic`. Plan 3 may emit `calibrated`.

---

### 4.2 EntityEvidence

```python
class EntityEvidence(BaseModel):
    kind: EvidenceKind
    page_no: int | None
    source_block_id: str | None
    raw_ref: str | None
    text: str | None
    bbox: BBox | None
    weight: float
    reason: str
    metadata: dict[str, Any]
```

Validation:

```text
- weight is in [0.0, 1.0].
- page_no is >= 1 when present.
- source_block_id, when present, matches Plan 1 ExtractionBlock.id regex.
- reason is non-empty.
- extra fields are forbidden.
```

`bbox` imports the Plan 1 `BBox` from:

```python
from pdf2md.models.ir import BBox
```

---

### 4.3 EntityProposal

```python
class EntityProposal(BaseModel):
    id: str
    entity_type: EntityType
    subtype: str | None
    canonical_text: str | None
    page_no: int | None
    block_ids: list[str]
    confidence: float
    confidence_source: ConfidenceSource
    evidence: list[EntityEvidence]
    calibration_key: str | None
    metadata: dict[str, Any]
```

ID pattern:

```text
^ent:[a-z0-9_-]+:[A-Za-z0-9_.-]+:[a-z_]+:\d+$
```

Format:

```text
ent:<backend>:<document_id>:<entity_type>:<index>
```

Validation:

```text
- confidence is in [0.0, 1.0].
- evidence has at least one item.
- block_ids, when non-empty, all match Plan 1 ExtractionBlock.id regex.
- page_no is >= 1 when present.
- extra fields are forbidden.
```

`calibration_key` is forward compatibility for Plan 3:

```text
<backend>:<entity_type>:<detector_name>
```

Example:

```text
paddleocr:page_number:number_only_margin_detector
```

Plan 2 does not read priors. It only preserves the key needed for later calibration.

---

### 4.4 RelationProposal

```python
class RelationProposal(BaseModel):
    id: str
    relation_type: RelationType
    source_entity_id: str
    target_entity_id: str
    confidence: float
    confidence_source: ConfidenceSource
    evidence: list[EntityEvidence]
    metadata: dict[str, Any]
```

ID pattern:

```text
^rel:[a-z0-9_-]+:[A-Za-z0-9_.-]+:\d+$
```

Format:

```text
rel:<backend>:<document_id>:<index>
```

Validation:

```text
- confidence is in [0.0, 1.0].
- source_entity_id and target_entity_id match EntityProposal.id pattern.
- source_entity_id != target_entity_id.
- evidence has at least one item.
```

---

### 4.5 EntityProposalDocument

```python
class EntityProposalDocument(BaseModel):
    schema_name: Literal["pdf2md.EntityProposalDocument"]
    schema_version: Literal["1.0.0"]
    document_id: str
    backend: str
    backend_version: str | None
    page_count: int
    entities: list[EntityProposal]
    relations: list[RelationProposal]
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- document_id is non-empty.
- backend is non-empty.
- page_count >= 0.
- entity ids are unique.
- relation ids are unique.
- every relation source_entity_id exists in entities.
- every relation target_entity_id exists in entities.
- extra fields are forbidden.
```

Helper id factories:

```python
entity_id(backend, document_id, entity_type, index) -> str
relation_id(backend, document_id, index) -> str
```

Re-export these from:

```text
src/pdf2md/models/__init__.py
```

Append only. Do not remove Plan 1 exports.

---

## 5. Connector common module

File:

```text
src/pdf2md/connectors/common.py
```

This is where shared connector logic lives so that `backend/*/connector.py` stays thin.

### 5.1 Public API

```python
@dataclass(frozen=True)
class ConnectorResult:
    pages: list[PageExtractionIR]
    entities: EntityProposalDocument
    warnings: list[str]
```

```python
@dataclass(frozen=True)
class BackendConnectorConfig:
    backend: str
    default_backend_version: str | None
    markdown_file_candidates: tuple[str, ...]
    manifest_file_candidates: tuple[str, ...]
```

```python
def connect_raw_dir(
    *,
    raw_dir: Path,
    document_id: str,
    config: BackendConnectorConfig,
    out_dir: Path | None = None,
) -> ConnectorResult:
    ...
```

```python
def write_connector_result(
    *,
    result: ConnectorResult,
    backend: str,
    document_id: str,
    raw_dir: Path,
    out_dir: Path,
) -> Path:
    ...
```

Return value of `write_connector_result`:

```text
Path to <out-dir>/<backend>/manifest.json
```

---

### 5.2 Lenient input discovery

The common connector searches for markdown or text evidence in this order:

```text
1. output.md
2. output.mmd
3. result.md
4. result.mmd
5. any single *.md or *.mmd file in raw_dir
```

Manifest discovery:

```text
1. manifest.json
2. status.json
3. command.json
```

Manifest absence is not fatal.

Rules:

```text
- raw_dir missing: raise ValueError.
- raw_dir exists but no markdown-like file: produce zero pages, empty entities, warning "raw_text_missing".
- manifest missing: warning "manifest_missing".
- page size missing: use PageSize(width=1.0, height=1.0), warning "page_size_missing".
- bbox missing: bbox=None.
```

No connector test should require real PDFs.

---

## 6. Markdown-to-PageExtractionIR mapping

Plan 2 needs a minimal, deterministic parser. It is not a Markdown renderer. It only creates enough blocks to feed consensus and entity proposal tests.

Input:

```text
raw markdown text from one backend output
```

Page splitting:

```text
- Split on explicit markers first:
  - "<--- Page Split --->"
  - "\f"
  - "<!-- pagebreak -->"
- If none are present, produce one page.
```

Block splitting:

```text
- Split by blank lines.
- Preserve order.
- Trim whitespace.
- Drop empty chunks.
```

Block classification:

```text
# Heading                -> BlockKind.HEADING
## Heading               -> BlockKind.HEADING
display math block       -> BlockKind.FORMULA
HTML <table>...</table>  -> BlockKind.TABLE
markdown image ![](...)  -> BlockKind.FIGURE
"Figure 1..."            -> BlockKind.CAPTION
"Fig. 2..."              -> BlockKind.CAPTION
"Table 1..."             -> BlockKind.CAPTION
list item                -> BlockKind.LIST_ITEM
otherwise                -> BlockKind.PARAGRAPH
```

The connector should not invent structure it cannot justify. If a chunk is ambiguous, emit `BlockKind.PARAGRAPH`. Use `BlockKind.UNKNOWN` only when classification truly fails.

Block IDs use the Plan 1 factory:

```python
extraction_id(backend, document_id, page_no, block_index)
```

`PageExtractionIR` defaults:

```text
schema_name       = "pdf2md.PageExtractionIR"
schema_version    = "1.0.0"
backend           = config.backend
backend_version   = manifest-derived or config default
page_no           = 1-indexed
page_size         = PageSize(width=1.0, height=1.0) if unknown
bbox              = None unless native evidence provides it
confidence        = None in Plan 2 unless backend already supplies confidence
raw_artifact_ref  = relative path to raw markdown file where possible
metadata          = {"connector": "markdown_fallback"}
```

---

## 7. Document-level entity recogniser

The recogniser consumes the complete list of `PageExtractionIR` pages emitted by one backend and returns `EntityProposalDocument`.

It works at document level, not page by page, but it does not make final semantic decisions.

### 7.1 Entity detectors

Required detectors:

```text
heading_section_detector
toc_entry_detector
page_number_detector
footnote_detector
equation_detector
caption_detector
figure_table_detector
reference_section_detector
reference_item_detector
header_footer_detector
```

Each detector returns `EntityProposal` objects with:

```text
entity_type
canonical_text
page_no
block_ids
confidence
confidence_source = "heuristic"
calibration_key
evidence
metadata.detector
```

---

### 7.2 Required detection rules

#### Section proposals

Input signal:

```text
BlockKind.HEADING
markdown heading level in block metadata
numbered heading pattern such as "1 Introduction", "2.3 Methods"
```

Entity:

```text
entity_type = section
```

Metadata:

```json
{
  "heading_level": 1,
  "numbering": "2.3",
  "detector": "heading_section_detector"
}
```

#### TOC entry proposals

Input signal:

```text
A line with dotted leaders and terminal page number:
"2.3 Methods ........ 15"
```

Entity:

```text
entity_type = toc_entry
```

Metadata:

```json
{
  "target_page_candidate": 15,
  "target_title_candidate": "2.3 Methods",
  "detector": "toc_entry_detector"
}
```

#### Page number proposals

Input signal:

```text
A block whose normalised text is only an integer or roman numeral.
Prefer first or last block on a page when no bbox exists.
Prefer top or bottom margin when bbox exists.
```

Entity:

```text
entity_type = page_number
```

Important:

Page number proposals must not delete or overwrite the original block. The block remains in `PageExtractionIR`; the proposal only marks it as likely page furniture.

#### Footnote proposals

Input signal:

```text
"[1] text"
"1. text"
"¹ text"
short marker plus explanatory text near page end
```

Entity:

```text
entity_type = footnote
```

Metadata:

```json
{
  "marker": "1",
  "detector": "footnote_detector"
}
```

#### Equation proposals

Input signal:

```text
display math block
LaTeX delimiters
equation number at line end, such as "(3.1)"
```

Entity:

```text
entity_type = equation
```

Metadata:

```json
{
  "equation_number": "3.1",
  "sequence_key": "equation:3.1",
  "detector": "equation_detector"
}
```

#### Caption proposals

Input signal:

```text
"Figure 1..."
"Fig. 2..."
"Table 3..."
```

Entity:

```text
entity_type = caption
```

Metadata:

```json
{
  "caption_kind": "figure",
  "caption_number": "1",
  "detector": "caption_detector"
}
```

#### Figure and table proposals

Input signal:

```text
BlockKind.FIGURE
BlockKind.TABLE
markdown image
HTML table
```

Entity:

```text
entity_type = figure | table
```

#### Reference section proposal

Input signal:

```text
Heading equal or close to:
"References"
"Bibliography"
"Works cited"
```

Entity:

```text
entity_type = reference_section
```

#### Reference item proposals

Input signal:

```text
After reference_section:
"[1] ..."
"[Author, 2020] ..."
"Author. Title. Journal..."
```

Entity:

```text
entity_type = reference_item
```

Important:

The connector may use the fact that references tend to appear at the end of the document, but it must only record this as evidence. Final partitioning into body versus references belongs to Plan 5.

#### Header and footer proposals

Input signal:

```text
Repeated short text in first or last block position across several pages.
```

Entity:

```text
entity_type = header | footer
```

Plan 2 only requires a minimal detector over synthetic fixtures. It should not attempt advanced fuzzy matching.

---

## 8. Relation proposals

Required relation proposals:

```text
caption_of
toc_points_to
sequence_next
near
```

These are weak proposals, not final links.

### 8.1 caption_of

Create when:

```text
caption entity is adjacent to a figure or table entity on the same page
```

Do not require perfect direction. If the connector is unsure, use lower confidence.

### 8.2 toc_points_to

Create when:

```text
toc_entry title text approximately matches a section title
```

Use a simple normalised containment or token-overlap rule. No fuzzy library.

### 8.3 sequence_next

Create when:

```text
equation numbers are consecutive by reading order
figure numbers are consecutive by reading order
table numbers are consecutive by reading order
reference item numbers are consecutive by reading order
```

Only emit when the sequence is obvious.

### 8.4 near

Create when:

```text
two entities are adjacent on the same page and this adjacency may matter later
```

This relation is low confidence and mostly helps debugging.

---

## 9. Per-backend connector files

Each backend gets one file:

```text
backend/deepseek/connector.py
backend/glm/connector.py
backend/mineru/connector.py
backend/paddleocr/connector.py
```

Each file is thin.

Required module-level constants:

```python
BACKEND = "deepseek"      # or glm, mineru, paddleocr
BACKEND_VERSION = None
```

Required public function:

```python
def connect(
    raw_dir: Path,
    document_id: str,
    out_dir: Path | None = None,
) -> ConnectorResult:
    ...
```

Required CLI:

```bash
python backend/<backend>/connector.py \
  --raw-dir <raw-dir> \
  --document-id <document-id> \
  --out-dir <out-dir>
```

Required CLI behaviour:

```text
--help exits 0
valid fixture raw_dir exits 0
missing raw_dir exits 1
schema-invalid output exits 1
lenient missing manifest exits 0 with warning
```

Import rule:

```text
Importing backend/<backend>/connector.py must not import heavy backend OCR packages.
```

The connector file may import:

```text
argparse
pathlib
sys
pdf2md.connectors.common
```

It must not import:

```text
torch
paddle
paddleocr
mineru
transformers
cv2
fitz
numpy
```

This is tested by importability in a clean test environment.

---

## 10. Tests as milestones

Completion is certified by pytest, not by prose.

### 10.1 tests/test_entity_contracts.py

```text
class TestEntityEnums:
    test_entity_type_values_match_specification
    test_relation_type_values_match_specification
    test_evidence_kind_values_match_specification
    test_confidence_source_values_match_specification

class TestEntityEvidence:
    test_minimal_evidence_constructs
    test_evidence_accepts_ir_bbox
    test_evidence_rejects_weight_outside_unit_interval
    test_evidence_rejects_malformed_source_block_id
    test_evidence_forbids_extra_fields

class TestEntityProposal:
    test_entity_id_pattern_accepted
    test_entity_id_pattern_rejected
    test_entity_requires_at_least_one_evidence
    test_entity_block_ids_must_match_extraction_id_pattern
    test_entity_confidence_in_unit_interval
    test_entity_forbids_extra_fields

class TestRelationProposal:
    test_relation_id_pattern_accepted
    test_relation_id_pattern_rejected
    test_relation_requires_distinct_source_and_target
    test_relation_confidence_in_unit_interval
    test_relation_requires_evidence

class TestEntityProposalDocument:
    test_minimal_document_round_trip
    test_document_rejects_duplicate_entity_ids
    test_document_rejects_duplicate_relation_ids
    test_document_rejects_relation_with_unknown_source
    test_document_rejects_relation_with_unknown_target
    test_json_schema_export_basic_shape

class TestEntityIdFactories:
    test_entity_id_format
    test_relation_id_format
    test_factories_round_trip_through_validators
```

Expected count: 30 tests.

---

### 10.2 tests/test_connector_common.py

```text
class TestMarkdownPageParsing:
    test_single_page_markdown_builds_one_page_ir
    test_page_split_marker_builds_multiple_page_irs
    test_form_feed_builds_multiple_page_irs
    test_empty_markdown_builds_no_pages_and_warning
    test_block_order_is_monotonic_per_page
    test_page_numbers_are_one_indexed

class TestBlockClassification:
    test_markdown_heading_maps_to_heading_block
    test_display_math_maps_to_formula_block
    test_html_table_maps_to_table_block
    test_markdown_image_maps_to_figure_block
    test_figure_caption_maps_to_caption_block
    test_table_caption_maps_to_caption_block
    test_list_item_maps_to_list_item_block
    test_plain_text_maps_to_paragraph_block

class TestEntityRecognition:
    test_detects_section_entities_from_headings
    test_detects_toc_entry_entities
    test_detects_page_number_entities_without_promoting_them_to_headings
    test_detects_footnote_entities
    test_detects_equation_entities_with_sequence_key
    test_detects_caption_entities
    test_detects_figure_and_table_entities
    test_detects_reference_section_entity
    test_detects_reference_items_after_reference_section
    test_confidence_values_are_in_unit_interval
    test_every_entity_has_evidence

class TestRelationRecognition:
    test_caption_of_relation_created_for_adjacent_figure
    test_caption_of_relation_created_for_adjacent_table
    test_toc_points_to_relation_created_as_proposal
    test_sequence_next_relation_created_for_numbered_equations
    test_relation_endpoints_exist_in_entity_document

class TestConnectorWriting:
    test_write_connector_result_creates_manifest_pages_and_entities
    test_written_page_files_validate_as_page_extraction_ir
    test_written_entities_file_validates_as_entity_proposal_document
    test_missing_manifest_is_warning_not_failure
    test_missing_markdown_is_warning_not_failure
```

Expected count: 36 tests.

---

### 10.3 tests/test_backend_connectors.py

```text
class TestBackendConnectorImports:
    test_deepseek_connector_imports_without_heavy_dependencies
    test_glm_connector_imports_without_heavy_dependencies
    test_mineru_connector_imports_without_heavy_dependencies
    test_paddleocr_connector_imports_without_heavy_dependencies

class TestBackendConnectorPublicApi:
    test_each_connector_exposes_backend_constant
    test_each_connector_exposes_connect_function
    test_each_connector_connect_returns_connector_result
    test_each_connector_uses_expected_backend_name

class TestBackendConnectorCli:
    test_each_connector_help_exits_zero
    test_each_connector_cli_writes_expected_files_from_simple_fixture
    test_each_connector_cli_writes_expected_files_from_semantic_fixture
    test_each_connector_cli_missing_raw_dir_exits_nonzero
```

Expected count: 12 tests if parametrised by test function, or more if parametrised per backend. The committed test file must state the exact expected count in a comment so the reviewer can verify it.

---

## 11. Fixtures

### 11.1 simple_markdown/output.md

Must include:

```markdown
# Introduction

This is a simple paragraph.

<--- Page Split --->

# Methods

Another paragraph.
```

Purpose:

```text
- page splitting
- heading detection
- paragraph mapping
- section entity proposals
```

### 11.2 semantic_markdown/output.md

Must include one compact document with:

```markdown
# Contents

1 Introduction ........ 2

<--- Page Split --->

# 1 Introduction

1

Figure 1. Crystal structure overview.

![crystal](fig1.png)

\[
E = mc^2
\]

[1] This is a footnote.

<--- Page Split --->

# References

[1] A. Author. Example paper. Journal, 2020.
```

Purpose:

```text
- TOC proposal
- section proposal
- page number proposal
- caption proposal
- figure proposal
- equation proposal
- footnote proposal
- reference section proposal
- reference item proposal
- relation proposals
```

### 11.3 empty_markdown/output.md

Must be empty or whitespace-only.

Purpose:

```text
- lenient empty output behaviour
- no hard failure
- warning propagation
```

Each fixture has a small `manifest.json`:

```json
{
  "backend": "fixture",
  "backend_version": "0.0.0",
  "source": "tests"
}
```

---

## 12. Acceptance criteria

The reviewer accepts Plan 2 only when all criteria pass.

### 12.1 Targeted tests

```bash
pytest tests/test_entity_contracts.py -q
pytest tests/test_connector_common.py -q
pytest tests/test_backend_connectors.py -q
```

All pass. No `skip`. No `xfail`.

### 12.2 Plan 1 still passes

```bash
pytest tests/test_ir_contracts.py -q
```

Must still pass with the existing Plan 1 count.

### 12.3 Existing backend runner tests still pass

```bash
pytest tests/test_run_backends_config.py -q
```

This protects the existing runner and backend wrapper behaviour.

### 12.4 Whole suite has no regression

```bash
pytest tests/ -q
```

Must pass with no regression against the previous count.

### 12.5 Whitelist check

```bash
git diff --name-only main..HEAD
```

Must be a subset of the whitelist in section 2.

### 12.6 Smoke import

```bash
python -c "from pdf2md.models.entities import EntityProposalDocument; print(EntityProposalDocument.model_json_schema()['title'])"
```

Expected output:

```text
EntityProposalDocument
```

### 12.7 Backend connector smoke test

```bash
python backend/mineru/connector.py --help
python backend/deepseek/connector.py --help
python backend/paddleocr/connector.py --help
python backend/glm/connector.py --help
```

Each exits `0`.

### 12.8 Fixture end-to-end smoke

```bash
python backend/mineru/connector.py \
  --raw-dir tests/data/connector_fixtures/semantic_markdown \
  --document-id semantic_fixture \
  --out-dir /tmp/pdf2md_connector_smoke
```

Then:

```bash
python -c "from pathlib import Path; from pdf2md.models.ir import PageExtractionIR; from pdf2md.models.entities import EntityProposalDocument; p=Path('/tmp/pdf2md_connector_smoke/mineru'); PageExtractionIR.model_validate_json((p/'pages/page_0001.json').read_text()); EntityProposalDocument.model_validate_json((p/'entities.json').read_text()); print('ok')"
```

Expected output:

```text
ok
```

---

## 13. Implementation order

### A. Entity contracts first

Implement only:

```text
src/pdf2md/models/entities.py
src/pdf2md/models/__init__.py
tests/test_entity_contracts.py
```

Run:

```bash
pytest tests/test_entity_contracts.py -q
pytest tests/test_ir_contracts.py -q
```

Reason:

The connector output schema must be frozen before writing parsing logic. This mirrors Plan 1 discipline.

---

### B. Common connector logic

Implement only:

```text
src/pdf2md/connectors/__init__.py
src/pdf2md/connectors/common.py
tests/test_connector_common.py
tests/data/connector_fixtures/*
```

Run:

```bash
pytest tests/test_entity_contracts.py tests/test_connector_common.py -q
```

Reason:

All semantic detection and markdown fallback logic should be centralised once. Backend files must remain thin.

---

### C. Backend-local connector files

Implement:

```text
backend/deepseek/connector.py
backend/glm/connector.py
backend/mineru/connector.py
backend/paddleocr/connector.py
tests/test_backend_connectors.py
```

Run:

```bash
pytest tests/test_backend_connectors.py -q
```

Reason:

This gives the requested `connector.py` in each backend while avoiding duplicate detector logic.

---

### D. Regression pass

Run:

```bash
pytest tests/test_ir_contracts.py -q
pytest tests/test_run_backends_config.py -q
pytest tests/ -q
git diff --name-only main..HEAD
```

Reason:

The reviewer must be able to certify that Plan 2 did not disturb Plan 1 or the backend runner.

---

## 14. What Plan 2 must not accidentally become

Do not implement consensus here.

Bad:

```text
"Choose the best backend block."
"Resolve conflict between MinerU and PaddleOCR."
"Use calibrated backend probability."
"Decide that this page number is definitely furniture."
"Attach every caption to final figure node."
"Build DoclingDocument."
```

Good:

```text
"Backend A proposes this block is a page number with confidence 0.68."
"Backend B proposes this caption may belong to this figure."
"This heading may correspond to this TOC entry."
"This equation appears to be number 3.1."
"This reference item appears after a References heading."
```

This is the correct level for Plan 2.

---

## 15. Practical reviewer checklist

The reviewer should ask these questions:

```text
1. Are PageExtractionIR objects produced by connector code, not by tests faking them?
2. Are entity proposals explicit Pydantic objects, not metadata blobs?
3. Are relation proposals weak and auditable?
4. Does every proposal have evidence?
5. Does every confidence stay in [0, 1]?
6. Do connector imports avoid OCR dependencies?
7. Are backend connector files thin?
8. Are backend OCR wrappers untouched?
9. Is runner untouched?
10. Does Plan 1 still pass?
11. Does the whole test suite still pass?
12. Is git diff contained inside the whitelist?
```

---

## 16. Main improvement over the earlier Plan 2 draft

This version pins:

```text
- exact file whitelist
- exact new schema
- exact output layout
- exact connector API
- exact backend-local connector requirement
- exact lenient behaviour
- exact pytest modules
- exact fixture purpose
- exact acceptance commands
- exact boundary between connector, calibration, consensus, linker, and exporter
```

This should make implementation substantially less ambiguous and easier to review.
