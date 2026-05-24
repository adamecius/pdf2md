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

## PR #1 — 2026-05-24T20:30:00Z — mode: agent — Plan 005_0
- branch: plan-005-0-semantic-backends
- tasks_attempted:
    - T1 (regex backend): files_touched=[backend/semantic/regex/patterns.py, backend/semantic/regex/smoke_test.py, backend/semantic/regex/README.md, tests/data/semantic_fixtures/sample_text.txt], tests_pass=[H3 regex smoke: exit 0, 18 markers, 12 distinct types ≥3], tests_fail_env=[], tests_fail_real=[]
    - T2 (GROBID backend): files_touched=[backend/semantic/grobid/grobid_client.py, backend/semantic/grobid/tei_parser.py, backend/semantic/grobid/smoke_test.py, backend/semantic/grobid/README.md], tests_pass=[py_compile all 3 .py files; round-trip TEI parse against a minimal synthetic doc → 1 figure + 1 bibliography marker + 1 bib entry; smoke CLI argparse + --help; env_not_ready path exits cleanly when GROBID is not running], tests_fail_env=[H1 — full Docker round-trip requires Docker daemon + ~4 GB image pull; deferred to human verification], tests_fail_real=[]
    - T3 (DeepSeek-VL2 backend): files_touched=[backend/semantic/deepseek_vl2/env.yaml, backend/semantic/deepseek_vl2/vlm_client.py, backend/semantic/deepseek_vl2/prompt_templates.py, backend/semantic/deepseek_vl2/smoke_test.py, backend/semantic/deepseek_vl2/README.md], tests_pass=[py_compile prompt_templates.py + smoke_test.py in main pdf2md env (vlm_client.py imports torch and is only valid inside pdf2md-deepseek-vl2)], tests_fail_env=[H2 — full GPU round-trip requires creating the pdf2md-deepseek-vl2 conda env (+ ~5.6 GB model download) and an NVIDIA GPU; deferred to human verification], tests_fail_real=[]
- automated_test_commands:
    - `conda run -n pdf2md python backend/semantic/regex/smoke_test.py --text tests/data/semantic_fixtures/sample_text.txt --out-dir /tmp/regex_smoke` → exit 0, 18 markers, 12 distinct types
    - `conda run -n pdf2md python -c "import py_compile; [py_compile.compile(p, doraise=True) for p in ['backend/semantic/regex/patterns.py','backend/semantic/regex/smoke_test.py','backend/semantic/grobid/grobid_client.py','backend/semantic/grobid/tei_parser.py','backend/semantic/grobid/smoke_test.py','backend/semantic/deepseek_vl2/prompt_templates.py','backend/semantic/deepseek_vl2/smoke_test.py']]"` → OK on all 7 files
    - `conda run -n pdf2md python backend/semantic/grobid/smoke_test.py --pdf /etc/hostname --out-dir /tmp/grobid_smoke_fake` → env_not_ready path triggered, clean error message (exit 3 set; conda-run wrapper sometimes maps to 0 on stdout but the sys.exit code is correct)
    - `conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x` → 928 passed, 212 skipped, 16 xfailed, 0 failed (no regressions from plan 005 scaffolding)
- runner_contract_compliance:
    - All three backends ship smoke_test.py with --out-dir writing semantic_result-style JSON; regex matches the §4 runner contract; grobid + deepseek_vl2 match the same shape with backend-specific timing fields.
- isolation_check:
    - `grep -rn "import pdf2md\\|from pdf2md" backend/semantic/` → no matches. Plan 005 hard-constraint "no imports from src/pdf2md/" satisfied.
- dependencies_added: []
- external_tools_used: []
- forbidden_files_touched: []
- environment_modifying_commands: []
- blockers: []
- status: ready_for_review
