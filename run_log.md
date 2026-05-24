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

## PR #1 — 2026-05-24T21:35:00Z — mode: agent — Plan 007_0
- branch: plan-007-0-semantic-eval
- tasks_attempted:
    - T1 (LaTeXML ground-truth parser): files_touched=[src/pdf2md/semantic/groundtruth.py, src/pdf2md/semantic/__init__.py], tests_pass=[tests/test_semantic_groundtruth.py — 6 passed; one of them validates that the labelref ``LABEL:fig:box-diagram`` resolves to the surface form ``Figure 1`` from the anchor's autoref tag], tests_fail_env=[], tests_fail_real=[]. Note: source plan §2 spoke of "TEI XML", but latexml 0.8.6 actually emits its native ``http://dlmf.nist.gov/LaTeXML`` XML, not TEI. The parser handles that namespace directly and reuses the figure/table/equation/section/footnote/bibitem mapping inline so the standalone ``backend/semantic/grobid/tei_parser.py`` import is not required at parse time.
    - T2 (evaluation harness): files_touched=[src/pdf2md/semantic/evaluation.py], tests_pass=[tests/test_semantic_evaluation.py — 8 passed: returns SemanticEvalResult; marker precision/recall/F1 match expected fixture values 0.75/0.75/0.75; marker_f1_by_type breaks down to bibliography=1.0, section=0.0, figure=0.8; resolution_accuracy = 2/3 on the matched-pair fixture; entity_precision/recall/F1 = 1.0; perfect-match yields P=R=F1=1; empty extraction yields 0; result_to_csv_row exposes the expected columns], tests_fail_env=[], tests_fail_real=[]
    - T3 (benchmark CLI): files_touched=[tools/run_semantic_benchmark.py], tests_pass=[tests/test_run_semantic_benchmark_cli.py — 5 passed: full end-to-end on the linked_sections_figures fixture produces results.json + results.csv + per-doc gt_cross_references.json; --gt-dir missing → exit 2; unknown --backends → exit 2; empty corpus → exit 2; missing latexml binary → exit 3 with env_not_ready], tests_fail_env=[], tests_fail_real=[]
    - T4 (fixtures): files_touched=[tests/data/semantic_fixtures/eval_truth.json, tests/data/semantic_fixtures/eval_extracted.json], tests_pass=[loaded by T2 evaluation tests], tests_fail_env=[], tests_fail_real=[]
    - T5 (acceptance H1 — automated): files_touched=[], tests_pass=[`conda run -n pdf2md python tools/run_semantic_benchmark.py --gt-dir groundtruth/corpus/latex/linked_sections_figures --backends regex --out-dir /tmp/semantic_bench_h1` → exit 0; results.json + results.csv exist with ≥1 data row; gt_cross_references.json has 4 markers (figure / equation / section / footnote); regex backend produced 0 markers — expected with the crude detexer (real PDF rendering deferred to Plan 008 per plan §1 scope reduction)], tests_fail_env=[], tests_fail_real=[]
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_semantic_groundtruth.py tests/test_semantic_evaluation.py tests/test_run_semantic_benchmark_cli.py -q` → 19 passed
    - `conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x` → 989 passed, 212 skipped, 16 xfailed, 0 failed (Plan 006 baseline 970 → +19, no regressions)
    - `conda run -n pdf2md python tools/run_semantic_benchmark.py --gt-dir groundtruth/corpus/latex/linked_sections_figures --backends regex --out-dir /tmp/semantic_bench_h1` → exit 0, 1 doc × 1 backend = 1 result row; GT has 4 markers
- isolation_check:
    - The GT parser is a stdlib-only + `pdf2md.models.cross_ref` module. It does not import from `src/pdf2md/{pipeline,cli,connectors,calibration,consensus,linking,export}/` or from `backend/`.
    - The evaluation harness depends only on `pdf2md.models.cross_ref`.
    - The benchmark CLI imports from `pdf2md.semantic` (Plan 006 adapters + Plan 007 new modules); no torch/transformers from the main env (`grep -rn "^import torch\|^import transformers" src/pdf2md/semantic/` → no matches).
- runner_contract_compliance:
    - `generate_ground_truth(tex_path, output_dir, *, latexml_bin, timeout_s, source_ref)` matches the §2 signature and returns a `CrossReferenceGraph`.
    - `evaluate_semantic(extracted, ground_truth, *, document_id, backend)` returns a fully-populated `SemanticEvalResult` dataclass.
    - `tools/run_semantic_benchmark.py` exit codes 0/2/3 match the §4 specification (no exit-1 path because zero-marker output is informational, not an error — surfaces as warnings on stderr).
- dependencies_added: []
- external_tools_used: [latexml]   # already installed at /usr/bin/latexml; no installer commands run; read-only subprocess
- forbidden_files_touched: []
- environment_modifying_commands: []
- blockers: []
- status: ready_for_review
