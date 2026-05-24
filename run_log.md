# Run log

Append-only log of agent-mode PRs for the current plan. Reset only by feedback mode under `archive plan`.

## Entry format

    ## PR #N — <ISO timestamp> — mode: agent
    - tasks_attempted:
        - T<k>: files_touched=[...], tests_pass=[...], tests_fail_env=[...], tests_fail_real=[]
    - dependencies_added: []
    - external_tools_used: []
    - blockers: []
    - status: in_progress | ready_for_review | halted

## PR #1 — 2026-05-24T20:55:00Z — mode: agent — Plan 006_0
- branch: plan-006-0-semantic-integration
- tasks_attempted:
    - T1 (CrossReferenceGraph schema): files_touched=[src/pdf2md/models/cross_ref.py, src/pdf2md/models/__init__.py], tests_pass=[tests/test_cross_ref_contracts.py — 14 passed], tests_fail_env=[], tests_fail_real=[]
    - T2 (SemanticBackend ABC): files_touched=[src/pdf2md/semantic/__init__.py, src/pdf2md/semantic/base.py], tests_pass=[indirectly covered by adapter/ensemble suites], tests_fail_env=[], tests_fail_real=[]
    - T3 (adapters): files_touched=[src/pdf2md/semantic/regex_adapter.py, src/pdf2md/semantic/grobid_adapter.py, src/pdf2md/semantic/vlm_adapter.py], tests_pass=[tests/test_semantic_regex_adapter.py — 6 passed; GROBID/VLM availability gating verified via test_build_cross_references_cli.py], tests_fail_env=[GROBID full round-trip — H2, deferred, requires Docker daemon; VLM full round-trip — H3, deferred, requires pdf2md-deepseek-vl2 conda env + GPU + ~5.6 GB model download], tests_fail_real=[]
    - T4 (resolver): files_touched=[src/pdf2md/semantic/resolver.py], tests_pass=[tests/test_semantic_resolver.py — 8 passed (exact + fuzzy + bibliography + footnote + cross-type isolation + ordering + SemanticEntity-as-candidate + unresolved)], tests_fail_env=[], tests_fail_real=[]
    - T5 (ensemble): files_touched=[src/pdf2md/semantic/ensemble.py], tests_pass=[tests/test_semantic_ensemble.py — 7 passed (marker dedup keeps higher confidence; distinct markers preserved; entity dedup; empty-input ValueError; unavailable backends skipped; empty-result fallback graph; empty-backend-list ValueError)], tests_fail_env=[], tests_fail_real=[]
    - T6 (CLI): files_touched=[tools/build_cross_references.py], tests_pass=[tests/test_build_cross_references_cli.py — 7 passed (regex end-to-end; grobid missing-pdf exit 2; grobid env_not_ready exit 3; vlm env_not_ready exit 3; regex missing-text exit 2; regex missing-file exit 2; ensemble runs regex only when others unavailable)], tests_fail_env=[], tests_fail_real=[]
    - T7 (acceptance H1 — automated): files_touched=[], tests_pass=[`conda run -n pdf2md python tools/build_cross_references.py --backend regex --text tests/data/semantic_fixtures/sample_text.txt --out-dir /tmp/cross_ref_h1` → exit 0, 18 markers, regex present in backend_versions], tests_fail_env=[], tests_fail_real=[]
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_cross_ref_contracts.py tests/test_semantic_regex_adapter.py tests/test_semantic_resolver.py tests/test_semantic_ensemble.py tests/test_build_cross_references_cli.py -q` → 42 passed
    - `conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x` → 970 passed, 212 skipped, 16 xfailed, 0 failed (no regressions; Plan 005 baseline was 928 passed, this PR adds 42 new tests for net +42)
    - `conda run -n pdf2md python tools/build_cross_references.py --backend regex --text tests/data/semantic_fixtures/sample_text.txt --out-dir /tmp/cross_ref_h1` → exit 0, "cross_references: 18 markers (bibliography=3, chapter=1, corollary=1, definition=1, equation=2, example=1, figure=2, footnote=1, proof=1, section=2, table=2, theorem=1); 0 entities; backends=[regex]; out=/tmp/cross_ref_h1/cross_references.json"
- isolation_check:
    - `grep -rn "^import torch\|^import transformers\|^from torch\|^from transformers" src/pdf2md/semantic/` → no matches. The VLM adapter only invokes `backend/semantic/deepseek_vl2/smoke_test.py` via `conda run -n pdf2md-deepseek-vl2 python ...`. Plan 006 hard-constraint satisfied.
    - Adapter import strategy: regex + grobid adapters use `importlib.util.spec_from_file_location` to load the standalone backend modules from `backend/semantic/<name>/`, so the Plan 005 isolation tree remains importable on its own (no `__init__.py` added to `backend/`).
- runner_contract_compliance:
    - All three adapters implement `SemanticBackend.{name, version, is_available, extract}` and return a `CrossReferenceGraph`.
    - `tools/build_cross_references.py` exits 0 on success, 2 on bad input, 3 on env_not_ready, 1 on backend-ran-but-no-markers, matching the exit code conventions used by the Plan 005 smoke scripts and `pipeline.runner`.
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- environment_modifying_commands: []
- blockers: []
- status: ready_for_review
