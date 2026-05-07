# Plan 3 - Confidence prior calibration

Status: draft, ready to implement after Plan 2  
Repo: `pdf2md`  
Owner: calibration layer  
Sequence: this is plan 3 of 6. It depends on Plans 1 and 2 and blocks Plan 4.

---

## 0. Scope and constraints

This plan introduces calibrated backend priors.

Plan 1 froze the page-level evidence contracts: `PageExtractionIR` and `ConsensusIR`.

Plan 2 added backend connectors that emit:

```text
<out-dir>/<backend>/
  manifest.json
  pages/page_0001.json
  entities.json
```

where `pages/*.json` are `PageExtractionIR` files and `entities.json` is an `EntityProposalDocument`.

Plan 3 consumes those Plan 2 outputs, compares them against ground truth, and produces calibrated priors that Plan 4 can use during consensus.

This plan does not run OCR. It does not modify backend wrappers. It does not change connector logic. It does not perform consensus. It does not resolve semantic links. It does not export Docling.

The output of this plan is a versioned prior file per backend, plus calibration reports:

```text
priors/<backend>.json
reports/calibration_report.json
```

The core question answered by this plan is:

```text
Given backend B, entity class C, relation class R, block kind K, and detector/calibration key D,
how reliable has this backend been against ground truth?
```

Plan 4 will use these priors as scoring inputs. Plan 3 only produces them.

Hard constraints:

```text
- No new runtime dependencies.
- No OCR execution in tests.
- No conda calls in tests.
- No modification to Plan 1 IR contracts.
- No modification to Plan 2 connector contracts.
- No modification to backend OCR wrappers.
- No modification to src/pdf2md/backends/runner.py.
- No modification to src/pdf2md/cli/main.py.
- Calibration must be lenient: missing backend output, missing truth files, or empty samples produce warnings, not hard failure.
- Invalid input JSON or schema-invalid objects may fail in strict mode.
- Tests must use synthetic fixtures, not real LaTeX compilation or real OCR.
```

Out of scope:

```text
- Running local backend models.
- Generating LaTeX ground truth.
- Generating Docling ground truth.
- Changing connector confidence values in-place.
- Consensus scoring.
- Semantic linker.
- Linked structure.
- Docling exporter.
```

---

## 1. Why this plan exists

Plan 2 gives every backend a common evidence format. However, every backend has different strengths and weaknesses:

```text
MinerU may be better at tables.
PaddleOCR may be better at raw text but weaker at semantic sections.
DeepSeek may produce rich markdown but weak geometry.
GLM may have different semantic hallucination patterns.
```

The consensus factory should not treat all proposals equally. It needs calibrated priors per backend and per detector or class.

Plan 3 therefore computes empirical reliability from ground truth:

```text
backend + block_kind       -> block prior
backend + entity_type      -> entity prior
backend + relation_type    -> relation prior
backend + calibration_key  -> detector prior
```

The connector already emits `calibration_key` in `EntityProposal`. That key is the bridge between Plan 2 and Plan 3.

---

## 2. File whitelist

The reviewer rejects the plan if any implementation modifies files outside this whitelist.

```text
src/pdf2md/models/__init__.py
src/pdf2md/models/priors.py

src/pdf2md/calibration/__init__.py
src/pdf2md/calibration/matching.py
src/pdf2md/calibration/metrics.py
src/pdf2md/calibration/io.py

tools/calibrate_priors.py

tests/test_prior_contracts.py
tests/test_calibration_matching.py
tests/test_calibration_metrics.py
tests/test_calibrate_priors_cli.py

tests/data/calibration_fixtures/minimal_truth/truth.json
tests/data/calibration_fixtures/minimal_predictions/mineru/entities.json
tests/data/calibration_fixtures/minimal_predictions/mineru/pages/page_0001.json
tests/data/calibration_fixtures/minimal_predictions/mineru/manifest.json

tests/data/calibration_fixtures/mixed_predictions/truth.json
tests/data/calibration_fixtures/mixed_predictions/mineru/entities.json
tests/data/calibration_fixtures/mixed_predictions/mineru/pages/page_0001.json
tests/data/calibration_fixtures/mixed_predictions/mineru/manifest.json
tests/data/calibration_fixtures/mixed_predictions/paddleocr/entities.json
tests/data/calibration_fixtures/mixed_predictions/paddleocr/pages/page_0001.json
tests/data/calibration_fixtures/mixed_predictions/paddleocr/manifest.json

tests/data/calibration_fixtures/empty_predictions/truth.json
tests/data/calibration_fixtures/empty_predictions/deepseek/entities.json
tests/data/calibration_fixtures/empty_predictions/deepseek/manifest.json
```

