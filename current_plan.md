# Plan 4 - Consensus factory v2

Status: draft, ready to implement after Plan 3
Repo: `pdf2md`
Owner: consensus layer
Sequence: this is plan 4 of 6. It depends on Plans 1, 2, and 3. It blocks Plan 5.

---

## 0. Current repository status and adequacy

The repository is now in the right state for Plan 4.

Plan 1 provides the canonical `ConsensusIR` output contract, including `ConsensusBlock`, `Conflict`, `BackendManifest`, id factories, conflict ids, candidate ids, and unresolved selection semantics.

Plan 2 provides backend-local connectors. Each backend connector emits:

```text
<connector-output>/<backend>/
  manifest.json
  pages/page_0001.json
  entities.json
```

where `pages/*.json` validate as `PageExtractionIR` and `entities.json` validates as `EntityProposalDocument`.

Plan 3 provides calibrated priors. It defines:

```text
CalibrationPriorDocument
CalibrationTruthDocument
lookup_confidence(...)
tools/calibrate_priors.py
```

The Plan 3 prior document exposes calibrated confidence for:

```text
block_kind
entity_type
relation_type
calibration_key
```

Therefore Plan 4 should not invent a new scoring contract. It must consume:

```text
PageExtractionIR
EntityProposalDocument
CalibrationPriorDocument
```

and emit only:

```text
ConsensusIR
consensus_report.json
```

The important architectural caution is that old semantic-document code still exists in the repository. Plan 4 must not reuse it as a hidden linker. It may remain untouched for compatibility, but the new consensus factory must stop at page-level consensus. Plan 5 will do document-level semantic linking.

---

## 1. Scope and constraints

Plan 4 implements the consensus factory.

The consensus factory is a page-level resolver. It groups candidate blocks from multiple backend connector outputs, scores them using calibrated priors, selects a canonical block when evidence is sufficient, and records explicit conflicts when evidence is ambiguous.

This plan does not perform whole-document semantic linking. It does not resolve TOC to sections. It does not attach footnotes to anchors. It does not attach captions globally. It does not decide the reference section globally. It does not export Docling.

The output of Plan 4 is:

```text
<out-dir>/
  consensus_ir.json
  reports/
    consensus_report.json
```

`consensus_ir.json` must validate as `pdf2md.models.ir.ConsensusIR`.

Hard constraints:

```text
- No new runtime dependencies.
- No OCR execution in tests.
- No conda calls in tests.
- No modification to Plan 1 IR contracts.
- No modification to Plan 2 entity or connector contracts.
- No modification to Plan 3 prior contracts.
- No modification to backend OCR wrappers.
- No modification to src/pdf2md/backends/runner.py.
- No modification to src/pdf2md/cli/main.py.
- Consensus must be lenient: missing entity files, missing prior files, missing backend pages, or empty pages produce warnings, not hard failure.
- Invalid input JSON or schema-invalid objects may fail in strict mode.
- Tests must use synthetic fixtures, not real LaTeX compilation or real OCR.
```

Out of scope:

```text
- Running local backend models.
- Generating ground truth.
- Calibrating priors.
- Updating connector confidence values in-place.
- Whole-document semantic linker.
- Linked structure.
- Docling exporter.
- RAG export.
```

---

## 2. File whitelist

The reviewer rejects the plan if any implementation modifies files outside this whitelist.

