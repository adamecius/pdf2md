# Additional Plan 6 — Document Section Detectors (Index, Glossary) and Cross-Linking

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
Phase 4 — Semantic document construction and export preparation
(Extension of the entity-detection and cross-reference graph stack
established in Plans 005–008.)

Current roadmap estimate:
Phase-2 follow-up to PR #124. No ROADMAP.md percentage change until human
approval.

Note:
This plan extends the connector-side entity detectors and the semantic-layer
resolver to recognise document *back-matter sections* (Index, Glossary) and
to cross-link their entries to body content (sections, chapters, first
mention). It does NOT touch the OCR-side IR enrichment work (bbox / font
metadata); that is its own follow-up plan and is intentionally deferred.

Owner:
Agent team / human reviewer

Sequence:
Follow-up to PR #124 (`fix-semantic-installs`). Standalone from the numbered
Plans 1–18 sequence.

Previous work:
PR #124 — equation resolver, broken-bracket bibs, implicit-bib heuristic
upgrade, mineru/paddleocr block-fusion fix, duplicate-bib promotion.

Required previous plan status:
PR #124 merged.

Next plans after completion:
* Additional Plan 7 — Document-class classifier (article / book / document)
  so the semantic-layer detectors can adapt to the source. Filed because
  GROBID is article-trained and does not natively handle books.
* Additional Plan 8 — OCR-side IR enrichment (bbox + font metadata) for
  bottom-of-page / small-font footnote enforcement.

Branch name:
additional-plan-6-document-section-detectors

---

## 1. Purpose

Add detection for two more document back-matter sections — **Index** and
**Glossary** — alongside the existing Bibliography detection, then emit
cross-reference edges that link entries inside those sections back to the
body content they refer to.

The pipeline today recognises:

