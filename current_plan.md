# Plan 008_0: Semantic CrossReferenceGraph Viewer & D3 Export

## Status: active
## Date: 2026-05-24
## Depends on: Plan 007_0 (human_verified, archived as M22)

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
plan-008-0-semantic-viewer

Source plan:
plans/008_0-visualization-web-integration.md

---

## 1. Goal

Make the semantic layer's `CrossReferenceGraph` visualisable. Ship:

1. A **graph exporter** that converts a `CrossReferenceGraph` (with
   optional structural context from a `LinkedStructure` JSON) into a
   D3-compatible node/link JSON format.
2. A **standalone CLI** `tools/export_cross_ref_graph.py` that consumes
   one or more `cross_references.json` files and writes the D3 JSON to
   disk.
3. A **static HTML viewer** under `webui/cross_ref/` that loads a D3
   force-directed layout from the exported JSON. No build step — pure
   HTML + JS + D3 from CDN — so it can be served by any static file
   server (or opened directly via `file://`).

Scope reductions vs. the source plan:

- PDF.js page-overlay view (source §2.2) → **deferred to Plan 008_1**.
- Evaluation dashboard (source §2.3) → **deferred to Plan 008_2**;
  the Plan 007_0 `results.csv` is already inspectable in any spreadsheet.
- Integrated `pdf2md` CLI subcommand (source §4.3) → **deferred to
  Plan 006_1** (which already owns the public CLI surface).
- Integration with the existing React/Vite `webui/validator/` workspace
  → **deferred to Plan 008_3**; this plan ships a separate vanilla-HTML
  page under `webui/cross_ref/` to avoid coupling agent-mode work to
  Node toolchain availability.

## 2. Graph export module

`src/pdf2md/semantic/graph_export.py`:

```python
@dataclass(frozen=True)
class GraphExport:
    nodes: list[dict[str, object]]
    edges: list[dict[str, object]]
    metadata: dict[str, object]

def export_graph(
    xref: CrossReferenceGraph,
    *,
    document_id: str | None = None,
    extra_nodes: list[SemanticEntity] | None = None,
) -> GraphExport:
    """Convert a CrossReferenceGraph into a D3-compatible payload.

    Nodes come from:
      - The unique union of every marker.source_ref          (type="marker_source")
      - Every distinct target_ref on resolved edges          (type="target")
      - Every SemanticEntity in xref.entities ∪ extra_nodes  (type=<entity_type>)

    Edges come from xref.edges; resolved edges link source_ref → target_ref,
    unresolved edges link source_ref → a synthetic "unresolved" sink so
    the viewer can highlight them.
    """
```

Output schema:

```json
{
  "schema_version": "1.0.0",
  "document_id": "linked_sections_figures",
  "nodes": [
    {"id": "#/texts/0",       "type": "marker_source", "label": "#/texts/0"},
    {"id": "#fig:box-diagram","type": "figure",        "label": "fig:box-diagram"},
    {"id": "_unresolved",     "type": "unresolved",    "label": "(unresolved)"}
  ],
  "edges": [
    {"source": "#/texts/0", "target": "#fig:box-diagram",
     "marker_type": "figure", "label": "Figure 1", "resolved": true},
    {"source": "#/texts/3", "target": "_unresolved",
     "marker_type": "figure", "label": "Figure 99", "resolved": false}
  ],
  "metadata": {
    "doc_hash": "sha256:...",
    "total_markers": 4,
    "resolved_count": 3,
    "unresolved_count": 1,
    "backend_versions": {"regex": "0.1.0"}
  }
}
```

## 3. CLI

`tools/export_cross_ref_graph.py`:

```
python tools/export_cross_ref_graph.py \
    --xref out/cross_references.json \
    --output out/graph.json \
    [--document-id <slug>] \
    [--inline-viewer out/viewer.html]
```

- Reads one `cross_references.json` (Plan 006 schema).
- Writes the D3 JSON to `--output`.
- With `--inline-viewer`, also writes a self-contained HTML file with
  the D3 payload inlined into a `<script>` tag — opens directly with
  `file://`, no static-server needed.

Exit codes: 0 success, 2 bad input.

## 4. Static viewer

`webui/cross_ref/`:

- `index.html` — minimal page with a `#chart` SVG container, a file
  input that loads `graph.json` (or `graph_inline.json` adjacent to the
  HTML), and D3 v7 from `https://cdn.jsdelivr.net/npm/d3@7`.