```text
src/pdf2md/consensus/__init__.py
src/pdf2md/consensus/grouping.py
src/pdf2md/consensus/scoring.py
src/pdf2md/consensus/factory.py
src/pdf2md/consensus/io.py
src/pdf2md/consensus/reporting.py

tools/build_consensus.py

tests/test_consensus_grouping.py
tests/test_consensus_scoring.py
tests/test_consensus_factory.py
tests/test_build_consensus_cli.py

tests/data/consensus_fixtures/simple_agreement/mineru/entities.json
tests/data/consensus_fixtures/simple_agreement/mineru/pages/page_0001.json
tests/data/consensus_fixtures/simple_agreement/mineru/manifest.json
tests/data/consensus_fixtures/simple_agreement/paddleocr/entities.json
tests/data/consensus_fixtures/simple_agreement/paddleocr/pages/page_0001.json
tests/data/consensus_fixtures/simple_agreement/paddleocr/manifest.json
tests/data/consensus_fixtures/simple_agreement/priors/mineru.json
tests/data/consensus_fixtures/simple_agreement/priors/paddleocr.json

tests/data/consensus_fixtures/ambiguous_page_number/mineru/entities.json
tests/data/consensus_fixtures/ambiguous_page_number/mineru/pages/page_0001.json
tests/data/consensus_fixtures/ambiguous_page_number/mineru/manifest.json
tests/data/consensus_fixtures/ambiguous_page_number/paddleocr/entities.json
tests/data/consensus_fixtures/ambiguous_page_number/paddleocr/pages/page_0001.json
tests/data/consensus_fixtures/ambiguous_page_number/paddleocr/manifest.json
tests/data/consensus_fixtures/ambiguous_page_number/priors/mineru.json
tests/data/consensus_fixtures/ambiguous_page_number/priors/paddleocr.json

tests/data/consensus_fixtures/single_source/deepseek/entities.json
tests/data/consensus_fixtures/single_source/deepseek/pages/page_0001.json
tests/data/consensus_fixtures/single_source/deepseek/manifest.json
tests/data/consensus_fixtures/single_source/priors/deepseek.json
```

Explicit non-whitelist files:

```text
src/pdf2md/models/ir.py
src/pdf2md/models/entities.py
src/pdf2md/models/priors.py
src/pdf2md/connectors/common.py
src/pdf2md/calibration/*
src/pdf2md/backends/runner.py
src/pdf2md/cli/main.py
src/pdf2md/pipeline/convert.py
src/pdf2md/utils/semantic_document_builder.py
src/pdf2md/models/semantic_document.py
backend/*/connector.py
backend/*/pdf2md_*.py
backend/*/pdf2ir_*.py
tools/calibrate_priors.py
pyproject.toml
current_plan.md
```

Rationale: Plan 4 is a consumer of Plans 1 to 3. If Plan 4 needs to change those contracts, then the earlier plans are not frozen.

---

## 3. Inputs and outputs

### 3.1 Input: connector outputs

Expected layout:

```text
<input-root>/
  mineru/
    manifest.json
    pages/page_0001.json
    entities.json
  paddleocr/
    manifest.json
    pages/page_0001.json
    entities.json
  deepseek/
    manifest.json
    pages/page_0001.json
    entities.json
```

Required per backend:

```text
pages/*.json
```

Optional per backend:

```text
entities.json
manifest.json
```

Rules:

```text
- Missing backend directory: warning, not failure.
- Missing pages directory: warning, backend ignored.
- Missing entities.json: warning, block consensus still runs.
- Empty pages: warning, backend ignored.
- Invalid JSON: warning in lenient mode, exception in strict mode.
```

### 3.2 Input: calibrated priors

Expected layout:

```text
<priors-root>/
  mineru.json
  paddleocr.json
  deepseek.json
  glm.json
```

Rules:

```text
- Missing prior file for a backend: warning; use default confidence 0.5.
- Invalid prior file: warning in lenient mode, exception in strict mode.
- Missing specific metric key: use prior.default_confidence.
```

### 3.3 Output

Canonical output layout:

```text
<out-dir>/
  consensus_ir.json
  reports/
    consensus_report.json
```

`consensus_ir.json` must validate as `pdf2md.models.ir.ConsensusIR`.

---

## 4. Consensus architecture

Plan 4 introduces five modules.

```text
src/pdf2md/consensus/grouping.py   # candidate groups
src/pdf2md/consensus/scoring.py    # scoring and priors
src/pdf2md/consensus/factory.py    # ConsensusIR construction
src/pdf2md/consensus/io.py         # filesystem loading and writing
src/pdf2md/consensus/reporting.py  # audit report dicts
```

No module imports OCR backends.

---

## 5. Candidate grouping

File:

```text
src/pdf2md/consensus/grouping.py
```

### 5.1 Public API

