# Plan 5 - Semantic linker and linked structure

Status: draft, ready to implement after Plan 4  
Repo: `pdf2md`  
Owner: semantic linker layer  
Sequence: plan 5 of 6. It depends on Plans 1 to 4 and blocks Plan 6.

---

## 0. Current repository status and adequacy

The repository is ready for Plan 5.

Current achieved chain:

```text
Plan 1: PageExtractionIR and ConsensusIR contracts
Plan 2: backend connectors and EntityProposalDocument
Plan 3: calibrated priors and CalibrationPriorDocument
Plan 4: page-level ConsensusIR and consensus_report.json
```

Plan 4 is implemented as an isolated page-level consensus package:

```text
src/pdf2md/consensus/grouping.py
src/pdf2md/consensus/scoring.py
src/pdf2md/consensus/factory.py
src/pdf2md/consensus/io.py
src/pdf2md/consensus/reporting.py
tools/build_consensus.py
```

This is adequate because Plan 5 can consume `ConsensusIR` without redoing backend grouping, candidate scoring, page-local entity enrichment, or conflict creation.

Important caution:

The repository still has legacy semantic-document utilities:

```text
src/pdf2md/models/semantic_document.py
src/pdf2md/utils/semantic_document_builder.py
```

These are loose dictionary-based helpers. They can remain for compatibility, but Plan 5 must not build the new pipeline on them. Plan 5 introduces a new Pydantic `LinkedStructure` contract. Plan 6 will project `LinkedStructure` to Docling.

---

## 1. Scope and constraints

Plan 5 implements the semantic linker.

The semantic linker is a whole-document layer. It consumes page-level consensus and backend entity proposals, then resolves document-level structure that page-local consensus cannot resolve safely.

It builds:

```text
linked_structure.json
reports/linking_report.json
```

The linked structure captures:

```text
document nodes
reading order
section hierarchy
TOC entries and section targets
page number sequence
headers and footers
footnote anchors
captions and their target figures/tables
equation sequence
figure/table sequence
reference section and reference items
bibliographic mentions
unresolved semantic conflicts
```

Hard constraints:

```text
- No new runtime dependencies.
- No OCR execution in tests.
- No conda calls in tests.
- No modification to Plan 1 IR contracts.
- No modification to Plan 2 entity or connector contracts.
- No modification to Plan 3 prior contracts.
- No modification to Plan 4 consensus contracts.
- No modification to backend OCR wrappers.
- No modification to src/pdf2md/backends/runner.py.
- No modification to src/pdf2md/cli/main.py.
- Semantic linking must be lenient: unresolved links become warnings and unresolved relation candidates, not hard failures.
- Invalid input JSON or schema-invalid objects may fail in strict mode.
- Tests must use synthetic fixtures, not real LaTeX compilation or real OCR.
```

Out of scope:

```text
- Running local backend models.
- Ground-truth generation.
- Calibrating priors.
- Page-level consensus.
- Changing ConsensusIR in-place.
- Docling export.
- Pandoc export.
- RAG export.
```

---

## 2. File whitelist

The reviewer rejects the plan if any implementation modifies files outside this whitelist.

```text
src/pdf2md/models/__init__.py
src/pdf2md/models/linked.py

src/pdf2md/linking/__init__.py
src/pdf2md/linking/extract.py
src/pdf2md/linking/resolvers.py
src/pdf2md/linking/builder.py
src/pdf2md/linking/io.py
src/pdf2md/linking/reporting.py

tools/build_linked_structure.py

tests/test_linked_structure_contracts.py
tests/test_linking_extract.py
tests/test_linking_resolvers.py
tests/test_linked_structure_builder.py
tests/test_build_linked_structure_cli.py

tests/data/linking_fixtures/simple_document/consensus_ir.json
tests/data/linking_fixtures/simple_document/consensus_report.json
tests/data/linking_fixtures/simple_document/entities/mineru.json
tests/data/linking_fixtures/simple_document/entities/paddleocr.json
tests/data/linking_fixtures/simple_document/priors/mineru.json
tests/data/linking_fixtures/simple_document/priors/paddleocr.json

tests/data/linking_fixtures/toc_footnotes_references/consensus_ir.json
tests/data/linking_fixtures/toc_footnotes_references/consensus_report.json
tests/data/linking_fixtures/toc_footnotes_references/entities/mineru.json
tests/data/linking_fixtures/toc_footnotes_references/entities/paddleocr.json
tests/data/linking_fixtures/toc_footnotes_references/priors/mineru.json
tests/data/linking_fixtures/toc_footnotes_references/priors/paddleocr.json

tests/data/linking_fixtures/unresolved_ambiguity/consensus_ir.json
tests/data/linking_fixtures/unresolved_ambiguity/consensus_report.json
tests/data/linking_fixtures/unresolved_ambiguity/entities/mineru.json
tests/data/linking_fixtures/unresolved_ambiguity/priors/mineru.json
```

