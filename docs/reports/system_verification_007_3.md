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
| 006_5 | theorem-family moves OFF 0% on real data | **INCONCLUSIVE** (corpus gap) |
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

## 006_5 — Theorem-family off 0%  → INCONCLUSIVE (corpus gap, not a code defect)

Commands:
```bash
# markers of theorem-family type across all committed graphs
python -c "...count markers with marker_type in {theorem,definition,corollary,proof,example}..."
# theorem-family entities across all committed entities_*.json (+ scratch connector runs)
python -c "...count entities with those entity_types..."
```
Result: **0 theorem-family markers and 0 theorem-family entities** anywhere in
the corpus — across example01/02/3, every OCR backend, and every connector run
(including the canonical book run in local scratch). The baseline's 0% for
theorem/definition/corollary/proof/example is therefore **a property of the
corpus, not a failure of the 006_5 connector detector**: these three documents
(two physics arXiv articles and a solid-state physics book) contain no formal
`Theorem/Definition/Corollary/Proof/Example` environments to detect or resolve.

The 006_5 connector-side detector remains covered by its unit tests
(`tests/test_theorem_entity_detection.py`, `tests/test_theorem_candidate_roundtrip.py`)
and the resolver matcher by `tests/test_semantic_resolver.py`. Confirming it on
**real data** requires a theorem-bearing document in the corpus — this is the
primary next-plan recommendation (corpus expansion, 007_1).

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

Because there are 0 theorem-family markers/entities (see 006_5), there are 0
resolved theorem-family edges, so the first-hit-wins duplicate-number concern
has **no risk surface on this corpus**. The count of markers whose target
number was non-unique among candidates is **0**. This must be re-measured once
a theorem-bearing document is added.

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

6 of 7 rows PASS; 006_5 is INCONCLUSIVE solely because the corpus contains no
theorem-family content (a data gap, not a code defect). No regression in any
measured dimension. The clear next step is a theorem-bearing corpus addition so
006_5 can be confirmed end-to-end on real data.
