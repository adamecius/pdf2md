# Plan 008_5 — Adjudication Review UX: Document-in-Context Viewer

Status:
agent_complete

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
Phase 7b — Visualization and human-in-the-loop review

Current roadmap estimate:
No numeric change (UX enabler; unblocks Plan 007_3 Phase 2).

Owner:
Agent team / human reviewer

Sequence:
Plan 008_5 (viewer UX sub-plan; extends 008_4 Adjudicate tab). Runs BEFORE
Plan 007_3 Phase 2 — the adjudication session needs a reviewable GUI.

Previous plan:
Plan 007_3 — Full System Diagnostic (Phase 1 complete; Phase 2 paused pending
this viewer improvement).

Required previous plan status:
agent_complete / human_verification_required for 007_3 (Phase 1 landed).

Next plan after completion:
Resume Plan 007_3 Phase 2 (human adjudication) using the improved viewer.

Branch name:
plan-008_5-adjudication-review-ux

---

## 1. Purpose

The current cross-reference viewer makes human review and adjudication hard:
a marker shows only a terse label (e.g. `"[1]"`) with a context table that is
mostly empty (the `marker:` ids are not graph nodes, so `source_ref`,
`char_offset`, `backend`, `page_no` render as `—`), resolution is a flat
dropdown of *every* entity in the document, and there is no way to see the
source document — so "the marker does not connect or has text" and is hard to
review.

This plan makes the adjudication experience reviewable by surfacing the
**document itself** (already available, untapped) and the **marker in its
context**:

- The committed `docling.json` per example carries the full document text
  (~300 text items, with page provenance) — render it as a readable
  **Document** pane (the "book").
- Each marker encodes its page (`#/document/pages/N`) and its text
  (`edge.label`), so each marker can be **located in the document**, its
  surrounding sentence shown inline, and highlighted in the Document pane on
  click.
- Unresolved markers get **ranked candidate suggestions** (same type, then
  same page) as one-click resolve buttons instead of a flat dropdown.
- **List <-> graph <-> text cross-highlighting** lets a reviewer trace a
  marker across the marker list, the graph, and the document text.
- **Connection clarity:** resolved vs unresolved endpoints are obvious, with
  the target's text shown inline.

This is a static-viewer change only (HTML/CSS/JS). No backend, no Python, no
data regeneration. Verification is in-product (the human opens the page).

---

## 2. Source-of-truth hierarchy

ROADMAP.md, project.md, STATE.md, current_plan.md, next_plan.md, history.md.
This plan controls only the work described here.

---

## 3. Repository and environment protocol

Standard branch protocol (this branch stacks on Plan 007_3, which is paused at
its human gate; the known scratch files stay in `.git/info/exclude`).

No conda env or pipeline execution required. JS is syntax-checked with the
`node20` env (`conda run -n node20 node --check webui/cross_ref/viewer.js`).
Behavioural verification is the human opening the served page.

---

## 4. Scope, constraints, and dependencies

In scope (all in `webui/cross_ref/`):

1. A **Document** tab rendering `docling.json` text in reading order, grouped
   by page, readable, each text item anchored by `self_ref`.
2. A **marker->document locator**: parse the page from the marker id
   (`#/document/pages/N`) and match `edge.label` within that page's text
   (fallback: document-wide label search). Show the matched sentence inline in
   each adjudication / marker row, with the marker text emphasised.
3. Clicking a marker scrolls the Document pane to and highlights its context.
4. **Ranked candidate suggestions** for unresolved markers: same-type first,
   then same-page, as one-click resolve buttons; the full dropdown remains as
   a fallback.
5. **Cross-highlighting**: hovering/selecting a marker highlights its graph
   link + target node and its document sentence, and clicking a graph xref
   link selects the corresponding marker row.
6. **Connection clarity**: show the resolved target's text/label inline;
   distinguish resolved vs unresolved endpoints visually.
7. CSS for the document pane, highlights, and candidate chips.

Out of scope:

1. Any change under `src/`, `backend/`, `tools/`, `tests/`.
2. Regenerating or editing `webui/cross_ref/data/**` (read-only here).
3. Embedding/rendering source PDF page images (the PDFs are not in the tracked
   repo; the docling text pane is the chosen "see the book" surface).
4. Changes to the adjudication file schema or `manage_adjudications.py`.
5. The semantic backends, resolver, router, or export code.

Hard constraints:

