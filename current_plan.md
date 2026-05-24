# Plan 005_0: Semantic Backends — Installation and Smoke Tests

## Status: active
## Date: 2026-05-24
## Depends on: Plan 004_0 (human_verified, archived as M19)

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

Branch name:
plan-005-0-semantic-backends

Source plan:
plans/005_0-semantic-backends-installation-smoke-tests.md

---

## 1. Goal

Install three semantic backends (GROBID, DeepSeek-VL2, regex/heuristic) following
the same isolation pattern as extraction backends under `backend/<name>/`. Verify
each runs independently. No integration with the `pdf2md` pipeline, no label
changes, no routing logic, no imports from `src/pdf2md/`.

## 2. Backends

### 2.1 GROBID

- **Deployment**: Docker container (`grobid/grobid:0.8.1` or latest)
- **Env**: No conda env needed (service over HTTP)
- **Adapter**: Python client (plain `requests`, no extra package required)
- **Smoke test**: Send a sample PDF → receive TEI XML → parse at least one
  `<ref type="biblio">` and one `<ref type="figure">` from response

```bash
# Pull and run
docker pull grobid/grobid:0.8.1
docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.1

# Smoke test (from the main pdf2md env — only stdlib + requests needed)
python backend/semantic/grobid/smoke_test.py --pdf tests/data/sample_article.pdf
```

Expected output: `grobid_smoke_result.json` with extracted refs count > 0.

Note: GROBID's `processFulltextDocument` runs on port **8070** (the
default), not 5070 as in the source plan. Local default kept at 8070.

### 2.2 DeepSeek-VL2

- **Deployment**: Local GPU, isolated conda env `pdf2md-deepseek-vl2`
- **Model**: `deepseek-ai/deepseek-vl2-small` (2.8B active, fits single GPU)
- **Adapter**: Python script loading model, sending page image + prompt, parsing JSON
- **Smoke test**: Send one page image → receive structured JSON with ≥1 detected
  reference marker

```bash
conda env create -f backend/semantic/deepseek_vl2/env.yaml
conda activate pdf2md-deepseek-vl2

python backend/semantic/deepseek_vl2/smoke_test.py --image tests/data/sample_page.png
```

Expected output: `vlm_smoke_result.json` with detected markers list.

### 2.3 Regex/heuristic

- **Deployment**: No env needed (stdlib + `re`)
- **Adapter**: Python module with pattern matchers
- **Smoke test**: Feed sample extracted text → detect figure/table/equation refs

```bash
python backend/semantic/regex/smoke_test.py --text tests/data/sample_text.txt
```

Expected output: `regex_smoke_result.json` with detected patterns.

## 3. File structure

```text
backend/semantic/
├── grobid/
│   ├── README.md              # Install instructions, Docker commands
│   ├── smoke_test.py          # Standalone test script
│   ├── grobid_client.py       # Thin HTTP wrapper around the GROBID service
│   └── tei_parser.py          # TEI XML → list of refs/entities
├── deepseek_vl2/
│   ├── README.md              # Conda env setup, model download
│   ├── smoke_test.py          # Standalone test script
│   ├── env.yaml               # Conda environment spec
│   ├── vlm_client.py          # Model loading + inference
│   └── prompt_templates.py    # Structured output prompts
└── regex/
    ├── README.md
    ├── smoke_test.py
    └── patterns.py            # Pattern definitions + matchers
```

## 4. Runner contract (same pattern as extraction backends)

Each semantic backend adapter exposes:

```python
def extract_semantics(
    pdf_path: Path,           # Or page image path for VLM
    text_items: list[dict],   # Already-extracted text with positions (optional)
    output_dir: Path,
) -> dict:
    """Returns dict with: markers, entities, backend_version, timing."""
```

Output: `semantic_result.json` in `output_dir`.

## 5. Acceptance criteria

- [ ] GROBID Docker container starts, accepts PDF, returns TEI with refs
      (human-verified H1: requires Docker daemon + network to pull image)
- [ ] DeepSeek-VL2 loads in isolated conda env, processes one page, returns JSON
      (human-verified H2: requires GPU + conda env creation + model download)
- [x] Regex backend detects ≥3 pattern types from sample text
      (automated H3: 18 markers / 12 distinct types observed on the
       sample_text.txt fixture in the main pdf2md env, exit 0)
