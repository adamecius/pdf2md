# STATE.md

Compact project-state surface for agents and human reviewers. This file answers, at a glance, what exists, what is incomplete, what is in flight, and what should happen next. It complements `project.md` (durable architecture), `ROADMAP.md` (long-range product direction), `history.md` (completed milestones), and the active plan files.

Update this file whenever a plan changes subsystem status, in-flight work, next action, or a known verification gap. Do not use it to replace detailed plan acceptance criteria or milestone history.

## Current subsystem state

| Subsystem | Status | Last milestone / evidence | Notes | Next action |
|---|---|---|---|---|
| Ground-truth corpus and validation | built | M9, M13, M17 | Source-known corpus discovery, reports, calibration-prior generation, and MVP corpus evaluation exist. | Keep expanding fixtures and regression coverage as feature plans require. |
| Backend OCR extraction | built | M10 and earlier backend setup milestones | MinerU, PaddleOCR, DeepSeek, and related backend readiness are represented through connector and smoke-readiness work. | Maintain backend descriptors/environments; avoid running backend OCR unless a plan explicitly requires it. |
| Connector normalization | partial | M11, M12, current Plan 006_5 | PageExtractionIR and EntityProposalDocument validation exist; theorem-family entity emission from real connector output remains the active gap. | Complete Plan 006_5 connector-side theorem-family detection. |
| Page/block ConsensusIR | built | M14 | Calibration-weighted block consensus is retained for the structural Docling-export branch, not as the semantic resolver spine. | Human decision remains: confirm long-term structural role or deprecate after Docling export hardening. |
| LinkedStructure and Docling export | built | M15, M16, M24 | Cross-page structural linking and Docling export validation/hardening exist. Markdown remains a preview convenience. | Continue validating against source-known corpora and real backend outputs. |
| Semantic resolver and CrossReferenceGraph | built with gap | M21, M30, M31 | Equation normalization, graph consensus, index/glossary/document-class support, synthetic theorem-family resolver matching, export, and viewer scaffolding exist. Real theorem-family resolution is blocked on connector candidates. | Complete Plan 006_5, then reassess unresolved-marker diagnostics. |
| Static cross-reference viewer | built, verification gap | M23 | Viewer/export path exists, but historical render verification was not persistently captured. | Future viewer changes must use in-product verification artifacts. |
| React/Vite validator staging surface | partial | Unrecorded / state-sync evidence | Staging surface exists on synthesized data; it is not yet wired to real CrossReferenceGraph outputs. | Decide data-source wiring before treating it as a complete deliverable. |
| End-to-end runner / corpus evaluation | built | M17, M18 | MVP corpus evaluation and single-document orchestration are present. | Use for regression evidence as backend/semantic plans mature. |
| Teaching loop for unresolved markers | planned | Next placeholder Plan 008_4 | Intended to inspect unresolved markers and persist human corrections/teaching artifacts. | Draft Plan 008_4 after Plan 006_5 and validator data-source decision. |

## Active and next work

| Slot | Plan | Status | Notes |
|---|---|---|---|
| Current | Plan 006_5 — Connector-Side Theorem-Family Entity Detector | active placeholder | Must be expanded into a full template-compliant plan before source-code implementation. |
| Next | Plan 008_4 — Unresolved-Marker Diagnostic and Human Teaching Loop | draft placeholder | Should wait until real theorem-family connector candidates exist and validator data-source scope is decided. |

## Governance state

| Surface | Status | Notes |
|---|---|---|
| `agent.md` | built | Operating protocol with three modes; lifecycle mechanics delegate to the plan templates. |
| `PLAN_TEMPLATE.md` | built | Full plan lifecycle authority; includes dependency graph and persistent verification-surface guidance. |
| `PLAN_TEMPLATE_LITE.md` | built | Lite tier for docs/governance/small plans that still obeys the same lifecycle and hand-off semantics. |
| `project.md` | built | Durable architecture document; sequencing belongs in plans/ROADMAP, while this state table tracks built/partial/planned. |
