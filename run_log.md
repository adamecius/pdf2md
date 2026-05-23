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

## PR #1 — 2026-05-23T19:30:00Z — mode: agent
- tasks_attempted:
    - A1: files_touched=[], tests_pass=[tests/test_linking_extract.py (16), tests/test_linked_structure_builder.py (16), tests/test_linking_resolvers.py (32), tests/test_build_linked_structure_cli.py (12), tests/test_linked_structure_contracts.py (13) → 110 existing pass on baseline]; real Plan 13 ConsensusIR is not available on disk because no real Plan 9/10/11/12/13 outputs were committed (see blockers). The linker was exercised against existing synthetic `tests/data/linking_fixtures/simple_document/consensus_ir.json` to confirm the path runs end-to-end.
    - A2: files_touched=[src/pdf2md/linking/reporting.py, tools/build_linked_structure.py, tests/test_build_linked_structure_cli.py], tests_pass=[14 new Plan 14 hardening tests in tests/test_build_linked_structure_cli.py (TestPlan14ReportHardening + TestPlan14CLI classes); 110 existing linking tests still pass]. Reporting extended with `link_status_counts`, `relation_type_status` table, `low_confidence` block (configurable threshold), `inputs_used`, `inspection_status` (taxonomy: ready_for_plan_15, ready_with_warnings, not_ready_for_plan_15, diagnostic_only), `inspection_notes`, and `plan15_readiness`. Builder/extract/resolvers/io left untouched — they already work end-to-end on synthetic real-shaped fixtures.
    - A3: files_touched=[tools/build_linked_structure.py, src/pdf2md/linking/reporting.py], tests_pass=[CLI accepts `--inspection-status`, `--inspection-note`; defaults to `diagnostic_only`; rejects unknown statuses via argparse; `--verbose` prints the Plan 15 readiness summary to stdout; only the two allowed disk outputs `linked_structure.json` and `reports/linking_report.json` are written]. Plan 14 hard constraints #13-#15 honoured: `linked_structure_report.json` and `linked_structure_summary.txt` and `linking_summary.txt` are NOT written.
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_linking_extract.py tests/test_linked_structure_builder.py tests/test_linking_resolvers.py tests/test_build_linked_structure_cli.py tests/test_linked_structure_contracts.py -q` → 124 passed (110 existing + 14 new)
    - `conda run -n pdf2md pytest tests/ -q` → 801 passed, 212 skipped (environmental), 0 failed
- cli_smoke:
    - `tools/build_linked_structure.py --consensus-ir tests/data/linking_fixtures/simple_document/consensus_ir.json --consensus-report ... --entities-root ... --priors-root ... --out-dir /tmp/plan14_smoke --inspection-status ready_for_plan_15 --inspection-note "synthetic; reading order verified" --verbose` → exit 0; report includes `plan15_readiness.has_reading_order=True`, `entities_root_used=True`, `priors_root_used=True`, `docling_export_handled_by="plan_15"`; only two disk outputs written.
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- conditional_file_changes: none (builder.py, extract.py, resolvers.py, io.py, __init__.py left untouched; no consensus/calibration/connector/export code modified)
- blockers:
    - real_plan13_consensus_ir_missing: No real Plan 13 `consensus_ir.json` is committed under `groundtruth/runs/`. The synthetic `tests/data/linking_fixtures/simple_document/consensus_ir.json` exercises the same `build_linked_structure.py` code path the real CLI would use against real Plan 13 outputs. Inspection status remains `diagnostic_only` until real consensus outputs become available and a human classifies Plan 15 readiness.
- status: ready_for_review