* `REFERENCE_SECTION` + `REFERENCE_ITEM` for bibliographies (PR #123 / #124).
* `SECTION` / `CHAPTER` for normal headings.
* `TOC_ENTRY` for table-of-contents entries.

The pipeline does NOT recognise:

* Index sections (`# Index`, `# Subject Index`) or their entries
  (`Hall effect, 5, 17, 42`).
* Glossary sections (`# Glossary`) or their entries
  (`Conductivity — the property of a material...`).
* Cross-links from an index entry to the body chapter/section it points at.
* Cross-links from a glossary entry to its first body mention.

This plan adds those detections plus the cross-link relations, so a
downstream semantic graph contains the document's complete back-matter
structure and a UI can navigate from an index page-number to the actual
content.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

`src/pdf2md/models/entities.py` defines the canonical `EntityType` and
`RelationType` taxonomies. Any extension must be additive — existing
consumers that look for `SECTION` / `CHAPTER` / `TOC_ENTRY` must keep
working.

`src/pdf2md/models/cross_ref.py` defines the canonical `RefType` taxonomy
used by the semantic layer. Any extension here is also additive.

This plan controls only the work explicitly described here.

---

## 3. Scope and deliverables

### 3.1 New `EntityType` values (additive)

```python
class EntityType(str, Enum):
    ...
    # New back-matter types
    INDEX_SECTION = "index_section"
    INDEX_ENTRY = "index_entry"
    GLOSSARY_SECTION = "glossary_section"
    GLOSSARY_ENTRY = "glossary_entry"
```

### 3.2 New / extended detectors in `src/pdf2md/connectors/common.py`

1. **`heading_section_detector` extension** — when a `BlockKind.HEADING`
   matches one of:
   * `index`, `subject index`, `name index`, `author index` → emit
     `INDEX_SECTION` + set `index_started = True`.
   * `glossary`, `terms`, `vocabulary` → emit `GLOSSARY_SECTION` + set
     `glossary_started = True`.

2. **`index_entry_detector`** — while `index_started`, each
   `BlockKind.PARAGRAPH` matching the index-entry shape (`Term, page-list`
   where the page-list is one or more numbers possibly separated by commas
   and dashes) becomes an `INDEX_ENTRY`. The detector parses the term
   (everything before the first numeric page reference) and the page list
   (a `set[int]`) into structured metadata:

   ```python
   metadata={
       "index_term": "Hall effect",
       "index_pages": [5, 17, 42],
       "index_subentries": [],   # filled when the line has nested children
   }
   ```

3. **`glossary_entry_detector`** — while `glossary_started`, each
   `BlockKind.PARAGRAPH` matching the glossary-entry shape (`Term :
   definition` or `Term — definition` or **Term**: definition) becomes a
   `GLOSSARY_ENTRY` with the term and definition in metadata.

4. **Section termination** — both `index_started` and `glossary_started`
   flip back to `False` when a `BlockKind.HEADING` at the same level or
   higher is encountered (mirrors the existing `refs_started` semantics).

### 3.3 New cross-link relations

The existing `RelationType.TOC_POINTS_TO` already models "this entry
points at that page / section." Reuse it for:

* `INDEX_ENTRY` → matching `SECTION` / `CHAPTER`. **Emit BOTH** kinds of
  match when both exist:
  * Page-number match — for every page number in `index_pages`, find
    the SECTION / CHAPTER whose `page_no` equals that page; emit one
    edge per match.
  * Heading-text match — if the index term itself matches a chapter or
    section heading (case-insensitive substring against the heading's
    `canonical_text`), emit an additional edge to that section. This
    catches index entries like `Hall effect, 5, 17, 42` where there's
    also a `# Hall effect` chapter heading elsewhere in the document.

  Each edge carries `metadata.match_strategy` set to `page` or
  `heading_text` so consumers can distinguish.

* `TOC_ENTRY` → matching `SECTION` / `CHAPTER` by page number (this is
  already partially modeled by the existing detector; this plan
  formalises it and ensures the relation is emitted).

For glossary entries:

* `GLOSSARY_ENTRY` → body blocks on the pages *explicitly listed in the
  glossary entry itself*, via a new relation
  `RelationType.GLOSSARY_DEFINES = "glossary_defines"`. The glossary
  entry text is expected to carry a page-list (mirroring index entries),
  e.g. `Conductivity, 12, 47-49` or `Berry phase ... 8-10`. We link
  ONLY to body content on those pages — no substring scanning of the
  body for term occurrences, since (a) it produces noisy matches on
  author names / partial words, and (b) glossaries typically list the
  defining pages explicitly.

  If multiple body blocks live on a listed page, emit one edge per
  block on that page; downstream consumers can deduplicate by section
  membership.

  If the glossary entry has no page list (definition-only glossary,
  e.g. `Conductivity — the property of a material...`), emit a
  GLOSSARY_ENTRY entity but NO `GLOSSARY_DEFINES` edges. The detector
  records `metadata.has_page_list = False` so audits can see this case.

### 3.4 Semantic-layer integration

The semantic-layer resolver (`src/pdf2md/semantic/resolver.py`) is
**not** touched in this plan.

The rationale: index/glossary entities are emitted on the connector
side and cross-linked there; the semantic-backend layer (GROBID, regex,
DeepSeek-VL2) doesn't emit index / glossary markers in any document
fixture we currently bench against. Adding resolver strategies for
markers nobody produces would be premature.

Document-class awareness — picking different semantic backends or
detector configurations based on whether the source is an article, a
book, or a generic document — is handled by **Additional Plan 7**.
That plan will, among other things, decide whether to fire the
index/glossary detectors at all for article-shaped inputs (where
they shouldn't appear), and whether to enable book-specific semantic
extraction paths.

### 3.5 Webui

* Render new entity types (INDEX_SECTION, INDEX_ENTRY, GLOSSARY_SECTION,
  GLOSSARY_ENTRY) with their own node colours.
* Show the new cross-link edges as dashed grey arrows so they don't drown
  out the marker→target edges.

---

## 4. Out of scope

* OCR-side bbox / font metadata enrichment — deferred to a follow-up plan.
* TOC reverse-link from body section back to TOC entry.
* Multi-level (nested) index entries beyond a one-deep `index_subentries`
  list — only one level of nesting is parsed.
* Multi-column index layout reconstruction — assumed to come out as
  single-column markdown from the OCR.

---

## 5. Acceptance criteria

1. Unit tests for:
   * Index heading detection on `# Index`, `# Subject Index`,
     `# Author Index`.
   * Glossary heading detection on `# Glossary`, `# Terms`.
   * Index entry parsing for `Hall effect, 5, 17, 42` (term + pages).
   * Index entry parsing for `Berry phase, 12–14` (page range).
   * Glossary entry parsing for `Conductivity — property of a material...`
     and `**Term**: definition`.
   * Section termination on next heading.
   * Cross-link emission: INDEX_ENTRY page 5 → SECTION/CHAPTER on page 5.
   * Cross-link emission: GLOSSARY_ENTRY "Hall" → earliest body block
     containing "Hall".

2. End-to-end test on a synthetic book-style fixture:
   * Body with `# Hall effect` on page 5, `# Berry phase` on page 12.
   * Tail `# Index` with entries:
     * `Hall effect, 5, 17, 42`
     * `Berry phase, 12`
   * Assert: 2 INDEX_ENTRY entities, and TOC_POINTS_TO edges from:
     * `Hall effect` entry → SECTION on page 5 (page match, also
       heading-text match — two edges, both flagged with the right
       `match_strategy`).
     * `Berry phase` entry → SECTION on page 12 (page + heading match
       collapse to two edges with different `match_strategy`).
   * Verify each edge's `metadata.match_strategy` is one of
     `{"page", "heading_text"}`.

3. End-to-end test on a synthetic glossary fixture:
   * Body with content on pages 1, 3, 7.
   * `# Glossary` section with entries:
     * `Conductivity, 3, 7`
     * `Hall — physicist (no page reference)`
   * Assert:
     * 2 GLOSSARY_ENTRY entities.
     * `Conductivity` entry emits GLOSSARY_DEFINES edges to body blocks
       on pages 3 and 7 only (NOT page 1, NOT any other body content
       containing the substring "conductivity").
     * `Hall` entry emits NO GLOSSARY_DEFINES edges, and its metadata
       has `has_page_list=False`.

3. Full regression suite green (current: 1069 passed, 216 skipped, 16
   xfailed).

4. No regression in any PR #124 numbers (example01/02 bibliography
   resolution rates unchanged).

---

## 6. Implementation order

1. Add the four new `EntityType` values and the new `RelationType`
   `GLOSSARY_DEFINES`.
2. Extend `heading_section_detector` to flip `index_started` /
   `glossary_started`.
3. Implement `index_entry_detector` + `glossary_entry_detector` in
   `recognize_entities` (parallel to the existing `reference_item_detector`
   block).
4. Implement section termination on next heading.
5. Implement cross-link emission in `_relations` (or a new `_back_matter_relations`
   helper).
6. Add unit tests covering each detector path.
7. Add the synthetic book-fixture end-to-end test.
8. Update `webui/cross_ref/viewer.js` to render the new node types and edge
   relation kind.
9. Update plan + commit + open PR.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Index-entry regex over-matches body lines like `Section 2, page 5` | Require `index_started` flag (only fire inside detected Index section). |
| Glossary regex over-matches dialog text like `Alice: hello.` | Require `glossary_started` flag + minimum term length (≥ 2 words OR ≥ 4 chars). |
| GLOSSARY_DEFINES cross-link matches the wrong body mention (e.g. matches "Hall" inside "Hall, J." author name) | Use word-boundary regex with case folding; require the body block to NOT be a `FOOTNOTE` / `REFERENCE_ITEM`. |
| New entity types break existing consumers that switch on a closed set | All additions are at the end of the enum; type-switches use `default: skip` semantics already. |
| Multi-level nested index entries dropped | Acknowledged; out of scope. One-deep subentries captured in metadata.

---

## 8. Open questions — resolved

The three open questions from the initial draft have been answered by
the human reviewer:

1. **INDEX_ENTRY cross-link strategy** — emit BOTH page-number and
   heading-text-match edges (one per match). More edges is better;
   downstream consumers can filter by `match_strategy` if they only
   want one kind.

2. **GLOSSARY_ENTRY linking** — link only to the pages explicitly
   listed in the glossary entry itself; do NOT scan the body for
   substring matches.

3. **Semantic-layer resolver extension** — deferred to Additional
   Plan 7 (document-class classifier). This plan stays connector-side
   only.
