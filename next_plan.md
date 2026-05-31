# Plan 008_4 — Unresolved-Marker Diagnostic and Human Teaching Loop

Status:
draft

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
Phase 5b / Phase 7b — Semantic evaluation and visualization.

Current roadmap estimate:
No numeric change until drafted and human-approved.

Owner:
Human reviewer to draft; agent must not implement from this placeholder.

Sequence:
Follows Plan 006_5 after theorem-family candidates exist on real connector outputs.

Previous plan:
Plan 006_5 — Connector-Side Theorem-Family Entity Detector.

Branch name:
plan-008_4-unresolved-marker-teaching-loop

---

## 1. Purpose

Create an unresolved-marker diagnostic and human teaching loop so reviewers can inspect unresolved cross-reference markers, assign/confirm targets, and feed corrections back into resolver rules, priors, or validation fixtures.

## 2. Expected direction

This placeholder should be expanded into a full PLAN_TEMPLATE-compliant plan. Expected themes:

```text
collect unresolved RefMarkers and nearest candidate context
surface unresolved cases in the validator/viewer
persist human decisions as machine-readable verification or teaching artifacts
separate product verification evidence from ad-hoc prose notes
avoid changing resolver behavior without tests and fixtures
```

## 3. Drafting note

Do not promote this placeholder until Plan 006_5 is human-verified and the validator real-data wiring decision in `project.md` has been addressed or explicitly scoped.
