# pdf2md

`pdf2md` is a multi-backend document reconstruction system for converting complete sequential PDF documents into a structured Docling representation.

The project is designed for scientific and technical documents where the document structure matters: sections, table of contents, equations, tables, figures, captions, footnotes, glossary-like sections, references, bibliography entries, page sequence, headers, footers, and reading order.

The goal is not simply to extract text. The goal is to reconstruct the document as a semantic object with provenance, confidence, conflicts, and explicit relations.

---

## Documentation

The operator manual lives under [`docs/`](docs/) and follows the
[Diataxis](https://diataxis.fr/) structure:

- [`docs/getting-started.md`](docs/getting-started.md) — install and
  run your first conversion (5 minutes after backend setup).
- [`docs/tutorials/`](docs/tutorials/) — guided walkthroughs:
  [01 setup](docs/tutorials/01-setup-backends.md) ·
  [02 first conversion](docs/tutorials/02-first-conversion.md) ·
  [03 calibrate priors](docs/tutorials/03-calibrate-priors-on-corpus.md) ·
  [04 batch + multi-backend](docs/tutorials/04-batch-processing.md).
- [`docs/how-to/`](docs/how-to/) — task-oriented recipes (datasets,
  factory priors, troubleshooting).
- [`docs/reference/`](docs/reference/) — contracts and CLI surfaces
  (calibration, datasets registry, export formats).
- [`docs/explanation/`](docs/explanation/) — design rationale and
  pipeline stages.

`project.md` and `ROADMAP.md` remain canonical for the architecture
and roadmap respectively.

---

## Installation

### Requirements

| | Version | Notes |
|---|---|---|
| Python | 3.11–3.13 | Recommended: **3.12** (matches all backend env files). |
| OS | Linux / macOS / Windows | Backend GPU recipes are Linux + NVIDIA. |
| `conda` (or `mamba`) | any recent | Backend envs are conda envs by convention. |

System packages (only required if you want to compile the LaTeX
ground-truth corpus or run the calibration tutorial):

```
TeX Live ≥ 2024 with lualatex, latexmk
latexml         (optional — produces the XML twin used by some fixtures)
```

The main package itself has no system dependencies beyond a working
Python.

### 1. Install the main package

```bash
git clone https://github.com/adamecius/pdf2md.git
cd pdf2md
conda create -n pdf2md python=3.12 -y
conda activate pdf2md
python -m pip install -e .
```

Confirm:

```bash
pdf2md --help
```

The main package pulls in:

| Dep | Pin | Used by |
|---|---|---|
| `pydantic` | `>=2.6` | All IR / entity / prior / linked / export models. |
| `typer` | `>=0.12` | CLI surface (`pdf2md ...`). |
| `PyMuPDF` | `>=1.24` | Connector + testing-fixture PDF parsing. |
| `docling-core` | `>=2.0` | Canonical export-target schema. |

For development tooling (`ruff`, `mypy`, `pytest`):

```bash
python -m pip install -e ".[dev]"
```

### 2. Supported backends

A backend is **supported** when it has a tested setup script and a
pinned working version. All four current backends are supported on
Linux + NVIDIA GPU; `glm` also works on any host with network access
and an API key (no GPU). MinerU and DeepSeek are GPU-required.

| Backend | Env name | Python | Key versions (pinned) | GPU | Setup |
|---|---|---|---|---|---|
| **paddleocr** | `pdf2md-paddleocr` | 3.12 | `paddlepaddle==3.0.0` (cu118 wheel for GPU), `paddleocr>=2.7,<3.0`, `PyMuPDF>=1.24` | CUDA 11.8 + cuDNN 8 | [`backend/paddleocr/setup.py`](backend/paddleocr/setup.py) |
| **mineru** | `pdf2md-mineru` | 3.12 | `mineru[pipeline]==3.1.4`, `torch==2.7.0+cu126`, `torchvision==0.22.0+cu126` | CUDA 12.6 | [`backend/mineru/setup.py`](backend/mineru/setup.py) |
| **deepseek** | `pdf2md-deepseek` | 3.12.9 | `transformers==4.46.3`, `tokenizers==0.20.3`, `numpy==2.2.6`, `vllm==0.8.5+cu118` | CUDA 11.8 | [`backend/deepseek/setup.py`](backend/deepseek/setup.py) |
| **glm** | `pdf2md-glm` | 3.12 | `requests>=2.31`, `PyMuPDF>=1.24` (API-based; no model) | not required | [`backend/glm/setup_env.py`](backend/glm/setup_env.py) |

"Supported" here means: the listed setup script installs the listed
versions and `tools/backend_smoke.py` has been observed to run an
end-to-end PDF→IR conversion with that combination. Newer upstream
releases may work but are not part of the supported set.

### 3. Install a backend

Each backend lives in its own conda env so version conflicts
(CUDA, paddle, torch) don't poison each other. You only need one
backend to run a conversion; install more for calibrated
multi-backend consensus.

Easiest path — install the backend's pinned env via the simple
`setup_env.py`:

```bash
# Pick one (or more):
python backend/paddleocr/setup_env.py
python backend/mineru/setup_env.py
python backend/deepseek/setup_env.py
python backend/glm/setup_env.py
```

The `setup_env.py` scripts read the per-backend `environment.yml` and
`requirements.txt` files (which carry the pinned versions in the
table above). They are deterministic and offline-friendly once the
wheels are cached.

For the **rich** installer (system checks, GPU detection, optional
model downloads, CUDA toolkit install), each backend also ships a
`setup.py`:

```bash
python backend/paddleocr/setup.py     # PaddleOCR with GPU detection
python backend/mineru/setup.py        # MinerU + vLLM acceleration
python backend/deepseek/setup.py      # DeepSeek-OCR-2 + vLLM + CUDA 11.8 toolkit
# glm has no rich setup — setup_env.py is sufficient (API-based)
```

Use `setup_env.py` to reproduce the supported version set exactly.
Use `setup.py` when you need GPU/system-level orchestration (CUDA
toolkit, vLLM wheels, model weight downloads).

### 4. Wire the backend into the runner

```bash
cp pdf2md.backends.example.toml pdf2md.backends.toml
# Edit: set `enabled = true` for the backends you installed.
```

For paddleocr GPU runtime, uncomment the
`[backends.paddleocr.env]` block in `pdf2md.backends.toml` and set
`LD_LIBRARY_PATH` to the cuDNN / cuBLAS / nvrtc directories inside
the `pdf2md-paddleocr` conda env. See
[`backend/paddleocr/README.md`](backend/paddleocr/README.md) for the
full GPU recipe (paddle 3.0.0 cu118 + cuDNN 8 — paddle 3.1+ has an
oneDNN runtime bug that crashes PPStructureV3).

### 5. Verify the installation

```bash
# Smoke-check the main env
pdf2md --help
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x

# Smoke-check a backend (replace paddleocr with the one you installed)
DOC=linked_sections_figures
PDF="groundtruth/corpus/latex/$DOC/$DOC.pdf"
conda run -n pdf2md python tools/backend_smoke.py \
    --input-pdf "$PDF" \
    --out-dir /tmp/backend_smoke \
    --gate-minimum 1 --verbose
```

If anything fails, see
[`docs/how-to/troubleshoot-local-runs.md`](docs/how-to/troubleshoot-local-runs.md)
for common error signatures (CUDA libs, paddle PIR bug, LaTeX toolchain).

For the full operator manual,
[`docs/getting-started.md`](docs/getting-started.md) walks the same
flow with the next steps after install.

---

## 1. Project goal

`pdf2md` processes different classes of complete PDF documents:

- scanned or image-based PDFs;
- born-digital PDFs with embedded text;
- mixed PDFs with both text layer and scanned regions;
- PDFs compiled from LaTeX;
- tagged PDFs when structural tags are available.

The output target is a Docling-compatible document representation, with optional downstream exports such as Markdown previews, RAG chunks, JSON reports, and inspection artefacts.

The system assumes that the input is a complete sequential document, not a collection of loose pages. It uses the internal structure of the document itself, including page order, table of contents, section hierarchy, captions, references, glossary or index-like sections, and bibliography material, as evidence for reconstruction.

---

## 2. Core idea

Different extraction backends see different parts of the same document well.

One backend may be strong on OCR text. Another may be better on tables. Another may detect formulae more reliably. Embedded PDF text may be more accurate than OCR in born-digital documents, while OCR may be necessary for scanned regions. Tagged PDF, LaTeX-derived XML, and geometric extraction may provide additional evidence.

`pdf2md` treats every backend as evidence, not as truth.

The pipeline compares backend outputs, records agreement and conflict, and builds a post-consensus semantic structure. The final Docling output is generated from this semantic structure, not from a single backend.

---

## 3. Target architecture

The target system is:

```text
Complete sequential PDF (any class: scanned, born-digital, mixed, LaTeX, tagged)

  -> visual OCR via the configured backend ensemble
  -> per-backend PageExtractionIR
  -> EntityProposalDocument
  -> CalibrationPriorDocument (resolved at consensus load time;
                               see "Prior resolution" below)
  -> ConsensusIR              (Bayesian feature picker over backends)
  -> LinkedStructure
  -> Docling JSON
  -> validation and confidence reporting
```

There is no PDF-type classifier or input-routing stage. Every document
goes through the same visual-OCR backend ensemble; the consensus stage
picks the most reliable feature extraction per BlockKind / EntityType,
not the input-classification stage.

Ground truth is produced from:

```text
.tex source
  -> LuaLaTeX / tagged PDF
  -> LaTeXML XML
  -> semantic ground-truth contracts
  -> Docling ground-truth JSON
```

The ground-truth corpus is used to measure backend success and failure, and to calibrate confidence in the backend ensemble.

---

## 4. Processing pipeline

The intended high-level pipeline is:

```text
PDF document
  -> backend extraction (visual OCR ensemble)
  -> per-backend PageExtractionIR
  -> entity proposals
  -> backend calibration priors (loaded via three-level fallback)
  -> page-level ConsensusIR
  -> whole-document LinkedStructure
  -> Docling JSON
  -> validation, reports, RAG chunks, Markdown preview
```

The pipeline is deliberately staged.

Low-level comparison happens early, at page and block level. Whole-document reasoning happens later, when the system has enough evidence to resolve relations such as captions, references, footnotes, section hierarchy, table of contents, and bibliography structure.

Docling is the canonical structured export target. Markdown is a human-readable preview, not the source of truth.

### Prior resolution (Plan 19)

Calibration priors are *loaded* at consensus time via a three-level
fallback chain — the consensus pipeline never blocks waiting for
calibration data:

```text
user-calibrated prior at <priors-dir>/<backend>.json   (refresh via tools/calibrate_priors.py)
  -> factory prior at src/pdf2md/data/factory_priors/<backend>.json
  -> uninformative prior built at runtime
     (uniform 0.50 confidence, status=UNINFORMATIVE)
```

The chain is silent in the happy path; the two fallback transitions
emit warnings `prior_factory:<backend>` and `prior_uninformative:<backend>`
so reports record which level was used. Calibration is offline: run
`tools/calibrate_priors.py` against a ground-truth corpus to refresh
priors; the `--from-scratch` flag stamps `calibration_mode="from_scratch"`
in the output metadata.

---

## 5. Main architecture files

The target architecture is described across a small set of repository files.

| File | Role |
|---|---|
| `project.md` | Durable product and architecture description. This is the best high-level description of the system goal. |
| `README.md` | Public entry point. It explains what the project does, how the pipeline works, and where to start. |
| `ROADMAP.md` | Durable product roadmap from current prototype state to MVP and production readiness. |
| `PLAN_TEMPLATE.md` | Standard template for future executable plans, including agent tasks and human verification checkpoints. |
| `current_plan.md` | Current implementation plan, including task whitelist, tests, and acceptance criteria. This is operational, not the product vision. |
| `next_plan.md` | Next planned milestone. Useful for development sequencing, but not the canonical architecture. |
| `history.md` | Completed milestones and archived implementation history. |
| `agent.md` | Rules for Codex or other coding agents working on the repository. |
| `docs/calibration.md` | Operator's guide for `tools/calibrate_priors.py`, the three-level prior fallback, and the factory-prior update protocol. |
| `docs/datasets.md` | External ground-truth dataset registry (`pdf2md datasets …` CLI). |
| `docs/docling_layer.md` | Legacy Docling inspection-layer pointer. Marks the deprecated `pdf2md._legacy.docling_adapter` path and redirects readers to the canonical export under `src/pdf2md/export/`. |

The durable product architecture should live in `project.md` and be summarised in this README. The active implementation plan should live in `current_plan.md`. Historical plans and logs should not be used as the product vision unless they have been consolidated into `project.md` or `ROADMAP.md`.

---

## 6. Ground truth strategy

The project uses a growing LaTeX-derived ground-truth corpus.

For controlled documents, the source of truth is built from:

```text
.tex source
  -> LuaLaTeX / LaTeX compiled PDF
  -> tagged PDF where available
  -> LaTeXML XML
  -> semantic ground-truth contracts
  -> Docling ground-truth JSON
```

The ground-truth corpus is used to test and improve the full pipeline.

For each document, the system can compare:

```text
backend output
  -> consensus output
  -> linked semantic structure
  -> Docling export
```

against the LaTeX-derived ground truth.

This allows the system to learn which backends are reliable for which document features. For example, one backend may be trusted more for equations, another for tables, another for captions, and another for reading order.

Successes and failures against the ground-truth corpus are used to calibrate backend confidence and improve the ensemble.

---

## 7. Robust ensemble OCR and extraction

`pdf2md` is designed as an ensemble system. OCR and document extraction are not delegated to a single backend. Each backend contributes evidence about the same complete document, and that evidence is judged against prior experience from the ground-truth corpus.

The ground-truth corpus is used to measure backend behaviour feature by feature. The system should learn where each backend succeeds and where it fails.

Examples:

```text
Backend A may be strong on body text but weak on tables.
Backend B may be strong on formula detection but weak on reading order.
Backend C may be strong on captions but weak on footnotes.
The embedded PDF text layer may be reliable for born-digital text but incomplete for figures or scanned regions.
Tagged PDF structure may be reliable for hierarchy but incomplete for visual layout.
LaTeXML may be highly reliable for source-known structure but unavailable for ordinary PDFs.
```

These observations become calibration priors. During consensus, backend outputs are not treated equally in all situations. Their evidence is weighted according to previously observed reliability on similar document features.

The intended learning loop is:

```text
ground-truth corpus
  -> backend success/failure measurements
  -> feature-specific backend confidence
  -> weighted page-level consensus
  -> whole-document semantic linking
  -> Docling output with provenance and confidence
```

When backends agree, confidence increases. When they disagree, the system uses calibrated priors, document structure, geometry, embedded text, tagged structure, and semantic constraints to select, defer, or mark conflicts explicitly.

This is the reason for maintaining a growing source-known ground-truth corpus. The corpus does not only test the pipeline. It trains the trust model for the ensemble.

The aim is robust OCR and extraction through calibrated agreement, especially for scientific documents containing equations, tables, captions, references, footnotes, and mixed text/image regions.

---

## 8. Document model

The project distinguishes several layers.

### PageExtractionIR

The page extraction layer stores primitive evidence from each backend:

```text
page number
block type
text
bounding box
confidence
backend provenance
raw artefact reference
```

This layer is page-local. It is designed for backend comparison and conflict detection.

### EntityProposalDocument

Backends and connector layers can emit entity proposals for higher-level interpretation, such as possible captions, references, equations, footnote markers, table-of-contents entries, and bibliography material.

Entity proposals are evidence. They are not final structure.

### CalibrationPriorDocument

Calibration priors describe how much the ensemble should trust a backend for specific evidence types, document features, or extraction behaviours.

These priors are expected to improve as the ground-truth corpus grows.

### ConsensusIR

The consensus layer groups backend candidates and selects or records candidate blocks.

It does not pretend that every conflict is resolved. When backends disagree, the conflict is kept as part of the document evidence.

### LinkedStructure

The linked structure is the whole-document semantic layer.

It resolves or records relations such as:

```text
section contains paragraph
caption belongs to figure or table
footnote marker links to footnote body
reference mention links to bibliography item
equation sequence
figure sequence
table sequence
page number sequence
table of contents entry points to section
headers and footers repeat across pages
```

This layer is where the document becomes more than a list of extracted blocks.

### Docling export

The Docling export layer projects the linked semantic structure into a Docling-compatible JSON document.

It preserves:

```text
text items
groups
tables
pictures
pages
provenance
conflicts
relation metadata
warnings
pdf2md-specific audit metadata
```

---

## 9. Backends

Backends are isolated and interchangeable.

Each backend is expected to produce normalised extraction artefacts through a connector. Backend execution is separated from the central pipeline so that different tools, models, environments, and hardware requirements can coexist.

Typical backend categories include:

```text
OCR/layout backends
embedded-text PDF extraction
geometry/media extraction
tagged-PDF extraction
LaTeX/XML-derived ground-truth extraction
```

The central pipeline should not depend on one backend being correct. It should use backend agreement, calibrated priors, document structure, and ground-truth evaluation to decide confidence.

---

## 10. Current repository direction

The repository is organised around staged contracts and validation tools.

Important surfaces include:

```text
src/pdf2md/models/
  IR, entity, prior, linked, and export contracts

src/pdf2md/connectors/
  backend output normalisation

src/pdf2md/calibration/
  backend prior calibration

src/pdf2md/consensus/
  page-level candidate grouping and scoring

src/pdf2md/linking/
  whole-document semantic linking

src/pdf2md/export/
  Docling, RAG, and Markdown export layers

tools/
  command-line tools for calibration, consensus, linking, export,
  local preflight, and ground-truth validation

groundtruth/corpus/latex/
  LaTeX-derived ground-truth documents and artefacts
```

The project is currently in a late-prototype / early-alpha stage. The core contracts and staged architecture are in place. The main remaining work is local end-to-end validation across real documents and real backend outputs.

---

## 11. Local acceptance programme

The local acceptance programme validates the system progressively. The durable sequence is defined in `ROADMAP.md`; individual executable plans must follow `PLAN_TEMPLATE.md` and be promoted through `current_plan.md` only after human verification.

Current MVP path:

```text
Plan 8  - local ground-truth corpus validation plus documentation consistency
Plan 9  - real backend smoke readiness
Plan 10 - connector implementation and PageExtractionIR validation
Plan 11 - EntityProposalDocument validation
Plan 12 - real calibration prior generation
Plan 13 - weighted ConsensusIR on real outputs
Plan 14 - LinkedStructure and cross-page semantic linking
Plan 15 - Docling export validation
Plan 16 - end-to-end runner and MVP corpus evaluation
Plan 17+ - production readiness after MVP
```

This sequence exists to avoid confusing environment problems with repository defects and to keep every implementation milestone human-verifiable.

Missing tools such as `lualatex`, `latexml`, backend conda environments, CUDA, or model weights are reported as environment-not-ready conditions, not as unit-test failures.

---

## 12. Typical development flow

Install the central package in the main repository environment:

```bash
python -m pip install -e .
```

Run the local environment preflight:

```bash
python tools/local_groundtruth_preflight.py \
  --repo-root . \
  --out-dir groundtruth/runs/local_preflight \
  --required-backends mineru,paddleocr,deepseek \
  --verbose
```

Validate the local ground-truth corpus:

```bash
python tools/local_groundtruth_validate.py \
  --corpus-root groundtruth/corpus/latex \
  --out-dir groundtruth/runs/local_groundtruth_validation \
  --verbose
```

Run staged pipeline tools as appropriate:

```bash
python tools/calibrate_priors.py --help
python tools/build_consensus.py --help
python tools/build_linked_structure.py --help
python tools/export_linked_docling.py --help
```

Backend model execution should happen inside each backend-specific environment, not inside the main `pdf2md` environment.

---

## 13. Design principles

### Complete document, not loose pages

The system assumes the input is a complete sequential document. Page order, section progression, references, captions, and structural repetition are all useful evidence.

### Evidence, not single-backend truth

No backend is assumed to be authoritative. The system records agreement, disagreement, confidence, and provenance.

### Ground truth grows over time

The LaTeX-derived ground-truth corpus is expected to expand. Each new fixture increases the ability to test and calibrate the system.

### Robustness comes from calibrated agreement

The system should become more accurate as it observes more successes and failures against ground truth. Backend confidence should be feature-specific, not global.

### Conflicts are first-class

A conflict should not disappear silently. If a relation, block, table, equation, or reference cannot be resolved safely, the unresolved state is recorded.

### Docling is the canonical export target

Markdown and RAG outputs are useful, but Docling is the main structured representation.

---

## 14. Repository governance for agents

Coding agents should follow the repository plan protocol.

The durable project architecture is described in `project.md`.

The durable implementation roadmap is described in `ROADMAP.md`.

Future executable plans should follow `PLAN_TEMPLATE.md`.

The current implementation task, whitelist, and required tests are described in `current_plan.md`.

The completed milestone record is maintained in `history.md`.

Agent work should not modify files outside the active plan whitelist.

---

## 15. Status

The project has implemented substantial parts of the multi-pipeline architecture:

```text
backend connector contracts
PageExtractionIR and ConsensusIR contracts
entity proposal contracts
calibration prior contracts
page-level consensus
whole-document linked structure
Docling / RAG / Markdown export layer
LaTeX-derived ground-truth generation and validation tooling
local environment preflight tooling
```

The next major milestones are:

```text
validate the ground-truth corpus locally
run real backend smoke checks
normalise real backend outputs into PageExtractionIR and EntityProposalDocument
run real calibration prior generation
validate weighted consensus, semantic linking and Docling export
run full local end-to-end corpus evaluation
calibrate backend confidence from observed success and failure
```

Concrete TODOs queued for future plans (not yet drafted):

```text
- consensus-calibration-and-real-example workflow
    Resolved by the docs-as-manual reorganisation:
    see docs/tutorials/03-calibrate-priors-on-corpus.md (calibration
    against the LaTeX corpus) and docs/tutorials/02-first-conversion.md +
    docs/tutorials/04-batch-processing.md (using the runner on real
    PDFs with calibrated priors).

- docling-strict-validation hardening (Plan 17 A8 follow-up)
    Strip pdf2md-only extras from docling pictures/tables, uppercase
    prov.bbox.coord_origin (TOPLEFT/BOTTOMLEFT), and emit the
    required prov.charspan field on every prov entry. Closes the two
    xfailed TestDoclingCoreStrictValidation cases.
```

---

## 16. Licence and contribution policy

This repository is distributed under the licence declared in `LICENSE`.

Contribution rules are described in `CONTRIBUTING.md` and `CLA.md`.