```python
@dataclass(frozen=True)
class BlockCandidate:
    backend: str
    page_no: int
    block: ExtractionBlock
    page_size: PageSize
    entity_ids: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class CandidateGroup:
    id: str
    page_no: int
    candidates: tuple[BlockCandidate, ...]
    reason: str
    metadata: dict[str, Any]
```

```python
def normalise_text(text: str | None) -> str: ...
def token_overlap(a: str | None, b: str | None) -> float: ...
def bbox_iou(a: BBox | None, b: BBox | None) -> float | None: ...
```

```python
def group_page_candidates(
    *,
    page_no: int,
    candidates: list[BlockCandidate],
    text_threshold: float = 0.75,
    bbox_threshold: float = 0.50,
) -> list[CandidateGroup]: ...
```

```python
def group_document_candidates(
    *,
    pages_by_backend: dict[str, list[PageExtractionIR]],
    entities_by_backend: dict[str, EntityProposalDocument],
) -> list[CandidateGroup]: ...
```

### 5.2 Grouping rules

Only candidates on the same page may be grouped.

Two candidates are grouped when at least one of these is true:

```text
- same block kind and normalised text exact match
- same block kind and token overlap >= text_threshold
- compatible block kind and token overlap >= text_threshold
- bbox IoU >= bbox_threshold and text overlap >= 0.25
```

Compatible block kinds:

```text
heading <-> paragraph
formula <-> paragraph
caption <-> paragraph
page_number <-> paragraph
footnote <-> paragraph
reference <-> paragraph
bibitem <-> paragraph
figure <-> paragraph
table <-> paragraph
```

Do not group candidates from different pages.

Do not put two candidates from the same backend in the same group unless they have the same block id. If one backend emits duplicates, keep them as separate groups and warn later.

### 5.3 Entity support map

`group_document_candidates` uses `EntityProposalDocument` only to attach entity ids to block candidates.

Mapping rule:

```text
entity.block_ids contains ExtractionBlock.id -> candidate.entity_ids includes entity.id
```

It must not resolve final semantic relations.

---

## 6. Consensus scoring

File:

```text
src/pdf2md/consensus/scoring.py
```

### 6.1 Public API

```python
@dataclass(frozen=True)
class ConsensusScoringSettings:
    text_weight: float = 0.35
    bbox_weight: float = 0.15
    order_weight: float = 0.10
    kind_weight: float = 0.10
    backend_prior_weight: float = 0.20
    entity_prior_weight: float = 0.10
    unresolved_margin: float = 0.05
    min_agreement_score: float = 0.50
    default_prior_confidence: float = 0.50
```

```python
@dataclass(frozen=True)
class CandidateScore:
    candidate: BlockCandidate
    score: float
    text_score: float
    bbox_score: float
    order_score: float
    kind_score: float
    backend_prior: float
    entity_prior: float
    metadata: dict[str, Any]
```

```python
@dataclass(frozen=True)
class GroupScore:
    group: CandidateGroup
    candidate_scores: tuple[CandidateScore, ...]
    selected: CandidateScore | None
    agreement_score: float
    selection_mode: SelectionMode
    conflict_kind: ConflictKind | None
    metadata: dict[str, Any]
```

```python
def score_candidate_group(
    *,
    group: CandidateGroup,
    priors_by_backend: dict[str, CalibrationPriorDocument],
    entities_by_backend: dict[str, EntityProposalDocument],
    settings: ConsensusScoringSettings = ConsensusScoringSettings(),
) -> GroupScore: ...
```

```python
def infer_block_kind_from_entities(
    *,
    candidate: BlockCandidate,
    entity_document: EntityProposalDocument | None,
    prior: CalibrationPriorDocument | None,
    default_confidence: float,
) -> tuple[BlockKind, float, dict[str, Any]]: ...
```

### 6.2 Prior lookup rules

For backend block prior:

```python
lookup_confidence(prior, CalibrationTarget.BLOCK_KIND, block.kind.value)
```

For entity proposal prior:

```python
lookup_confidence(prior, CalibrationTarget.ENTITY_TYPE, entity.entity_type.value)
lookup_confidence(prior, CalibrationTarget.CALIBRATION_KEY, entity.calibration_key)
```

