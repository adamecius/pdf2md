# Plan 014_1 — networkx-Backed LinkedStructure Graph

Status:
finished

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
Phase 4 — Semantic reconstruction (structural linking)

Current roadmap estimate:
From 80% to 85% (Phase 4)

Owner:
Agent team / human reviewer

Sequence:
Plan 014_1 (linking sub-plan, extends Plan 14 — LinkedStructure)

Previous plan:
Plan 006_4 — Backend Restructure

Required previous plan status:
human_verified (or agent_complete with deferred verification)

Next plan after completion:
Plan 006_1 — Semantic router with calibrated weights

Branch name:
plan-014_1-networkx-linked-structure

---

## 1. Purpose

Back the cross-page `LinkedStructure` graph with networkx, replacing the
hand-built list-of-relations data structure in `builder.py`. The domain-
specific resolvers (reading order, section hierarchy, ToC, page numbers,
headers/footers, captions, footnotes) stay unchanged — they already produce
`ResolvedLink` objects. This plan only changes how those links become a graph
and what traversal primitives are available downstream.

What networkx gives for free: cycle detection, topological sort (reading
order verification), shortest-path queries (section hierarchy traversal),
connected-component analysis (orphan node detection), and a standard API
that any future consumer (RAG chunking, Docling export, visualization) can
use without re-deriving adjacency.

Current state: `builder.py` (268 lines) iterates resolver results and
appends `LinkedRelation`s to a flat list inside `LinkedStructure`. There
is no graph object, no adjacency, no traversal API. Consumers walk the
list manually.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

STATE.md is the compact current-state surface.

current_plan.md is the active execution contract for agents.

next_plan.md is the next planned execution contract.

history.md records completed milestones after human verification.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-014_1-networkx-linked-structure
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. If git status is not clean before branch creation, stop and report.
4. Do not modify files outside the whitelist.
5. Do not install or use undeclared dependencies beyond networkx.
6. Do not change ROADMAP.md progress unless the plan explicitly allows it.
7. Do not mark this plan human_verified or finished.

Main conda environment:

```text
pdf2md
```

Repository-level commands must run using:

```bash
conda run -n pdf2md python <command>
```

This plan does NOT require backend execution. No OCR or semantic-model run
required.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Add `networkx>=3.0` to `[project.dependencies]` in `pyproject.toml`.
2. Refactor `builder.py` to construct a `nx.DiGraph` internally as the
   resolver results are wired. Each `LinkedNode` becomes a graph node
   (keyed by `node.id`); each `LinkedRelation` becomes a directed edge
   with `relation_type`, `confidence`, `status`, and `evidence` as edge
   attributes.
3. Expose the `nx.DiGraph` on `LinkedStructure` as a `.graph` property
   (or a `to_networkx()` method), while keeping the existing `.nodes`
   and `.relations` lists for backward compatibility (they are populated
   FROM the graph, not the other way around).
4. Add utility functions in a new `src/pdf2md/linking/graph_utils.py`:
   - `reading_order_sort(g) -> list[str]`: topological sort on
     `PAGE_SEQUENCE` + `READING_ORDER` edges.
   - `section_ancestors(g, node_id) -> list[str]`: walk `CONTAINS`
     edges upward.
   - `detect_cycles(g) -> list[list[str]]`: simple cycle detection.
   - `orphan_nodes(g) -> list[str]`: nodes with degree 0.
5. Tests: the existing `test_linked_structure_builder.py` and
   `test_linking_resolvers.py` must pass unchanged (backward compat);
   new tests for the graph utilities.

Out of scope:

1. Any resolver logic change (resolvers produce `ResolvedLink`; that
   contract is unchanged).
2. Any change to `LinkedNode`, `LinkedRelation`, or `LinkedStructure`
   pydantic models in `models/linked.py` (the `.graph` property is
   additive, not a schema change).
3. Docling export changes (it reads `.nodes`/`.relations`, which still
   exist).
4. Viewer or graph_export changes.
5. Semantic resolver or cross-reference layer changes.

Hard constraints:

1. `LinkedStructure.nodes` and `LinkedStructure.relations` must remain
   populated and identical to their pre-plan values for the same input.
   Consumers that iterate these lists must not break.
