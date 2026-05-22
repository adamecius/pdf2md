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

## M4 — 2026-05-05 — Human repository hygiene cleanup

- goal: remove transient planning and generated artifacts that should not remain tracked in git.
- archived_plan_summary: human commit `d1d82840` performed a large-scale cleanup that deleted temporary plan files (`next_plan.md`, `current_status.md`, `description.md`), test artifacts (`test_visual.md`, `test_visual.pdf`), and extensive generated `.current/**` groundtruth/backend output trees to reduce repository noise and improve traceability.
- tests_passed_automated: []
- tests_passed_human: []
- key_artifacts: commit `d1d82840ae37e4e1751fea5a8144dd8270302f4e` (message: "perform pending file cleaning").
- notes: author/committer recorded as Jose H Garcia on 2026-05-05.

## M5 — 2026-05-07 — Consensus factory v2

- goal: implement the Plan 4 page-local consensus factory that consumes `PageExtractionIR`, `EntityProposalDocument`, and `CalibrationPriorDocument` inputs and emits validated `ConsensusIR` plus `reports/consensus_report.json` without document-level semantic linking.
- archived_plan_summary: added the `pdf2md.consensus` package with candidate grouping, calibrated scoring, conflict-aware `ConsensusIR` construction, filesystem I/O, audit reporting, and the `tools/build_consensus.py` CLI. Synthetic fixtures cover simple multi-backend agreement, ambiguous page-number versus footnote evidence, and single-source output. Human feedback accepted the PR and requested closing the current plan.
- tests_passed_automated: [`pytest tests/test_consensus_grouping.py -q`, `pytest tests/test_consensus_scoring.py -q`, `pytest tests/test_consensus_factory.py -q`, `pytest tests/test_build_consensus_cli.py -q`, `pytest tests/test_ir_contracts.py -q`, `pytest tests/test_entity_contracts.py -q`, `pytest tests/test_connector_common.py -q`, `pytest tests/test_backend_connectors.py -q`, `pytest tests/test_prior_contracts.py -q`, `pytest tests/test_calibration_matching.py -q`, `pytest tests/test_calibration_metrics.py -q`, `pytest tests/test_calibrate_priors_cli.py -q`, `pytest tests/test_run_backends_config.py -q`, `pytest tests/test_semantic_document_builder.py -q`, `pytest tests/ -q`]
- tests_passed_human: [`PR accepted by human feedback on 2026-05-07`]
- key_artifacts: [`src/pdf2md/consensus/grouping.py`, `src/pdf2md/consensus/scoring.py`, `src/pdf2md/consensus/factory.py`, `src/pdf2md/consensus/io.py`, `src/pdf2md/consensus/reporting.py`, `tools/build_consensus.py`, `tests/data/consensus_fixtures/*`, `tests/test_consensus_grouping.py`, `tests/test_consensus_scoring.py`, `tests/test_consensus_factory.py`, `tests/test_build_consensus_cli.py`]
- notes: Plan archival was performed after human feedback accepted the PR and asked to close the current plan. The only recorded environment limitation was that `git diff --name-only main..HEAD` could not run in the checkout because no `main` ref existed; committed files were otherwise kept within the Plan 4 whitelist.

## M6 — 2026-05-22 — Plan 5: LinkedStructure semantic linking

- goal: build a document-level LinkedStructure from ConsensusIR, EntityProposalDocument, and CalibrationPriorDocument inputs, with cross-page semantic linking, resolvers, and an audit report.
- archived_plan_summary: added the `pdf2md.linking` package (extraction, resolvers, builder, reporting, I/O) and the `LinkedStructure` model, plus the `tools/build_linked_structure.py` CLI. Implemented and reworked across run_log PR #1 and PR #2.
- tests_passed_automated: [`pytest tests/test_linked_structure_contracts.py -q`, `pytest tests/test_linking_extract.py -q`, `pytest tests/test_linking_resolvers.py -q`, `pytest tests/test_linked_structure_builder.py -q`, `pytest tests/test_build_linked_structure_cli.py -q`, `pytest tests/ -q`]
- tests_passed_human: [PR accepted by human feedback]
- key_artifacts: [`src/pdf2md/models/linked.py`, `src/pdf2md/linking/`, `tools/build_linked_structure.py`, `tests/test_linked_structure_contracts.py`, `tests/test_linking_extract.py`, `tests/test_linking_resolvers.py`, `tests/test_linked_structure_builder.py`, `tests/test_build_linked_structure_cli.py`]
- notes: archived retroactively on 2026-05-22 during the Plan 7→8 transition; this plan was completed but never given a milestone at the time. Original evidence is run_log PR #1–#2, preserved in the git history of run_log.md.

