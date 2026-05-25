# GROBID semantic backend

GROBID ([github.com/kermitt2/grobid](https://github.com/kermitt2/grobid))
is a machine-learning service for scholarly document analysis. Plan 005
uses GROBID's `processFulltextDocument` endpoint to obtain TEI XML and
extract bibliography entries and cross-reference markers.

Out of the three semantic backends, GROBID is the strongest on
scholarly articles (numbered or author-year citations, bibliography
resolution) and the weakest on non-article PDFs (textbooks, theses
where layout dominates).

## Install

GROBID is a Java service. The install kit mirrors the OCR
extraction backends (`backend/paddleocr/`, `backend/mineru/`,
`backend/deepseek/`, `backend/glm/`):

```text
backend/semantic/grobid/
├── environment.yml      # minimal conda spec (python + openjdk=17 + wget + unzip)
├── requirements.txt     # empty — GROBID is Java, no pip deps
├── setup_env.py         # bootstrap (env create only)
├── setup.py             # main installer (env + tarball + gradle build + launchers + verify)
└── delete_env.py        # teardown
```

One-shot install (recommended):

```bash
python backend/semantic/grobid/setup.py
```

This:

1. Runs preflight checks (RAM ≥4 GB, free disk ≥4 GB, port 8070 free).
2. Creates the `pdf2md-grobid` conda env from `environment.yml`
   (Python 3.11 + OpenJDK 17 + wget + unzip).
3. Downloads `grobid-<version>.zip` into `${CONDA_PREFIX}/share/`.
4. Runs `./gradlew clean install --no-daemon` (slow on first run —
   10–20 min, ~3 GB peak in Gradle cache).
5. Writes `${CONDA_PREFIX}/bin/start_grobid` and
   `${CONDA_PREFIX}/bin/stop_grobid` launchers.
6. Background-starts the service, polls `/api/isalive` until it
   answers `true`, then stops cleanly (use `--keep-running` to leave
   it up after install).

Step-by-step if you'd rather:

```bash
python backend/semantic/grobid/setup_env.py --manager conda
python backend/semantic/grobid/setup.py --skip-env-create
```

Useful flags (full list with `python backend/semantic/grobid/setup.py --help`):

| Flag | Meaning |
|---|---|
| `--manager {conda,venv}` | venv mode requires system OpenJDK ≥17 on `$PATH`. |
| `--env-name NAME`        | Override the default `pdf2md-grobid`. |
| `--grobid-version VER`   | Pin a specific GROBID release (default `0.8.1`). |
| `--port N`               | Override the GROBID port (default `8070`). |
| `--skip-env-create`      | Assume the conda env already exists. |
| `--skip-build`           | Assume `${CONDA_PREFIX}/share/grobid-<ver>/` is already built. |
| `--skip-checks`          | Skip preflight checks. |
| `--skip-verify`          | Skip the `/api/isalive` poll. |
| `--keep-running`         | Leave GROBID running after verify. |
| `--check-only`           | Run preflight only and exit 0. |
| `--force-redownload`     | Re-download the GROBID tarball. |

Teardown:

```bash
python backend/semantic/grobid/delete_env.py
```

(This removes the conda env and the GROBID tree inside it.)

## Run the smoke test

After the env is installed, start GROBID and run the smoke test from
the main `pdf2md` env (the HTTP client uses `requests`, which lives
in the main env, not in `pdf2md-grobid`):

```bash
conda activate pdf2md-grobid
start_grobid &
# Wait ~30 s for the JVM warm-up after the first /api/isalive=true.
curl -s http://localhost:8070/api/isalive   # → "true"

conda run -n pdf2md python backend/semantic/grobid/smoke_test.py \
    --pdf tests/data/<your_sample_article>.pdf \
    --out-dir /tmp/grobid_smoke
```

Expected output line:

```text
grobid smoke: <N> markers, <M> bib entries, <K> ms, out=/tmp/grobid_smoke/grobid_smoke_result.json
```

Plan 005 H1 requires `N ≥ 1` and at least one marker with
`marker_type == "bibliography"`.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | success — markers found, ≥1 bibliography marker |
| 1 | repository defect — markers empty or no bibliography marker |
| 2 | bad argument — PDF not found |
| 3 | `env_not_ready` — GROBID service not reachable |

## Output shape

`grobid_smoke_result.json`:

```jsonc
{
  "backend": "grobid",
  "backend_version": "0.8.x",
  "input_path": "tests/data/sample_article.pdf",
  "input_bytes": 134567,
  "endpoint": "http://localhost:8070",
  "elapsed_ms": 1820.0,
  "markers": [
    {"marker_type": "bibliography", "marker_text": "[3]", "target": "#b2"},
    {"marker_type": "figure", "marker_text": "Figure 1", "target": "#fig_0"}
  ],
  "bib_entries": [
    {"ref_id": "b0", "raw_text": "Smith, J. ... 2020 ..."}
  ],
  "counts_by_type": {"bibliography": 18, "figure": 4, "table": 2, "_bib_entries": 22},
  "warnings": []
}
```

## Library use

```python
from backend.semantic.grobid import grobid_client, tei_parser

endpoint = grobid_client.GrobidEndpoint()  # localhost:8070
if not grobid_client.is_alive(endpoint):
    raise SystemExit("GROBID not running — start with: start_grobid &")

tei_xml = grobid_client.process_fulltext_document(
    pdf_path=Path("paper.pdf"), endpoint=endpoint
)
parsed = tei_parser.parse_tei(tei_xml)
for m in parsed.markers:
    print(m.marker_type, m.marker_text, m.target)
```

Plan 006's in-tree adapter wraps this under
`src/pdf2md/semantic/grobid_adapter.py` — it gates on
`grobid_client.is_alive(endpoint)` and returns an empty
`CrossReferenceGraph` (with the `env_not_ready` semantics) when the
service is down.

## Limitations

- GROBID's quality drops sharply outside English-language scholarly
  articles. Tuned for the conference-paper / journal-article shape.
- `processFulltextDocument` is the slowest of GROBID's endpoints
  (~1-3 s per page on CPU). Plan 006's ensemble mode may use the
  faster `processReferences` endpoint when only bibliography is
  needed.
- The TEI parser here is narrow: it does not resolve targets to
  DoclingDocument items — that is Plan 006 resolver territory.
- No retries on HTTP failure. If GROBID restarts mid-PDF, you get an
  `env_not_ready` exit and need to rerun.
- First Gradle build is slow (10–20 min). Subsequent restarts are
  fast (~30 s warm-up).