- `viewer.js` — force-directed layout, colored nodes by `type`,
  dashed-red edges for `resolved=false`, hover tooltip with the marker
  label, basic legend.
- `style.css` — minimal styling.
- `README.md` — how to run the viewer (open `index.html`, point at
  `graph.json` or use a CLI-generated inline viewer).

Hard rule: no `package.json`, no Vite, no React. Pure HTML/JS so the
agent-mode whitelist does not need Node tooling.

## 5. File whitelist

```text
src/pdf2md/semantic/graph_export.py
src/pdf2md/semantic/__init__.py
tools/export_cross_ref_graph.py
webui/cross_ref/index.html
webui/cross_ref/viewer.js
webui/cross_ref/style.css
webui/cross_ref/README.md
tests/test_graph_export.py
tests/test_export_cross_ref_graph_cli.py
current_plan.md
run_log.md
```

## Forbidden files

```text
src/pdf2md/semantic/base.py
src/pdf2md/semantic/regex_adapter.py
src/pdf2md/semantic/grobid_adapter.py
src/pdf2md/semantic/vlm_adapter.py
src/pdf2md/semantic/resolver.py
src/pdf2md/semantic/ensemble.py
src/pdf2md/semantic/groundtruth.py
src/pdf2md/semantic/evaluation.py
src/pdf2md/models/**/*
src/pdf2md/pipeline/**/*
src/pdf2md/cli/**/*
src/pdf2md/connectors/**/*
src/pdf2md/calibration/**/*
src/pdf2md/consensus/**/*
src/pdf2md/linking/**/*
src/pdf2md/export/**/*
backend/**/*
webui/validator/**/*
webui/shared/**/*
webui/scripts/**/*
webui/package.json
webui/package-lock.json
project.md
ROADMAP.md
README.md
history.md
PLAN_TEMPLATE.md
agent.md
plans/**/*
docs/**/*
groundtruth/**/*
```

## Allowed dependencies

Python packages used by the new files:

```text
pydantic, dataclasses    (already required)
json, argparse, sys      (stdlib)
pathlib                  (stdlib)
pytest                   (already required)
```

JS dependencies for the static viewer are loaded from a CDN at runtime
(`d3@7`). No npm install commands are run in agent mode.

## Allowed environment-modifying commands

```text
none in agent mode
```

## 6. Acceptance criteria

- [ ] `export_graph(xref)` returns a `GraphExport` with at least one
      node per unique `source_ref` and one edge per `RefEdge` (A1).
- [ ] Resolved edges in the exported payload have `resolved=true` and
      the expected `target` id; unresolved edges link to the synthetic
      `_unresolved` sink (A2).
- [ ] `tools/export_cross_ref_graph.py --xref ... --output ...` exits
      0 and writes a JSON file with the documented top-level keys
      (`schema_version`, `document_id`, `nodes`, `edges`, `metadata`)
      (A3).
- [ ] `--inline-viewer <path>.html` writes an HTML file that contains
      the D3 payload inlined under a `<script id="graph-data">` tag
      AND references the D3 v7 CDN URL (A4).
- [ ] `webui/cross_ref/index.html` parses (HTML syntactically valid)
      and references both the local `viewer.js` and the D3 CDN (A5,
      done as a simple text check — no headless browser required).
- [ ] Full regression: `pytest tests/ -q --ignore=tests/_legacy_temp -x`
      stays green at 989+ passed (A6).

---

## 7. Human verification checkpoints

### Checkpoint H1 — Export + open viewer

```bash
# 1. Generate a CrossReferenceGraph (existing Plan 006 CLI).
conda run -n pdf2md python tools/build_cross_references.py \
    --backend regex \
    --text tests/data/semantic_fixtures/sample_text.txt \
    --out-dir /tmp/h1_export

# 2. Convert to D3 JSON + inline viewer.
conda run -n pdf2md python tools/export_cross_ref_graph.py \
    --xref /tmp/h1_export/cross_references.json \
    --output /tmp/h1_export/graph.json \
    --inline-viewer /tmp/h1_export/viewer.html

# 3. Open in a browser.
xdg-open /tmp/h1_export/viewer.html
```

Pass criteria:

```text
exit codes 0 on both commands
/tmp/h1_export/graph.json contains nodes[] and edges[]
/tmp/h1_export/viewer.html opens and renders a force-directed graph
```

(The browser step is human-verified — the agent does not run a browser.)

---

## PR_reviews

(none yet)

## Feedback

(none yet)
