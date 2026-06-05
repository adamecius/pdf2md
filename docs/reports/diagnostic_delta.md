# Plan 007_3 — Post-Refactoring Calibration Delta

Compares the recomputed post-refactoring calibration
(`semantic_calibration_post_refactoring.json`) against the 007_2 baseline
(`semantic_calibration_baseline.json`), per marker_type × OCR-resolution
backend, as `baseline → post (Δ)`.

## Method and reproduction

```bash
env PYTHONPATH=src /home/jgarcia/miniconda3/envs/pdf2md/bin/python \
  tools/semantic_calibration_report.py --data-dir webui/cross_ref/data --out-dir /tmp/post_cal
```

Recomputing on the committed `webui/cross_ref/data` graphs reproduces the
baseline **byte-identically**: 0 of the cross-backend-matrix cells differ,
44/44 graph combinations match. This is the determinism guarantee from Plan
007_2 and confirms the committed graph snapshot is unchanged.

## Why the delta is zero (regeneration scope)

A true post-006_5 regeneration would require re-running the **OCR connector**
(`recognize_entities`) on the source documents so the per-backend
`entities.json` carry theorem-family entities, then re-resolving. That is
**moot on this corpus and not feasible on this host**:

- **Corpus gap:** none of example01 / example02 / example3 contain any
  theorem-family content. Across every committed graph and every connector
  run (including the canonical book run), there are **0 theorem-family
  markers** and **0 theorem-family entities**. example01/02 are physics
  arXiv articles; example3 is a solid-state physics book — none use formal
  `Theorem/Definition/Corollary/Proof/Example` environments. So
  regenerating cannot move theorem-family off 0% regardless of code.
- **OCR not exercised:** regenerating entities needs MinerU/DeepSeek OCR on
  the source PDFs, which is out of reach here (heavy backends; sources live
  only in untracked local scratch). The `regex` semantic backend alone does
  not produce OCR entities.

The committed graphs therefore remain the reference, the recompute confirms
**no regression**, and the theorem-family confirmation is deferred to a
theorem-bearing corpus (see `system_verification_007_3.md`, row 006_5, and
the next-plan recommendation).

## Per-example resolution (aggregated over all backend combinations)

| example | resolved / total | unresolved | rate |
|---|---:|---:|---:|
| example01 (article) | 1438 / 1976 | 538 | 0.728 |
| example02 (article) | 1373 / 2800 | 1427 | 0.490 |
| example3 (book) | 27387 / 55632 | 28245 | 0.492 |

The unresolved counts are the Phase-2 adjudication workload.

## Per marker_type × backend delta

| marker_type | backend | baseline | post | Δ |
|---|---|---:|---:|---:|
| bibliography | consensus | 0.684 | 0.684 | +0.000 |
| bibliography | deepseek | 0.684 | 0.684 | +0.000 |
| bibliography | mineru | 0.684 | 0.684 | +0.000 |
| bibliography | paddleocr | 0.034 | 0.034 | +0.000 |
| chapter | consensus | 0.479 | 0.479 | +0.000 |
| chapter | deepseek | 0.250 | 0.250 | +0.000 |
| chapter | mineru | 0.259 | 0.259 | +0.000 |
| chapter | paddleocr | 0.000 | 0.000 | +0.000 |
| corollary | consensus | 0.000 | 0.000 | +0.000 |
| corollary | deepseek | 0.000 | 0.000 | +0.000 |
| corollary | mineru | 0.000 | 0.000 | +0.000 |
| corollary | paddleocr | 0.000 | 0.000 | +0.000 |
| definition | consensus | 0.000 | 0.000 | +0.000 |
| definition | deepseek | 0.000 | 0.000 | +0.000 |
| definition | mineru | 0.000 | 0.000 | +0.000 |
| definition | paddleocr | 0.000 | 0.000 | +0.000 |
| equation | consensus | 0.959 | 0.959 | +0.000 |
| equation | deepseek | 0.959 | 0.959 | +0.000 |
| equation | mineru | 0.956 | 0.956 | +0.000 |
| equation | paddleocr | 0.002 | 0.002 | +0.000 |
| example | consensus | 0.000 | 0.000 | +0.000 |
| example | deepseek | 0.000 | 0.000 | +0.000 |
| example | mineru | 0.000 | 0.000 | +0.000 |
| example | paddleocr | 0.000 | 0.000 | +0.000 |
| figure | consensus | 0.602 | 0.602 | +0.000 |
| figure | deepseek | 0.515 | 0.515 | +0.000 |
| figure | mineru | 0.537 | 0.537 | +0.000 |
| figure | paddleocr | 0.000 | 0.000 | +0.000 |
| footnote | consensus | 0.388 | 0.388 | +0.000 |
| footnote | deepseek | 0.386 | 0.386 | +0.000 |
| footnote | mineru | 0.384 | 0.384 | +0.000 |
| footnote | paddleocr | 0.002 | 0.002 | +0.000 |
| proof | consensus | 0.000 | 0.000 | +0.000 |
| proof | deepseek | 0.000 | 0.000 | +0.000 |
| proof | mineru | 0.000 | 0.000 | +0.000 |
| proof | paddleocr | 0.000 | 0.000 | +0.000 |
| section | consensus | 0.855 | 0.855 | +0.000 |
| section | deepseek | 0.847 | 0.847 | +0.000 |
| section | mineru | 0.839 | 0.839 | +0.000 |
| section | paddleocr | 0.003 | 0.003 | +0.000 |
| table | consensus | 0.477 | 0.477 | +0.000 |
| table | deepseek | 0.477 | 0.477 | +0.000 |
| table | mineru | 0.477 | 0.477 | +0.000 |
| table | paddleocr | 0.000 | 0.000 | +0.000 |
| theorem | consensus | 0.000 | 0.000 | +0.000 |
| theorem | deepseek | 0.000 | 0.000 | +0.000 |
| theorem | mineru | 0.000 | 0.000 | +0.000 |
| theorem | paddleocr | 0.000 | 0.000 | +0.000 |
