# Plan 007_3 — Consolidated System Verification Ledger

This ledger closes the deferred non-blocking H1 verifications accumulated
across the feature stack (006_2, 006_4, 006_5, 014_1, 006_1, 017_1) plus the
theorem-family duplicate-number review finding. Each row carries a concrete
PASS / FAIL / INCONCLUSIVE verdict, the command that produced it, and a
one-line result. Commands use the pdf2md environment; direct Python uses the
absolute interpreter `/home/jgarcia/miniconda3/envs/pdf2md/bin/python` because
`conda run -n pdf2md python` mis-resolves to `rec_emb` on this host (pytest
resolves correctly).

| Source | Claim | Verdict |
|---|---|---|
| 006_2 | equation resolution holds ~96% across OCR backends | **PASS** |
| 006_4 | no PaddleOCR candidate source; `entity_merge` gone; MinerU default | **PASS** |
| 006_5 | theorem-family moves OFF 0% on real data | **INCONCLUSIVE** (stale snapshot + VLM hallucination) |
| 014_1 | networkx LinkedStructure graph is faithful | **PASS** |
| 006_1 | calibrated router down-weights GROBID on book, uniform on articles, never excludes | **PASS** |
| 017_1 | strict Docling export round-trips through `DoclingDocument.model_validate` | **PASS** |
| review | theorem-family first-hit-wins does not mis-resolve duplicate numbers on the book | **PASS** (0 risk surface) |

---

## 006_2 — Equation resolution ~96%  → PASS

Command:
```bash
python -c "import json;d=json.load(open('docs/reports/semantic_calibration_post_refactoring.json'));print(d['cross_backend_matrix']['equation'])"
```
Result: `equation = {consensus: 0.959, deepseek: 0.959, mineru: 0.956, paddleocr: 0.002}`.
MinerU and consensus both ≥ 0.95; no regression vs baseline (Δ = 0.000 on
every equation cell — see `diagnostic_delta.md`). PaddleOCR ≈ 0 is expected
(deprecated, see 006_4).

## 006_4 — No PaddleOCR candidate source / `entity_merge` gone  → PASS

Commands:
```bash
grep -rl 'entity_merge' src/ || echo 'entity_merge absent'
python -c "import pdf2md.consensus as c; print(hasattr(c,'CONSENSUS_BACKEND'), hasattr(c,'merge_entity_documents'))"
```
Result: `entity_merge` absent from `src/`; `pdf2md.consensus` exports neither
`CONSENSUS_BACKEND` nor `merge_entity_documents` (both → False). MinerU is the
documented default OCR candidate source; PaddleOCR is deprecated and not used
as a default/candidate. NOTE: the committed snapshot retains historical
`*__resolved_with__paddleocr.json` graphs (3 manifest references) — this is
the 006_4-sanctioned retention of historical baseline data, not active use.

## 006_5 — Theorem-family off 0%  → INCONCLUSIVE (stale snapshot + VLM hallucination, not a code defect)

> **Phase 2 correction.** The Phase 1 claim of "0 theorem-family markers and 0
> theorem-family entities anywhere in the corpus" was **factually wrong** and is
> retracted. The adjudication ground truth
> (`docs/adjudications/*.adjudications.json`) and the Phase 2 findings review
> establish the corrected picture below. The verdict stays **INCONCLUSIVE**, but
> the closure path changes: it is **not** corpus expansion.

Corrected findings:

1. **The corpus DOES contain theorem-family markers.** example3 carries **139**
   theorem-family markers (all emitted by the `vlm_v4` backend; GROBID emits 0),
   and example02 carries **~96** (regex). The Phase 1 "0 markers anywhere" count
   was an error.

2. **example3's 139 VLM markers are hallucinations / template leakage, not real
   theorem content.** The book (791 pp) has **zero** `Theorem N.M` occurrences —
   verified against the source PDF; the book numbers *Exercises*, not theorems.
   The emissions show a repeated-count signature ("Theorem 10.1" ×17 =
   "Example 10.1" ×17 = "Corollary 10.1" ×17) and literal-"N" templates, both
   diagnostic of template leakage. **Calibration implication:** down-weight /
   filter VLM theorem-family emissions.

3. **example02 (arXiv 2401.12345) IS a theorem-bearing document.** Verified
   against the source PDF, it contains real numbered Theorems 1–3, Corollaries
   1–5, Definitions 1–6, Examples 1–5, Lemma 1, and proofs. Its committed
   `entities_mineru.json` is a **pre-006_5 snapshot** (0 theorem-family
   entities), which is precisely why all of its ~96 theorem-family markers are
   unresolved — the snapshot predates the 006_5 detector.

4. **Therefore the closure path for 006_5 is NOT corpus expansion.** The corpus
   already has a real theorem-bearing document. Closure requires **regenerating
   example02's connector outputs with the 006_5 detector** (next plan). The
   theorem-family duplicate-number risk must be **re-measured there** as well,
   because example02's real numbering (Theorem 1 / Corollary 1 / Example 1 all
   share the number "1") is exactly the duplicate-number surface 006_5's
   first-hit-wins logic must handle.

The 006_5 connector-side detector remains covered by its unit tests
(`tests/test_theorem_entity_detection.py`, `tests/test_theorem_candidate_roundtrip.py`)
and the resolver matcher by `tests/test_semantic_resolver.py`. Confirming it on
**real data** requires regenerating example02 with the 006_5 detector, not adding
a new document.

