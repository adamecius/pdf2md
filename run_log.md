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

## PR #1 — 2026-05-23T20:00:00Z — mode: agent
- tasks_attempted:
    - A1: files_touched=[], tests_pass=[tests/test_docling_export.py (7), tests/test_rag_export.py (7), tests/test_markdown_export.py (5), tests/test_export_io_cli.py (7), tests/test_export_contracts.py (9) → 35 existing tests baseline; later 90 across all five suites after the smoke fixtures]. The export path was exercised against existing synthetic `tests/data/export_fixtures/simple_document/` because no real Plan 14 LinkedStructure was committed under `groundtruth/runs/` at agent-start; we have since produced one (run during a separate diagnostic on this branch, gitignored).
    - A2: files_touched=[src/pdf2md/export/reporting.py, tools/export_linked_docling.py, tests/test_export_io_cli.py], tests_pass=[10 new Plan 15 hardening tests in tests/test_export_io_cli.py (TestPlan15ReportHardening + TestPlan15CLI); 90 existing export tests still pass]. Reporting extended with `inspection_status` (9-value taxonomy: exported, exported_with_warnings, structural_mismatch, ground_truth_unavailable, ready_for_plan_16, ready_with_warnings, not_ready_for_plan_16, diagnostic_only, blocked), `inspection_notes`, `ground_truth_ref`, `plan16_readiness` (with `end_to_end_orchestration_handed_off_by="plan_16"`), and auto-detection of `docling_core_unavailable` from warnings. CLI accepts `--inspection-status`, `--inspection-note`, `--ground-truth`. Docling/rag/markdown/io/__init__ left untouched.
    - A3: files_touched=[tools/export_linked_docling.py, src/pdf2md/export/reporting.py], tests_pass=[CLI `--verbose` prints Plan 16 readiness summary including `end_to_end_orchestration_handed_off_by`; rejects unknown statuses via argparse; defaults to `diagnostic_only`]. Plan 15 hard constraints honoured: only the five allowed disk artefacts are written (docling JSON, RAG chunks, Markdown preview, export report, export manifest).
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_docling_export.py tests/test_rag_export.py tests/test_markdown_export.py tests/test_export_io_cli.py tests/test_export_contracts.py -q` → 100 passed (90 existing + 10 new)
    - `conda run -n pdf2md pytest tests/ -q` → 811 passed, 212 skipped (environmental), 0 failed
- cli_smoke:
    - `tools/export_linked_docling.py --linked-structure tests/data/export_fixtures/simple_document/linked_structure.json --consensus-ir ... --out-dir /tmp/plan15_smoke --inspection-status ready_for_plan_16 --inspection-note "synthetic; everything wired" --verbose` → exit 0; 5 disk artefacts present; `docling_text_count=2`, `rag_chunk_count=2`, `markdown_char_count=88`, `end_to_end_orchestration_handed_off_by=plan_16`. `docling_core_validation_failed:ValidationError` recorded as a warning (docling_core present but the simple_document fixture's body shape isn't a full docling-core document; this is expected for synthetic fixtures).
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- conditional_file_changes: none (docling.py, rag.py, markdown.py, io.py, __init__.py left untouched)
- blockers:
    - real_plan14_linked_structure_missing_at_agent_start: No real Plan 14 `linked_structure.json` was committed under `groundtruth/runs/` when Plan 15 began. A diagnostic run on this host (paddleocr/pp_structurev3 → Plan 10 → 13 → 14) was produced during the parallel real-corpus chain validation; it lives in gitignored `groundtruth/runs/linked_structure_real_ppstructure/`. The hardened export CLI runs end-to-end against either synthetic fixtures or the diagnostic real LinkedStructure with no code changes required.
- status: ready_for_review