- [x] Each backend has a README with install instructions
- [x] Each smoke test is runnable independently without pipeline code
- [x] No imports from `src/pdf2md/` — these are standalone at this stage
      (verified: ``grep -r 'import pdf2md\|from pdf2md' backend/semantic/``
       returns nothing)

---

## File whitelist

```text
backend/semantic/grobid/README.md
backend/semantic/grobid/grobid_client.py
backend/semantic/grobid/tei_parser.py
backend/semantic/grobid/smoke_test.py
backend/semantic/deepseek_vl2/README.md
backend/semantic/deepseek_vl2/env.yaml
backend/semantic/deepseek_vl2/vlm_client.py
backend/semantic/deepseek_vl2/prompt_templates.py
backend/semantic/deepseek_vl2/smoke_test.py
backend/semantic/regex/README.md
backend/semantic/regex/patterns.py
backend/semantic/regex/smoke_test.py
tests/data/semantic_fixtures/sample_text.txt
current_plan.md
run_log.md
```

## Forbidden files

```text
src/**/*.py
backend/{paddleocr,mineru,deepseek,glm}/**/*
tools/**/*
docs/**/*
project.md
ROADMAP.md
README.md
history.md
PLAN_TEMPLATE.md
agent.md
```

## Allowed dependencies

Python packages that may be imported by the new files:

```text
re                  (stdlib)
json                (stdlib)
pathlib             (stdlib)
argparse            (stdlib)
sys                 (stdlib)
time                (stdlib)
requests            (already in the pdf2md env, transitively via docling)
```

Heavier dependencies (`torch`, `transformers`, `accelerate`, `pillow`,
`grobid-client-python`) live ONLY inside the per-backend conda envs and
ONLY as conda-managed installs declared in `backend/semantic/<name>/env.yaml`
or in the per-backend README. They are NOT installed in the main `pdf2md`
env by this plan.

## Allowed environment-modifying commands

```text
none in agent mode

(Plan 005 deliberately ships the install scripts and configuration but
does not execute Docker pulls or conda env creations from the agent.
Those installations are part of the human verification step — H1 and H2
in §6 below — because they require a Docker daemon, network access, and
optionally a GPU.)
```

## 6. Human verification checkpoints

### Checkpoint H1 — GROBID Docker smoke

Required environment: Docker daemon, network access.

Preconditions:

```bash
# From a sandbox with Docker installed:
docker pull grobid/grobid:0.8.1
docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.1
# Wait ~30s for the service to come up
curl -s http://localhost:8070/api/isalive   # → "true"
```

Command:

```bash
conda run -n pdf2md python backend/semantic/grobid/smoke_test.py \
    --pdf tests/data/<a_sample_article>.pdf \
    --out-dir /tmp/grobid_smoke
```

Pass criteria:

```text
exit code 0
/tmp/grobid_smoke/grobid_smoke_result.json exists
result.markers has length > 0
result.markers contains at least one entry with marker_type="bibliography"
```

### Checkpoint H2 — DeepSeek-VL2 GPU smoke

Required environment: NVIDIA GPU, CUDA-capable host, conda.

Preconditions:

```bash
conda env create -f backend/semantic/deepseek_vl2/env.yaml
# Model download happens on first run via Hugging Face
```

Command:

```bash
conda run -n pdf2md-deepseek-vl2 python backend/semantic/deepseek_vl2/smoke_test.py \
    --image tests/data/<a_sample_page>.png \
    --out-dir /tmp/vlm_smoke
```

Pass criteria:

```text
exit code 0
/tmp/vlm_smoke/vlm_smoke_result.json exists
result.markers has length >= 1
result.backend_version contains the model id
```

### Checkpoint H3 — Regex smoke (also runnable as automated)

Required environment: main pdf2md env (or any Python ≥3.10).

Command:

```bash
conda run -n pdf2md python backend/semantic/regex/smoke_test.py \
    --text tests/data/semantic_fixtures/sample_text.txt \
    --out-dir /tmp/regex_smoke
```

Pass criteria:

```text
exit code 0
/tmp/regex_smoke/regex_smoke_result.json exists
result.markers contains ≥3 distinct marker_type values
```

---

## PR_reviews

(none yet)

## Feedback

(none yet)
