# PHASE 1 Code Review — old_code

**Project**: pdf2md  
**Date**: April 26, 2026  
**Scope**: Legacy review of `old_code/`, with emphasis on Task 1.2 (IR Deep Dive)

## 1) Executive Summary

The legacy codebase already contains a strong DocIR foundation that is close to the target architecture: explicit IR dataclasses, deterministic ID helpers, normalization utilities, JSON serialization helpers, and exporters that consume IR rather than deriving IR from Markdown. The most important blocker is **schema contract drift** between the implemented `DocumentIR` (`schema_version="0.1"`) and a separate “proposed” fixture contract used in groundtruth tests (`schema_version="docir.v0-proposed"`). Phase 2 should converge this into one canonical schema with explicit versioning/migration rules.

## 2) Legacy Structure Review (Task 1.1)

- `old_code/doc2md/cli.py` orchestrates extraction and can emit markdown + DocIR JSON/chunks from a single CLI invocation.
- `old_code/doc2md/backends/*` follows adapter-style backend separation and optional dependency handling.
- `old_code/doc2md/exporters/*` treats DocIR as canonical source, then derives Markdown/JSONL exports.
- `old_code/tests/*` already encodes important contracts for determinism, serialization stability, backend availability checks, and CLI behavior.

This maps well to the target architecture (light core + backend isolation + IR-centered flow).

## 3) IR Deep Dive (Task 1.2)

### 3.1 Current IR Building Blocks

Primary IR schema in `old_code/doc2md/ir/schema.py`:
- `DocumentIR` (top-level document payload).
- `PageIR` (page metadata + routing metadata).
- `BlockIR` (content units with type/role/text/markdown/relations via IDs).
- `MediaRef` (extracted media metadata).
- `Provenance` (backend/strategy/page/confidence lineage).
- `BackendRun` (execution run metadata and errors).

Supporting modules:
- `ids.py`: deterministic IDs for document/page/block/media.
- `normalize.py` + compatibility alias `normalise.py`: stable text normalization.
- `serialize.py` + alias `serialise.py`: dataclass ↔ dict/json helpers.

### 3.2 What Works Well

1. **Deterministic identity model**
   - Stable ID helpers exist and are tested for deterministic behavior.
2. **Clean serialization boundary**
   - Dataclass payloads are consistently converted with `to_dict/from_dict/to_json/from_json`.
3. **Backward-compatible naming shims**
   - `serialise.py` and `normalise.py` preserve UK spelling compatibility safely.
4. **IR-first exports**
   - Markdown exporter consumes `DocumentIR` and applies deterministic ordering/rendering rules.
5. **Provenance-aware block model**
   - `BlockIR.provenance` allows multi-backend lineage and quality metadata.

### 3.3 Gaps / Risks

1. **Schema drift across artifacts (highest priority)**
   - Implemented schema (`0.1`) differs from groundtruth “proposed” contract (`docir.v0-proposed`) in field names/shape.
   - Example: tests reference top-level fields like `source`, `body`, `furniture`, `groups`, `relations`, `created_at`, while implemented `DocumentIR` uses `source_path`, `pages`, `blocks`, etc.
2. **Dual model lineage**
   - `old_code/doc2md/models.py` contains non-IR pipeline dataclasses (profile/routing/page results) plus another `MediaRef` type, which can confuse boundaries unless naming/scope are enforced.
3. **No formal schema migration strategy**
   - Current code assumes direct constructor compatibility; version upgrades could break silently without migration/validation.
4. **Validation layer is implicit**
   - Dataclasses are lightweight, but there is no strict runtime schema validator (useful for backend adapter contracts).

## 4) Recommended Direction for Next Phases

1. **Converge to one canonical DocumentIR contract**
   - Decide whether to keep `0.1` shape and migrate fixtures, or adopt `v0-proposed` and migrate code.
2. **Add explicit version + migration utilities**
   - Introduce schema upgrade path (`from_version -> to_version`) and strict validation checks.
3. **Clarify model boundaries**
   - Keep profiling/routing operational models separate from canonical IR namespace to avoid type confusion.
4. **Preserve deterministic guarantees**
   - Keep existing ID generation and normalization rules as non-negotiable contracts for benchmark reproducibility.

## 5) Phase 1 Completion Statement

Phase 1 review is complete. IR deep-dive findings are documented and ready to drive Phase 2 interconnection/validation work.