2. The networkx graph is a derived view, not the serialization format.
   `LinkedStructure` still serializes as the same JSON schema (nodes +
   relations lists). The graph is reconstructed on load if needed.
3. No existing test may regress.
4. networkx is the ONLY new dependency.

Allowed Python dependencies:

```text
networkx>=3.0
```

Allowed external tools:

```text
none
```

Allowed environment-modifying commands:

```text
pip install networkx (via pyproject.toml)
```

---

## 5. File whitelist and forbidden files

The agent may create or modify only these files:

```text
pyproject.toml                              (add networkx dep)
src/pdf2md/linking/builder.py               (refactor to use nx.DiGraph)
src/pdf2md/linking/graph_utils.py           (new)
src/pdf2md/linking/__init__.py              (re-export graph_utils)
tests/test_linked_structure_builder.py      (may add graph-property tests)
tests/test_linking_graph_utils.py           (new)
```

The agent must not modify these files:

```text
README.md
ROADMAP.md
project.md
STATE.md
current_plan.md
next_plan.md
history.md
src/pdf2md/models/linked.py
src/pdf2md/linking/resolvers.py
src/pdf2md/linking/extract.py
src/pdf2md/linking/io.py
src/pdf2md/linking/reporting.py
src/pdf2md/semantic/*
src/pdf2md/connectors/*
src/pdf2md/consensus/*
src/pdf2md/export/*
src/pdf2md/calibration/*
src/pdf2md/diagnostics/*
backend/*
webui/*
tools/*
```

Expected output artefacts:

```text
none beyond modified source + new test files
```

---

## 6. Agent tasks

### Task A1 — Add networkx dependency

Title:
Add networkx to pyproject.toml

Goal:
Make networkx available to the linking module.

Files allowed:

```text
pyproject.toml
```

Implementation requirements:

1. Add `"networkx>=3.0"` to the `[project.dependencies]` list.
2. Verify: `pip install -e .` succeeds and `import networkx` works in
   the pdf2md conda env.

Automated tests required:

```bash
conda run -n pdf2md python -c "import networkx; print('networkx', networkx.__version__)"
```

Completion evidence:
pyproject.toml diff, import succeeds.

Human verification required:
no

### Task A2 — Refactor builder.py to construct nx.DiGraph

Title:
Build the linked graph on networkx

Goal:
After running all resolvers, construct a `nx.DiGraph` from the resolver
results, and expose it while keeping `.nodes`/`.relations` populated.

Files allowed:

```text
src/pdf2md/linking/builder.py
tests/test_linked_structure_builder.py
```

Implementation requirements:

1. In `build_linked_structure()`, after collecting all `ResolvedLink`s
   and building `LinkedNode`/`LinkedRelation` objects:
   - Create a `nx.DiGraph`.
   - `g.add_node(node.id, **{field: getattr(node, field) for relevant fields})`
     for each `LinkedNode`.
   - `g.add_edge(rel.source_id, rel.target_id, relation_type=rel.relation_type.value,
     confidence=rel.confidence, status=rel.status.value)` for each
     `LinkedRelation`.
2. Store the graph on `LinkerRunResult` as `.graph: nx.DiGraph`.
3. `LinkedStructure.nodes` and `.relations` remain populated identically
   to the pre-plan behavior — the graph is additive.