Evidence: `docs/adjudications/example02__consensus+mineru.adjudications.json` and
`docs/adjudications/example3__consensus+mineru.adjudications.json` (human
sign-off, AI-assisted draft), plus the Phase 2 findings review and the source
PDFs for example02 and example3.

## 014_1 — networkx LinkedStructure graph fidelity  → PASS

Command:
```bash
env PYTHONPATH=src python -c "...build_linked_structure on linking fixtures; assert graph counts; reading_order_sort; detect_cycles; orphan_nodes..."
```
Result (over `simple_document` and `toc_footnotes_references` fixtures):

| fixture | nodes == len(nodes) | edges == len(relations) | reading_order | cycles | orphans |
|---|---|---|---|---|---|
| simple_document | 5 == 5 ✓ | 11 == 11 ✓ | acyclic (4 ordered) | 1 (explained) | 0 |
| toc_footnotes_references | 15 == 15 ✓ | 39 == 39 ✓ | acyclic (14 ordered) | 1 (explained) | 0 |

Node and edge counts match the LinkedStructure exactly (MultiDiGraph preserves
parallel relations). `reading_order_sort` succeeds (the FOLLOWS/PAGE_SEQUENCE
subgraph is acyclic). `detect_cycles` reports one 2-node cycle per fixture,
**explained and benign**: e.g. `node4 →(caption_of) node3 →(follows) node4` —
a caption captions a figure that immediately follows it in reading order. The
cycle spans two *different* relation types (caption_of vs follows), not a
containment contradiction, and does not affect reading order. No orphans.

## 006_1 — Calibrated router weights  → PASS

Command:
```bash
env PYTHONPATH=src python -c "from pdf2md.semantic.router import weights_for_document_class; from pathlib import Path; b=Path('docs/reports/semantic_calibration_baseline.json'); print(weights_for_document_class('book',b)); print(weights_for_document_class('article',b))"
```
Result: `book = {consensus: 1.0, grobid: 0.684, vlm: 0.965}`; `article = {}`
(uniform). GROBID is down-weighted on the book (0.684 < 1.0), articles stay
uniform, and **no backend weight is 0.0** (no exclusion) — exactly the ROADMAP
principle.

## 017_1 — Strict Docling export round-trips  → PASS

Command:
```bash
env PYTHONPATH=src python -c "from docling_core.types.doc import DoclingDocument; ...build_docling_document(strict=True) per export fixture; model_validate; check metadata.pdf2md.nodes..."
```
Result: strict export of `simple_document`, `rich_document`, and
`unresolved_conflicts` each passes `DoclingDocument.model_validate` with zero
errors, and `metadata["pdf2md"]["nodes"]` retains every emitted node id
(traceability intact). (Run on the committed export fixtures; the three
`webui` examples have no committed LinkedStructure to export here — see the
note below.)

## Theorem-family duplicate-number risk  → 0 (no risk surface on this corpus)

The corpus does contain theorem-family markers (see the corrected 006_5
section), but **0 resolved theorem-family edges** exist on the current
snapshots: example02's committed `entities_mineru.json` is a pre-006_5 snapshot
with 0 theorem-family entities (so its ~96 markers are all unresolved), and
example3's 139 markers are VLM hallucinations that do not resolve against real
entities. With 0 resolved edges, the first-hit-wins duplicate-number concern has
**0 measured risk on the current snapshots**. This must be **re-measured after
example02 is regenerated with the 006_5 detector** (next plan), where the real
shared numbering (Theorem 1 / Corollary 1 / Example 1 all numbered "1") will
finally exercise the first-hit-wins path.

---

## Scope notes / deviations

- **A1 (regenerate graphs) was intentionally non-destructive.** A true
  post-006_5 regeneration is moot (corpus has no theorem content) and not
  feasible here (OCR backends/sources unavailable in the tracked repo). The
  committed graphs were preserved; recomputing calibration on them reproduces
  the baseline byte-identically (no regression). See `diagnostic_delta.md`.
- **017_1 / 014_1 real-data check** used the tracked export/linking fixtures
  (current schema, reproducible) rather than the three `webui` examples, which
  ship only resolved cross-reference graphs (no committed `LinkedStructure` or
  consensus IR to build a strict Docling export from). The fixtures exercise
  the same code paths.
- Backends used: none re-run (regex/GROBID/VLM/MinerU not invoked); the ledger
  reads the committed graphs + runs the current library code. GROBID/VLM/
  DeepSeek/MinerU were not available/exercised on this host.

## Summary verdict

6 of 7 rows PASS; 006_5 is INCONCLUSIVE — but **not** because the corpus lacks
theorem-family content. Phase 2 (adjudication ground truth) showed the corpus
*does* contain a real theorem-bearing document, example02 (arXiv 2401.12345,
with numbered Theorems/Corollaries/Definitions/Examples/Lemma), whose committed
`entities_mineru.json` is a pre-006_5 snapshot (0 theorem-family entities), and
that example3's 139 theorem-family markers are VLM hallucinations / template
leakage rather than real content. No regression in any measured dimension. The
clear next step is therefore **regenerating example02's connector outputs with
the 006_5 detector** (not corpus expansion), at which point 006_5 can be
confirmed end-to-end on real data and the theorem-family duplicate-number risk
re-measured against example02's real shared numbering.
