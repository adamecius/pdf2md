# Plan 1 — IR contracts: `PageExtractionIR` and `ConsensusIR`

Status: draft, ready to implement
Repo: `pdf2md`
Owner: data contracts
Sequence: this is plan 1 of 6. It blocks plans 2–6.

---

## 0. Scope and constraints

This plan defines and freezes two Pydantic v2 contracts that every later plan depends on:

- `PageExtractionIR` — what each backend connector (plan 2) emits per page.
- `ConsensusIR` — what the consensus factory (plan 4) emits per document.

This plan **only** delivers schemas, validators, JSON-Schema export, and the test suite that certifies them. **No** consensus logic, **no** connector code, **no** linker, **no** changes to existing backends.

The plan completes when `pytest` passes the test module listed in §7 against an implementation that touches only the files in §3.

Hard constraints:
- Pure Pydantic v2. No new runtime dependencies. `pydantic>=2` is already in `pyproject.toml`.
- No I/O in the model layer beyond `model_dump`/`model_validate` and `model_json_schema`.
- The contracts are versioned (`SCHEMA_VERSION = "1.0.0"`); bumping is out of scope here.
- Files outside the whitelist must remain byte-identical.

Out of scope:
- Loading real backend outputs.
- Consensus heuristics or scoring.
- Calibrated confidence priors (those land in plan 3 and are referenced from plan 4).
- Schema migration / backward-compat layer (only one version exists today).

---

## 1. Why two IRs and not one

`PageExtractionIR` is *evidence* — what one backend saw on one page. It is per-backend, per-page, never canonical, may overlap or contradict another backend.

`ConsensusIR` is *resolution* — a per-document, page-keyed structure where every block has a unique canonical identity, an explicit `selection_mode`, and a back-reference to the contributing `ExtractionBlock` candidates. Conflicts that the consensus factory could not resolve are first-class objects (`Conflict`), not warnings.

Conflating the two is the current sin of `consensus_report.py` + `semantic_document_builder.py`: candidates and resolutions live in the same object, and there is no place to record an unresolved conflict that the linker (plan 5) might still resolve.

---

## 2. File whitelist (minimal)

The reviewer will diff against `main` and reject the plan if any file outside this list is modified.

```
src/pdf2md/models/__init__.py
src/pdf2md/models/ir.py
tests/test_ir_contracts.py
tests/data/ir_fixtures/page_extraction_ir.min.json
tests/data/ir_fixtures/page_extraction_ir.full.json
tests/data/ir_fixtures/consensus_ir.min.json
tests/data/ir_fixtures/consensus_ir.full.json
tests/data/ir_fixtures/consensus_ir.with_conflicts.json
```

Notes:
- `src/pdf2md/models/__init__.py` is touched **only** to add re-exports (`from .ir import …`). If the existing `__init__.py` already re-exports `Document/Page/Block`, the new exports are appended; existing names are not removed.
- `src/pdf2md/models/ir.py` currently contains placeholder text (per `next_plan.md` §13); it gets replaced.
- Existing `tests/test_ir_scaffolding.py` is **not** edited. It stays as a placeholder. The new test file `tests/test_ir_contracts.py` is the certifying module.
- The five JSON fixtures are tiny (each ≤ 2 KB), hand-crafted, and committed.
- `pyproject.toml` is **not** touched.

---

## 3. Module layout (single file)

`src/pdf2md/models/ir.py` exposes, in this order:

```
SCHEMA_VERSION                # "1.0.0"
CoordOrigin                   # Enum: BOTTOMLEFT, TOPLEFT
BlockKind                     # Enum: paragraph, heading, formula, figure, table,
                              #       caption, list, list_item, footnote, page_number,
                              #       header, footer, reference, bibitem, code, unknown
SelectionMode                 # Enum: agreed, single_source, fallback, unresolved
ConflictKind                  # Enum: text_conflict, kind_conflict, bbox_conflict,
                              #       presence_conflict, order_conflict
BBox                          # frozen model
Span                          # frozen model
PageSize                      # frozen model
ExtractionBlock
PageExtractionIR
Conflict
ConsensusBlock
ConsensusPage
BackendManifest
ConsensusIR
```

Everything is `BaseModel` with `model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True)`.

ID conventions enforced by `field_validator`:

