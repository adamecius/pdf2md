# Plan 006_0: Semantic Layer Integration & Label Extension

## Status: active
## Date: 2026-05-24
## Depends on: Plan 005_0 (human_verified, archived as M20)

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Branch name:
plan-006-0-semantic-integration

Source plan:
plans/006_0-semantic-layer-integration-labels.md

---

## 1. Goal

Integrate the three standalone semantic backends installed by Plan 005_0
(`backend/semantic/grobid`, `backend/semantic/deepseek_vl2`,
`backend/semantic/regex`) into the `pdf2md` codebase via a unified
`SemanticBackend` interface. Define the `CrossReferenceGraph` pydantic
schema as a sidecar contract, add a deterministic marker resolver, and
provide an ensemble runner that merges results from multiple semantic
backends. This plan does NOT yet add CLI integration for `pdf2md convert`
nor a semantic router — those are deferred to Plan 006_1 once the schema
and adapters land.

Scope reductions vs. the source plan:

- Profiler/router extension (source §3, §4) → **deferred to Plan 006_1**;
  Plan 006_0 only ships the schema, adapters, resolver, and ensemble.
- CLI `--semantic` flag integration (source §7, §8 cli.py) → **deferred to
  Plan 006_1**; this plan ships a standalone `tools/build_cross_references.py`
  CLI as the proof-of-life entry point.

## 2. Schema: CrossReferenceGraph (new pydantic models)

Add to `src/pdf2md/models/cross_ref.py` (new module, registered via
`src/pdf2md/models/__init__.py`):

```python
class RefType(str, Enum):
    FIGURE, TABLE, EQUATION, THEOREM, DEFINITION, PROOF,
    COROLLARY, EXAMPLE, SECTION, CHAPTER, BIBLIOGRAPHY, FOOTNOTE

class RefMarker(BaseModel):
    source_ref: str               # JSON pointer to DocItem: "#/texts/42"
    marker_text: str
    marker_type: RefType
    char_offset: tuple[int, int]
    confidence: float
    backend: str

class RefEdge(BaseModel):
    marker: RefMarker
    target_ref: str | None
    resolved: bool
    resolution_method: str        # "exact" | "fuzzy" | "grobid_tei" | "unresolved"

class SemanticEntity(BaseModel):
    item_ref: str
    entity_type: RefType
    label: str | None
    confidence: float
    backend: str

class CrossReferenceGraph(BaseModel):
    schema_version: str = "1.0"
    doc_hash: str
    markers: list[RefMarker]
    edges: list[RefEdge]
    entities: list[SemanticEntity]
    backend_versions: dict[str, str]
```

Persisted as `cross_references.json` alongside DoclingDocument JSON.

## 3. SemanticBackend interface and adapters

```python
class SemanticBackend(ABC):
    @abstractmethod
    def extract(
        self,
        pdf_path: Path,
        text_items: list[dict] | None,
        output_dir: Path,
    ) -> CrossReferenceGraph: ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def version(self) -> str: ...
```

Adapters (all live under `src/pdf2md/semantic/`):

- `regex_adapter.py` — wraps `backend/semantic/regex/patterns.py`. **In-process**
  (no subprocess); the regex backend is stdlib-only.
- `grobid_adapter.py` — wraps `backend/semantic/grobid/grobid_client.py` and
  `tei_parser.py`. **In-process** (HTTP client only); the Docker daemon is
  managed externally and is a precondition for runtime use, not for import.
- `vlm_adapter.py` — wraps `backend/semantic/deepseek_vl2/`. **Subprocess**
  via `conda run -n pdf2md-deepseek-vl2 python backend/semantic/deepseek_vl2/smoke_test.py ...`,
  matching the pattern used by `pipeline.runner` for extraction backends.
  The adapter MUST NOT import `torch` or `transformers` from the main
  `pdf2md` env.

All adapters convert their native output into a `CrossReferenceGraph`.

## 4. Resolver

`src/pdf2md/semantic/resolver.py` — deterministic module that consumes
`RefMarker`s and a `LinkedStructure` (or a list of structural items) and
emits `RefEdge`s. Resolution strategies:

