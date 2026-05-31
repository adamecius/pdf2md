# Plan 006_5 — Connector-Side Theorem-Family Entity Detector

Status:
active

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Linked ROADMAP phase:
Phase 4b — Semantic cross-reference layer.

Current roadmap estimate:
No numeric change until human verification. This plan closes the real-data gap left by Plan 006_3.

Owner:
Agent team / human reviewer.

Sequence:
Plan 006_5 (must run after State-Sync 001 and Plan 006_3).

Previous plan:
State-Sync 001 — Governance, Architecture, and History Re-Sync.

Required previous plan status:
human_verification_required or human_verified for the docs-only resync; Plan 006_3 archived as finished.

Next plan after completion:
Plan 008_4 — Unresolved-marker Diagnostic and Human Teaching Loop.

Branch name:
plan-006_5-theorem-family-entities

---

## 1. Purpose

Plan 006_3 added resolver-side theorem-family matching and fixture tests, but real documents still resolve 0% theorem/definition/corollary/example/proof markers because connectors do not emit theorem-family candidate entities. This plan adds connector-side detection so real OCR output can produce same-type candidates for the existing resolver ladder.

## 2. Source-of-truth hierarchy

`project.md` defines the two-branch architecture and records the 006_5 gap.
`ROADMAP.md` tracks Phase 4b.
`history.md` records completed milestones through the state-sync.
`agent.md` and `PLAN_TEMPLATE.md` define the operating protocol.

## 3. Scope sketch for human expansion

The human reviewer should expand this into a full PLAN_TEMPLATE-compliant plan before agent-mode implementation. Expected scope:

```text
src/pdf2md/connectors/common.py theorem-family block/entity detector
src/pdf2md/models/* only if new EntityType values are required
tests for theorem / definition / lemma / proposition / corollary / example / proof
fixture or cached-output bench showing real example02 theorem-family candidates > 0
no resolver rewrite unless an integration defect is found
```

## 4. Acceptance criteria sketch

```text
connector emits theorem-family EntityProposal candidates with normalized type and number
existing Plan 006_3 resolver tests remain green
real-data theorem-family resolution moves above 0 on a representative cached document
no regression in equation/citation/figure/table resolution
full test suite remains green or environment failures are classified
```

## 5. Human verification

Before implementation, replace this sketch with a full task/test/file-whitelist plan. The theorem-family detector is source-code work and must not proceed from this placeholder alone.