Explicit non-whitelist files:

```text
src/pdf2md/models/ir.py
src/pdf2md/models/entities.py
src/pdf2md/models/priors.py
src/pdf2md/connectors/common.py
src/pdf2md/calibration/*
src/pdf2md/consensus/*
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
pyproject.toml
current_plan.md
```

Rationale:

Plan 5 consumes Plans 1 to 4. If it requires changing those contracts, the earlier plan is not frozen. Do not do that here.

---

## 3. Inputs and outputs

### Required input

```text
consensus_ir.json
```

Must validate as:

```text
pdf2md.models.ir.ConsensusIR
```

### Optional inputs

```text
reports/consensus_report.json
entities/<backend>.json
entities/<backend>/entities.json
priors/<backend>.json
```

Entity files must validate as `EntityProposalDocument`. Prior files must validate as `CalibrationPriorDocument`.

Rules:

```text
- missing consensus_ir.json: fatal.
- missing consensus report: warning, continue.
- missing entities root: warning, continue with ConsensusIR only.
- missing priors root: warning, use default confidence.
- invalid optional file: warning in lenient mode, exception in strict mode.
```

### Output

```text
<out-dir>/linked_structure.json
<out-dir>/reports/linking_report.json
```

`linked_structure.json` must validate as:

```text
pdf2md.models.linked.LinkedStructure
```

---

## 4. New schema: LinkedStructure

File:

```text
src/pdf2md/models/linked.py
```

This module contains Pydantic v2 models and pure id helpers only. No I/O.

Schema version:

```python
LINKED_SCHEMA_VERSION = "1.0.0"
```

All models use:

```python
ConfigDict(extra="forbid", frozen=False, populate_by_name=True, use_enum_values=True)
```

### 4.1 Enums

```python
class LinkedNodeType(str, Enum):
    DOCUMENT = "document"
    TITLE = "title"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    EQUATION = "equation"
    FOOTNOTE = "footnote"
    PAGE_NUMBER = "page_number"
    HEADER = "header"
    FOOTER = "footer"
    TOC_ENTRY = "toc_entry"
    REFERENCE_SECTION = "reference_section"
    REFERENCE_ITEM = "reference_item"
    BIBLIOGRAPHY_MARKER = "bibliography_marker"
    CODE = "code"
    UNKNOWN = "unknown"
```

```python
class LinkedRelationType(str, Enum):
    CONTAINS = "contains"
    FOLLOWS = "follows"
    PARENT_OF = "parent_of"
    CAPTION_OF = "caption_of"
    FOOTNOTE_ANCHOR_FOR = "footnote_anchor_for"
    TOC_POINTS_TO = "toc_points_to"
    REFERENCES = "references"
    EQUATION_SEQUENCE_NEXT = "equation_sequence_next"
    FIGURE_SEQUENCE_NEXT = "figure_sequence_next"
    TABLE_SEQUENCE_NEXT = "table_sequence_next"
    REFERENCE_SEQUENCE_NEXT = "reference_sequence_next"
    PAGE_NUMBER_SEQUENCE_NEXT = "page_number_sequence_next"
    HEADER_REPEATS_AS = "header_repeats_as"
    FOOTER_REPEATS_AS = "footer_repeats_as"
    DERIVED_FROM_CONSENSUS = "derived_from_consensus"
    UNRESOLVED_CANDIDATE = "unresolved_candidate"
```

```python
class LinkStatus(str, Enum):
    RESOLVED = "resolved"
    RESOLVED_LOW_CONFIDENCE = "resolved_low_confidence"
    UNRESOLVED = "unresolved"
```