- `ExtractionBlock.id` matches `^[a-z0-9_-]+:[A-Za-z0-9_.-]+:p\d+:b\d+$` — `<backend>:<doc>:p<page>:b<index>`.
- `ConsensusBlock.id` matches `^con:[A-Za-z0-9_.-]+:p\d+:b\d+$`.
- `Conflict.id` matches `^conf:[A-Za-z0-9_.-]+:\d+$`.

These regexes live next to the models as module-level constants so plans 2 and 4 can reuse them.

---

## 4. `PageExtractionIR` — fields

```
schema_name: Literal["pdf2md.PageExtractionIR"]
schema_version: Literal["1.0.0"]
document_id: str            # non-empty
backend: str                # canonical backend name; non-empty
backend_version: str | None
page_no: int                # >= 1
page_size: PageSize         # {width: float > 0, height: float > 0}
blocks: list[ExtractionBlock]
raw_artifact_ref: str | None  # path or json-pointer to backend's raw output
metadata: dict[str, Any]    # free-form, opaque
```

`ExtractionBlock`:

```
id: str
backend: str                # must equal parent.backend
page_no: int                # must equal parent.page_no
kind: BlockKind
bbox: BBox | None           # None allowed (e.g., logical-only output)
order: int                  # >= 0, monotonic recommended (not enforced cross-block)
text: str
confidence: float | None    # 0.0 <= c <= 1.0
spans: list[Span] | None    # optional sub-block spans
raw_ref: str | None
metadata: dict[str, Any]
```

`Span`:

```
text: str
bbox: BBox | None
char_start: int             # >= 0
char_end: int               # > char_start
```

`BBox`:

```
l: float
t: float
r: float
b: float
coord_origin: CoordOrigin
```

Validators on `BBox`:
- `r > l`
- For `BOTTOMLEFT`: `t > b`
- For `TOPLEFT`:    `b > t`

The mismatch of conventions is the bug source we want to kill at construction time.

`PageSize`:

```
width: float > 0
height: float > 0
```

Cross-field validators on `PageExtractionIR` (model-level, after fields):
- All `blocks[i].page_no == self.page_no`.
- All `blocks[i].backend == self.backend`.
- `len({b.id for b in blocks}) == len(blocks)` (unique ids within a page).

---

## 5. `ConsensusIR` — fields

```
schema_name: Literal["pdf2md.ConsensusIR"]
schema_version: Literal["1.0.0"]
document_id: str
page_count: int             # >= 0
pages: list[ConsensusPage]
conflicts: list[Conflict]
backends: list[BackendManifest]
agreement_summary: dict[str, Any]
metadata: dict[str, Any]
```

`ConsensusPage`:

```
page_no: int                # >= 1
page_size: PageSize
blocks: list[ConsensusBlock]
```

`ConsensusBlock`:

```
id: str                                 # con:<doc>:p<n>:b<k>
kind: BlockKind
bbox: BBox | None
order: int
text: str
selection_mode: SelectionMode
selected_source: str | None             # backend name; None iff selection_mode==unresolved
agreement_score: float                  # 0.0 <= s <= 1.0
candidate_ids: list[str]                # ExtractionBlock.id values, cross-backend
conflict_ids: list[str]                 # Conflict.id values; may be empty
metadata: dict[str, Any]
```

`Conflict`:

```
id: str
kind: ConflictKind
page_no: int
candidate_ids: list[str]                # at least 2
description: str
resolution: Literal["unresolved", "resolved_by_consensus", "resolved_by_linker"]
selected_candidate_id: str | None       # in candidate_ids when resolution != unresolved
metadata: dict[str, Any]
```

`BackendManifest`:

```
backend: str
backend_version: str | None
manifest_ref: str | None                # path to local_run_manifest.json, etc.
prior_ref: str | None                   # forward-compat for plan 3 priors; not validated here
```

