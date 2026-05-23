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

## M10 — 2026-05-22 — Plan 9: Real backend smoke readiness

- goal: verify that configured real backend execution can be attempted, classified, and reported before connector normalisation, by reusing the existing repository backend runner.
- archived_plan_summary: added `src/pdf2md/local/backend_smoke.py`, which wraps the existing backend execution path (`pdf2md.config.load_backend_config` / `get_enabled_backends` and `pdf2md.backends.runner.run_configured_backends`), attempts configured backends on a real PDF, classifies each into a smoke status (success, env_not_ready, model_missing, dependency_missing, backend_crash, output_missing, timeout, not_configured), and emits a deterministic `BackendSmokeReport` with a configurable success gate; plus the `tools/backend_smoke.py` CLI with strict and non-strict gate modes and 15 mocked unit tests. Implemented in commit `1783cf81` (PR #89); review-mode evaluation passed; marked `human_verified` in `0f2972d8`.
- tests_passed_automated: [`pytest tests/test_backend_smoke.py -q` → 15 passed; `pytest tests/ -q` → 707 passed, 212 skipped, 0 failed]
- tests_passed_human: [H1–H4 verified on 2026-05-22 via `sandbox/plan9_human_verification.sh` — all PASS; human verification accepted]
- key_artifacts: [`src/pdf2md/local/backend_smoke.py`, `tools/backend_smoke.py`, `tests/test_backend_smoke.py`, `plans/archive/plan-9-backend-smoke-readiness.md`]
- notes: Plan 9 reused the existing backend runner with no parallel runner. On the development machine no backend configuration was present, so the smoke run classified all four backends as not_configured — expected; a real backend `success` status requires configured backend conda environments and a real PDF. Archived on 2026-05-22 during the Plan 9→10 transition; Plan 10 (Connector Implementation and PageExtractionIR Validation) promoted to current_plan.md.

## M11 — 2026-05-23 — Plan 10: Connector implementation and PageExtractionIR validation

- goal: validate that raw backend outputs convert through the existing repository connector entrypoint (`pdf2md.connectors.common.connect_raw_dir`) into structurally valid and semantically useful `PageExtractionIR`, without running calibration, consensus, semantic linking, Docling export, RAG export, Markdown export, or the end-to-end runner.
- archived_plan_summary: added `src/pdf2md/local/connector_validation.py` (Pydantic `ConnectorValidationReport`/`ConnectorValidationResult`, the five-status taxonomy `validated | connector_crash | schema_failed | missing_required_output | deferred_from_plan_9`, preferred and reduced gate logic, semantic-quality detection, per-backend `page_extraction_ir.json` writer, Plan 11 hand-off summary) and the `tools/validate_connectors_page_ir.py` CLI accepting `--plan9-report`, `--backend-output`, `--out-dir`, `--preferred-gate-minimum`, `--allow-reduced-gate`, and `--verbose`. Fixtures: `minimal_markdown_backend`, `missing_output_backend`, `schema_failure_backend`. The existing connector entrypoint was reused unchanged. Implemented in commit `2b9ea1fa` (run_log PR #1, status=ready_for_review).
- tests_passed_automated: [`pytest tests/test_connector_page_ir_validation.py -q` → 15 passed; `pytest tests/test_connector_page_ir_validation.py tests/test_backend_smoke.py tests/test_local_groundtruth_validate.py -q` → 44 passed; `pytest tests/ -q` → 722 passed, 212 skipped, 0 failed]
- tests_passed_human: [H1, H2, H4, H5 verified on 2026-05-23 via `/tmp/plan10_human_verification.sh` — all PASS; H3 PASS within the five-status taxonomy (every backend classified deferred_from_plan_9 because the archived Plan 9 report has zero successful backends); H0 SKIP for the same upstream reason — recorded in `## Feedback #1` of the archived plan]
- key_artifacts: [`src/pdf2md/local/connector_validation.py`, `tools/validate_connectors_page_ir.py`, `tests/test_connector_page_ir_validation.py`, `tests/data/connector_validation_fixtures/minimal_markdown_backend/output.md`, `tests/data/connector_validation_fixtures/missing_output_backend/.gitkeep`, `tests/data/connector_validation_fixtures/schema_failure_backend/output.md`, `plans/archive/plan-10-connector-pageextractionir-validation.md`]
- notes: Plan 10 reused the existing connector path with no parallel architecture and no connector-code changes. Because the archived Plan 9 report has zero successful real backends, real-backend preferred/minimum gates could not be exercised in this archival; the synthetic backend run (`--backend-output minimal_markdown_backend=tests/data/connector_validation_fixtures/minimal_markdown_backend`) drove the same connector code path the real CLI would use, producing `semantic_quality_passed=true`, `page_count=2`, `block_count=6`. When real Plan 9 success backends become available, H2/H3 should be rerun against those outputs before any downstream plan depends on real connector outputs. Archived on 2026-05-23 during the Plan 10→11 transition; Plan 11 (EntityProposalDocument Validation) promoted to current_plan.md; Plan 12 (Real Calibration Prior Generation) promoted to next_plan.md.

## M12 — 2026-05-23 — Plan 11: EntityProposalDocument validation

- goal: validate `EntityProposalDocument` outputs produced by the existing connector path (same connector validated in Plan 10) using the repository's existing `EntityProposalDocument`, `EntityType`, `RelationType`, `EntityEvidence`, `ConfidenceSource`, and `EvidenceKind` schema, without inventing new entity or relation types and without running calibration, consensus, linking, export, or end-to-end work.
- archived_plan_summary: added `src/pdf2md/local/entity_proposal_validation.py` (Pydantic `EntityValidationReport`/`EntityValidationResult`, the five-status taxonomy `validated | no_entities_produced | schema_failed | connector_crash | deferred_from_plan_10`, preferred/reduced gate logic with the no-entity rule excluding `no_entities_produced` from validated counts, semantic-plausibility detection, per-backend `entity_proposals.json` writer, Plan 12 hand-off summary) and the `tools/validate_entity_proposals.py` CLI accepting `--plan10-report`, `--backend-entities`, `--page-ir`, `--backend-raw-dir`, `--out-dir`, `--preferred-gate-minimum`, `--allow-reduced-gate`, and `--verbose`. Six fixture files cover the valid, no-entity, and schema-failure paths; relation-endpoint and evidence-source-block-id cross-references are validated by the repository's existing `EntityProposalDocument._validate_document` and `EntityEvidence._validate_source_block_id`. Implemented in commit `55608cdb` (run_log PR #1, status=ready_for_review).
- tests_passed_automated: [`pytest tests/test_entity_proposal_validation.py -q` → 18 passed; `pytest tests/test_entity_proposal_validation.py tests/test_connector_page_ir_validation.py tests/test_backend_smoke.py -q` → 48 passed; `pytest tests/ -q` → 740 passed, 212 skipped, 0 failed]
- tests_passed_human: [H1, H2, H3, H4, H5 verified on 2026-05-23 via `/tmp/plan11_human_verification.sh` — all PASS; H3 chains a synthetic Plan 10 report (generated on the fly by running `tools/validate_connectors_page_ir.py` against the Plan 10 fixture) into `tools/validate_entity_proposals.py`; H0 SKIP because no on-disk real Plan 10 connector validation report exists — recorded in `## Feedback #1` of the archived plan]
- key_artifacts: [`src/pdf2md/local/entity_proposal_validation.py`, `tools/validate_entity_proposals.py`, `tests/test_entity_proposal_validation.py`, `tests/data/entity_proposal_validation_fixtures/valid_entities/entities.json`, `tests/data/entity_proposal_validation_fixtures/valid_entities/page_extraction_ir.json`, `tests/data/entity_proposal_validation_fixtures/no_entities/entities.json`, `tests/data/entity_proposal_validation_fixtures/no_entities/page_extraction_ir.json`, `tests/data/entity_proposal_validation_fixtures/schema_failure/entities.json`, `tests/data/entity_proposal_validation_fixtures/schema_failure/page_extraction_ir.json`, `plans/archive/plan-11-entity-proposal-document-validation.md`]
- notes: Plan 11 reused the existing connector path and the existing entity schema with no parallel architecture and no schema changes. Because no on-disk real Plan 10 connector validation report exists yet (Plan 10 archival did not commit `groundtruth/runs/connector_validation/`), H3 was exercised by generating a synthetic Plan 10 report from the Plan 10 fixture and chaining it into Plan 11 — the same Plan 10 → Plan 11 chain the real CLI would use. When real Plan 10 outputs become available, H2/H3 should be rerun against those outputs before any downstream plan depends on real entity outputs. Archived on 2026-05-23 during the Plan 11→12 transition; Plan 12 (Real Calibration Prior Generation) promoted to current_plan.md; Plan 13 (Weighted ConsensusIR on Real Outputs) promoted to next_plan.md.