```python
class LinkEvidenceKind(str, Enum):
    CONSENSUS_BLOCK = "consensus_block"
    ENTITY_PROPOSAL = "entity_proposal"
    RELATION_PROPOSAL = "relation_proposal"
    PRIOR = "prior"
    TEXT_PATTERN = "text_pattern"
    READING_ORDER = "reading_order"
    PAGE_SEQUENCE = "page_sequence"
    TOC_PATTERN = "toc_pattern"
    SECTION_HIERARCHY = "section_hierarchy"
    REFERENCE_PATTERN = "reference_pattern"
    CAPTION_PATTERN = "caption_pattern"
    FOOTNOTE_PATTERN = "footnote_pattern"
```

### 4.2 LinkEvidence

```python
class LinkEvidence(BaseModel):
    kind: LinkEvidenceKind
    source_id: str | None
    page_no: int | None
    confidence: float
    reason: str
    metadata: dict[str, Any]
```

Validation:

```text
- page_no >= 1 when present.
- confidence in [0.0, 1.0].
- reason is non-empty.
- extra fields are forbidden.
```

### 4.3 LinkedNode

```python
class LinkedNode(BaseModel):
    id: str
    node_type: LinkedNodeType
    text: str | None
    page_no: int | None
    order: int
    consensus_block_id: str | None
    source_backend: str | None
    source_entity_ids: list[str]
    confidence: float
    status: LinkStatus
    evidence: list[LinkEvidence]
    metadata: dict[str, Any]
```

ID pattern:

```text
^node:[A-Za-z0-9_.-]+:\d+$
```

Validation:

```text
- page_no >= 1 when present.
- order >= 0.
- confidence in [0.0, 1.0].
- evidence has at least one item.
- consensus_block_id, when present, matches ConsensusBlock id pattern.
- source_entity_ids, when present, match EntityProposal id pattern.
- extra fields are forbidden.
```

Node id factory:

```python
linked_node_id(document_id: str, index: int) -> str
```

### 4.4 LinkedRelation

```python
class LinkedRelation(BaseModel):
    id: str
    relation_type: LinkedRelationType
    source_node_id: str
    target_node_id: str
    confidence: float
    status: LinkStatus
    evidence: list[LinkEvidence]
    metadata: dict[str, Any]
```

ID pattern:

```text
^lrel:[A-Za-z0-9_.-]+:\d+$
```

Validation:

```text
- source_node_id and target_node_id match LinkedNode id pattern.
- source_node_id != target_node_id.
- confidence in [0.0, 1.0].
- evidence has at least one item.
- extra fields are forbidden.
```

Relation id factory:

```python
linked_relation_id(document_id: str, index: int) -> str
```

### 4.5 LinkedConflict

```python
class LinkedConflict(BaseModel):
    id: str
    conflict_type: str
    source_conflict_id: str | None
    node_ids: list[str]
    relation_ids: list[str]
    description: str
    status: LinkStatus
    evidence: list[LinkEvidence]
    metadata: dict[str, Any]
```

Validation:

```text
- id is non-empty.
- source_conflict_id, when present, matches Conflict id pattern.
- node_ids match LinkedNode id pattern.
- relation_ids match LinkedRelation id pattern.
- description is non-empty.
- evidence has at least one item.
- extra fields are forbidden.
```

Conflict id factory:

```python
linked_conflict_id(document_id: str, index: int) -> str
```

### 4.6 LinkedStructure

```python
class LinkedStructure(BaseModel):
    schema_name: Literal["pdf2md.LinkedStructure"]
    schema_version: Literal["1.0.0"]
    document_id: str
    source_consensus_ir: str | None
    source_consensus_report: str | None
    source_entity_documents: list[str]
    source_prior_documents: list[str]
    nodes: list[LinkedNode]
    relations: list[LinkedRelation]
    conflicts: list[LinkedConflict]
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- document_id is non-empty.
- node ids are unique.
- relation ids are unique.
- conflict ids are unique.
- every relation endpoint exists in nodes.
- every conflict node id exists in nodes.
- every conflict relation id exists in relations.
- extra fields are forbidden.
```

Re-export from:

```text
src/pdf2md/models/__init__.py
```

Append only. Do not remove Plan 1 to Plan 4 exports.

---

## 5. Linker modules

