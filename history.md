# History

Append-only log of completed milestones. Edited only by feedback mode under the explicit `archive plan` instruction.

## Entry format

    ## M<N> — <YYYY-MM-DD> — <short title>
    - goal: <one line>
    - archived_plan_summary: <one paragraph>
    - tests_passed_automated: [...]
    - tests_passed_human: [...]
    - key_artifacts: [...]
    - notes: <free text, brief>

---

## M1 — TBD — Backend runner and config-driven orchestration

- goal: run any subset of configured backends on a single PDF and preserve raw outputs.
- archived_plan_summary: scaffolding of `run-backends` CLI, `pdf2md.backends.toml` schema, per-backend output trees under `.tmp/<run-name>/raw/<backend>/`.
- key_artifacts: `src/pdf2md/cli.py`, `backend/<name>/pdf2ir_*.py`, `pdf2md.backends.example.toml`.
- notes: only configured and enabled backends run; API backends require explicit configuration.

## M2 — TBD — LaTeX ground-truth harness

- goal: produce deterministic source-known fixtures and pre-Docling ground truth from LaTeX sources.
- archived_plan_summary: generation, runner, and validation scripts; expected contracts emitted at generation time rather than guessed later.
- key_artifacts: `latex_to_pre_docling_groundtruth.py`, `generate_latex_docling_groundtruth.py`, `validate_latex_docling_groundtruth.py`, `semantic_document_groundtruth.json`, `expected_semantic_contract.json`, `expected_docling_contract.json`.

## M3 — TBD — Backend IR matches ground truth

- goal: per-backend extraction IR aligned with LaTeX-derived ground truth at block-level granularity.
- archived_plan_summary: backend adapter normalization, kind mapping, bbox/text comparison hashes; consensus-stage candidate grouping operational.
- key_artifacts: backend extraction IR trees under `backend/<name>/.current/extraction_ir/...`, `consensus_report.py`, `semantic_linker.py`, `media_materializer.py`.
- notes: block-level matching achieved; semantic-linking parity is M4 work.
