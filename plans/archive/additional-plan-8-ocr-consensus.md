# Additional Plan 8 — OCR-Side Weighted Consensus (`consensus` OCR option)

Status:
finished

Implementation note (PR #128):
Implemented via :func:`pdf2md.consensus.merge_entity_documents` rather
than the heavier :func:`build_consensus_ir` route originally sketched
in §3.1. The block-level ConsensusIR sits at the wrong abstraction for
the webui resolver bridge, which consumes
:class:`EntityProposalDocument` directly. The lightweight
entity-level merge keeps highest-confidence per dedup key and records
``merged_from_backends`` for audits — same shape the semantic side's
:func:`merge_graphs` produces. The full block-level ConsensusIR
remains available behind ``pdf2md.consensus.build_consensus_ir`` for
future stages.

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
Phase 3 — Consensus and ensemble logic
(Specialisation of the existing Plan 13 weighted-ConsensusIR pipeline
for the cross-reference viewer.)

Current roadmap estimate:
Post-PR-#127 follow-up. No ROADMAP.md percentage change until human
approval.

Note:
PR #127 (Plan 7) added a **semantic-layer** consensus option to the
cross-reference viewer (best-of-confidence merge of regex + GROBID +
DeepSeek-VL2 via :func:`merge_graphs`, with Plan-7 doc-class-aware
backend weights). It did NOT add an OCR-side consensus — picking the
"best" entity per type from the three OCR backends. That work is
what this plan covers.

The existing :mod:`pdf2md.consensus` module (built in Plan 13)
already implements weighted ConsensusIR. The gap is:

* No CLI / script that runs the OCR consensus on the
  `pdf2md/.tmp/papers_run/<example>/` cache layout.
* No serialisation of the consensus output in the
  `entities_consensus.json` shape the webui expects.
* No `consensus` entry in `webui/cross_ref/data/manifest.json`'s
  `ocr_backends` list.

This plan wires those three pieces so the viewer's OCR dropdown gets
a fourth option labelled `consensus`.

Owner:
Agent team / human reviewer

Sequence:
Follow-up to Additional Plan 7 (document-class classifier). Independent
of Additional Plan 6 (Index/Glossary detectors).

Previous work:
* PR #127 — semantic-layer consensus surfaced in the viewer.
* Plan 13 (draft) — weighted ConsensusIR implementation in
  `src/pdf2md/consensus/`.

Required previous plan status:
PR #127 merged. Plan 13's `consensus.factory.build_consensus_ir` is
already implemented and tested.

Branch name:
additional-plan-8-ocr-consensus

---

## 1. Purpose

Produce a single `EntityProposalDocument` per example that represents
the OCR-side consensus across `deepseek` / `mineru` / `paddleocr`,
ship it as `webui/cross_ref/data/<example>/entities_consensus.json`,
and surface it as the fourth `ocr_backends` choice in the viewer
manifest. The resolved-with files (e.g.
`grobid__resolved_with__consensus.json`) follow the existing per-OCR
pattern.

This closes the user-reported gap from the PR #127 review: "the whole
point of the consensus shall be to unify the answer of the three
backends, so we shall have one which is unified based on the best
scores from the groundtruth, that shall be called consensus, the same
with the semantic layer."

---

## 2. Source-of-truth hierarchy

`src/pdf2md/consensus/` — existing weighted-consensus implementation
(Plan 13). The MVP for this plan uses it as-is.

`src/pdf2md/calibration/` — existing calibration-prior generator
(Plan 12). The MVP uses default uniform priors; later iterations can
plug in fixture-tuned priors.

This plan controls only the wiring between consensus and the viewer.

---

## 3. Scope and deliverables

### 3.1 OCR consensus runner

A small repo-level CLI (or a `tools/` script committed to the repo)
that:

1. Loads the three per-OCR `EntityProposalDocument`s from
   `pdf2md/.tmp/papers_run/<example>/connector_<ocr>/<ocr>/entities.json`.
2. Calls
   `pdf2md.consensus.factory.build_consensus_ir(per_backend_entities,
   priors=...)` to produce a single consensus document.
3. Writes the consensus to
   `webui/cross_ref/data/<example>/entities_consensus.json`.
4. Writes
   `webui/cross_ref/data/<example>/<sem>__resolved_with__consensus.json`
   for every semantic backend in the manifest (mirroring the existing
   per-OCR resolved-with shape).

### 3.2 Manifest entry

`webui/cross_ref/data/manifest.json` gets a new entry:

```json
{
  "id": "consensus",
  "label": "consensus (deepseek ∪ mineru ∪ paddleocr)",
  "notes": "Weighted consensus across the three OCR backends via Plan 13's ConsensusIR pipeline."
}
```

### 3.3 Viewer support

`webui/cross_ref/viewer.js` already loads `entities_<ocr>.json` from
the manifest's `ocr_backends` list — no code change required. The
document-class badge (Plan 7) reads from the entities metadata, so it
automatically picks up the consensus's classification.

---

## 4. Out of scope

* Building a new consensus algorithm. Plan 13's
  `ConsensusFactory` is the source of truth.
* Calibration-prior tuning per OCR backend. Default uniform priors
  are acceptable for an initial iteration.
* Replacing the per-OCR options. The four backends (`deepseek`,
  `mineru`, `paddleocr`, `consensus`) all stay selectable so users
  can compare consensus against the individual backends.

---

## 5. Acceptance criteria

1. `webui/cross_ref/data/<example>/entities_consensus.json` exists
   for both `example01` and `example02`.
2. `webui/cross_ref/data/<example>/<sem>__resolved_with__consensus.json`
   exists for every semantic backend in the manifest.
3. Manifest has the new `consensus` `ocr_backends` entry.
4. Viewer renders the consensus selection without errors; document-
   class badge appears with class `article` (since both fixtures are
   articles).
5. Full regression green.

---

## 6. Open questions

1. Should the consensus runner be a tools/-level script or a proper
   `pdf2md.cli` subcommand?
2. Should it auto-emit on every benchmark run, or be on-demand?
3. Should we ship a "best-of-confidence" fallback for documents where
   Plan 13's ConsensusIR isn't available, similar to what the
   semantic-layer consensus did before Plan 13 existed?
