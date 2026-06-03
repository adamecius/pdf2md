# STATE.md

Compact project-state surface for agents and human reviewers. This file answers, at a glance, what exists, what is incomplete, what is in flight, and what should happen next. It complements `project.md` (durable architecture), `ROADMAP.md` (long-range product direction), `history.md` (completed milestones), and the active plan files.

Update this file whenever a plan changes subsystem status, in-flight work, next action, or a known verification gap. Do not use it to replace detailed plan acceptance criteria or milestone history.

## Current subsystem state

| Subsystem | Status | Last milestone / evidence | Notes | Next action |
|---|---|---|---|---|
| Ground-truth corpus and validation | built | M9, M13, M17 | Source-known corpus discovery, reports, calibration-prior generation, and MVP corpus evaluation exist. | Keep expanding fixtures and regression coverage as feature plans require. |
| Backend OCR extraction | built | M10, M35, M36 | MinerU is documented as the default OCR candidate source, DeepSeek as an alternative, and PaddleOCR as deprecated for semantic cross-reference candidate extraction. | Maintain backend descriptors/environments; avoid running backend OCR unless a plan explicitly requires it. |
| Connector normalization | built | M11, M12, M33 | PageExtractionIR and EntityProposalDocument validation exist; theorem-family entity emission from real connector output is now implemented. | Use Plan 006_4 to remove the unused OCR entity consensus bridge, not to change connector detection. |
| Page/block ConsensusIR | built | M14, M36 | Calibration-weighted block consensus is retained for the structural Docling-export branch, not as the semantic resolver spine. | Keep page-level ConsensusIR separate from semantic resolver routing work. |
| OCR entity consensus bridge | removed | M29, M36 | AP8 introduced `merge_entity_documents`, but the 007_2 evidence and runtime audit marked it as dead code for the semantic cross-reference path; Plan 006_4 removed the module and tests. | No follow-up unless historical fixtures or docs still mention the removed bridge. |
| LinkedStructure and Docling export | built | M15, M16, M24, M37 | Cross-page structural linking and Docling export validation/hardening exist; LinkedStructure is networkx-backed with `reading_order_sort`, `section_ancestors`, `detect_cycles`, `orphan_nodes` available. Markdown remains a preview convenience. | Continue validating against source-known corpora and real backend outputs. |
| Semantic resolver and CrossReferenceGraph | built | M21, M30, M31, M33, M35, M36 | Equation normalization, theorem-family entities, graph consensus, index/glossary/document-class support, export, viewer scaffolding, and calibration reporting exist without the dead OCR entity-merge bridge. | Use the 007_2 baseline to drive later routing work. |
| Semantic calibration | built | M35; `docs/reports/semantic_calibration_baseline.md` | Per-marker-type × OCR-backend resolution matrix and deterministic JSON calibration weights exist for the examples-only snapshot. | Review the baseline in product, then consume it in 006_1/router work. |
| Static cross-reference viewer | built | M23, M34 | Viewer/export path exists; the 008_4 Adjudicate tab closes the persistent unresolved-marker verification gap. | Keep viewer changes tied to reproducible artifacts. |
| React/Vite validator staging surface | partial | Unrecorded / state-sync evidence | Staging surface exists on synthesized data; it is not yet wired to real CrossReferenceGraph outputs. | Decide data-source wiring before treating it as a complete deliverable. |
| End-to-end runner / corpus evaluation | built | M17, M18 | MVP corpus evaluation and single-document orchestration are present. | Use for regression evidence as backend/semantic plans mature. |
| Teaching loop for unresolved markers | built | M34 | Adjudicate tab, label export/import, schema validation, and management CLI exist for unresolved-marker teaching artifacts. | Feed real adjudication sessions into future resolver/routing plans. |

## Active and next work

| Slot | Plan | Status | Notes |
|---|---|---|---|
| Current | Plan 006_1 — Semantic Router with Calibrated Weights | active | Replace the hardcoded GROBID_BOOK_WEIGHT with data-driven weights from the 007_2 baseline; auto document-class detection; CLI routing flags. No backend excluded (down-weight only). |
| Next | To be determined after 006_1 | not_yet_drafted | Candidates: validator real-data wiring, ground-truth corpus expansion 007_1, PaddleOCR test-fixture cleanup. |
| Done | Plan 014_1 — networkx-Backed LinkedStructure Graph | finished (PR #146, merged) | LinkedStructure is networkx-backed; reading-order/ancestry/cycle/orphan utilities available. |

## Governance state

| Surface | Status | Notes |
|---|---|---|
| `agent.md` | built | Operating protocol with three modes; lifecycle mechanics delegate to the plan templates. |
| `PLAN_TEMPLATE.md` | built | Full plan lifecycle authority; includes dependency graph and persistent verification-surface guidance. |
| `PLAN_TEMPLATE_LITE.md` | built | Lite tier for docs/governance/small plans that still obeys the same lifecycle and hand-off semantics. |
| `project.md` | built | Durable architecture document; sequencing belongs in plans/ROADMAP, while this state table tracks built/partial/planned. |