Use the maximum available entity prior for entity support on that block.

If no prior exists:

```text
default_prior_confidence = 0.50
```

### 6.3 Candidate score

Each candidate score is:

```text
score =
  text_weight          * text_score
+ bbox_weight          * bbox_score
+ order_weight         * order_score
+ kind_weight          * kind_score
+ backend_prior_weight * backend_prior
+ entity_prior_weight  * entity_prior
```

All component scores are in `[0.0, 1.0]`.

Component definitions:

```text
text_score:
  maximum token overlap between candidate text and other candidates in the group;
  1.0 for a single-source group.

bbox_score:
  mean bbox IoU against other candidates with bbox;
  0.5 when bbox is unavailable for the group.

order_score:
  1.0 when candidate order is close to median order in group;
  degrade linearly with distance.

kind_score:
  1.0 when candidate kind is the group majority kind;
  0.75 when compatible with majority kind;
  0.25 otherwise.

backend_prior:
  Plan 3 block_kind prior for the candidate backend and candidate kind.

entity_prior:
  maximum Plan 3 entity or calibration_key prior attached to the candidate block;
  0.5 if no entity proposal supports the candidate.
```

### 6.4 Entity-to-block-kind enrichment

This is allowed in Plan 4 because it is page-local, not document-level linking.

Mapping:

```text
EntityType.PAGE_NUMBER       -> BlockKind.PAGE_NUMBER
EntityType.FOOTNOTE          -> BlockKind.FOOTNOTE
EntityType.EQUATION          -> BlockKind.FORMULA
EntityType.CAPTION           -> BlockKind.CAPTION
EntityType.FIGURE            -> BlockKind.FIGURE
EntityType.TABLE             -> BlockKind.TABLE
EntityType.REFERENCE_ITEM    -> BlockKind.BIBITEM
EntityType.REFERENCE_SECTION -> BlockKind.HEADING
```

Rule:

```text
If an entity-supported block kind has higher calibrated confidence than the raw block kind prior by at least 0.10, the selected consensus block may use the entity-supported kind.
```

The selected block metadata must record:

```json
{
  "kind_source": "entity_prior",
  "raw_block_kind": "paragraph",
  "entity_type": "page_number"
}
```

If confidence margin is smaller than 0.10, do not rewrite the kind. Record a conflict when the ambiguity matters.

### 6.5 Selection modes

Selection mode is decided per candidate group.

```text
agreed:
  group has at least two candidates and top score >= min_agreement_score,
  and top score is not within unresolved_margin of the second score.

single_source:
  group has one candidate and top score >= min_agreement_score.

fallback:
  group has at least one candidate, top score < min_agreement_score,
  but there is no competing candidate within unresolved_margin.

unresolved:
  no clear winner, or top two candidates are within unresolved_margin,
  or candidates disagree on text/kind in a way that cannot be resolved.
```

For `unresolved`:

```text
selected = None
ConsensusBlock.selected_source = None
ConsensusBlock.selection_mode = "unresolved"
ConsensusBlock.conflict_ids contains one conflict id
```

For resolved selections:

```text
ConsensusBlock.selected_source = selected.candidate.backend
```

---

## 7. Conflict creation

File:

```text
src/pdf2md/consensus/factory.py
```

When a group is unresolved, create a `Conflict`.

Conflict kind:

```text
text_conflict:
  candidates have high layout/order agreement but incompatible text.

kind_conflict:
  candidates have similar text but different non-compatible kinds,
  or entity-supported kind conflicts with raw block kind.

bbox_conflict:
  candidates have similar text and kind but incompatible bbox.

presence_conflict:
  one backend emits a meaningful block while others emit no nearby candidate,
  and the selected score is below min_agreement_score.

order_conflict:
  candidates have similar text and kind but strongly different reading order.
```

Conflict fields:

```text
id: conflict_id(document_id, index)
kind: ConflictKind
page_no: group.page_no
candidate_ids: all extraction block ids in the group
description: compact human-readable explanation
resolution: "unresolved"
selected_candidate_id: None
metadata:
  group_id
  candidate_scores
  conflict_reason
```