Plan 5 introduces:

```text
src/pdf2md/linking/extract.py
src/pdf2md/linking/resolvers.py
src/pdf2md/linking/builder.py
src/pdf2md/linking/io.py
src/pdf2md/linking/reporting.py
src/pdf2md/linking/__init__.py
```

No module imports OCR backends.

No module imports legacy `semantic_document_builder`.

---

## 6. Extraction layer

File:

```text
src/pdf2md/linking/extract.py
```

Public API:

```python
@dataclass(frozen=True)
class LinkCandidate:
    consensus_block_id: str
    node_type: LinkedNodeType
    text: str
    page_no: int
    order: int
    source_backend: str | None
    source_entity_ids: tuple[str, ...]
    confidence: float
    metadata: dict[str, Any]
```

```python
def consensus_block_to_node_type(block: ConsensusBlock) -> LinkedNodeType: ...
def entity_support_for_block(*, consensus_block: ConsensusBlock, entities_by_backend: dict[str, EntityProposalDocument]) -> list[EntityProposal]: ...
def extract_link_candidates(*, consensus: ConsensusIR, entities_by_backend: dict[str, EntityProposalDocument], priors_by_backend: dict[str, CalibrationPriorDocument]) -> list[LinkCandidate]: ...
def normalise_text(text: str | None) -> str: ...
```

Mapping from `ConsensusBlock.kind`:

```text
heading      -> section
paragraph    -> paragraph
formula      -> equation
figure       -> figure
table        -> table
caption      -> caption
list         -> list
list_item    -> list_item
footnote     -> footnote
page_number  -> page_number
header       -> header
footer       -> footer
reference    -> reference_item
bibitem      -> reference_item
code         -> code
unknown      -> unknown
```

Entity proposals may refine the type when they support the consensus block through `ConsensusBlock.candidate_ids`.

Example:

```text
ConsensusBlock.kind = paragraph
EntityProposal.entity_type = toc_entry
entity.block_ids intersects ConsensusBlock.candidate_ids
=> LinkCandidate.node_type = toc_entry
```

---

## 7. Resolver layer

File:

```text
src/pdf2md/linking/resolvers.py
```

Public API:

```python
@dataclass(frozen=True)
class ResolvedLink:
    relation_type: LinkedRelationType
    source_candidate_id: str
    target_candidate_id: str
    confidence: float
    status: LinkStatus
    evidence: tuple[LinkEvidence, ...]
    metadata: dict[str, Any]
```

```python
@dataclass(frozen=True)
class ResolverResult:
    links: tuple[ResolvedLink, ...]
    warnings: tuple[str, ...]
```

Required resolvers:

```python
def resolve_reading_order(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_section_hierarchy(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_toc_links(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_page_number_sequence(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_repeating_headers_footers(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_captions(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_footnotes(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_equation_sequence(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_figure_table_sequence(candidates: list[LinkCandidate]) -> ResolverResult: ...
def resolve_references(candidates: list[LinkCandidate]) -> ResolverResult: ...
def run_all_resolvers(candidates: list[LinkCandidate]) -> ResolverResult: ...
```

---

## 8. Required resolver behaviour

### Reading order

Create `FOLLOWS` links between adjacent body candidates.

Rules:

```text
- Sort by page_no, then order.
- Exclude page_number, header, footer.
- Include sections, paragraphs, lists, figures, tables, captions, equations, footnotes, reference items.
```

### Section hierarchy

Create `PARENT_OF` and `CONTAINS` relations.

Rules:

```text
- Section level comes from metadata when available.
- Else infer from numbered headings such as "1", "1.2", "1.2.3".
- Else default to level 1 and warn.
- A section is parent of later deeper sections until an equal or higher-level section appears.
- Body blocks after a section are contained by the nearest preceding section.
```

Warnings:

```text
section_level_missing:<node_id>
```

### TOC links

Create `TOC_POINTS_TO` links.

Rules:

```text
- Parse dotted leader lines such as "2.3 Methods ........ 15".
- Match by exact title, then target page plus token overlap, then strong token overlap.
```

Warnings:

```text
toc_target_missing:<node_id>
toc_target_ambiguous:<node_id>
```

### Page number sequence

Create `PAGE_NUMBER_SEQUENCE_NEXT` links.

