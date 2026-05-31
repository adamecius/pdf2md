# Additional Plan 7 — Document-Class Classifier (Article / Book / Document)

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
Phase 4 — Semantic document construction and export preparation
(Extension of the semantic-backend ensemble built in Plan 005 / 006.)

Current roadmap estimate:
Post-PR-#124 follow-up. No ROADMAP.md percentage change until human
approval.

Note:
GROBID is trained primarily on scholarly articles. It does not natively
handle book-shaped documents (chapters, indices, glossaries, multi-author
contributions). On book-shaped inputs (e.g. `multi_chapter_book` fixture)
it under-detects bibliography entries, mis-detects chapter headings as
sections, and misses index / glossary structure entirely.

This plan introduces a lightweight **document-class classifier** that
inspects the connector-side entity-proposal output and tags the document
as one of `article`, `book`, or `document` (a catch-all). Downstream
stages (semantic backends, detector enablement, resolver tie-breakers)
then consult this tag to adapt their behaviour.

This plan does NOT change the existing semantic-backend bench numbers —
it only adds a class hint that future work can leverage.

Owner:
Agent team / human reviewer

Sequence:
Follow-up to Additional Plan 6 (Index/Glossary detectors).

Previous work:
* PR #124 — bibliography / equation resolver fixes.
* Additional Plan 6 — Index/Glossary detectors and back-matter cross-linking.

Required previous plan status:
Additional Plan 6 merged.

Branch name:
additional-plan-7-document-class-classifier

---

## 1. Purpose

Decide, per document, whether it is best modelled as:

* `article` — single contribution, ≤ ~50 pages, one bibliography, no
  chapters, no index, no glossary.
* `book` — multi-chapter, ≥ ~50 pages typically, chapters as top-level
  headings, often has an index and/or glossary, may have a per-chapter
  bibliography.
* `document` — anything that doesn't cleanly fit the above (reports,
  notes, technical manuals, presentations exported to PDF, …).

Expose the classification on the `EntityProposalDocument` metadata so
downstream stages can consult it without re-deriving the answer.

The classifier is **rule-based** (not ML) for this plan, so it is
deterministic, fast, and inspectable. A future plan can train an ML
classifier on labelled fixtures if accuracy is insufficient.

---

## 2. Source-of-truth hierarchy

`src/pdf2md/models/entities.py` defines `EntityProposalDocument`. The
new `document_class` field is added to its `metadata` dictionary (no
schema bump — `metadata` is already `dict[str, Any]`).

ROADMAP.md and project.md describe the broader semantic-layer
architecture. This plan adds a classification step on top of the
existing connector output without changing the contract any
consumer relies on today.

---

## 3. Scope and deliverables

### 3.1 New classifier module

`src/pdf2md/semantic/document_class.py`

```python
class DocumentClass(str, Enum):
    ARTICLE = "article"
    BOOK = "book"
    DOCUMENT = "document"  # catch-all

@dataclass(frozen=True)
class DocumentClassification:
    document_class: DocumentClass
    confidence: float            # 0..1
    features: dict[str, Any]     # the signals that drove the decision

def classify_document(
    proposals: EntityProposalDocument,
    pages: list[PageExtractionIR],
) -> DocumentClassification: ...
```

### 3.2 Rule-based classifier

The classifier inspects four signals:

1. **Page count** — total `len(pages)`.
2. **Chapter density** — count of `CHAPTER` entities and their
   distribution across pages.
3. **Back-matter shape** — presence of `REFERENCE_SECTION` (one vs.
   many), `INDEX_SECTION`, `GLOSSARY_SECTION`.
4. **Heading hierarchy** — number of distinct H1 headings versus H2/H3.

Decision tree:

```text
if INDEX_SECTION present OR GLOSSARY_SECTION present:
    → BOOK (confidence 0.95)
elif CHAPTER count >= 3:
    → BOOK (confidence 0.85)
elif page_count >= 50 AND chapter count >= 1:
    → BOOK (confidence 0.70)
elif REFERENCE_SECTION count == 1 AND page_count <= 30:
    → ARTICLE (confidence 0.85)
elif REFERENCE_SECTION present AND page_count <= 50:
    → ARTICLE (confidence 0.70)
else:
    → DOCUMENT (confidence 0.50)
```

