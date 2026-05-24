# Plan 005: Semantic Backends — Installation & Smoke Tests

## Status: DRAFT
## Date: 2026-05-24
## Depends on: Plan 004 (project docs aligned)

---

## 1. Goal

Install three semantic backends (GROBID, DeepSeek-VL2, regex/heuristic) following
the same isolation pattern as extraction backends. Verify each runs independently.
No integration with the pipeline, no label changes, no routing logic.

## 2. Backends

### 2.1 GROBID

- **Deployment**: Docker container (`grobid/grobid:0.8.1` or latest)
- **Env**: No conda env needed (service over HTTP)
- **Adapter**: Python client using `grobid-client-python` (pip, pure Python)
- **Smoke test**: Send a sample PDF → receive TEI XML → parse at least one
  `<ref type="biblio">` and one `<ref type="figure">` from response

```bash
# Pull and run
docker pull grobid/grobid:0.8.1
docker run -d --name grobid -p 5070:5070 grobid/grobid:0.8.1

# Smoke test
python backend/semantic/grobid/smoke_test.py --pdf tests/data/sample_article.pdf
```

Expected output: `grobid_smoke_result.json` with extracted refs count > 0.

### 2.2 DeepSeek-VL2

- **Deployment**: Local GPU, isolated conda env `pdf2md-deepseek-vl2`
- **Model**: `deepseek-ai/deepseek-vl2-small` (2.8B active, fits single GPU)
- **Adapter**: Python script loading model, sending page image + prompt, parsing JSON
- **Smoke test**: Send one page image → receive structured JSON with ≥1 detected
  reference marker

```bash
conda create -n pdf2md-deepseek-vl2 python=3.11
conda activate pdf2md-deepseek-vl2
pip install torch torchvision transformers accelerate pillow

python backend/semantic/deepseek_vl2/smoke_test.py --image tests/data/sample_page.png
```

Expected output: `vlm_smoke_result.json` with detected markers list.

### 2.3 Regex/heuristic

- **Deployment**: No env needed (stdlib + re)
- **Adapter**: Python module with pattern matchers
- **Smoke test**: Feed sample extracted text → detect figure/table/equation refs

```bash
python backend/semantic/regex/smoke_test.py --text tests/data/sample_text.txt
```

Expected output: `regex_smoke_result.json` with detected patterns.

## 3. File structure

```
backend/semantic/
├── grobid/
│   ├── README.md              # Install instructions, Docker commands
│   ├── smoke_test.py          # Standalone test script
│   ├── grobid_client.py       # Thin wrapper around grobid-client-python
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

Output: `semantic_result.json` in output_dir.

## 5. Acceptance criteria

- [ ] GROBID Docker container starts, accepts PDF, returns TEI with refs
- [ ] DeepSeek-VL2 loads in isolated conda env, processes one page, returns JSON
- [ ] Regex backend detects ≥3 pattern types from sample text
- [ ] Each backend has a README with install instructions
- [ ] Each smoke test is runnable independently without pipeline code
- [ ] No imports from `src/pdf2md/` — these are standalone at this stage
