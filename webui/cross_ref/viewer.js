/*
 * Plan 008_0 — vanilla-JS static viewer for the CrossReferenceGraph.
 *
 * Loads a D3 force-directed layout from a graph.json payload produced
 * by tools/export_cross_ref_graph.py. The page works both:
 *   - via a <input type="file"> picker (default), and
 *   - by loading "graph.json" automatically when served from a static
 *     HTTP server (open() is not available via file://).
 *
 * No build step, no React, no npm. D3 v7 is loaded from a CDN by
 * index.html.
 */

const status = document.getElementById('status');
const fileInput = document.getElementById('graph-file');
const svg = d3.select('#chart');
let simulation = null;

function setStatus(text) {
  status.textContent = text;
}

function clearChart() {
  svg.selectAll('*').remove();
  if (simulation) {
    simulation.stop();
    simulation = null;
  }
}

function renderGraph(data) {
  clearChart();
  const width = window.innerWidth;
  const height = window.innerHeight - 60;
  svg.attr('viewBox', [0, 0, width, height]);

  const color = d3.scaleOrdinal(d3.schemeTableau10);

  const links = data.edges.map(d => Object.assign({}, d));
  const nodes = data.nodes.map(d => Object.assign({}, d));

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(60))
    .force('charge', d3.forceManyBody().strength(-150))
    .force('center', d3.forceCenter(width / 2, height / 2));

  const link = svg.append('g').attr('stroke-opacity', 0.6)
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('class', d => 'link' + (d.resolved ? '' : ' unresolved'))
    .attr('stroke-width', 1.2);

  const node = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('class', 'node')
    .call(drag(simulation));

  node.append('circle')
    .attr('r', d => d.type === 'unresolved' ? 10 : 6)
    .attr('fill', d => color(d.type));

  node.append('title').text(d => `${d.type}: ${d.label}`);
  node.append('text').attr('dx', 8).attr('dy', 3).text(d => d.label);

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  setStatus(
    ` — ${data.nodes.length} nodes, ${data.edges.length} edges ` +
    `(resolved: ${data.metadata.resolved_count}, ` +
    `unresolved: ${data.metadata.unresolved_count})`,
  );
}

function drag(sim) {
  function dragstarted(event) {
    if (!event.active) sim.alphaTarget(0.3).restart();
    event.subject.fx = event.subject.x;
    event.subject.fy = event.subject.y;
  }
  function dragged(event) {
    event.subject.fx = event.x;
    event.subject.fy = event.y;
  }
  function dragended(event) {
    if (!event.active) sim.alphaTarget(0);
    event.subject.fx = null;
    event.subject.fy = null;
  }
  return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
}

fileInput.addEventListener('change', async () => {
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    renderGraph(data);
  } catch (err) {
    setStatus(`Error loading ${file.name}: ${err.message}`);
  }
});

// When served from a static HTTP server (e.g. `python -m http.server`),
// auto-load `graph.json` from the same directory if present.
(async function tryAutoload() {
  if (window.location.protocol === 'file:') {
    return;
  }
  try {
    const resp = await fetch('graph.json');
    if (!resp.ok) return;
    const data = await resp.json();
    renderGraph(data);
  } catch (err) {
    // Silent: no graph.json next to the page is the normal first-load case.
  }
})();