Rules:

```text
- Arabic numerals and roman numerals are supported.
- PDF page_no is the monotonic anchor.
- Roman front matter may switch to Arabic body numbering.
- A footnote-like number must not be forced into page number sequence.
```

Warnings:

```text
page_number_sequence_gap:<node_id>
page_number_sequence_conflict:<node_id>
```

### Repeating headers and footers

Create `HEADER_REPEATS_AS` and `FOOTER_REPEATS_AS` links when the same normalised text appears in header/footer position on two or more pages.

Pure page numbers must not be marked as repeating footers.

### Captions

Create `CAPTION_OF` links.

Rules:

```text
- Figure captions target nearest figure on same page.
- Table captions target nearest table on same page.
- Prefer explicit caption kind and number.
- Adjacent-page targets are allowed only as low confidence.
- Do not cross more than one page.
```

Warnings:

```text
caption_target_missing:<node_id>
caption_target_ambiguous:<node_id>
```

### Footnotes

Create `FOOTNOTE_ANCHOR_FOR` links.

Rules:

```text
- Parse footnote markers such as [1], 1., and superscript-like digits.
- Prefer same page anchors.
- Never link a footnote to a page_number node.
```

Warnings:

```text
footnote_anchor_missing:<node_id>
footnote_anchor_ambiguous:<node_id>
```

### Equations

Create `EQUATION_SEQUENCE_NEXT` links.

Rules:

```text
- Extract equation numbers from text or metadata.
- Link consecutive equations in reading order.
- Number gaps are warnings, not failures.
```

### Figures and tables

Create:

```text
FIGURE_SEQUENCE_NEXT
TABLE_SEQUENCE_NEXT
```

Rules:

```text
- Extract numbers from captions or metadata.
- Link consecutive numbers.
- Prefer target object node over caption node when CAPTION_OF exists.
```

### References

Create:

```text
REFERENCE_SEQUENCE_NEXT
REFERENCES
```

Rules:

```text
- Detect reference section by section title: References, Bibliography, Works cited.
- Reference items after this section are bibliography material.
- Reference items with markers [1], [2], etc. get sequence links.
- Body mentions like [1] or (Author, 2020) may link to reference items.
```

Warnings:

```text
reference_section_missing
reference_target_missing:<node_id>
reference_target_ambiguous:<node_id>
```

---

## 9. Builder layer

File:

```text
src/pdf2md/linking/builder.py
```

Public API:

```python
@dataclass(frozen=True)
class LinkerSettings:
    strict: bool = False
    default_confidence: float = 0.50
    low_confidence_threshold: float = 0.60
```

```python
@dataclass(frozen=True)
class LinkerRunResult:
    linked: LinkedStructure
    report: dict[str, Any]
    warnings: list[str]
```

```python
def build_linked_structure(
    *,
    consensus: ConsensusIR,
    entities_by_backend: dict[str, EntityProposalDocument],
    priors_by_backend: dict[str, CalibrationPriorDocument],
    consensus_report: dict[str, Any] | None = None,
    source_consensus_ir: str | None = None,
    source_consensus_report: str | None = None,
    source_entity_documents: list[str] | None = None,
    source_prior_documents: list[str] | None = None,
    settings: LinkerSettings = LinkerSettings(),
) -> LinkerRunResult: ...
```

Build steps:

```text
1. Extract LinkCandidate objects from ConsensusIR.
2. Create one LinkedNode per candidate.
3. Always create a document node.
4. Add DERIVED_FROM_CONSENSUS relation from document node to every non-document node.
5. Run all resolvers.
6. Convert ResolvedLink objects to LinkedRelation objects.
7. Preserve source ConsensusIR conflicts as LinkedConflict objects.
8. Convert unresolved resolver warnings into LinkedConflict objects when node-specific.
9. Validate LinkedStructure through Pydantic.
10. Build linking_report.json.
```

Document node:

```text
id = node:<document_id>:0
node_type = document
page_no = None
order = 0
text = None
confidence = 1.0
status = resolved
```

---

## 10. I/O layer

File:

```text
src/pdf2md/linking/io.py
```

Public API:

```python
@dataclass(frozen=True)
class LinkerLoadResult:
    consensus: ConsensusIR
    consensus_report: dict[str, Any] | None
    entities_by_backend: dict[str, EntityProposalDocument]
    priors_by_backend: dict[str, CalibrationPriorDocument]
    source_entity_documents: list[str]
    source_prior_documents: list[str]
    warnings: list[str]
```

```python
def load_linker_inputs(
    *,
    consensus_ir_path: Path,
    consensus_report_path: Path | None = None,
    entities_root: Path | None = None,
    priors_root: Path | None = None,
    strict: bool = False,
) -> LinkerLoadResult: ...
```

```python
def write_linker_outputs(*, result: LinkerRunResult, out_dir: Path) -> None: ...
```

Lenient warnings:

```text
consensus_report_missing
entities_root_missing
priors_root_missing
entities_missing:<backend>
prior_missing:<backend>
invalid_consensus_ir
invalid_consensus_report
invalid_entities:<backend>
invalid_prior:<backend>
```

Only invalid or missing `consensus_ir.json` is fatal in lenient mode.

---

## 11. Reporting

File:

```text
src/pdf2md/linking/reporting.py
```

Report shape:

```json
{
  "schema_name": "pdf2md.LinkingReport",
  "schema_version": "1.0.0",
  "document_id": "doc-1",
  "node_count": 12,
  "relation_count": 20,
  "conflict_count": 1,
  "warnings": [],
  "node_type_counts": {"section": 2},
  "relation_type_counts": {"follows": 8},
  "unresolved": [{"id": "lconf:doc-1:0", "conflict_type": "footnote_anchor_missing"}]
}
```

The report is an audit artefact. Plan 6 consumes `linked_structure.json`, not the report.

---

## 12. CLI tool

File:

```text
tools/build_linked_structure.py
```

Required CLI:

```bash
python tools/build_linked_structure.py \
  --consensus-ir tests/data/linking_fixtures/simple_document/consensus_ir.json \
  --consensus-report tests/data/linking_fixtures/simple_document/consensus_report.json \
  --entities-root tests/data/linking_fixtures/simple_document/entities \
  --priors-root tests/data/linking_fixtures/simple_document/priors \
  --out-dir /tmp/pdf2md_linked
```

Required options:

```text
--consensus-ir PATH
--consensus-report PATH       optional
--entities-root PATH          optional
--priors-root PATH            optional
--out-dir PATH
--strict
--verbose
--low-confidence-threshold FLOAT default 0.60
```

Exit codes:

```text
0 = linked structure written successfully, even if warnings exist
1 = invalid CLI arguments or strict-mode input failure
```

---

## 13. Tests as milestones

Completion is certified by pytest, not by prose.

### 13.1 `tests/test_linked_structure_contracts.py`

Expected count: 34 tests.

Must cover:

```text
- enum values
- LinkEvidence validation
- LinkedNode validation
- LinkedRelation validation
- LinkedConflict validation
- LinkedStructure round trip
- duplicate ids rejected
- relation endpoints must exist
- conflict node and relation ids must exist
- id factories round trip through validators
- JSON Schema export
```

### 13.2 `tests/test_linking_extract.py`

Expected count: 16 tests.

Must cover:

```text
- ConsensusBlock kind to node type mapping
- entity support through ConsensusBlock.candidate_ids
- TOC entity refines paragraph to toc_entry
- reference section entity refines heading to reference_section
- one LinkCandidate per ConsensusBlock
- page/order/source backend preservation
- prior confidence usage when available
```

### 13.3 `tests/test_linking_resolvers.py`

Expected count: 32 tests.

Must cover:

```text
- reading order FOLLOWS links
- section hierarchy
- TOC links
- page number sequence
- repeated headers and footers
- caption links
- footnote anchor links
- equation sequence
- figure/table sequence
- reference section, reference sequence, and body references
- warnings for missing or ambiguous targets
```

### 13.4 `tests/test_linked_structure_builder.py`

Expected count: 16 tests.

Must cover:

```text
- simple document builds valid LinkedStructure
- document node is created
- every ConsensusBlock becomes a node
- all nodes derive from document or consensus
- expected FOLLOWS, CONTAINS, CAPTION_OF, TOC_POINTS_TO, FOOTNOTE_ANCHOR_FOR, REFERENCES relations
- unresolved ambiguity creates LinkedConflict
- source ConsensusIR conflicts are preserved
- missing entities and priors warn but build
- Pydantic round trip
- report counts match structure
```

