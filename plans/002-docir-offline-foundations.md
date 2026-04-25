# Add DocIR-first offline foundations without breaking deterministic v1

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

The repository has a working deterministic-first milestone, but the next architecture step needs a canonical document representation that is not tied to Markdown. A prior proposal introduced the DocIR-first and backend-modular direction. This plan adapts that direction to current repository constraints so we can evolve safely: keep the current CLI and profiler/router behavior, keep default tests offline, and add DocIR and backend interfaces as foundations only.

## Scope

In scope:
- Add DocIR core modules under `doc2md/ir/` with minimal, extensible models and JSON serialization helpers.
- Add backend interface foundations under `doc2md/backends/` with a deterministic backend adapter that emits minimal DocIR from the existing pipeline.
- Add exporters under `doc2md/exporters/` where Markdown is generated from DocIR and JSONL chunks expose provenance fields needed for RAG workflows.
- Add optional backend stubs with lazy imports and clear missing-dependency errors.
- Add offline unit tests for DocIR serialization, stable IDs, exporters, and optional-backend error behavior.
- Keep `python -m doc2md --help` and existing deterministic pipeline behavior working.

Out of scope:
- Running OmniDocBench by default.
- Installing visual model dependencies.
- Replacing current profiler/router heuristics.
- Implementing full candidate-merging, orchestration, or heavy backend execution.
- Making Markdown canonical.

## Current known state

- The active completed milestone is `plans/001-deterministic-extraction.md`, which already delivers profile -> route -> deterministic extraction -> Markdown output for suitable pages.
- Current architecture guidance in `AGENTS.md` enforces profiler/router/strategy separation and offline-friendly default dependencies.
- The prior proposal contained a broader multi-plan architecture that is directionally compatible but assumes a larger reorganization and permissive heavy-backend growth.
- The repository currently has no `doc2md/ir/`, `doc2md/backends/`, or `doc2md/exporters/` package structure.

Compatibility conclusion:
- The proposal is compatible if staged as additive foundations and if the deterministic lane remains the default and always-available path.
- Optional heavy backends must remain optional and lazy-loaded.
- License-aware usage must remain explicit: core path should stay dependency-light and suitable for free, offline learning workflows.

## Target behavior

After this work:

1. `python -m doc2md --help` still works from the package entry point.
2. A deterministic command can emit a minimal `*.docir.json` output through the new foundations (even if content richness is initially limited).
3. Markdown output is produced by exporting from DocIR rather than directly from raw extraction output in the new path.
4. `pytest -q` passes without network, GPU, OmniDocBench, or heavy backend packages.
5. Optional backends fail gracefully with clear install guidance when unavailable.

## Design and decisions

DocIR model strategy:
- Align with the proposal requirement for schema validation by using Pydantic models for `doc2md/ir/schema.py` when implementing this phase.
- Include minimal core entities only for this phase: `DocumentIR`, `PageIR`, `BlockIR`, `MediaRef`, `Provenance`, and `BackendRun`.
- Keep schema extensible and preserve stable IDs and provenance fields.

Serialization strategy:
- Add explicit helpers in `doc2md/ir/serialize.py` for `to_dict`, `from_dict`, `to_json`, and `from_json`.
- Add validation-oriented helpers (for example `model_validate`/schema checks) to ensure fixture and runtime DocIR payloads are schema-checked.
- Keep canonical persisted representation as `*.docir.json`.

Backend interface strategy:
- Define `ExtractionBackend` base contract in `doc2md/backends/base.py`.
- Implement a simple registry with explicit names in `doc2md/backends/registry.py`.
- Add `doc2md/backends/deterministic.py` adapter using existing profiler/router/strategy components.

Exporter strategy:
- Implement DocIR exporters under `doc2md/exporters/`.
- `markdown.py` must read DocIR objects only.
- `chunks_jsonl.py` must include `chunk_id`, `text`, `markdown`, `page_indexes`, `source_block_ids`, `media_refs`, and optional `heading_path`.

Optional backend stubs:
- Add stub modules for docling/mineru/paddleocr_vl/glm_ocr/dots_ocr/firered/marker/olmocr.
- Each stub uses lazy import and raises a precise runtime error that states which package is missing and that the backend is optional.

Testing strategy:
- Keep default tests entirely offline and synthetic.
- Add focused tests only for newly introduced foundations.

## Milestones

### Milestone 1 - Add architecture policy updates and plan alignment

Files:
- `AGENTS.md`
- `plans/002-docir-offline-foundations.md`

Work:
Document the non-commercial/free-learning usage intent and license-aware dependency guidance. Record the adapted execution plan that maps proposal ideas to current architecture and phased delivery.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help

Expected result:
CLI help still works and planning docs are consistent.

### Milestone 2 - Introduce DocIR core and serializers