The consensus factory must never silently discard a conflict.

---

## 8. Consensus factory

File:

```text
src/pdf2md/consensus/factory.py
```

### 8.1 Public API

```python
@dataclass(frozen=True)
class ConsensusRunResult:
    consensus: ConsensusIR
    report: dict[str, Any]
    warnings: list[str]
```

```python
@dataclass(frozen=True)
class ConsensusFactorySettings:
    scoring: ConsensusScoringSettings
    strict: bool = False
```

```python
def build_consensus_ir(
    *,
    document_id: str,
    pages_by_backend: dict[str, list[PageExtractionIR]],
    entities_by_backend: dict[str, EntityProposalDocument],
    priors_by_backend: dict[str, CalibrationPriorDocument],
    settings: ConsensusFactorySettings,
) -> ConsensusRunResult: ...
```

### 8.2 Output construction

`ConsensusIR` fields:

```text
schema_name = "pdf2md.ConsensusIR"
schema_version = "1.0.0"
document_id = input document_id
page_count = max page_no seen across all backends
pages = contiguous pages from 1 to page_count
conflicts = all unresolved group conflicts
backends = one BackendManifest per backend
agreement_summary = compact summary metrics
metadata = {"factory": "consensus_v2"}
```

`ConsensusPage.blocks`:

```text
one ConsensusBlock per CandidateGroup
ordered by page_no, then selected block order or group order
```

Validation rule:

The produced object must pass:

```python
ConsensusIR.model_validate(consensus.model_dump(mode="json"))
```

No dict-only construction is accepted.

---

## 9. Consensus I/O

File:

```text
src/pdf2md/consensus/io.py
```

### 9.1 Public API

```python
@dataclass(frozen=True)
class ConsensusInput:
    document_id: str
    connector_root: Path
    priors_root: Path | None
    backends: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class ConsensusLoadResult:
    pages_by_backend: dict[str, list[PageExtractionIR]]
    entities_by_backend: dict[str, EntityProposalDocument]
    priors_by_backend: dict[str, CalibrationPriorDocument]
    warnings: list[str]
```

```python
def load_consensus_inputs(
    *,
    connector_root: Path,
    document_id: str,
    backends: list[str] | None = None,
    priors_root: Path | None = None,
    strict: bool = False,
) -> ConsensusLoadResult: ...
```

```python
def write_consensus_outputs(
    *,
    result: ConsensusRunResult,
    out_dir: Path,
) -> None: ...
```

### 9.2 Lenient warnings

```text
backend_missing:<backend>
pages_missing:<backend>
entities_missing:<backend>
prior_missing:<backend>
invalid_page:<backend>:<file>
invalid_entities:<backend>
invalid_prior:<backend>
empty_pages:<backend>
```

In lenient mode, invalid backend input is skipped and warning is recorded.

In strict mode, invalid JSON or schema-invalid input raises.

---

## 10. Reporting

File:

```text
src/pdf2md/consensus/reporting.py
```

Required report shape:

```json
{
  "schema_name": "pdf2md.ConsensusReport",
  "schema_version": "1.0.0",
  "document_id": "doc-1",
  "page_count": 1,
  "backend_count": 2,
  "block_count": 3,
  "conflict_count": 1,
  "selection_counts": {
    "agreed": 1,
    "single_source": 1,
    "fallback": 0,
    "unresolved": 1
  },
  "warnings": [],
  "backend_summary": {
    "mineru": {
      "page_count": 1,
      "block_count": 3,
      "prior_loaded": true
    }
  },
  "conflicts": [
    {
      "id": "conf:doc-1:0",
      "kind": "kind_conflict",
      "page_no": 1,
      "candidate_ids": ["mineru:doc-1:p1:b1", "paddleocr:doc-1:p1:b1"]
    }
  ]
}
```

The report is an audit artefact. It is not used by Plan 5 as a contract.

---

## 11. CLI tool

File:

```text
tools/build_consensus.py
```

Required CLI:

```bash
python tools/build_consensus.py \
  --connector-root tests/data/consensus_fixtures/simple_agreement \
  --document-id doc-1 \
  --priors-root tests/data/consensus_fixtures/simple_agreement/priors \
  --backends mineru,paddleocr \
  --out-dir /tmp/pdf2md_consensus
```

Required options:

```text
--connector-root PATH
--document-id TEXT
--priors-root PATH             optional
--backends LIST                comma-separated backend names, optional
--out-dir PATH
--strict
--verbose
--min-agreement-score FLOAT    default 0.50
--unresolved-margin FLOAT      default 0.05
```

Exit codes:

```text
0 = consensus written successfully, even if warnings exist
1 = invalid CLI arguments or strict-mode input failure
```

---

## 12. Tests as milestones

Completion is certified by pytest, not by prose.

### 12.1 `tests/test_consensus_grouping.py`

```text
class TestConsensusTextUtilities:
    test_normalise_text_lowercases_and_collapses_whitespace
    test_token_overlap_exact_match_is_one
    test_token_overlap_disjoint_is_zero
    test_bbox_iou_returns_none_when_missing_bbox
    test_bbox_iou_computes_overlap_for_same_origin
    test_bbox_iou_rejects_or_returns_none_for_mixed_origin

class TestCandidateGrouping:
    test_groups_same_page_same_kind_same_text_across_backends
    test_groups_same_page_high_text_overlap_across_backends
    test_groups_compatible_paragraph_and_heading
    test_groups_by_bbox_when_text_is_partial
    test_does_not_group_candidates_from_different_pages
    test_does_not_group_unrelated_low_overlap_blocks
    test_does_not_group_two_different_blocks_from_same_backend
    test_entity_ids_are_attached_to_block_candidates
```

Expected count: 14 tests.

### 12.2 `tests/test_consensus_scoring.py`

```text
class TestPriorLookupScoring:
    test_missing_prior_uses_default_confidence
    test_block_kind_prior_contributes_to_score
    test_entity_type_prior_contributes_to_score
    test_calibration_key_prior_can_raise_entity_prior

class TestEntityKindInference:
    test_page_number_entity_can_infer_page_number_block_kind
    test_footnote_entity_can_infer_footnote_block_kind
    test_small_prior_margin_does_not_rewrite_kind
    test_kind_rewrite_metadata_records_raw_kind_and_entity_type

class TestCandidateGroupScoring:
    test_single_source_group_scores_as_single_source
    test_two_strong_candidates_score_as_agreed
    test_close_top_scores_become_unresolved
    test_low_score_without_close_competitor_becomes_fallback
    test_scoring_is_deterministic_for_same_inputs
```

Expected count: 13 tests.

### 12.3 `tests/test_consensus_factory.py`

```text
class TestConsensusFactory:
    test_simple_agreement_builds_valid_consensus_ir
    test_consensus_pages_are_contiguous_from_one
    test_agreed_group_creates_agreed_consensus_block
    test_single_source_group_creates_single_source_consensus_block
    test_ambiguous_group_creates_unresolved_block_and_conflict
    test_conflict_ids_exist_in_top_level_conflicts
    test_candidate_ids_are_preserved_on_consensus_blocks
    test_backend_manifest_entries_are_created
    test_agreement_summary_counts_selection_modes
    test_missing_entities_file_warns_but_still_builds_consensus
    test_missing_prior_warns_and_uses_default
    test_consensus_ir_round_trips_through_pydantic

class TestConsensusReport:
    test_report_contains_document_backend_and_conflict_summary
    test_report_conflicts_match_consensus_conflicts
```

Expected count: 14 tests.

### 12.4 `tests/test_build_consensus_cli.py`

```text
class TestConsensusIO:
    test_load_consensus_inputs_reads_pages_entities_and_priors
    test_load_consensus_inputs_lenient_missing_prior_adds_warning
    test_load_consensus_inputs_lenient_missing_entities_adds_warning
    test_load_consensus_inputs_strict_invalid_page_raises
    test_write_consensus_outputs_writes_consensus_and_report

class TestBuildConsensusCLI:
    test_cli_help_exits_zero
    test_cli_writes_consensus_and_report_for_simple_agreement
    test_cli_writes_conflict_for_ambiguous_fixture
    test_cli_single_source_fixture_writes_single_source_block
    test_cli_missing_prior_root_still_succeeds_leniently
    test_cli_strict_mode_fails_on_invalid_input
    test_written_consensus_validates_as_consensus_ir
```

