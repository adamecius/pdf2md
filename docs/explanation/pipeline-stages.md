# Pipeline stages

`pdf2md` converts a sequential PDF into a Docling-compatible structured
document by passing the input through a staged pipeline. Each stage
has a single responsibility, a Pydantic contract, and an owner module
under `src/pdf2md/`.

This page explains what each stage does in operator terms — what
input it consumes, what output it produces, and which module owns it.

For the durable architecture description (model contracts, design
principles, conflict semantics), see
[`../../project.md`](../../project.md). For the public-facing pitch
of the pipeline, see [`../../README.md`](../../README.md).

---

## At a glance

```text
PDF
  ↓  (1) backend extraction       ── src/pdf2md/backends/runner.py
raw/<backend>/output.md + manifest
  ↓  (2) connector canonicalisation ── src/pdf2md/connectors/common.py
PageExtractionIR per backend + EntityProposalDocument
  ↓  (3) calibration prior resolution ── src/pdf2md/consensus/io.py
prior per backend (user / factory / uninformative)
  ↓  (4) consensus scoring          ── src/pdf2md/consensus/{factory,grouping,scoring}.py
ConsensusIR (block-level winners + conflicts)
  ↓  (5) linking                    ── src/pdf2md/linking/{builder,resolvers,extract}.py
LinkedStructure (document-wide nodes + relations)
  ↓  (6) export                     ── src/pdf2md/export/{docling,markdown,rag}.py
Docling JSON + Markdown preview + RAG chunks
```

The orchestrator that wires the stages together is
[`src/pdf2md/pipeline/orchestrator.py`](../../src/pdf2md/pipeline/orchestrator.py).
Per-stage tools under `tools/` let you invoke any single stage in
isolation (useful for debugging).

---

## 1. Backend extraction

**Owner:** [`src/pdf2md/backends/runner.py`](../../src/pdf2md/backends/runner.py).

Reads `pdf2md.backends.toml`, dispatches each enabled OCR backend as
a subprocess (via `conda run -n pdf2md-<backend> ...`), captures
stdout/stderr, and writes a per-backend `manifest.json` with timing
and exit status. The backends themselves live under `backend/<name>/`
and own their own conda envs.

Output is a per-backend `output.md` + `manifest.json` in
`<run-dir>/raw/<backend>/`.

**Why a subprocess per backend?** Each backend has its own model and
CUDA toolchain. Isolating them per conda env prevents version
conflicts (paddle 3.0 vs 3.1, torch ABI breaks, CUDA 11 vs 12) and
lets a failure in one backend not poison the others.

---

## 2. Connector canonicalisation

**Owner:** [`src/pdf2md/connectors/common.py`](../../src/pdf2md/connectors/common.py).

Takes each backend's raw markdown + manifest and converts it into the
canonical IR layout the rest of the pipeline expects:

```
connector_canonical/<doc>/<backend>/
├── pages/page_NNNN.json     (PageExtractionIR per page)
├── entities.json            (EntityProposalDocument)
└── manifest.json
```

The connector also classifies blocks (`PARAGRAPH`, `HEADING`,
`CAPTION`, `FIGURE`, `TABLE`, `FORMULA`, …) and proposes entities
(captions referencing figures, footnote markers, equation refs).

Contracts: `PageExtractionIR` and `EntityProposalDocument` in
[`src/pdf2md/models/ir.py`](../../src/pdf2md/models/ir.py) +
[`src/pdf2md/models/entities.py`](../../src/pdf2md/models/entities.py).

---

## 3. Calibration prior resolution

**Owner:** prior loading sits in
[`src/pdf2md/consensus/io.py`](../../src/pdf2md/consensus/io.py); the
prior contracts and the three-level fallback chain are in
[`src/pdf2md/models/priors.py`](../../src/pdf2md/models/priors.py).

For each backend with page data, resolve a `CalibrationPriorDocument`
in this order (Plan 19):

1. **User prior** at `<priors-dir>/<backend>.json` (silent success).
2. **Factory prior** shipped at
   `src/pdf2md/data/factory_priors/<backend>.json`
   (warning: `prior_factory:<backend>`).