Files:
- `doc2md/ir/__init__.py`
- `doc2md/ir/schema.py`
- `doc2md/ir/ids.py`
- `doc2md/ir/serialize.py`
- `doc2md/ir/normalize.py`

Work:
Implement minimal canonical schema, stable ID helpers, and JSON serialization helpers.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_ir_serialize.py tests/test_ir_ids.py tests/test_ir_validation.py

Expected result:
DocIR round-trip, stable IDs, and schema validation behavior are validated without external services.

### Milestone 3 - Add backend interface + deterministic DocIR adapter + exporters

Files:
- `doc2md/backends/__init__.py`
- `doc2md/backends/base.py`
- `doc2md/backends/registry.py`
- `doc2md/backends/deterministic.py`
- `doc2md/exporters/__init__.py`
- `doc2md/exporters/json_ir.py`
- `doc2md/exporters/markdown.py`
- `doc2md/exporters/chunks_jsonl.py`

Work:
Add backend contract, registry, deterministic adapter, and exporters that consume DocIR.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help
    pytest -q tests/test_markdown_export.py tests/test_chunks_jsonl.py

Expected result:
CLI remains stable and exporters work from DocIR fixtures.

### Milestone 4 - Add optional backend stubs and offline behavior tests

Files:
- `doc2md/backends/docling_backend.py`
- `doc2md/backends/mineru_backend.py`
- `doc2md/backends/paddleocr_vl_backend.py`
- `doc2md/backends/glm_ocr_backend.py`
- `doc2md/backends/dots_ocr_backend.py`
- `doc2md/backends/firered_backend.py`
- `doc2md/backends/marker_backend.py`
- `doc2md/backends/olmocr_backend.py`
- `tests/test_missing_optional_backends.py`

Work:
Add lazy-import backend stubs and tests confirming clear optional dependency errors.

Validation:

    cd /workspace/pdf2md
    pytest -q tests/test_missing_optional_backends.py

Expected result:
Missing optional dependency messages are explicit and deterministic.

### Milestone 5 - Integrate minimal DocIR output path in CLI

Files:
- `doc2md/cli.py`
- optional small updates in `doc2md/config.py` or `doc2md/models.py`

Work:
Add a minimally invasive path to emit deterministic DocIR JSON while preserving current CLI behavior and existing deterministic Markdown output.

Validation:

    cd /workspace/pdf2md
    python -m doc2md --help
    python -m doc2md groundtruth/test1.pdf -o /tmp/doc2md_out -vv
    pytest -q

Expected result:
Help works, deterministic run succeeds, and tests remain offline.

## Validation

Repository root validation commands for this plan:

    cd /workspace/pdf2md
    python -m doc2md --help
    python -m doc2md groundtruth/test1.pdf -o /tmp/doc2md_out -vv
    pytest -q

Success signals:
- CLI remains package-runnable.
- Deterministic processing still produces usable output.
- DocIR serialization/export tests pass.
- Optional backend stubs do not break default tests.

## Risks and rollback notes

- Risk: coupling DocIR integration too tightly to current deterministic flow can break the existing CLI behavior. Mitigation: add DocIR path incrementally and preserve current success path until tests pass.
- Risk: introducing heavy dependencies accidentally. Mitigation: keep core implementation in stdlib + existing dependencies; use lazy optional stubs only.
- Risk: schema churn causes fragile tests. Mitigation: keep minimal schema and grow fields additively.
- Rollback: all new packages (`ir`, `backends`, `exporters`) are additive and can be temporarily bypassed by keeping current deterministic lane in place.

## Progress

- [x] 2026-04-25: Evaluated proposal compatibility against current `AGENTS.md` and active plan.
- [x] 2026-04-25: Added adapted execution plan for DocIR offline foundations.
- [x] 2026-04-25: Removed the temporary `plan_proposal/` workspace after integrating its direction into repository-level planning.
- [x] 2026-04-25: Implemented backend interface foundation (`doc2md/backends/base.py`, `registry.py`, `deterministic.py`) and optional backend stubs.
- [x] 2026-04-25: Added offline tests for backend registry, optional dependency failures, and deterministic DocIR emission.

## Surprises & Discoveries

- 2026-04-25: The prior proposal treated license restrictions as less central, but repository-level direction now explicitly prioritizes free-learning and license-aware optional dependency choices.

## Decision Log

- 2026-04-25: Accept proposal direction (DocIR-first + modular backends) but stage it incrementally to avoid breaking deterministic v1.
- 2026-04-25: Keep default stack dependency-light and offline; heavy/uncertain-license backends remain optional stubs.

## Outcomes & Retrospective

- 2026-04-25: Proposal has been adapted into a concrete, architecture-compatible ExecPlan that can be implemented in phases without destabilizing the current milestone.