- **Exact**: "Figure 3" → search caption/label text for "Figure 3".
- **Fuzzy**: normalize "Fig.", "fig.", "Figure" → single canonical form.
- **Bibliography**: "[15]" → match against entries with
  `entity_type=BIBLIOGRAPHY`.
- **Footnote**: superscript "3" → match against same-page FOOTNOTE markers.
- **Cross-chapter**: "Chapter 5" → match against SECTION/CHAPTER entries.

If no match is found, emit a `RefEdge` with `resolved=False` and
`resolution_method="unresolved"`.

## 5. Ensemble

`src/pdf2md/semantic/ensemble.py` — runs a list of `SemanticBackend`s,
collects each `CrossReferenceGraph`, and merges them with deduplication:

- Markers are deduped on `(marker_text, source_ref, char_offset)` —
  keeping the highest-confidence entry.
- Entities are deduped on `(item_ref, entity_type)`.
- `backend_versions` is merged as a dict.

## 6. Proof-of-life CLI

`tools/build_cross_references.py` — minimal CLI:

```
python tools/build_cross_references.py \
    --pdf <input.pdf> \
    --backend regex \
    --out-dir out/
```

Behaviour:

- `--backend regex` runs the regex adapter on a flat text dump of the PDF
  (loaded via the existing `pipeline.io` helpers if available, otherwise
  the user passes `--text <text_file>`); always available in the main
  pdf2md env.
- `--backend grobid` runs the grobid adapter; **gated** at runtime on the
  GROBID service being reachable on `http://localhost:8070`; otherwise
  exits with status 3 and a clean message.
- `--backend vlm` runs the vlm adapter; **gated** on the
  `pdf2md-deepseek-vl2` conda env existing; otherwise exits 3.
- `--backend ensemble` runs all available backends and emits the merged
  graph.

Output: `<out-dir>/cross_references.json` plus a small text summary.

## 7. Tests

`tests/test_cross_ref_contracts.py`:

- Round-trip `CrossReferenceGraph` ↔ JSON.
- Validation: empty doc_hash, invalid RefType, confidence outside [0,1].
- Marker dedup logic in the ensemble.

`tests/test_semantic_regex_adapter.py`:

- Feed the regex adapter the `tests/data/semantic_fixtures/sample_text.txt`
  fixture (from Plan 005_0).
- Assert ≥3 distinct `marker_type` values present in the resulting
  `CrossReferenceGraph`.
- Confirm `backend_versions["regex"]` is non-empty.

`tests/test_semantic_resolver.py`:

- Synthetic fixture: 3 markers (`Figure 3`, `[15]`, `Section 2.1`) +
  3 candidate targets. Assert all three are resolved with the correct
  `resolution_method`.
- One unresolved marker — assert `resolved=False`,
  `resolution_method="unresolved"`.

`tests/test_semantic_ensemble.py`:

- Two `FakeSemanticBackend` instances returning overlapping markers with
  different confidences. Assert dedup keeps the higher confidence and
  merges `backend_versions`.

`tests/test_build_cross_references_cli.py`:

- `--backend regex --text sample_text.txt --out-dir <tmp>` → exit 0,
  `cross_references.json` exists with ≥1 marker.
- `--backend grobid` with no GROBID running → exit 3, clean message.
- `--backend vlm` with no `pdf2md-deepseek-vl2` env → exit 3.

## 8. File structure (new)

```text
src/pdf2md/models/cross_ref.py            # New schema module
src/pdf2md/models/__init__.py             # Re-exports
src/pdf2md/semantic/__init__.py
src/pdf2md/semantic/base.py               # SemanticBackend ABC
src/pdf2md/semantic/regex_adapter.py
src/pdf2md/semantic/grobid_adapter.py
src/pdf2md/semantic/vlm_adapter.py
src/pdf2md/semantic/resolver.py
src/pdf2md/semantic/ensemble.py
tools/build_cross_references.py
tests/test_cross_ref_contracts.py
tests/test_semantic_regex_adapter.py
tests/test_semantic_resolver.py
tests/test_semantic_ensemble.py
tests/test_build_cross_references_cli.py
```

## 9. Acceptance criteria

- [ ] `CrossReferenceGraph` schema defined as pydantic models in
      `src/pdf2md/models/cross_ref.py` and re-exported from `models/`.