Expected count: 12 tests.

---

## 13. Fixtures

### 13.1 `simple_agreement`

Backends:

```text
mineru
paddleocr
```

Pages:

```text
page 1:
  heading: "Introduction"
  paragraph: "This is the first paragraph."
```

Entities:

```text
section proposal for heading
```

Priors:

```text
both backends have reasonable heading and paragraph priors
mineru slightly higher section detector prior
```

Expected:

```text
ConsensusIR has one page.
Heading group selection_mode = agreed.
Paragraph group selection_mode = agreed.
No conflicts.
```

### 13.2 `ambiguous_page_number`

Backends:

```text
mineru
paddleocr
```

Pages:

```text
page 1:
  block text "1"
```

Entities:

```text
mineru proposes page_number
paddleocr proposes footnote
```

Priors:

```text
similar calibrated confidence for page_number and footnote
```

Expected:

```text
ConsensusIR contains an unresolved block.
One Conflict with kind_conflict.
candidate_ids include both backend extraction ids.
```

A second test may alter priors in memory so page_number wins by a clear margin, proving calibrated priors can resolve a page-local ambiguity.

### 13.3 `single_source`

Backend:

```text
deepseek
```

Pages:

```text
page 1:
  heading: "Abstract"
  paragraph: "Only one backend produced this page."
```

Expected:

```text
ConsensusIR has single_source blocks.
No conflicts.
Warnings are empty if prior is present.
```

---

## 14. Acceptance criteria

The reviewer accepts Plan 4 only when all criteria pass.

### 14.1 Targeted tests

```bash
pytest tests/test_consensus_grouping.py -q
pytest tests/test_consensus_scoring.py -q
pytest tests/test_consensus_factory.py -q
pytest tests/test_build_consensus_cli.py -q
```

All pass. No `skip`. No `xfail`.

### 14.2 Plans 1 to 3 still pass

```bash
pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
pytest tests/test_connector_common.py -q
pytest tests/test_backend_connectors.py -q
pytest tests/test_prior_contracts.py -q
pytest tests/test_calibration_matching.py -q
pytest tests/test_calibration_metrics.py -q
pytest tests/test_calibrate_priors_cli.py -q
```

All pass.

### 14.3 Existing runner and semantic-document tests still pass

```bash
pytest tests/test_run_backends_config.py -q
pytest tests/test_semantic_document_builder.py -q
```

The semantic-document builder is not part of Plan 4, but this check confirms legacy downstream code was not broken.

### 14.4 Whole suite has no regression

```bash
pytest tests/ -q
```

Must pass with no regression against the previous count.

### 14.5 Whitelist check

```bash
git diff --name-only main..HEAD
```

Must be a subset of the whitelist in section 2.

### 14.6 Smoke import

```bash
python -c "from pdf2md.consensus.factory import build_consensus_ir; print(build_consensus_ir.__name__)"
```

Expected output:

```text
build_consensus_ir
```

### 14.7 CLI smoke test

```bash
python tools/build_consensus.py \
  --connector-root tests/data/consensus_fixtures/simple_agreement \
  --document-id doc-1 \
  --priors-root tests/data/consensus_fixtures/simple_agreement/priors \
  --backends mineru,paddleocr \
  --out-dir /tmp/pdf2md_consensus_smoke
```

Then:

```bash
python -c "from pathlib import Path; from pdf2md.models.ir import ConsensusIR; p=Path('/tmp/pdf2md_consensus_smoke/consensus_ir.json'); ConsensusIR.model_validate_json(p.read_text()); print('ok')"
```

Expected output:

```text
ok
```

---

## 15. Implementation order

### A. Grouping layer first

Implement only:

```text
src/pdf2md/consensus/__init__.py
src/pdf2md/consensus/grouping.py
tests/test_consensus_grouping.py
```

Run:

```bash
pytest tests/test_consensus_grouping.py -q
pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
```

Reason: candidate grouping is the foundation. If grouping is unstable, scoring and conflicts become meaningless.

### B. Scoring layer

Implement:

```text
src/pdf2md/consensus/scoring.py
tests/test_consensus_scoring.py
```

Run:

```bash
pytest tests/test_consensus_grouping.py tests/test_consensus_scoring.py -q
```

Reason: scoring must consume Plan 3 priors and Plan 2 entity proposals before the factory creates `ConsensusIR`.

### C. Factory and reporting

Implement:

```text
src/pdf2md/consensus/factory.py
src/pdf2md/consensus/reporting.py
tests/test_consensus_factory.py
tests/data/consensus_fixtures/simple_agreement/*
tests/data/consensus_fixtures/ambiguous_page_number/*
tests/data/consensus_fixtures/single_source/*
```

Run:

```bash
pytest tests/test_consensus_factory.py -q
```

Reason: only after grouping and scoring are stable should the system emit canonical `ConsensusIR`.

### D. I/O and CLI

Implement:

```text
src/pdf2md/consensus/io.py
tools/build_consensus.py
tests/test_build_consensus_cli.py
```

Run:

```bash
pytest tests/test_build_consensus_cli.py -q
```

Reason: the CLI should only bind together tested pure components.

### E. Regression pass

Run:

```bash
pytest tests/test_consensus_grouping.py -q
pytest tests/test_consensus_scoring.py -q
pytest tests/test_consensus_factory.py -q
pytest tests/test_build_consensus_cli.py -q

pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
pytest tests/test_connector_common.py -q
pytest tests/test_backend_connectors.py -q
pytest tests/test_prior_contracts.py -q
pytest tests/test_calibration_matching.py -q
pytest tests/test_calibration_metrics.py -q
pytest tests/test_calibrate_priors_cli.py -q

pytest tests/test_run_backends_config.py -q
pytest tests/test_semantic_document_builder.py -q
pytest tests/ -q

git diff --name-only main..HEAD
```

---

## 16. What Plan 4 must not accidentally become

Do not implement semantic linking here.

Bad:

```text
"Attach this footnote to its anchor."
"Resolve TOC entry to section globally."
"Partition the document into body and bibliography."
"Build equation sequence across the whole document."
"Build LinkedStructure."
"Build DoclingDocument."
"Export markdown or RAG JSON."
```

Good:

```text
"Group candidate blocks on page 1."
"Use calibrated prior to prefer page_number over generic paragraph."
"Mark mineru and paddleocr disagreement as kind_conflict."
"Emit unresolved ConsensusBlock with conflict id."
"Write ConsensusIR and consensus_report.json."
```

This is the correct level for Plan 4.

---

## 17. Practical reviewer checklist

The reviewer should ask:

```text
1. Does Plan 4 consume PageExtractionIR from Plan 1?
2. Does it consume EntityProposalDocument from Plan 2?
3. Does it consume CalibrationPriorDocument from Plan 3?
4. Does it emit valid ConsensusIR?
5. Are ambiguous groups represented as Conflict objects?
6. Are candidate_ids preserved?
7. Are conflict_ids valid and present in top-level conflicts?
8. Are missing priors handled leniently?
9. Are missing entities handled leniently?
10. Does the scoring layer use lookup_confidence instead of custom prior parsing?
11. Does the consensus factory avoid document-level semantic linking?
12. Are legacy semantic-document files untouched?
13. Is git diff contained inside the whitelist?
```

---

## 18. Main design boundary for Plan 5

Plan 5, the semantic linker, may consume:

```text
ConsensusIR
EntityProposalDocument from each backend
CalibrationPriorDocument
consensus_report.json
```

Plan 5 may then use document-level evidence:

```text
page-number monotonicity
TOC to section matching
reference-section partitioning
equation sequence
figure/table sequence
footnote anchors
caption attachment
```

Plan 4 must not do those things. It only produces the reliable, auditable page-level consensus substrate.