### 13.5 `tests/test_build_linked_structure_cli.py`

Expected count: 12 tests.

Must cover:

```text
- load_linker_inputs reads consensus, entities, and priors
- lenient missing entities/prior roots warn
- strict invalid optional input raises
- write_linker_outputs writes both files
- CLI help exits zero
- CLI writes valid linked_structure.json
- CLI unresolved fixture writes conflict
- CLI missing optional inputs succeeds leniently
```

---

## 14. Fixtures

### 14.1 `simple_document`

Shape:

```text
page 1:
  section "Introduction"
  paragraph "This is the introduction."
  figure
  caption "Figure 1. Example figure."
```

Expected:

```text
document node
section node
paragraph node
figure node
caption node
FOLLOWS relations
CONTAINS or PARENT_OF relations
CAPTION_OF relation
no conflicts
```

### 14.2 `toc_footnotes_references`

Shape:

```text
page 1:
  section "Contents"
  toc_entry "1 Introduction ........ 2"

page 2:
  section "1 Introduction"
  paragraph with footnote marker [1]
  footnote "[1] Footnote text."
  equation "(1)"
  equation "(2)"

page 3:
  section "References"
  reference item "[1] A. Author. Example paper. Journal, 2020."
  reference item "[2] B. Author. Second paper. Journal, 2021."
  paragraph with body reference marker [1]
```

Expected:

```text
TOC_POINTS_TO
FOOTNOTE_ANCHOR_FOR
EQUATION_SEQUENCE_NEXT
REFERENCE_SEQUENCE_NEXT
REFERENCES
page number sequence when page numbers are present
```

### 14.3 `unresolved_ambiguity`

Shape:

```text
ConsensusIR contains an unresolved conflict from Plan 4.
Entity proposals are insufficient to resolve it.
```

Expected:

```text
LinkedStructure preserves source conflict as LinkedConflict.
No fake relation is created.
Warnings include unresolved semantic ambiguity.
```

---

## 15. Acceptance criteria

The reviewer accepts Plan 5 only when all criteria pass.

### 15.1 Targeted tests

```bash
pytest tests/test_linked_structure_contracts.py -q
pytest tests/test_linking_extract.py -q
pytest tests/test_linking_resolvers.py -q
pytest tests/test_linked_structure_builder.py -q
pytest tests/test_build_linked_structure_cli.py -q
```

All pass. No `skip`. No `xfail`.

### 15.2 Plans 1 to 4 still pass

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
```

All pass.

### 15.3 Existing legacy tests still pass

```bash
pytest tests/test_run_backends_config.py -q
pytest tests/test_semantic_document_builder.py -q
```

Plan 5 does not use the legacy builder, but it must not break it.

### 15.4 Whole suite has no regression

```bash
pytest tests/ -q
```

Must pass with no regression against the previous count.

### 15.5 Whitelist check

```bash
git diff --name-only main..HEAD
```

Must be a subset of the whitelist in section 2.

### 15.6 Smoke import

```bash
python -c "from pdf2md.models.linked import LinkedStructure; print(LinkedStructure.model_json_schema()['title'])"
```

Expected output:

```text
LinkedStructure
```

### 15.7 CLI smoke test

```bash
python tools/build_linked_structure.py \
  --consensus-ir tests/data/linking_fixtures/simple_document/consensus_ir.json \
  --consensus-report tests/data/linking_fixtures/simple_document/consensus_report.json \
  --entities-root tests/data/linking_fixtures/simple_document/entities \
  --priors-root tests/data/linking_fixtures/simple_document/priors \
  --out-dir /tmp/pdf2md_linking_smoke