- [ ] `SemanticBackend` ABC defined in `src/pdf2md/semantic/base.py`.
- [ ] Three adapters (`regex`, `grobid`, `vlm`) implement
      `SemanticBackend.extract()` and return `CrossReferenceGraph`.
- [ ] Resolver matches markers to targets using exact + fuzzy +
      bibliography + footnote + cross-chapter strategies.
- [ ] Ensemble merges multiple `CrossReferenceGraph`s with confidence-based
      dedup.
- [ ] `tools/build_cross_references.py` runs the regex backend end-to-end
      in the main `pdf2md` env (automated A1).
- [ ] All new test files pass: `pytest tests/test_cross_ref_contracts.py
      tests/test_semantic_regex_adapter.py tests/test_semantic_resolver.py
      tests/test_semantic_ensemble.py tests/test_build_cross_references_cli.py -q`
      (automated A2).
- [ ] No regressions: `pytest tests/ -q --ignore=tests/_legacy_temp` still
      green (automated A3).
- [ ] No imports from `backend/semantic/deepseek_vl2/vlm_client.py` or
      `pyhf-style torch/transformers` from the main `pdf2md` env. The VLM
      adapter only invokes the standalone smoke_test via subprocess
      (automated A4 via `grep`).

---

## File whitelist

```text
src/pdf2md/models/cross_ref.py
src/pdf2md/models/__init__.py
src/pdf2md/semantic/__init__.py
src/pdf2md/semantic/base.py
src/pdf2md/semantic/regex_adapter.py
src/pdf2md/semantic/grobid_adapter.py
src/pdf2md/semantic/vlm_adapter.py
src/pdf2md/semantic/resolver.py
src/pdf2md/semantic/ensemble.py
tools/build_cross_references.py
tests/test_cross_ref_contracts.py
tests/test_semantic_regex_adapter.py
tests/test_semantic_resolver.py
tests/test_semantic_ensemble.py
tests/test_build_cross_references_cli.py
current_plan.md
run_log.md
```

## Forbidden files

```text
src/pdf2md/pipeline/**/*
src/pdf2md/cli/**/*
src/pdf2md/connectors/**/*
src/pdf2md/calibration/**/*
src/pdf2md/consensus/**/*
src/pdf2md/linking/**/*
src/pdf2md/export/**/*
backend/**/*
project.md
ROADMAP.md
README.md
history.md
PLAN_TEMPLATE.md
agent.md
plans/**/*
docs/**/*
```

## Allowed dependencies

Python packages that may be imported by the new files. All are already
in the main `pdf2md` env:

```text
pydantic             (already required)
requests             (already transitively via docling)
pathlib, json, re, enum, abc, subprocess, sys, time, argparse  (stdlib)
pytest               (already required)
```

The VLM adapter MUST NOT import `torch` or `transformers` from the main
env — that env is `pdf2md-deepseek-vl2` and is invoked by subprocess.

## Allowed environment-modifying commands

```text
none in agent mode

(Plan 006_0 is in-tree code only — no Docker, no conda env creation,
no model downloads. Any runtime gating on Docker / GPU resources is
deferred to invocation time and exits cleanly when those resources
are absent.)
```

## 10. Human verification checkpoints

### Checkpoint H1 — Regex end-to-end via the new CLI

Required environment: main `pdf2md` env.

Command:

```bash
conda run -n pdf2md python tools/build_cross_references.py \
    --backend regex \
    --text tests/data/semantic_fixtures/sample_text.txt \
    --out-dir /tmp/cross_ref_smoke
```

Pass criteria:

```text
exit code 0
/tmp/cross_ref_smoke/cross_references.json exists
result.markers length > 0
result.backend_versions has key "regex"
```

### Checkpoint H2 — GROBID adapter (deferred to runtime; requires Docker)

Required environment: Docker daemon, GROBID running on port 8070.

Same gating as Plan 005 H1; the adapter exit-3 path is the agent-mode
test surface (test_build_cross_references_cli.py covers this). Full
round-trip is human-verified once Docker is available.

### Checkpoint H3 — VLM adapter (deferred to runtime; requires GPU + conda env)

Same gating as Plan 005 H2. Agent-mode test surface is the exit-3 path
when the `pdf2md-deepseek-vl2` env is not present.

---

## PR_reviews

(none yet)

## Feedback

(none yet)