3. **Uninformative prior** built in memory (uniform
   `default_confidence`, warning: `prior_uninformative:<backend>`).

The pipeline therefore always has a prior to score with — there is no
chicken-and-egg between calibration and consensus.

For the full reference + the calibrator CLI, see
[`../reference/calibration-priors.md`](../reference/calibration-priors.md).

---

## 4. Consensus scoring

**Owner:** [`src/pdf2md/consensus/`](../../src/pdf2md/consensus/).

Where the multi-backend evidence is fused. Three sub-stages:

- **Grouping** ([`grouping.py`](../../src/pdf2md/consensus/grouping.py)) —
  match candidate blocks across backends by text overlap, bbox IoU,
  and BlockKind compatibility into `CandidateGroup`s.
- **Scoring** ([`scoring.py`](../../src/pdf2md/consensus/scoring.py)) —
  per-group, compute a Bayesian weighted score for each candidate
  using text/bbox/order/kind agreement and the calibrated priors.
- **Factory** ([`factory.py`](../../src/pdf2md/consensus/factory.py))
  — assemble the `ConsensusIR` from per-group winners.

The scoring weights (rebalanced in Plan 19) put 0.35 of the total
weight on per-BlockKind prior confidence and 0.20 on per-EntityType
confidence — calibration is the dominant signal. Margin gates decide
whether to commit a winner or mark the group as unresolved (a
first-class conflict, not a silent drop).

Output: `ConsensusIR` containing per-page `ConsensusBlock`s + a
conflicts list.

---

## 5. Linking

**Owner:** [`src/pdf2md/linking/`](../../src/pdf2md/linking/).

Walks the document-wide ConsensusIR and builds a `LinkedStructure`:
nodes (sections, captions, footnotes, references, page-numbers, …)
connected by typed relations (`CAPTION_OF`, `REFERENCES`,
`READING_ORDER`, `IN_SECTION`, …).

The chain of resolvers ([`resolvers.py`](../../src/pdf2md/linking/resolvers.py))
runs in order:

```
reading_order → section_hierarchy → toc → page_numbers
→ repeating_headers_footers → captions → footnotes
→ equation_sequence → figure_table_sequence → references
```

Each resolver records `LinkEvidence` so a downstream reader can see
*why* a link was inferred. Unresolvable links become first-class
`LinkedConflict`s.

Contract: `LinkedStructure` in
[`src/pdf2md/models/linked.py`](../../src/pdf2md/models/linked.py).

---

## 6. Export

**Owner:** [`src/pdf2md/export/`](../../src/pdf2md/export/).

Produces the three operator-visible artefacts:

- **Docling JSON** (canonical) — `<run>/docling/<doc>.docling.json`.
- **Markdown preview** — `<run>/markdown/<doc>.preview.md`.
- **RAG chunks** — `<run>/rag/<doc>.rag_chunks.json`.

For the contract of each format and which consumer to use it with,
see [`../reference/export-formats.md`](../reference/export-formats.md).

---

## Cross-cutting: provenance and confidence

Every artefact along the chain — block, entity, prior, consensus
choice, linked node, exported chunk — carries provenance (where it
came from) and a confidence score. The export-stage RAG chunks
expose both to downstream search/retrieval, so a consumer can decide
whether to trust a snippet by its calibrated confidence rather than
treating all OCR output as equal.

This is the *evidence-not-truth* design principle from
[`../../project.md`](../../project.md) §13 expressed in the pipeline
data model.

---

## See also

- [`../../project.md`](../../project.md) — durable architecture and
  design principles.
- [`../../ROADMAP.md`](../../ROADMAP.md) — phase plan and the
  pre-MVP / post-MVP sequence.
- [`../reference/calibration-priors.md`](../reference/calibration-priors.md)
  — the calibration subsystem reference.
- [`../reference/export-formats.md`](../reference/export-formats.md) —
  the export layer reference.
- [`../tutorials/`](../tutorials/) — the operator walkthroughs.