```

Then:

```bash
python -c "from pathlib import Path; from pdf2md.models.linked import LinkedStructure; p=Path('/tmp/pdf2md_linking_smoke/linked_structure.json'); LinkedStructure.model_validate_json(p.read_text()); print('ok')"
```

Expected output:

```text
ok
```

---

## 16. Implementation order

### A. LinkedStructure contracts first

Implement only:

```text
src/pdf2md/models/linked.py
src/pdf2md/models/__init__.py
tests/test_linked_structure_contracts.py
```

Run:

```bash
pytest tests/test_linked_structure_contracts.py -q
pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
pytest tests/test_prior_contracts.py -q
```

### B. Extraction layer

Implement:

```text
src/pdf2md/linking/__init__.py
src/pdf2md/linking/extract.py
tests/test_linking_extract.py
```

Run:

```bash
pytest tests/test_linking_extract.py -q
```

### C. Resolver layer

Implement:

```text
src/pdf2md/linking/resolvers.py
tests/test_linking_resolvers.py
```

Run:

```bash
pytest tests/test_linking_resolvers.py -q
```

### D. Builder and report

Implement:

```text
src/pdf2md/linking/builder.py
src/pdf2md/linking/reporting.py
tests/test_linked_structure_builder.py
tests/data/linking_fixtures/*
```

Run:

```bash
pytest tests/test_linked_structure_builder.py -q
```

### E. I/O and CLI

Implement:

```text
src/pdf2md/linking/io.py
tools/build_linked_structure.py
tests/test_build_linked_structure_cli.py
```

Run:

```bash
pytest tests/test_build_linked_structure_cli.py -q
```

### F. Regression pass

Run all Plan 5 targeted tests, all Plan 1 to 4 targeted tests, legacy tests, full suite, and whitelist check.

---

## 17. What Plan 5 must not accidentally become

Do not implement Docling export here.

Bad:

```text
"Build DoclingDocument."
"Emit docling.json."
"Emit markdown."
"Emit RAG chunks."
"Map LinkedStructure to Docling groups and texts."
"Call docling-core."
```

Good:

```text
"Attach caption to figure in LinkedStructure."
"Resolve TOC entry to section node."
"Mark unresolved footnote anchor as LinkedConflict."
"Create reference sequence relations."
"Write linked_structure.json and linking_report.json."
```

---

## 18. Practical reviewer checklist

```text
1. Does Plan 5 consume ConsensusIR from Plan 4?
2. Does it consume EntityProposalDocument from Plan 2 when available?
3. Does it consume CalibrationPriorDocument from Plan 3 when available?
4. Does it emit valid LinkedStructure?
5. Does every node have evidence?
6. Does every relation have evidence?
7. Are unresolved links represented explicitly?
8. Are source ConsensusIR conflicts preserved?
9. Are page numbers handled with document sequence logic?
10. Are footnotes prevented from linking to page numbers?
11. Are TOC, captions, references, and equations resolved by document-level rules?
12. Is Docling export absent?
13. Are legacy semantic-document files untouched?
14. Is git diff contained inside the whitelist?
```

---

## 19. Main design boundary for Plan 6

Plan 6 may consume:

```text
LinkedStructure
ConsensusIR
EntityProposalDocument
CalibrationPriorDocument
```

Plan 6 may then project to:

```text
DoclingDocument
rich semantic JSON
markdown preview
RAG-friendly chunks
```

Plan 5 must not do these projections. It produces the stable graph that makes those projections safe.

---

## PR_review #2

- verdict: pass
- whitelist_violations: []
- test_contract_violations: []
- dependency_violations: []
- tasks_promoted: []
- notes:
  - Latest agent-mode PR #2 only changed Plan 5 implementation files, Plan 5 tests, and `run_log.md`; these are within the Plan 5 whitelist or the always-whitelisted run log.
  - Targeted Plan 5 tests now collect the expected 110 tests and all targeted suites pass with no skips or xfails.
  - Plans 1 to 4 regression tests, legacy tests, full `pytest tests/ -q`, import smoke, and CLI smoke pass.
  - `git diff --name-only main..HEAD` remains an environment-limited check because this checkout has no `main` ref; this is correctly recorded in `run_log.md`.
  - No dependency additions or external tool installs were recorded.
  - No `## Status` task table exists in this plan document, so no task-state promotion was written during this review.

---

## Feedback #2

- decision: accepted
- accepted_pr_review: PR_review #2
- status: complete
- notes:
  - Human feedback accepts the Plan 5 semantic linker implementation after the passing PR_review #2 verdict.
  - Plan 5 is considered complete and ready to be archived or used as the basis for Plan 6 when explicitly requested.
  - No further implementation changes are requested for Plan 5 in this feedback entry.

---

## Status

Plan 5 complete — accepted in Feedback #2 after PR_review #2 passed.