Explicit non-whitelist files:

```text
src/pdf2md/models/ir.py
src/pdf2md/models/entities.py
src/pdf2md/connectors/common.py
src/pdf2md/backends/runner.py
src/pdf2md/cli/main.py
src/pdf2md/pipeline/convert.py
backend/*/connector.py
backend/*/pdf2md_*.py
backend/*/pdf2ir_*.py
pyproject.toml
current_plan.md
```

Rationale:

Plan 3 is a consumer of Plan 2 outputs. If Plan 3 needs to change `EntityProposalDocument`, then Plan 2 was not really frozen. Do not do that in this plan.

---

## 3. Inputs and outputs

### 3.1 Input: backend predictions

Plan 3 reads Plan 2 connector outputs.

Required prediction files per backend:

```text
<prediction-root>/<backend>/
  entities.json
  pages/
    page_0001.json
    ...
```

`entities.json` must validate as:

```text
pdf2md.models.entities.EntityProposalDocument
```

`pages/*.json` must validate as:

```text
pdf2md.models.ir.PageExtractionIR
```

Page files are used for block-kind calibration. Entity files are used for entity and relation calibration.

Missing page files do not block entity calibration.

### 3.2 Input: ground truth

Plan 3 introduces a simple canonical calibration truth format for tests and future generated ground truth.

File name:

```text
truth.json
```

Schema name:

```text
pdf2md.CalibrationTruthDocument
```

This is not the final linked structure and not Docling. It is only a compact benchmark target for calibration.

The real LaTeX and Docling ground truth harness can later produce this truth format from existing files such as:

```text
groundtruth/corpus/latex/<doc_id>/<doc_id>.docling.json
groundtruth/corpus/latex/<doc_id>/<doc_id>.docling_groundtruth_meta.json
groundtruth/corpus/latex/<doc_id>/groundtruth/source_groundtruth_ir.json
groundtruth/corpus/latex/<doc_id>/groundtruth/semantic_document_groundtruth.json
```

Plan 3 does not require real corpus files in CI. Tests use synthetic `truth.json` fixtures.

### 3.3 Output: prior files

Canonical output layout:

```text
<out-dir>/
  priors/
    mineru.json
    paddleocr.json
    deepseek.json
    glm.json
  reports/
    calibration_report.json
```

Only backends seen in the input need a prior file.

---

## 4. New schema: `CalibrationPriorDocument`

File:

```text
src/pdf2md/models/priors.py
```

This module contains Pydantic v2 models and pure id/key helpers. No I/O.

All models use:

```python
ConfigDict(extra="forbid", frozen=False, populate_by_name=True)
```

The schema version is:

```python
PRIOR_SCHEMA_VERSION = "1.0.0"
```

### 4.1 Enums

```python
class CalibrationTarget(str, Enum):
    BLOCK_KIND = "block_kind"
    ENTITY_TYPE = "entity_type"
    RELATION_TYPE = "relation_type"
    CALIBRATION_KEY = "calibration_key"
```

```python
class CalibrationStatus(str, Enum):
    CALIBRATED = "calibrated"
    UNDERPOWERED = "underpowered"
    NO_SAMPLES = "no_samples"
```

```python
class MatchOutcome(str, Enum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
```

### 4.2 `CalibrationCounts`

```python
class CalibrationCounts(BaseModel):
    true_positive: int
    false_positive: int
    false_negative: int
```

Validation:

```text
- all values >= 0
```

### 4.3 `CalibrationMetric`

```python
class CalibrationMetric(BaseModel):
    target: CalibrationTarget
    key: str
    counts: CalibrationCounts
    precision: float
    recall: float
    f1: float
    support: int
    calibrated_confidence: float
    status: CalibrationStatus
    metadata: dict[str, Any]
```

Validation:

```text
- key is non-empty.
- precision, recall, f1, calibrated_confidence are in [0.0, 1.0].
- support >= 0.
```

