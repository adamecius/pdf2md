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

## PR #1 — 2026-05-24T22:00:00Z — mode: agent — Plan 008_0
- branch: plan-008-0-semantic-viewer
- tasks_attempted:
    - T1 (graph exporter): files_touched=[src/pdf2md/semantic/graph_export.py, src/pdf2md/semantic/__init__.py], tests_pass=[tests/test_graph_export.py — 8 passed: empty payload; markerless graph synthesises unresolved edges + marker nodes; resolved edge links to target node; marker extra metadata (source_ref/char_offset/backend) included on marker nodes; extra_entities surface as nodes; backend_versions pass through metadata; to_dict has the 5 documented top-level keys; repeated marker text + same source_ref at different offsets produces two distinct marker nodes], tests_fail_env=[], tests_fail_real=[]
    - T2 (export CLI): files_touched=[tools/export_cross_ref_graph.py], tests_pass=[tests/test_export_cross_ref_graph_cli.py — 5 passed: writes graph.json with the 5 top-level keys; --inline-viewer writes self-contained HTML with <script id="graph-data"> tag + D3 v7 CDN reference + the doc_hash from the source graph inlined verbatim; rejects missing --xref (exit 2); rejects malformed JSON (exit 2); the static viewer index.html exists, is syntactically valid HTML, and references viewer.js + style.css + the D3 v7 CDN], tests_fail_env=[], tests_fail_real=[]
    - T3 (static viewer): files_touched=[webui/cross_ref/index.html, webui/cross_ref/viewer.js, webui/cross_ref/style.css, webui/cross_ref/README.md], tests_pass=[verified by the static-viewer text-check test in tests/test_export_cross_ref_graph_cli.py + manual smoke: the `--inline-viewer` output is byte-identical to the same template loaded via index.html]. The viewer auto-loads ``graph.json`` from its directory when served over HTTP (skipped under file:// since fetch() is blocked there); under file:// the inline-viewer mode is the supported path.
    - T4 (acceptance H1 — automated dry-run): files_touched=[], tests_pass=[`conda run -n pdf2md python tools/build_cross_references.py --backend regex --text tests/data/semantic_fixtures/sample_text.txt --out-dir /tmp/h1_export` → exit 0; `conda run -n pdf2md python tools/export_cross_ref_graph.py --xref /tmp/h1_export/cross_references.json --output /tmp/h1_export/graph.json --inline-viewer /tmp/h1_export/viewer.html` → exit 0, 19 nodes / 18 edges, viewer.html + graph.json written, top-level keys present], tests_fail_env=[browser rendering — agent cannot launch a browser; deferred to H1 human step], tests_fail_real=[]
- automated_test_commands:
    - `conda run -n pdf2md pytest tests/test_graph_export.py tests/test_export_cross_ref_graph_cli.py -q` → 13 passed
    - `conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x` → 1002 passed, 212 skipped, 16 xfailed, 0 failed (Plan 007 baseline 989 → +13, no regressions)
- isolation_check:
    - `graph_export.py` depends only on `pdf2md.models.cross_ref` (pydantic models). No imports of `backend/`, `webui/validator/`, `webui/shared/`, or any other Plan 005-007 module beyond models. No torch/transformers/Node.
    - The static viewer loads D3 v7 from `https://cdn.jsdelivr.net/npm/d3@7` at runtime; no `package.json`/`package-lock.json` added to the repo and no npm install run in agent mode.
- runner_contract_compliance:
    - `export_graph(xref, *, document_id=None, extra_entities=None) -> GraphExport` and `GraphExport.to_dict() -> dict` match the §2 signatures.
    - `tools/export_cross_ref_graph.py` exit codes 0 (success) / 2 (bad input) match the §3 specification; the unused `1` exit code is intentionally absent (Plan 008_0 does not have a "ran but produced nothing meaningful" failure mode — the marker-only graph is the normal Plan 006 default and yields a valid renderable payload via synthetic unresolved edges).
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- environment_modifying_commands: []
- blockers: []
- status: ready_for_review
