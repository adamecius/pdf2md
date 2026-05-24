# Plan 008: Visualization & Web Integration

## Status: DRAFT
## Date: 2026-05-24
## Depends on: Plan 007 (GT and evaluation working)

---

## 1. Goal

Build visualization tools for the CrossReferenceGraph and integrate them into
a web interface alongside the existing Docling structural visualization.
This is a **user-facing deliverable**, not just internal tooling.

## 2. Visualization components

### 2.1 Document graph (primary deliverable)

Interactive graph where:
- **Nodes** = document elements (figures, tables, equations, theorems, sections,
  bibliography entries, footnotes) — colored by type
- **Edges** = cross-references (ref markers → targets) — styled by type
- **Pages** = optional grouping/clustering by page number
- **Cross-page edges** are visually distinct (the whole point)

Technology: D3.js force-directed graph or Cytoscape.js

```
CrossReferenceGraph → graph_export.json → D3/Cytoscape visualization
```

### 2.2 Page overlay (companion view)

Per-page visualization showing:
- Bounding boxes from DoclingDocument (via `get_visualization()` or custom)
- Reference markers highlighted with colored badges
- Lines connecting markers to their targets (same-page targets)
- Unresolved markers flagged in red

Technology: PDF.js + SVG overlay or matplotlib export

### 2.3 Evaluation dashboard

Comparison view for benchmark results:
- Backend × RefType heatmap (F1 scores)
- Per-document score cards
- Marker detection confusion matrix

Technology: Simple HTML + Chart.js or React component

## 3. Graph export format

```python
def export_graph(
    doc: DoclingDocument,
    xref: CrossReferenceGraph,
) -> dict:
    """Export D3-compatible JSON."""
    return {
        "nodes": [
            {
                "id": item.self_ref,
                "label": get_label(item),
                "type": get_type(item),     # "figure", "table", "theorem", ...
                "page": get_page(item),
                "bbox": get_bbox(item),      # For spatial layout option
            }
            for item in iterate_relevant_items(doc, xref)
        ],
        "edges": [
            {
                "source": edge.marker.source_ref,
                "target": edge.target_ref,
                "type": edge.marker.marker_type.value,
                "resolved": edge.resolved,
                "label": edge.marker.marker_text,
            }
            for edge in xref.edges
        ],
        "metadata": {
            "doc_hash": xref.doc_hash,
            "total_markers": len(xref.markers),
            "resolved_count": sum(1 for e in xref.edges if e.resolved),
            "unresolved_count": sum(1 for e in xref.edges if not e.resolved),
        }
    }
```

## 4. Web interface

### 4.1 Static site structure

```
web/
├── index.html                   # Landing page
├── viewer/
│   ├── graph.html               # Cross-reference graph viewer
│   ├── overlay.html             # Page overlay viewer
│   └── dashboard.html           # Evaluation dashboard
├── js/
│   ├── graph.js                 # D3/Cytoscape graph rendering
│   ├── overlay.js               # PDF.js + SVG overlay
│   └── dashboard.js             # Chart.js evaluation charts
├── css/
│   └── style.css
└── data/                        # Example outputs for demo
    ├── sample_docling.json
    ├── sample_cross_refs.json
    └── sample_eval.json
```

### 4.2 Integration with Docling visualization

Two complementary views accessible from the same interface:

1. **Structure view** (existing): DoclingDocument `get_visualization()` output —
   bounding boxes, reading order, element labels per page
2. **Semantic view** (new): CrossReferenceGraph as interactive graph —
   cross-page relationships, citation network, footnote associations

Toggle between views or show side-by-side.

### 4.3 CLI export

```bash
# Export graph JSON for external visualization
python -m pdf2md export-graph \
    --docling out/docling_document.json \
    --xref out/cross_references.json \
    --output out/graph.json

# Launch local web viewer
python -m pdf2md serve --port 8080 --data-dir out/
```

## 5. Interaction design

### Graph viewer
- Click node → show element details (text content, page, bbox)
- Click edge → show marker context (surrounding text)
- Filter by RefType (show only citation edges, only figure refs, etc.)
- Filter by page range
- Color unresolved edges in red
- Cluster nodes by page (spatial layout) or by type (semantic layout)
- sendPrompt-style: click node → "Show me all references to this figure"

### Page overlay
- Page navigation (prev/next)
- Toggle marker highlights on/off
- Hover marker → tooltip with target info
- Click marker → jump to target page

## 6. Acceptance criteria

- [ ] Graph export produces valid D3-compatible JSON from CrossReferenceGraph
- [ ] Interactive graph viewer renders nodes, edges, cross-page relationships
- [ ] Page overlay shows markers with bounding boxes on PDF pages
- [ ] Evaluation dashboard displays backend comparison heatmap
- [ ] Web interface serves locally via CLI command
- [ ] Demo works with example data from Plan 006
- [ ] Structure view (Docling) and semantic view (graph) accessible together
- [ ] Unresolved references visually flagged