Status is set by the metrics layer:

```text
support == 0              -> no_samples
0 < support < min_samples -> underpowered
support >= min_samples    -> calibrated
```

`calibrated_confidence` uses smoothed precision:

```text
(tp + alpha) / (tp + fp + alpha + beta)
```

Default smoothing:

```text
alpha = 1.0
beta = 1.0
```

This prevents tiny samples from producing hard 0.0 or 1.0 priors.

### 4.4 `CalibrationPriorDocument`

```python
class CalibrationPriorDocument(BaseModel):
    schema_name: Literal["pdf2md.CalibrationPriorDocument"]
    schema_version: Literal["1.0.0"]
    backend: str
    backend_version: str | None
    generated_from: list[str]
    min_samples: int
    smoothing_alpha: float
    smoothing_beta: float
    default_confidence: float
    block_kind_priors: list[CalibrationMetric]
    entity_type_priors: list[CalibrationMetric]
    relation_type_priors: list[CalibrationMetric]
    calibration_key_priors: list[CalibrationMetric]
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- backend is non-empty.
- min_samples >= 1.
- smoothing_alpha > 0.
- smoothing_beta > 0.
- default_confidence in [0.0, 1.0].
- each metric list has unique keys.
- extra fields are forbidden.
```

Required helper functions:

```python
prior_key(target: CalibrationTarget | str, key: str) -> str
lookup_prior(prior: CalibrationPriorDocument, target: CalibrationTarget | str, key: str) -> CalibrationMetric | None
lookup_confidence(prior: CalibrationPriorDocument, target: CalibrationTarget | str, key: str) -> float
```

`lookup_confidence` returns `prior.default_confidence` when no calibrated metric exists.

Re-export from:

```text
src/pdf2md/models/__init__.py
```

Append only. Do not remove Plan 1 or Plan 2 exports.

---

## 5. New schema: `CalibrationTruthDocument`

Also in:

```text
src/pdf2md/models/priors.py
```

This is the canonical truth format used by calibration tests and by local corpus tooling.

```python
class TruthEntity(BaseModel):
    id: str
    entity_type: EntityType
    canonical_text: str | None
    page_no: int | None
    metadata: dict[str, Any]
```

```python
class TruthRelation(BaseModel):
    id: str
    relation_type: RelationType
    source_truth_id: str
    target_truth_id: str
    metadata: dict[str, Any]
```

```python
class TruthBlock(BaseModel):
    id: str
    block_kind: BlockKind
    text: str | None
    page_no: int
    metadata: dict[str, Any]
```

```python
class CalibrationTruthDocument(BaseModel):
    schema_name: Literal["pdf2md.CalibrationTruthDocument"]
    schema_version: Literal["1.0.0"]
    document_id: str
    blocks: list[TruthBlock]
    entities: list[TruthEntity]
    relations: list[TruthRelation]
    metadata: dict[str, Any]
```

Validation:

```text
- document_id is non-empty.
- truth entity ids are unique.
- truth relation ids are unique.
- relation endpoints exist in truth entities.
- truth block ids are unique.
- page_no >= 1 for truth blocks and when present for truth entities.
- extra fields are forbidden.
```

Important:

This truth document is deliberately smaller than Docling. It is an evaluation target, not the export model.

---

## 6. Calibration matching

File:

```text
src/pdf2md/calibration/matching.py
```

This module is pure Python and deterministic.

### 6.1 Public API

```python
@dataclass(frozen=True)
class MatchRecord:
    target: CalibrationTarget
    key: str
    backend: str
    prediction_id: str | None
    truth_id: str | None
    outcome: MatchOutcome
    confidence: float | None
    metadata: dict[str, Any]
```

```python
def match_blocks(
    *,
    backend: str,
    pages: list[PageExtractionIR],
    truth: CalibrationTruthDocument,
) -> list[MatchRecord]:
    ...
```

```python
def match_entities(
    *,
    backend: str,
    predictions: EntityProposalDocument,
    truth: CalibrationTruthDocument,
) -> list[MatchRecord]:
    ...
```

```python
def match_relations(
    *,
    backend: str,
    predictions: EntityProposalDocument,
    truth: CalibrationTruthDocument,
) -> list[MatchRecord]:
    ...
```

