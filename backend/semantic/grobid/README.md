# GROBID semantic backend

GROBID ([github.com/kermitt2/grobid](https://github.com/kermitt2/grobid))
is a machine-learning service for scholarly document analysis. Plan 005
uses GROBID's `processFulltextDocument` endpoint to obtain TEI XML and
extract bibliography entries and cross-reference markers.

Out of the three semantic backends, GROBID is the strongest on
scholarly articles (numbered or author-year citations, biblio
resolution) and the weakest on non-article PDFs (textbooks, theses
where layout dominates).

## Install

GROBID runs as a Docker container. No conda env is required — only
`requests`, already present in the main `pdf2md` env.

```bash
docker pull grobid/grobid:0.8.1
docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.1
```

GROBID needs ~30 s to warm up after `docker run`. Confirm:

```bash
curl -s http://localhost:8070/api/isalive   # → "true"
```

If you already use port 8070 for something else, remap with
`-p <host_port>:8070` and pass `--port <host_port>` to the smoke
test.

To stop and remove the container:

```bash
docker stop grobid && docker rm grobid
```

The `grobid/grobid:0.8.1` image is ~4 GB on first pull. CPU-only;
no GPU required.

## Run the smoke test

```bash
conda activate pdf2md

python backend/semantic/grobid/smoke_test.py \
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
    raise SystemExit("GROBID not running")

tei_xml = grobid_client.process_fulltext_document(
    pdf_path=Path("paper.pdf"), endpoint=endpoint
)
parsed = tei_parser.parse_tei(tei_xml)
for m in parsed.markers:
    print(m.marker_type, m.marker_text, m.target)
```

Plan 006 will wrap this in the `SemanticBackend` interface under
`src/pdf2md/semantic/grobid_adapter.py`. Until then, do not import
this module from `src/pdf2md/`.

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