4. Add at least one test in `test_linked_structure_builder.py` asserting:
   - `.graph` is a `nx.DiGraph`.
   - Number of graph nodes == len(linked_structure.nodes).
   - Number of graph edges == len(linked_structure.relations).

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_linked_structure_builder.py -q
conda run -n pdf2md pytest tests/test_linking_resolvers.py -q
```

Completion evidence:
Files changed, tests run, all existing tests still pass.

Human verification required:
no

### Task A3 — Graph utility functions

Title:
Add graph traversal utilities for downstream consumers

Goal:
Provide reading-order sort, section ancestry, cycle detection, and orphan
detection as tested, reusable functions.

Files allowed:

```text
src/pdf2md/linking/graph_utils.py           (new)
src/pdf2md/linking/__init__.py              (add re-export)
tests/test_linking_graph_utils.py           (new)
```

Implementation requirements:

1. `reading_order_sort(g: nx.DiGraph) -> list[str]`:
   - Filter to edges with `relation_type` in
     (`PAGE_SEQUENCE`, `READING_ORDER`).
   - Return `nx.topological_sort()` on the subgraph.
   - Raise `ValueError` if cycles exist in those edge types.

2. `section_ancestors(g: nx.DiGraph, node_id: str) -> list[str]`:
   - Follow `CONTAINS` edges in reverse direction from `node_id`.
   - Return ancestor node IDs from immediate parent to root.

3. `detect_cycles(g: nx.DiGraph) -> list[list[str]]`:
   - Return `list(nx.simple_cycles(g))`.

4. `orphan_nodes(g: nx.DiGraph) -> list[str]`:
   - Return nodes where `g.degree(n) == 0`.

5. Re-export from `linking/__init__.py`.

6. Tests in `test_linking_graph_utils.py`:
   - Build a small `nx.DiGraph` with 5 nodes, PAGE_SEQUENCE + CONTAINS
     edges.
   - Assert `reading_order_sort` returns correct order.
   - Assert `section_ancestors` returns correct chain.
   - Inject a cycle; assert `detect_cycles` finds it.
   - Add an isolated node; assert `orphan_nodes` returns it.
   - Assert `reading_order_sort` raises on a cyclic subgraph.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/test_linking_graph_utils.py -q
```

Completion evidence:
Files changed, tests run, exit codes.

Human verification required:
no

---

## 7. Human verification checkpoints

### Verification model

Human verification for this plan is **non-blocking**. Real-data validation
(that the networkx graph correctly represents a LinkedStructure built from
actual backend output) will be performed **in the diagnostic page** once the
reviewer loads an example and inspects the graph structure there. This plan
is not blocked on that verification — once automated tests pass, it may
proceed to archival.

### Deferred checkpoint H1 (to be executed in-product)

Title:
Verify networkx graph fidelity on a real LinkedStructure

Verification surface:
in_product (cross-reference diagnostic page / viewer)

Pass criteria:

```text
LinkedStructure.nodes and .relations are identical to pre-plan for the
  same input (backward compatibility).
The .graph property is a nx.DiGraph with node count == len(.nodes) and
  edge count == len(.relations).
reading_order_sort returns a sensible page order for example01.
detect_cycles returns empty for a well-formed LinkedStructure.
No existing test regresses.
```

Evidence:
Will be captured during in-product review. Retained as the test output +
the reviewer's confirmation in the diagnostic page.

### Completion gate

This plan's completion gate is **automated tests only**:

```text
All A1/A2/A3 automated tests pass.
Full suite (pytest tests/ --ignore=tests/_legacy_temp -x) remains green.
No forbidden files modified.
networkx is the only new dependency.
LinkedStructure.nodes and .relations backward-compatible.
```

When the gate passes, the plan advances to
`agent_complete → human_verified → finished` without blocking on H1.
H1 is a deferred verification debt recorded in STATE.md.

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/test_linked_structure_builder.py -q
conda run -n pdf2md pytest tests/test_linking_resolvers.py -q
conda run -n pdf2md pytest tests/test_linking_graph_utils.py -q
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

Failure classes:

repository_defect:
Graph construction wrong; backward-compat broken (nodes/relations differ);
graph_utils logic error; cycle in reading-order subgraph of a well-formed
structure.

environment_missing:
networkx not installable.

test_expectation_wrong:
A test fixture or expectation contradicts the LinkedStructure contract.

upstream_dependency_issue:
networkx API change (unlikely with >=3.0 pin).

Failure handling:

If repository_defect: agent fixes or reports.
If environment_missing: agent reports.
If test_expectation_wrong: human revises.

---

## 9. Checkpoints, push policy, and hand-off

C0 Plan ready: status active; whitelist complete; tasks A1–A3; tests listed;
next plan = 006_1.

C1 Agent complete: all tasks attempted; tests green; no forbidden files
modified; networkx is the only dep added; report done; status agent_complete.

C2 Human signs off: reviews report and test results; sets human_verified.
H1 in-product verification is deferred and recorded in STATE.md.

C3 Finished and promoted: archived as
`plans/archive/014_1-networkx-linked-structure.md`; milestone appended to
history.md; STATE.md updated ("LinkedStructure" → built with networkx);
Plan 006_1 promoted to current_plan.md; new next_plan.md created.