```python
def normalise_text(text: str | None) -> str:
    ...
```

```python
def token_overlap(a: str | None, b: str | None) -> float:
    ...
```

### 6.2 Matching rules for blocks

A predicted `ExtractionBlock` matches a `TruthBlock` when:

```text
- page_no matches
- block kind matches
- normalised text matches exactly, or token overlap >= 0.80
```

If several predictions match the same truth block, choose the highest token overlap, then lowest page order. Remaining predictions are false positives.

Outputs:

```text
true_positive for matched predictions
false_positive for unmatched predictions
false_negative for unmatched truth blocks
```

Keys:

```text
target = block_kind
key = BlockKind value, such as "heading", "paragraph", "table"
```

### 6.3 Matching rules for entities

A predicted `EntityProposal` matches a `TruthEntity` when:

```text
- entity_type matches
- page_no matches when both are present
- canonical_text normalised exact match, or token overlap >= 0.75
```

Special cases:

```text
- page_number: exact canonical_text match preferred; page_no must match.
- equation: metadata.equation_number may match truth metadata.equation_number.
- caption: metadata.caption_number and caption_kind may match.
- reference_item: metadata.marker may match.
```

Outputs:

```text
true_positive for matched predictions
false_positive for unmatched predictions
false_negative for unmatched truth entities
```

Keys:

```text
target = entity_type
key = EntityType value, such as "section", "page_number", "caption"
```

Additional records:

Every prediction with a non-empty `calibration_key` also emits a second record:

```text
target = calibration_key
key = prediction.calibration_key
```

This lets Plan 4 score not only a class, but a specific detector.

### 6.4 Matching rules for relations

A predicted `RelationProposal` matches a `TruthRelation` when:

```text
- relation_type matches
- source and target predicted entities have matched truth entities
- matched truth source and target equal the truth relation endpoints
```

If entity matching is unavailable, relation matching returns false positives for predicted relations and false negatives for truth relations, with warning metadata `relation_matching_without_entity_matches`.

Keys:

```text
target = relation_type
key = RelationType value, such as "caption_of", "toc_points_to"
```

---

## 7. Calibration metrics

File:

```text
src/pdf2md/calibration/metrics.py
```

### 7.1 Public API

```python
@dataclass(frozen=True)
class CalibrationSettings:
    min_samples: int = 5
    smoothing_alpha: float = 1.0
    smoothing_beta: float = 1.0
    default_confidence: float = 0.5
```

```python
def compute_precision(tp: int, fp: int) -> float:
    ...
```

```python
def compute_recall(tp: int, fn: int) -> float:
    ...
```

```python
def compute_f1(precision: float, recall: float) -> float:
    ...
```

```python
def smoothed_precision(tp: int, fp: int, alpha: float, beta: float) -> float:
    ...
```

```python
def metric_from_counts(
    *,
    target: CalibrationTarget,
    key: str,
    counts: CalibrationCounts,
    settings: CalibrationSettings,
    metadata: dict[str, Any] | None = None,
) -> CalibrationMetric:
    ...
```

```python
def build_prior_document(
    *,
    backend: str,
    backend_version: str | None,
    generated_from: list[str],
    records: list[MatchRecord],
    settings: CalibrationSettings,
    warnings: list[str],
    metadata: dict[str, Any] | None = None,
) -> CalibrationPriorDocument:
    ...
```

### 7.2 Metric definitions

```text
precision = tp / (tp + fp), or 0.0 when denominator is 0
recall    = tp / (tp + fn), or 0.0 when denominator is 0
f1        = 2 * precision * recall / (precision + recall), or 0.0 when denominator is 0
support   = tp + fp + fn
```

`calibrated_confidence`:

```text
(tp + alpha) / (tp + fp + alpha + beta)
```

Status:

```text
support == 0              -> no_samples
0 < support < min_samples -> underpowered
support >= min_samples    -> calibrated
```

---

## 8. Calibration I/O

File:

```text
src/pdf2md/calibration/io.py
```

This module handles filesystem scanning and JSON loading. It must be lenient unless `strict=True`.

### 8.1 Public API

```python
@dataclass(frozen=True)
class CalibrationDocumentInput:
    document_id: str
    truth_path: Path
    prediction_roots: dict[str, Path]
```