1. The exported adjudication file format/`MarkerAdjudication` schema is
   unchanged (the agent's Task A4 validation in 007_3 still applies).
2. The viewer degrades gracefully when `docling.json` is absent for an example
   (no Document pane content, rows fall back to label-only — no crash).
3. No new runtime dependencies beyond the already-loaded d3 CDN.

Allowed dependencies: none new.

---

## 5. File whitelist and forbidden files

Whitelist:

```text
webui/cross_ref/index.html
webui/cross_ref/viewer.js
webui/cross_ref/style.css
webui/cross_ref/README.md
```

Forbidden:

```text
src/*
backend/*
tools/*
tests/*
webui/cross_ref/data/*
docs/*
ROADMAP.md
project.md
(STATE.md / current_plan.md / next_plan.md / history.md are governance only,
 edited at promotion/hand-off, not as plan implementation tasks)
```

---

## 6. Agent tasks

### A1 — Document pane

Add a "Document" tab (index.html) and `renderDocument(docling, graph)` in
viewer.js: texts in reading order grouped by page, each as a paragraph with
`data-self-ref` and `data-page`. Graceful empty state when no docling.

### A2 — Marker->document locator + inline context

`locateMarker(edge)` -> {page, snippetHtml, selfRef}. Parse page from
`edge.source` (`/pages\/(\d+)/`); within that page's docling texts find the
first containing `edge.label`; return the sentence with the label wrapped in
`<mark>`. Show the snippet inline in adjudication rows (and the markers pane);
clicking the row scrolls+highlights the Document pane item.

### A3 — Candidate suggestions

`rankCandidates(graph, edge)` -> same-type entities first, then same-page,
limited to ~6; render as one-click resolve chips in each unresolved row. Keep
the existing `entityOptions` dropdown as a fallback.

### A4 — Cross-highlighting + connection clarity

Hover/select a marker row -> highlight the matching graph xref link + target
node and the Document pane sentence. Clicking an xref link in the SVG selects
the marker row. In rows, show resolved target label/text inline and style
resolved/unresolved distinctly.

### A5 — CSS

Document pane (scrollable, readable column), `<mark>` highlight, selected
sentence, candidate chips, resolved/unresolved row accents.

Verification:

```bash
conda run -n node20 node --check webui/cross_ref/viewer.js   # JS parses
# in-product: python -m http.server -d webui/cross_ref ; load each example,
#   open Document + Adjudicate tabs, click markers, confirm context + candidates.
```

---

## 7. Human verification checkpoints

H1 (in-product): the human serves the page, confirms the Document pane shows
the text, a clicked marker highlights its sentence, candidate suggestions
appear for unresolved markers, and cross-highlighting works. This is also the
GUI the human then uses for Plan 007_3 Phase 2.

Completion gate (agent): `node --check` passes; graceful no-docling fallback;
only whitelisted files changed; no data/src/test edits.

---

## 8. Test matrix

```bash
conda run -n node20 node --check webui/cross_ref/viewer.js
env PYTHONPATH=src conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp   # unchanged; no src edits
```

Failure classes: repository_defect (JS error / crash on load / no graceful
fallback); test_expectation_wrong (n/a — no tests changed).

---

## 9. Checkpoints, push policy, and hand-off

C0 ready. C1 agent A1–A5 (node --check green; report). C2 human H1 in-product.
C3 finished: archived; STATE updated ("viewer: document-in-context review");
**resume Plan 007_3 Phase 2** with the improved GUI.

Push policy: agent may push + open draft PR; must not merge.

---

## 10. Report / reviewer checklist

Reviewer: (1) Document pane shows the book text? (2) clicking a marker
highlights its sentence? (3) candidate suggestions appear and resolve in one
click? (4) cross-highlighting list<->graph<->text works? (5)
resolved/unresolved connections are clear? (6) graceful when docling absent?
(7) only `webui/cross_ref/` files changed?

Status history:

```text
date — status — actor — note
2026-06-03 — active — agent — drafted from the user's review-UX feedback
                              ("markers don't connect or show text; let me see
                              the book"); document-text pane chosen over PDF
                              embedding (PDFs not in tracked repo).
```

---

## Agent report (C1)

```text
Plan: 008_5
Status: agent_complete (awaiting in-product H1)
Branch: plan-008_5-adjudication-review-ux
Files changed: webui/cross_ref/index.html, webui/cross_ref/viewer.js,
  webui/cross_ref/style.css
Forbidden files touched: none (no src/tools/tests/data changes)
Tasks: A1 Document pane / A2 marker->document locator + inline context /
  A3 ranked candidate chips / A4 cross-highlight + connection clarity / A5 CSS
Verification:
  conda run -n node20 node --check webui/cross_ref/viewer.js -> OK
  full suite (--ignore=tests/_legacy_temp) -> 1206 passed (no src changes)
  data-driven locator check (replicated logic on real graphs):
    example01: 52 marker edges -> 15 text-context, 2 page-only, 35 none
    example02: 126 edges -> 36 text-context, 23 page-only, 67 none
    (normalized label variants lifted example01 text hits 2 -> 15)
Blockers / honest gaps:
  - example3 (the BOOK) has NO docling.json in webui/cross_ref/data, and none
    exists in scratch either. The Document pane therefore shows its graceful
    empty state for example3; the enriched rows (label, page, candidate chips,
    connection) still work. Adding the book's docling export to the viewer
    data is a follow-up DATA task (out of this plan's read-only-data whitelist)
    and is the single biggest remaining win for "see the book".
  - ~35-67 markers/example have neither a text match nor a resolvable page in
    their source_ref; those rows show "no document context found" but remain
    adjudicable. Improving match recall is a possible follow-up.

What changed for the reviewer:
  - New default "Document" tab renders the source text (from docling) by page.
  - Each marker row now shows its sentence in context with the marker text
    highlighted, its page, a "show in document" jump, ranked same-type/same-
    page resolve chips (one-click), and a clear resolved/unresolved connection.
  - Hover/click a marker -> its graph link + endpoints and its document
    sentence highlight together; clicking a graph xref link jumps to the text.
```

## PR_reviews

(none yet)

## Feedback

(none yet)