## M7 — 2026-05-22 — Plan 6: Docling, RAG, and markdown export

- goal: export a LinkedStructure to Docling JSON, RAG chunk documents, and a markdown preview, with an export manifest and reporting.
- archived_plan_summary: added the `pdf2md.export` package (docling, rag, markdown, I/O, reporting) and the export models, plus the `tools/export_linked_docling.py` CLI. Implemented and reworked across run_log PR #3 and PR #4.
- tests_passed_automated: [`pytest tests/test_export_contracts.py -q`, `pytest tests/test_docling_export.py -q`, `pytest tests/test_rag_export.py -q`, `pytest tests/test_markdown_export.py -q`, `pytest tests/test_export_io_cli.py -q`, `pytest tests/ -q`]
- tests_passed_human: [PR accepted by human feedback]
- key_artifacts: [`src/pdf2md/models/export.py`, `src/pdf2md/export/`, `tools/export_linked_docling.py`, `tests/test_export_contracts.py`, `tests/test_docling_export.py`, `tests/test_rag_export.py`, `tests/test_markdown_export.py`, `tests/test_export_io_cli.py`]
- notes: archived retroactively on 2026-05-22 during the Plan 7→8 transition. Original evidence is run_log PR #3–#4, preserved in the git history of run_log.md.

## M8 — 2026-05-22 — Plan 7: Local environment and toolchain preflight

- goal: verify the local machine has the Python package surface, project and connector CLIs, LaTeX/LaTeXML tools, backend conda environments, and writable output roots required by the later local acceptance plans, without running OCR or LaTeX.
- archived_plan_summary: added `src/pdf2md/local/preflight.py` and `tools/local_groundtruth_preflight.py`, producing a machine-readable `PreflightReport` and a human-readable summary with strict and non-strict modes. Implemented in commit `4b616302`. Review `PR_review #5` confirmed the commit touched only the six whitelisted files with no dependency changes.
- tests_passed_automated: [`pytest tests/test_local_preflight.py -q` → 32 passed, 0 skipped/xfail; `pytest tests/ -q` → 678 passed, 212 skipped, 0 failed; `tools/local_groundtruth_preflight.py` → environment_ready=true, 26/26 required and 5/5 optional checks pass, `--strict` exits 0]
- tests_passed_human: [human verification accepted on 2026-05-22]
- key_artifacts: [`src/pdf2md/local/preflight.py`, `tools/local_groundtruth_preflight.py`, `tests/test_local_preflight.py`, `tests/data/local_preflight_fixtures/`]
- notes: the Plan 7 implementation never produced a run_log.md PR entry, so `PR_review #5` recorded a process-fail verdict despite all acceptance tests passing; the review section lives in current_plan.md commit `4b6a588a`. Human verification was accepted on 2026-05-22 and the plan archived; run_log.md was reset for Plan 8 in the same archival.

## M9 — 2026-05-22 — Plan 8: Local ground-truth corpus validation plus documentation consistency

- goal: verify that the local LaTeX-derived ground-truth corpus can be discovered, inspected, classified, and reported before any backend run, and perform a narrow documentation consistency check.
- archived_plan_summary: added `src/pdf2md/local/groundtruth.py` (corpus discovery, artefact inspection, readiness classification, deterministic `GroundtruthValidationReport`) and the inspect-only `tools/local_groundtruth_validate.py` CLI with strict and non-strict modes; fixtures for ready, partial, and empty corpora plus 14 unit tests. A4 documentation edits: `README.md` Section 12 dropped the obsolete `--run-validator` flag and `docs/docling_layer.md` gained a legacy/canonical clarification note. Implemented in commit `d86ac56b`; marked `human_verified` in `81444362`.
- tests_passed_automated: [`pytest tests/test_local_groundtruth_validate.py -q` → 14 passed; `pytest tests/test_local_preflight.py -q` → 32 passed; `pytest tests/ -q` → 692 passed, 212 skipped, 0 failed]
- tests_passed_human: [H1–H4 verified on 2026-05-22 via `sandbox/plan8_human_verification.sh` — all PASS; real corpus showed 57/57 documents ready; PR approved on the `plan-8-groundtruth-validation` branch]
- key_artifacts: [`src/pdf2md/local/groundtruth.py`, `tools/local_groundtruth_validate.py`, `tests/test_local_groundtruth_validate.py`, `tests/data/local_groundtruth_fixtures/`, `plans/archive/plan-8-groundtruth-validation.md`]
- notes: Plan 8 followed the PLAN_TEMPLATE lifecycle (draft → active → agent_in_progress → human_verification_required → human_verified → finished) and did not use run_log.md. Archived on 2026-05-22 during the Plan 8→9 transition; Plan 9 (Real Backend Smoke Readiness) promoted to current_plan.md.