```python
@dataclass(frozen=True)
class CalibrationLoadResult:
    truth: CalibrationTruthDocument | None
    pages_by_backend: dict[str, list[PageExtractionIR]]
    entities_by_backend: dict[str, EntityProposalDocument]
    warnings: list[str]
```

```python
def discover_calibration_inputs(
    *,
    root: Path,
    backends: list[str] | None = None,
) -> list[CalibrationDocumentInput]:
    ...
```

```python
def load_calibration_document(
    *,
    item: CalibrationDocumentInput,
    strict: bool = False,
) -> CalibrationLoadResult:
    ...
```

```python
def write_prior_outputs(
    *,
    priors: list[CalibrationPriorDocument],
    report: dict[str, Any],
    out_dir: Path,
) -> None:
    ...
```

### 8.2 Supported fixture layout

Tests use:

```text
tests/data/calibration_fixtures/<case>/
  truth.json
  <backend>/
    manifest.json
    entities.json
    pages/
      page_0001.json
```

`discover_calibration_inputs(root=tests/data/calibration_fixtures/mixed_predictions)` returns one document input where `prediction_roots` contains `mineru` and `paddleocr`.

### 8.3 Supported real corpus layout

The CLI also supports the local corpus shape:

```text
groundtruth/corpus/latex/<document_id>/
  truth.json
  <document_id>.docling.json
  <document_id>.docling_groundtruth_meta.json
  backend_ir/
    mineru/
      entities.json
      pages/
        page_0001.json
```

and Plan 2-style connector outputs:

```text
<document_id>/<backend>/
  entities.json
  pages/
    page_0001.json
```

For Plan 3 implementation, only `truth.json` is required in tests. Real Docling-to-truth conversion is allowed only as a best-effort helper and must not be necessary for CI.

Lenient warnings:

```text
truth_missing
prediction_missing:<backend>
entities_missing:<backend>
pages_missing:<backend>
invalid_truth:<path>
invalid_entities:<backend>
invalid_page:<backend>:<file>
```

---

## 9. CLI tool

File:

```text
tools/calibrate_priors.py
```

Required CLI:

```bash
python tools/calibrate_priors.py \
  --root tests/data/calibration_fixtures/mixed_predictions \
  --out-dir /tmp/pdf2md_priors \
  --backends mineru,paddleocr \
  --min-samples 2
```

Required options:

```text
--root PATH                 input root
--out-dir PATH              output directory
--backends LIST             comma-separated backend names, optional
--min-samples INT           default 5
--smoothing-alpha FLOAT     default 1.0
--smoothing-beta FLOAT      default 1.0
--default-confidence FLOAT  default 0.5
--strict                    fail on invalid inputs instead of warning
--verbose                   print report JSON
```

Exit codes:

```text
0 = priors written successfully, even if warnings exist
1 = invalid CLI arguments or strict-mode input failure
```

Output:

```text
<out-dir>/priors/<backend>.json
<out-dir>/reports/calibration_report.json
```

The report contains:

```json
{
  "schema_name": "pdf2md.CalibrationReport",
  "schema_version": "1.0.0",
  "document_count": 1,
  "backends": ["mineru", "paddleocr"],
  "prior_files": {
    "mineru": "priors/mineru.json",
    "paddleocr": "priors/paddleocr.json"
  },
  "warnings": [],
  "settings": {
    "min_samples": 2,
    "smoothing_alpha": 1.0,
    "smoothing_beta": 1.0,
    "default_confidence": 0.5
  }
}
```

---

## 10. Tests as milestones

Completion is certified by pytest, not by prose.

### 10.1 `tests/test_prior_contracts.py`