Push and PR policy:

```text
Agent may push the branch and open a draft PR.
Agent must not merge to main.
Agent must not direct-push to main.
```

Hand-off after human sign-off:

1. Archive as `plans/archive/014_1-networkx-linked-structure.md`.
2. Append milestone to history.md.
3. Update STATE.md: "LinkedStructure and Docling export" notes →
   "networkx-backed graph; reading_order_sort, section_ancestors,
   detect_cycles, orphan_nodes available."
4. Promote Plan 006_1 to current_plan.md.
5. Create new next_plan.md.
6. Record commit SHA / PR number.

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan: 014_1
Status:
Branch: plan-014_1-networkx-linked-structure
Commit or PR:
Files changed:
Forbidden files touched:
Tasks attempted: A1 / A2 / A3
Automated tests run / passed / failed:
Failure classes:
Dependencies added: networkx
Backward compat verified (nodes/relations identical): yes/no
Blockers:
Next recommended action:
```

Reviewer checklist:

1. Only whitelisted files changed?
2. No forbidden files (resolvers.py, models/linked.py, etc.) modified?
3. All tests green (including pre-existing linking tests)?
4. networkx is the only new dependency?
5. LinkedStructure.nodes and .relations backward-compatible?
6. graph_utils functions tested?
7. Is the next plan (006_1) clearly identified?
8. Is the deferred H1 verification gap recorded?
9. Safe to mark human_verified and proceed?

Status history:

```text
date — status — actor — note
2026-06-03 — active — human — plan drafted from linking module audit;
                               extends Plan 14 (LinkedStructure)
```

---

## Agent report (C1)

```text
Plan: 014_1
Status: agent_complete
Branch: plan-014_1-networkx-linked-structure
Commit or PR: (see PR opened against main)
Files changed: pyproject.toml, src/pdf2md/linking/builder.py,
  src/pdf2md/linking/__init__.py, src/pdf2md/linking/graph_utils.py (new),
  tests/test_linked_structure_builder.py,
  tests/test_linking_graph_utils.py (new)
Forbidden files touched: none
Tasks attempted: A1 / A2 / A3 (all)
Automated tests run / passed / failed:
  linking matrix (builder+resolvers+graph_utils+CLI) 87/87/0;
  full suite (--ignore=tests/_legacy_temp) 1174 passed, 212 skipped,
  16 xfailed, 0 failed; ruff clean on changed files.
Failure classes: none
Dependencies added: networkx>=3.0 (only)
Backward compat verified (nodes/relations identical): yes — node/relation
  construction is unchanged; the graph is an additive derived view.
Blockers: none

Design notes / deviations from the literal plan text:
1. Graph class is nx.MultiDiGraph, not nx.DiGraph. The fixtures produce
   parallel edges (a node both FOLLOWS and CONTAINS another), so a simple
   DiGraph would collapse them and violate hard constraint "edge count ==
   len(relations)". MultiDiGraph preserves one edge per relation; all
   required traversal primitives (topological_sort, simple_cycles, degree,
   in_edges) work on it unchanged.
2. .graph is exposed as a derived @property on LinkerRunResult (computed via
   graph_utils.linked_structure_to_graph) rather than a stored field. This
   honours hard constraint "the graph is reconstructed on load if needed",
   keeps LinkerRunResult constructible by existing callers
   (tools/build_linked_structure.py reconstructs it without a graph arg —
   that file is forbidden to edit), and guarantees the graph is always
   consistent with .nodes/.relations.
3. No property was added to the LinkedStructure pydantic model
   (models/linked.py is forbidden); projection lives in graph_utils as
   linked_structure_to_graph() and is re-exported from pdf2md.linking.
4. reading_order_sort uses FOLLOWS + PAGE_NUMBER_SEQUENCE_NEXT (the real
   enum members the plan referred to as READING_ORDER / PAGE_SEQUENCE);
   section_ancestors walks CONTAINS edges upward.

Next recommended action: human review; on sign-off, archive as
plans/archive/014_1-networkx-linked-structure.md, append history milestone,
update STATE.md LinkedStructure row, promote Plan 006_1.
```

## PR_reviews

(none yet)

## Feedback

(none yet)