The exact thresholds are documented as constants at the top of the
module so future tuning is one edit, not a code-archaeology trip.

### 3.3 Integration

`src/pdf2md/connectors/common.py:recognize_entities` calls
`classify_document` at the end (after the implicit-bib detector) and
writes the result to `EntityProposalDocument.metadata`:

```python
proposals = EntityProposalDocument(
    ...
    metadata={
        ...,
        "document_class": classification.document_class.value,
        "document_class_confidence": classification.confidence,
        "document_class_features": classification.features,
    },
)
```

### 3.4 Semantic-backend consumption

`src/pdf2md/semantic/ensemble.py` and the per-backend adapters read
`metadata["document_class"]` and can:

* Skip the GROBID backend on `BOOK`-class inputs where it's known to
  fail (or run it but down-weight its outputs in the ensemble).
* Enable book-only detectors (chapter-level bibliography, per-chapter
  numbering resets).
* Pass the document-class hint into the VLM prompt so it can adjust
  its detection strategy.

These integrations are scoped per-backend and added incrementally;
this plan only requires:

1. The classifier exists and is called.
2. Its output is on `EntityProposalDocument.metadata`.
3. **One** consumer demonstrates use of the field (the ensemble's
   weight mixer is the natural pick — it can down-weight GROBID on
   `BOOK` inputs).

### 3.5 Webui

Surface the document class as a small badge next to the example
selector — purely informative, no behaviour change in the viewer.

---

## 4. Out of scope

* ML-based classifier — explicitly deferred. If the rule-based version
  has acceptable accuracy on the labelled fixtures (`example01` = article,
  `example02` = article, `multi_chapter_book` = book), no ML is needed.
* Sub-classes (e.g. `book.textbook` vs. `book.monograph`,
  `article.preprint` vs. `article.journal`). Top-level only.
* Multi-document classification (e.g. a PDF that contains an article
  followed by appendix material from a book). Treat as the dominant
  class.

---

## 5. Acceptance criteria

1. Unit tests:
   * Each rule branch fires on a synthetic fixture that matches its
     decision criteria.
   * Confidence values fall in `[0.0, 1.0]`.
   * Features dictionary contains every signal used in the decision.

2. Fixture-based tests:
   * `example01` (1410.8140.pdf) → `ARTICLE`.
   * `example02` (math/CS paper) → `ARTICLE`.
   * `multi_chapter_book` ground-truth fixture → `BOOK`.

3. The ensemble weight mixer consults `document_class` and applies a
   smaller weight to GROBID's output when class == `BOOK`. This is
   tested via the existing semantic ensemble tests (extended).

4. Full regression green.

---

## 6. Implementation order

1. Add `DocumentClass` + `DocumentClassification` + `classify_document`.
2. Wire it into `recognize_entities` (writes metadata).
3. Add unit tests covering each decision branch.
4. Add fixture-based tests on example01 / example02 /
   multi_chapter_book.
5. Extend the ensemble mixer to consult `document_class`.
6. Update webui badge.
7. Update plan + commit + open PR.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Thresholds (page count, chapter count) overfit to the three current fixtures | Keep thresholds named and documented; expect to retune as more fixtures land. |
| Index/glossary signals from Additional Plan 6 dominate the decision tree on real books | That's by design — a document with an index IS a book by almost any working definition. |
| Article PDFs with appendix chapters get mis-classified as books | The `CHAPTER count >= 3` rule needs ≥ 3 chapters; appendix-only is usually 1-2. |
| Books without an index, glossary, or explicit chapter headings (e.g. a long monograph using SECTION-only) | Falls through to `DOCUMENT` class with confidence 0.50 — accurate signal that we don't know.

---

## 8. Open questions

1. Should the classifier also emit a **secondary** class (e.g. main =
   `BOOK`, secondary = `MULTI_AUTHOR`) or stay strictly single-class?
2. Should the GROBID adapter `skip` on `BOOK` inputs, or `run-but-
   down-weight`? The latter is safer but more code.
3. Where does the classifier live for the `pipeline` orchestrator
   (Plan 18)? Before or after the calibration stage?

Tagged for human-reviewer decision before implementation begins.