```text
class TestPriorEnums:
    test_calibration_target_values_match_specification
    test_calibration_status_values_match_specification
    test_match_outcome_values_match_specification

class TestCalibrationCounts:
    test_counts_accept_zero_and_positive_values
    test_counts_reject_negative_values

class TestCalibrationMetric:
    test_metric_accepts_valid_payload
    test_metric_rejects_empty_key
    test_metric_rejects_scores_outside_unit_interval
    test_metric_status_no_samples_requires_zero_support
    test_metric_status_underpowered_requires_positive_support_below_min_samples
    test_metric_status_calibrated_requires_support_at_least_min_samples

class TestCalibrationPriorDocument:
    test_minimal_prior_document_round_trip
    test_prior_document_rejects_duplicate_metric_keys_within_same_list
    test_prior_document_rejects_invalid_default_confidence
    test_json_schema_export_basic_shape

class TestCalibrationTruthDocument:
    test_truth_document_round_trip
    test_truth_document_rejects_duplicate_truth_entity_ids
    test_truth_document_rejects_duplicate_truth_relation_ids
    test_truth_document_rejects_relation_with_unknown_source
    test_truth_document_rejects_relation_with_unknown_target
    test_truth_document_rejects_duplicate_truth_block_ids

class TestPriorLookup:
    test_prior_key_format
    test_lookup_prior_finds_existing_metric
    test_lookup_confidence_returns_metric_confidence
    test_lookup_confidence_returns_default_for_missing_metric
```

Expected count: 25 tests.

### 10.2 `tests/test_calibration_matching.py`

```text
class TestTextNormalisation:
    test_normalise_text_lowercases_and_collapses_whitespace
    test_token_overlap_exact_match_is_one
    test_token_overlap_disjoint_is_zero
    test_token_overlap_partial_match_is_fractional

class TestBlockMatching:
    test_matching_block_kind_true_positive
    test_unmatched_prediction_block_is_false_positive
    test_unmatched_truth_block_is_false_negative
    test_same_truth_block_not_matched_twice

class TestEntityMatching:
    test_matching_section_entity_true_positive
    test_matching_page_number_requires_same_page
    test_matching_caption_can_use_caption_number_metadata
    test_matching_equation_can_use_equation_number_metadata
    test_unmatched_entity_prediction_is_false_positive
    test_unmatched_truth_entity_is_false_negative
    test_entity_with_calibration_key_emits_detector_record

class TestRelationMatching:
    test_matching_caption_of_relation_true_positive_when_endpoints_match
    test_unmatched_relation_prediction_is_false_positive
    test_unmatched_truth_relation_is_false_negative
    test_relation_matching_without_entity_matches_warns_or_marks_unmatched
```

Expected count: 20 tests.

### 10.3 `tests/test_calibration_metrics.py`

```text
class TestScalarMetrics:
    test_precision_regular_case
    test_precision_zero_denominator_returns_zero
    test_recall_regular_case
    test_recall_zero_denominator_returns_zero
    test_f1_regular_case
    test_f1_zero_denominator_returns_zero
    test_smoothed_precision_uses_alpha_beta

class TestMetricFromCounts:
    test_metric_from_counts_computes_precision_recall_f1
    test_metric_from_counts_marks_no_samples
    test_metric_from_counts_marks_underpowered
    test_metric_from_counts_marks_calibrated

class TestBuildPriorDocument:
    test_build_prior_document_groups_records_by_target_and_key
    test_build_prior_document_separates_block_entity_relation_and_calibration_key_priors
    test_build_prior_document_preserves_backend_and_generated_from
    test_build_prior_document_uses_default_confidence
```

Expected count: 15 tests.

### 10.4 `tests/test_calibrate_priors_cli.py`

```text
class TestCalibrationIO:
    test_discover_calibration_inputs_finds_fixture_document
    test_load_calibration_document_reads_truth_entities_and_pages
    test_load_calibration_document_lenient_missing_backend_adds_warning
    test_load_calibration_document_strict_invalid_truth_raises

class TestCalibratePriorsCLI:
    test_cli_help_exits_zero
    test_cli_writes_prior_and_report_for_minimal_fixture
    test_cli_writes_one_prior_per_backend_for_mixed_fixture
    test_cli_empty_predictions_writes_no_samples_prior
    test_cli_strict_mode_fails_on_invalid_input
    test_written_prior_validates_as_calibration_prior_document
    test_written_report_contains_prior_file_paths
```

Expected count: 11 tests.

---

## 11. Fixtures

### 11.1 `minimal_truth/truth.json`

A single document with:

```text
one heading block
one section entity
no relations
```

Purpose:

```text
- validates truth schema
- validates one true positive
- validates one backend prior
```

### 11.2 `minimal_predictions/mineru`

Contains:

```text
manifest.json
entities.json
pages/page_0001.json
```

The prediction exactly matches `minimal_truth`.

Expected calibration:

