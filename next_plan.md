# Plan 006_1 — Semantic Router with Calibrated Weights

Status:
not_yet_drafted

Linked ROADMAP phase:
Phase 4b — Semantic cross-reference layer (routing)

Previous plan:
Plan 014_1 — networkx-Backed LinkedStructure Graph

Branch name:
plan-006_1-semantic-router

---

## 1. Purpose

Consume the 007_2 per-marker-type × OCR-backend calibration baseline
(`docs/reports/semantic_calibration_baseline.{md,json}`) to route semantic
cross-reference resolution: pick the backend (or weighted blend) most likely
to resolve each marker type, instead of treating all backends equally.

## 2. Expected direction

This placeholder must be expanded into a full PLAN_TEMPLATE-compliant plan.
Expected themes:

```text
load the deterministic calibration weights from the 007_2 baseline JSON
route per marker-type to the highest-resolution backend (or weighted blend)
keep the resolver ladder unchanged; only the candidate-source weighting moves
add tests over the calibration-weighted routing decisions
```

## 3. Drafting note

Draft after Plan 014_1 is human-verified. The networkx-backed graph utilities
(reading_order_sort, section_ancestors, detect_cycles, orphan_nodes) may be
reused by routing diagnostics.