Cross-field validators on `ConsensusIR` (model-level):
- `page_count == len(pages)`.
- All `pages[i].page_no` are unique and contiguous starting at 1 when `page_count > 0`. (Use a dedicated method, not the validator, if you'd rather not enforce contiguity strictly; **the test will assert contiguity**.)
- Every `block.candidate_ids` element matches the `ExtractionBlock.id` regex (referential consistency is not checked here — that's a plan-4 concern).
- Every `block.conflict_ids` element exists in `self.conflicts`.
- For every `Conflict`: `selected_candidate_id` ∈ `candidate_ids` when `resolution != "unresolved"`.
- For every `ConsensusBlock`:
  - `selection_mode == "unresolved"` ⇒ `selected_source is None` and `len(conflict_ids) >= 1`.
  - `selection_mode != "unresolved"` ⇒ `selected_source is not None`.

Helper functions (also exported from `ir.py`, **pure**, no I/O):

```
extraction_id(backend, document_id, page_no, block_index) -> str
consensus_id(document_id, page_no, block_index) -> str
conflict_id(document_id, index) -> str
```

These are the canonical id factories used by plans 2 and 4.

---

## 6. JSON Schema export

The two top-level models must produce valid JSON Schemas via `model_json_schema()`. The test suite asserts:

- `schema["title"]` is `"PageExtractionIR"` / `"ConsensusIR"`.
- `schema["properties"]["schema_name"]["const"]` matches the literal.
- `schema["properties"]["schema_version"]["const"] == "1.0.0"`.
- `schema["additionalProperties"] is False` (because `extra="forbid"`).
- The schemas are round-trippable through `json.dumps(...)` (i.e., no non-serialisable artefacts leak).

No external `jsonschema` package needed; structural assertions on the dict are enough.

---

## 7. Tests (the milestone)

All tests live in `tests/test_ir_contracts.py`. They are organised in `pytest` classes per concern. Every test has a docstring stating the contract it certifies; the reviewer reads those.

```
class TestEnums:
    test_block_kind_values_match_specification
    test_selection_mode_values_match_specification
    test_conflict_kind_values_match_specification
    test_coord_origin_values_match_specification

class TestBBox:
    test_valid_bbox_bottomleft_constructs
    test_valid_bbox_topleft_constructs
    test_bbox_rejects_l_ge_r
    test_bbox_rejects_inverted_t_b_for_bottomleft
    test_bbox_rejects_inverted_b_t_for_topleft
    test_bbox_extra_field_forbidden

class TestPageSize:
    test_valid_page_size
    test_page_size_rejects_zero_or_negative

class TestExtractionBlock:
    test_minimal_construction
    test_id_pattern_accepted
    test_id_pattern_rejected_when_malformed
    test_confidence_in_unit_interval
    test_extra_field_forbidden

class TestPageExtractionIR:
    test_minimal_round_trip
    test_full_round_trip                  # uses page_extraction_ir.full.json
    test_blocks_must_share_page_no
    test_blocks_must_share_backend_name
    test_block_ids_must_be_unique
    test_schema_name_and_version_pinned
    test_json_schema_export_basic_shape

class TestConsensusBlock:
    test_unresolved_requires_no_selected_source_and_has_conflicts
    test_resolved_requires_selected_source
    test_agreement_score_in_unit_interval
    test_candidate_ids_must_match_extraction_id_pattern

class TestConflict:
    test_unresolved_allows_no_selected_candidate
    test_resolved_requires_selected_candidate_in_candidate_ids
    test_minimum_two_candidates

class TestConsensusIR:
    test_minimal_round_trip
    test_full_round_trip                  # uses consensus_ir.full.json
    test_with_conflicts_round_trip        # uses consensus_ir.with_conflicts.json
    test_page_count_must_match_pages_length
    test_pages_must_be_contiguous_from_one
    test_block_conflict_ids_must_exist_in_top_level_conflicts
    test_schema_name_and_version_pinned
    test_json_schema_export_basic_shape

class TestIdFactories:
    test_extraction_id_format
    test_consensus_id_format
    test_conflict_id_format
    test_factories_round_trip_through_validators
```

Implementation rules for the tests:
- Every "round-trip" test does: `model = T.model_validate_json(fixture_path.read_text())` → `payload = model.model_dump(mode="json")` → `T.model_validate(payload)` → assert deep-equality of both dumps.
- Every "rejects" test uses `pytest.raises(ValidationError)`.
- No test imports anything other than `json`, `pathlib`, `pytest`, `pydantic`, and `pdf2md.models.ir`.
- No test reads outside `tests/data/ir_fixtures/`.
- No fixtures rely on disk state mutated by previous tests.

The five fixtures cover:
- `page_extraction_ir.min.json` — one block, no bbox, no spans.
- `page_extraction_ir.full.json` — three blocks with bbox, spans, confidence, raw_ref, metadata.
- `consensus_ir.min.json` — one page, one resolved block, no conflicts.
- `consensus_ir.full.json` — three pages, mixed selection modes, agreement summary populated.
- `consensus_ir.with_conflicts.json` — one unresolved block referencing a `Conflict` with two candidates.

---

## 8. Acceptance criteria

The reviewer accepts the plan as complete when **all** of the following hold:

1. `pytest tests/test_ir_contracts.py -q` exits with code 0 and reports the full count of tests listed in §7. No `xfail`, no `skip`.
2. `git diff --name-only main..HEAD` returns a subset of the whitelist in §2. Any extraneous file fails the review.
3. `python -c "from pdf2md.models.ir import PageExtractionIR, ConsensusIR; print(PageExtractionIR.model_json_schema()['title'], ConsensusIR.model_json_schema()['title'])"` prints `PageExtractionIR ConsensusIR` without error.
4. The five fixture files load via `model_validate_json` without warnings.
5. No file outside the whitelist has been changed (`git diff --stat` confirms).
6. `pytest tests/ -q` (whole suite) shows no regression: existing tests must still pass at their previous count or above.

Criterion 6 is what guarantees we did not break the existing `Document/Page/Block` schema or the placeholder `tests/test_ir_scaffolding.py`.

---

## 9. Implementation order (internal)

A. Add the enums, `BBox`, `Span`, `PageSize`, `PageExtractionIR.ExtractionBlock`, `PageExtractionIR`. Run only the `TestEnums`, `TestBBox`, `TestPageSize`, `TestExtractionBlock`, `TestPageExtractionIR` classes.

B. Add `Conflict`, `ConsensusBlock`, `ConsensusPage`, `BackendManifest`, `ConsensusIR`. Run the rest.

C. Add the three id factories and run `TestIdFactories`.

D. Add re-exports to `src/pdf2md/models/__init__.py`. Re-run the entire `tests/` suite to confirm criterion 6.

Each step is independently runnable; the test file is committed last so the reviewer sees the green CI on the final commit.

---

## 10. Open questions (track separately, do not block this plan)

- Do we want `bbox` to default to `None` for logical-only blocks (e.g., `bibitem` from a connector that does not localise references)? Current draft: yes.
- Should `agreement_score` be `None` for `selection_mode == "single_source"`? Current draft: no — single-source is an agreement of one, score = `1.0 / num_backends_seen`. The exact formula is plan 4's job; this plan only enforces `0 ≤ s ≤ 1`.
- Whether `metadata` should be typed (`dict[str, str | int | float | bool | None | list | dict]`) instead of `dict[str, Any]` — left as `Any` for now to avoid coupling tests to Pydantic's serialization quirks.
---

## PR_review #15

- verdict: fail
- whitelist_violations: []
- test_contract_violations:
  - `pytest tests/test_ir_contracts.py -q` is not reproducible in the review environment from the committed tree: collection fails with `ModuleNotFoundError: No module named 'pdf2md'`. The previous PR relied on an editable install to make the package importable, but that install is not part of the committed patch or declared plan dependencies.
  - `pytest tests/ -q` fails during collection. The missing `.current/latex_docling_groundtruth/batch_001` fixture directory is a plausible environmental limitation, but the import-path failures (`pdf2md`, `tools`, and `tests`) show the committed tree does not satisfy the exact test commands as written without environment mutation.
  - The run log marks A6 as environmental but also records an undeclared environment-modifying command (`python -m pip install -e .`) used earlier in the PR. That makes the test evidence insufficient for promotion.
- dependency_violations:
  - `python -m pip install -e .` was used and recorded as an external environment-modifying command, but no plan dependency or current prompt authorized `pip`/editable installs for this plan.
- tasks_promoted: []
- notes:
  - The diff is limited to the plan's source/test fixture whitelist plus `run_log.md`, which is whitelisted by the agent protocol by default.
  - The core IR implementation and contract-test coverage are directionally aligned with the plan, but review cannot accept a PR whose required tests only pass after an undeclared editable install.
  - `current_plan.md` has no `## Status` section, so review could not update task state even if promotion were otherwise eligible.