```text
section entity -> true_positive
heading block  -> true_positive
precision, recall, f1 = 1.0 before smoothing
calibrated_confidence = smoothed precision
```

### 11.3 `mixed_predictions/truth.json`

A document with:

```text
section
page_number
caption
figure
caption_of relation
equation
reference_section
reference_item
```

Purpose:

```text
- mixed true positives
- false positives
- false negatives
- relation matching
- calibration_key priors
- multiple backend prior files
```

`mineru` fixture should be mostly correct.

`paddleocr` fixture should include at least:

```text
one correct page_number
one false positive footnote
one missed caption
```

This makes priors visibly different by backend.

### 11.4 `empty_predictions/deepseek`

Contains:

```text
manifest.json
entities.json
```

with zero entities and no pages.

Expected calibration:

```text
truth entities become false negatives
predicted support may be zero for some classes
prior document still writes
warnings may include pages_missing:deepseek
```

---

## 12. Acceptance criteria

The reviewer accepts Plan 3 only when all criteria pass.

### 12.1 Targeted tests

```bash
pytest tests/test_prior_contracts.py -q
pytest tests/test_calibration_matching.py -q
pytest tests/test_calibration_metrics.py -q
pytest tests/test_calibrate_priors_cli.py -q
```

All pass. No `skip`. No `xfail`.

### 12.2 Plans 1 and 2 still pass

```bash
pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
pytest tests/test_connector_common.py -q
pytest tests/test_backend_connectors.py -q
```

All pass.

### 12.3 Existing backend runner tests still pass

```bash
pytest tests/test_run_backends_config.py -q
```

This confirms calibration did not alter backend execution.

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
python -c "from pdf2md.models.priors import CalibrationPriorDocument, CalibrationTruthDocument; print(CalibrationPriorDocument.model_json_schema()['title'], CalibrationTruthDocument.model_json_schema()['title'])"
```

Expected output:

```text
CalibrationPriorDocument CalibrationTruthDocument
```

### 12.7 CLI smoke test

```bash
python tools/calibrate_priors.py \
  --root tests/data/calibration_fixtures/mixed_predictions \
  --out-dir /tmp/pdf2md_calibration_smoke \
  --backends mineru,paddleocr \
  --min-samples 2
