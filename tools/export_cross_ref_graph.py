"""Plan 008_0 export CLI: CrossReferenceGraph → D3 JSON.

Reads a ``cross_references.json`` produced by Plan 006 (the Plan 007_0
benchmark CLI writes the same format), converts it via
:func:`pdf2md.semantic.graph_export.export_graph`, and writes the D3
payload to ``--output``.

With ``--inline-viewer <path>.html`` the same payload is also written
into a self-contained HTML file whose ``<script id="graph-data">`` tag
holds the JSON inline, so the viewer can be opened with ``file://``
without serving the JSON over HTTP.

Exit codes:
    0 — success
    2 — bad input (missing file, malformed JSON, malformed schema)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.models import CrossReferenceGraph  # noqa: E402
from pdf2md.semantic.graph_export import export_graph  # noqa: E402


# Static viewer page bundled with this CLI. The placeholder
# ``__GRAPH_PAYLOAD__`` is replaced verbatim with the JSON payload so the
# generated HTML stays a single self-contained file that opens with
# ``file://``.
_INLINE_VIEWER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>pdf2md semantic graph (inline)</title>
  <style>
    body { font: 14px system-ui, sans-serif; margin: 0; padding: 0; }
    header { padding: 0.5rem 1rem; background: #f5f5f5; border-bottom: 1px solid #ddd; }
    #chart { width: 100vw; height: calc(100vh - 60px); }
    .node circle { stroke: #fff; stroke-width: 1.5px; }
    .link { stroke: #999; stroke-opacity: 0.6; }
    .link.unresolved { stroke: #c0392b; stroke-dasharray: 4 3; }
    .node text { font-size: 10px; pointer-events: none; }
  </style>
</head>
<body>
  <header>
    <strong>pdf2md semantic graph</strong>
    <span id="status"></span>
  </header>
  <svg id="chart"></svg>
  <script id="graph-data" type="application/json">__GRAPH_PAYLOAD__</script>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  <script>
    const data = JSON.parse(document.getElementById('graph-data').textContent);
    const status = document.getElementById('status');
    status.textContent = ` — ${data.nodes.length} nodes, ${data.edges.length} edges ` +
      `(resolved: ${data.metadata.resolved_count}, unresolved: ${data.metadata.unresolved_count})`;
    const svg = d3.select('#chart');
    const width = window.innerWidth, height = window.innerHeight - 60;
    svg.attr('viewBox', [0, 0, width, height]);
    const color = d3.scaleOrdinal(d3.schemeTableau10);

    const sim = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.edges).id(d => d.id).distance(60))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(width / 2, height / 2));

    const link = svg.append('g').selectAll('line').data(data.edges).join('line')
      .attr('class', d => 'link' + (d.resolved ? '' : ' unresolved'))
      .attr('stroke-width', 1.2);

    const node = svg.append('g').selectAll('g').data(data.nodes).join('g').attr('class', 'node');
    node.append('circle').attr('r', d => d.type === 'unresolved' ? 10 : 6)
      .attr('fill', d => color(d.type));
    node.append('title').text(d => `${d.type}: ${d.label}`);
    node.append('text').attr('dx', 8).attr('dy', 3).text(d => d.label);

    sim.on('tick', () => {
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
  </script>
</body>
</html>
"""


def _load_xref(xref_path: Path) -> CrossReferenceGraph:
    payload = xref_path.read_text(encoding="utf-8")
    return CrossReferenceGraph.model_validate_json(payload)


def _write_inline_viewer(payload: dict, out_path: Path) -> None:
    json_text = json.dumps(payload)
    html = _INLINE_VIEWER_TEMPLATE.replace("__GRAPH_PAYLOAD__", json_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a CrossReferenceGraph to D3-compatible JSON"
    )
    parser.add_argument("--xref", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--document-id", default=None)
    parser.add_argument(
        "--inline-viewer",
        type=Path,
        default=None,
        help="Optionally write a self-contained HTML viewer to this path",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not args.xref.is_file():
        print(f"error: --xref not found: {args.xref}", file=sys.stderr)
        return 2

    try:
        xref = _load_xref(args.xref)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: malformed cross_references.json: {exc}", file=sys.stderr)
        return 2

    graph = export_graph(xref, document_id=args.document_id)
    payload = graph.to_dict()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    if args.inline_viewer is not None:
        _write_inline_viewer(payload, args.inline_viewer)

    summary = (
        f"graph_export: {len(payload['nodes'])} nodes, "
        f"{len(payload['edges'])} edges; "
        f"resolved={payload['metadata']['resolved_count']}, "
        f"unresolved={payload['metadata']['unresolved_count']}; "
        f"out={args.output}"
    )
    if args.inline_viewer is not None:
        summary += f"; viewer={args.inline_viewer}"
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
