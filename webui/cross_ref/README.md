# pdf2md semantic graph viewer

Static, build-step-free viewer for a `CrossReferenceGraph` exported by
[tools/export_cross_ref_graph.py](../../tools/export_cross_ref_graph.py).

The page loads [D3 v7](https://cdn.jsdelivr.net/npm/d3@7) from a CDN at
runtime — there is no `package.json`, no React, no Vite. The page can
be served by any static file server (or opened directly with `file://`
when using the CLI's `--inline-viewer` mode).

## Quick start

```bash
# 1. Generate a cross_references.json (Plan 006_0 CLI).
conda run -n pdf2md python tools/build_cross_references.py \
    --backend regex \
    --text tests/data/semantic_fixtures/sample_text.txt \
    --out-dir /tmp/xref

# 2. Export to D3 JSON + a self-contained viewer.html.
conda run -n pdf2md python tools/export_cross_ref_graph.py \
    --xref /tmp/xref/cross_references.json \
    --output /tmp/xref/graph.json \
    --inline-viewer /tmp/xref/viewer.html

# 3a. Open the self-contained viewer with file://
xdg-open /tmp/xref/viewer.html

# 3b. OR: serve this directory with graph.json next to index.html.
cp /tmp/xref/graph.json webui/cross_ref/graph.json
python -m http.server -d webui/cross_ref 8080
# Then visit http://localhost:8080/
```

## File layout

```text
webui/cross_ref/
├── index.html          # Page shell + file picker + D3 CDN <script>
├── viewer.js           # Force-directed layout + autoload of graph.json
├── style.css           # Minimal styling
└── README.md           # this file
```

## Schema

`graph.json` follows the schema produced by
`pdf2md.semantic.graph_export.export_graph()`:

```json
{
  "schema_version": "1.0.0",
  "document_id": "sample",
  "nodes": [
    {"id": "marker:0:#/document:Figure 3",
     "type": "figure",
     "label": "Figure 3",
     "source_ref": "#/document",
     "char_offset": [12, 20],
     "backend": "regex"},
    {"id": "_unresolved", "type": "unresolved", "label": "(unresolved)"}
  ],
  "edges": [
    {"source": "marker:0:#/document:Figure 3",
     "target": "_unresolved",
     "marker_type": "figure",
     "label": "Figure 3",
     "resolved": false}
  ],
  "metadata": {
    "doc_hash": "sha256:...",
    "total_markers": 18,
    "resolved_count": 0,
    "unresolved_count": 18,
    "backend_versions": {"regex": "0.1.0"}
  }
}
```

## Visual encoding

- **Node colour** — categorical by `type` (Tableau10 scheme).
- **Node radius** — slightly larger for the synthetic `_unresolved`
  sink so it stands out.
- **Edge style** — solid grey for resolved edges, dashed red for
  unresolved ones.
- **Hover** — the SVG `<title>` carries `<type>: <label>` for native
  tooltips.

Plan 008_1 adds a PDF.js page-overlay companion view; Plan 008_2 adds
an evaluation dashboard.