```

Then:

```bash
python -c "from pathlib import Path; from pdf2md.models.priors import CalibrationPriorDocument; p=Path('/tmp/pdf2md_calibration_smoke/priors/mineru.json'); CalibrationPriorDocument.model_validate_json(p.read_text()); print('ok')"
```

Expected output:

```text
ok
```

---

## 13. Implementation order

### A. Prior and truth contracts first

Implement only:

```text
src/pdf2md/models/priors.py
src/pdf2md/models/__init__.py
tests/test_prior_contracts.py
```

Run:

```bash
pytest tests/test_prior_contracts.py -q
pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
```

Reason:

The prior file format must be frozen before writing metric and CLI logic.

### B. Matching layer

Implement:

```text
src/pdf2md/calibration/__init__.py
src/pdf2md/calibration/matching.py
tests/test_calibration_matching.py
```

Run:

```bash
pytest tests/test_prior_contracts.py tests/test_calibration_matching.py -q
```

Reason:

Calibration quality depends more on deterministic matching than on the arithmetic. The matching layer must be isolated and testable.

### C. Metrics layer

Implement:

```text
src/pdf2md/calibration/metrics.py
tests/test_calibration_metrics.py
```

Run:

```bash
pytest tests/test_calibration_metrics.py -q
```

Reason:

Metrics are pure functions and should not depend on filesystem layout.

### D. I/O and CLI

Implement:

```text
src/pdf2md/calibration/io.py
tools/calibrate_priors.py
tests/test_calibrate_priors_cli.py
tests/data/calibration_fixtures/*
```

Run:

```bash
pytest tests/test_calibrate_priors_cli.py -q
```

Reason:

Only after contracts, matching, and metrics are stable should the CLI tie them together.

### E. Regression pass

Run:

```bash
pytest tests/test_prior_contracts.py -q
pytest tests/test_calibration_matching.py -q
pytest tests/test_calibration_metrics.py -q
pytest tests/test_calibrate_priors_cli.py -q

pytest tests/test_ir_contracts.py -q
pytest tests/test_entity_contracts.py -q
pytest tests/test_connector_common.py -q
pytest tests/test_backend_connectors.py -q
pytest tests/test_run_backends_config.py -q

pytest tests/ -q
git diff --name-only main..HEAD
```

Reason:

Plan 3 must not perturb Plans 1 or 2.

---

## 14. What Plan 3 must not accidentally become

Do not implement consensus here.

Bad:

```text
"Select MinerU's block over PaddleOCR's block."
"Resolve page-number versus footnote ambiguity."
"Change EntityProposalDocument confidence in connector output."
"Merge backend entities into one document-level linked graph."
"Build DoclingDocument."
```

Good:

```text
"MinerU section detector has calibrated confidence 0.78."
"PaddleOCR page_number prior is underpowered with support 3."
"DeepSeek has no samples for table relations, so use default confidence."
"caption_of relation prior for mineru is calibrated from tp/fp/fn counts."
```

This is the correct level for Plan 3.

---

## 15. Practical reviewer checklist

The reviewer should ask:

```text
1. Are priors computed from Plan 2 outputs, not from raw backend text?
2. Are prediction files validated as PageExtractionIR and EntityProposalDocument?
3. Is ground truth normalised into CalibrationTruthDocument?
4. Are block, entity, relation, and calibration_key priors all represented?
5. Are precision, recall, f1, support, and smoothed confidence correct?
6. Are underpowered and no-sample cases explicit?
7. Does the CLI write one prior file per backend?
8. Does the CLI write a calibration report?
9. Does strict mode fail on invalid input?
10. Does lenient mode warn and continue?
11. Are Plans 1 and 2 untouched?
12. Is git diff contained inside the whitelist?
```

---

## 16. Main design boundary for Plan 4

Plan 4, the consensus factory, may consume:

```text
CalibrationPriorDocument
lookup_confidence(prior, block_kind, "heading")
lookup_confidence(prior, entity_type, "page_number")
lookup_confidence(prior, relation_type, "caption_of")
lookup_confidence(prior, calibration_key, "mineru:section:heading_section_detector")
```

Plan 4 must not need to know how these priors were computed.

That is the main deliverable of Plan 3.

---

## PR_review #23

- verdict: fail
- whitelist_violations: []
- test_contract_violations:
    - The PR did not implement the test contract counts from section 10: `tests/test_prior_contracts.py` has 12 tests instead of the expected 25, `tests/test_calibration_matching.py` has 5 instead of 20, `tests/test_calibration_metrics.py` has 3 instead of 15, and `tests/test_calibrate_priors_cli.py` has 4 instead of 11.
    - Fixture contracts from section 11 are not met: `minimal_truth/truth.json` contains paragraph, page_number, caption, figure, and caption_of data instead of a single heading block, one section entity, and no relations; `mixed_predictions/truth.json` omits equation, reference_section, and reference_item truth entities; the paddleocr fixture has no false positive footnote and no correct page_number.
    - The run log records `tests_fail_real=[initial_token_overlap_assertion_fixed]` for task B while still marking the PR `ready_for_review`; real failures during an agent task chain must halt or be resolved without being left as a failed-test entry.
    - The required acceptance command `git diff --name-only main..HEAD` did not execute successfully because the checkout lacks a `main` ref. The fallback `git diff --name-only HEAD^..HEAD` was reviewed, but it is not the exact required command.
- dependency_violations: []
- tasks_promoted: []
- notes:
    - The changed files in `HEAD^..HEAD` are within the Plan 3 whitelist, treating `run_log.md` as whitelisted by the agent protocol.
    - The implemented automated tests pass, and the broader repository suite passes in this checkout, but passing a smaller-than-specified test set is not enough to satisfy section 10.
    - Because the verdict is fail, no task is promoted to `done`.

## Feedback #23

- response_to: PR_review #23
- decision: current plan closed by human feedback.
- notes:
    - The follow-up agent work after this review addressed the test-count and fixture-contract findings in later commits, but no additional review-mode promotion is being requested in this feedback entry.
    - This is not an archive-plan action because the human did not use the explicit `archive plan` instruction required by `agent.md`; `history.md` and `run_log.md` are therefore left unchanged.
    - Future work should start from a new explicit plan or an explicit `archive plan` instruction if the canonical plan files should be reset.
