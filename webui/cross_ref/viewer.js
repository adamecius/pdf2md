/*
 * pdf2md viewer — semantic CrossReferenceGraph + docling structure side-by-side.
 *
 * Picks: example × semantic backend × OCR candidate source.
 * Loads precomputed JSON artifacts under ./data/<example>/ — see
 * the bench scripts under tools/ for how those are produced.
 */

const $ = (sel) => document.querySelector(sel);

const els = {
  example: $('#picker-example'),
  semantic: $('#picker-semantic'),
  ocr: $('#picker-ocr'),
  docClass: $('#doc-class'),
  status: $('#status'),
  chart: d3.select('#chart'),
  tabs: document.querySelectorAll('.tab'),
  tabStats: $('#tab-stats'),
  tabStructure: $('#tab-structure'),
  tabMarkers: $('#tab-markers'),
};

let manifest = null;
let docling = null;        // cached per example so we don't refetch
let lastExample = null;
let simulation = null;

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
// Cache-buster appended to every data-file fetch so browsers don't hold
// onto stale JSON after the data/ directory is regenerated.
const _cb = `?v=${Date.now()}`;

async function loadManifest() {
  const resp = await fetch(`data/manifest.json${_cb}`);
  if (!resp.ok) throw new Error(`manifest load failed: ${resp.status}`);
  manifest = await resp.json();
  populatePickers();
}

function populatePickers() {
  els.example.innerHTML = manifest.examples
    .map(e => `<option value="${e.id}">${e.label}</option>`).join('');
  els.semantic.innerHTML = manifest.semantic_backends
    .map(b => `<option value="${b.id}">${b.label}</option>`).join('');
  // The ocr select already has a "none" option in index.html.
  els.ocr.innerHTML =
    '<option value="">none (markers only, no OCR bridge)</option>' +
    manifest.ocr_backends.map(b => `<option value="${b.id}">${b.label}</option>`).join('');

  // Sensible defaults: example01 + vlm_v4 + deepseek.
  els.example.value = 'example01';
  els.semantic.value = 'vlm_v4';
  els.ocr.value = 'deepseek';

  [els.example, els.semantic, els.ocr].forEach(el => el.addEventListener('change', reload));
  els.tabs.forEach(t => t.addEventListener('click', () => activateTab(t.dataset.tab)));

  reload();
}

function activateTab(name) {
  els.tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById(`tab-${name}`).classList.add('active');
}

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------
async function reload() {
  const ex = els.example.value;
  const sem = els.semantic.value;
  const ocr = els.ocr.value;
  setStatus('Loading…');

  // Cache the docling JSON per example.
  if (ex !== lastExample) {
    try {
      const resp = await fetch(`data/${ex}/docling.json${_cb}`);
      docling = resp.ok ? await resp.json() : null;
    } catch {
      docling = null;
    }
    lastExample = ex;
  }

  const graphFile = ocr
    ? `data/${ex}/${sem}__resolved_with__${ocr}.json`
    : `data/${ex}/${sem}.json`;
  let graph;
  try {
    const resp = await fetch(`${graphFile}${_cb}`);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    graph = await resp.json();
  } catch (err) {
    setStatus(`error loading ${graphFile}: ${err.message}`);
    return;
  }

  // Document-class badge (Plan 7). The class lives in the entities
  // file metadata, not the graph itself. Skip the fetch when no OCR
  // is selected — without an OCR the badge has no source.
  if (ocr) {
    try {
      const er = await fetch(`data/${ex}/entities_${ocr}.json${_cb}`);
      if (er.ok) {
        const ents = await er.json();
        renderDocClassBadge(ents.metadata || {});
      } else {
        renderDocClassBadge({});
      }
    } catch {
      renderDocClassBadge({});
    }
  } else {
    renderDocClassBadge({});
  }

  renderGraph(graph);
  renderStats(graph, { example: ex, semantic: sem, ocr });
  renderStructure(docling);
  renderMarkers(graph);

  const r = graph.metadata.resolved_count || 0;
  const u = graph.metadata.unresolved_count || 0;
  setStatus(
    `${graph.nodes.length} nodes · ${graph.edges.length} edges ` +
    `(${r} resolved, ${u} unresolved)`,
  );
}

function setStatus(text) { els.status.textContent = text; }


function renderDocClassBadge(meta) {
  if (!els.docClass) return;
  const cls = meta.document_class;
  if (!cls) {
    els.docClass.textContent = '';
    els.docClass.className = 'doc-class';
    return;
  }
  const conf = meta.document_class_confidence;
  const pct = (typeof conf === 'number') ? `  ${(conf * 100).toFixed(0)}%` : '';
  els.docClass.textContent = `doc · ${cls}${pct}`;
  els.docClass.className = `doc-class ${cls}`;
  const feat = meta.document_class_features;
  if (feat) {
    els.docClass.title = `Plan 7 classifier — ${cls} (conf ${conf?.toFixed(2)})\n` +
      `pages=${feat.page_count} chapters=${feat.chapter_count} ` +
      `references=${feat.reference_section_count} index=${feat.index_section_count} ` +
      `glossary=${feat.glossary_section_count}`;
  }
}

// ---------------------------------------------------------------------------
// Graph rendering
//
// Schema 1.1 (graph_export.has_hierarchy=true) emits:
//   - one `document` root node
//   - one `page` node per page in the OCR proposals
//   - back-matter section nodes (`bibliography_section`, etc.)
//   - entity / marker / unresolved nodes (as before)
//   - `contains` edges from document → page → entity (and document →
//     section → entity for back-matter)
//   - `cross_reference` edges from marker → resolved target (as
//     before; now tagged with edge_kind)
//
// Layout strategy: hybrid force-directed. Containment edges are short
// + stiff (≈40 px) so children cluster around their parent. The
// document node is anchored at center. Cross-reference edges get
// longer (≈140 px) and a softer link strength so they curve through
// the graph rather than fighting the containment layout. Visually
// they're drawn LAST (on top) and as Bézier arcs, not straight lines,
// so they read as "this is a different kind of relationship".
// ---------------------------------------------------------------------------
const NODE_RADIUS = {
  document: 16,
  page: 10,
  bibliography_section: 12,
  index_section: 12,
  glossary_section: 12,
  reference_section: 12,
  unresolved: 10,
  default: 6,
};
const NODE_COLOR_OVERRIDES = {
  document: '#444',
  page: '#a7c7e7',
  bibliography_section: '#ffb380',
  index_section: '#ffcf80',
  glossary_section: '#80c8ff',
  unresolved: '#d33',
};

function _nodeRadius(type) { return NODE_RADIUS[type] ?? NODE_RADIUS.default; }


function renderGraph(data) {
  els.chart.selectAll('*').remove();
  if (simulation) { simulation.stop(); simulation = null; }

  const width = els.chart.node().clientWidth || 800;
  const height = els.chart.node().clientHeight || 600;
  els.chart.attr('viewBox', [0, 0, width, height]);

  const palette = d3.scaleOrdinal(d3.schemeTableau10);
  const colorFor = (type) => NODE_COLOR_OVERRIDES[type] ?? palette(type);

  const nodes = data.nodes.map(d => Object.assign({}, d));
  const links = data.edges.map(d => Object.assign({}, d));
  const hierarchical = !!data.metadata?.has_hierarchy;

  // Anchor the document node at the center when present — gives the
  // force layout a stable backbone instead of letting it drift.
  if (hierarchical) {
    for (const n of nodes) {
      if (n.type === 'document') {
        n.fx = width / 2;
        n.fy = height / 2;
      }
    }
  }

  // Two link forces — one for the structural backbone, one for
  // cross-references. The structural force is stiff + short; the
  // cross-ref force is loose + longer.
  const containmentLinks = links.filter(d => d.edge_kind === 'contains');
  const crossRefLinks = links.filter(d => d.edge_kind !== 'contains');

  simulation = d3.forceSimulation(nodes)
    .force('link_contain', d3.forceLink(containmentLinks).id(d => d.id).distance(45).strength(0.9))
    .force('link_xref', d3.forceLink(crossRefLinks).id(d => d.id).distance(140).strength(0.05))
    .force('charge', d3.forceManyBody().strength(d => d.type === 'document' ? -800 : -130))
    .force('center', hierarchical ? null : d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => _nodeRadius(d.type) + 2));

  // Containment backbone — thin grey lines drawn under the cross-ref
  // arcs.
  const containmentLine = els.chart.append('g').attr('class', 'links-contain')
    .selectAll('line').data(containmentLinks).join('line')
    .attr('class', 'link contains')
    .attr('stroke', '#cbd2d8')
    .attr('stroke-width', 1)
    .attr('stroke-opacity', 0.7);

  // Cross-reference arcs — thicker, colored by resolved status,
  // drawn as Bézier paths so they curve gracefully across the
  // hierarchy instead of cutting through it.
  const xrefPath = els.chart.append('g').attr('class', 'links-xref')
    .selectAll('path').data(crossRefLinks).join('path')
    .attr('class', d => 'link xref ' + (d.resolved ? 'resolved' : 'unresolved'))
    .attr('fill', 'none')
    .attr('stroke', d => d.resolved ? '#2ca02c' : '#d62728')
    .attr('stroke-opacity', d => d.resolved ? 0.55 : 0.7)
    .attr('stroke-width', 1.4);

  const node = els.chart.append('g').attr('class', 'nodes')
    .selectAll('g').data(nodes).join('g')
    .attr('class', d => 'node node-' + d.type)
    .call(drag(simulation));

  node.append('circle')
    .attr('r', d => _nodeRadius(d.type))
    .attr('fill', d => colorFor(d.type))
    .attr('stroke', '#fff').attr('stroke-width', 1);
  node.append('title').text(d => {
    const lines = [`${d.type}: ${d.label}`];
    if (d.page_no != null) lines.push(`page ${d.page_no}`);
    if (d.parent_id) lines.push(`parent: ${d.parent_id}`);
    return lines.join('\n');
  });
  node.append('text')
    .attr('dx', d => _nodeRadius(d.type) + 3).attr('dy', 3)
    .style('font-weight', d => d.type === 'document' || d.type === 'page' || (d.type || '').endsWith('_section') ? 600 : 400)
    .text(d => {
      // Truncate long bibliography labels so they don't take over the
      // canvas.
      const label = d.label || '';
      if (label.length > 36 && (d.type === 'bibliography' || (d.type || '').endsWith('_section'))) {
        return label.slice(0, 36) + '…';
      }
      return label;
    });

  simulation.on('tick', () => {
    containmentLine
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    xrefPath.attr('d', d => {
      const sx = d.source.x, sy = d.source.y;
      const tx = d.target.x, ty = d.target.y;
      const dx = tx - sx, dy = ty - sy;
      const dr = Math.sqrt(dx * dx + dy * dy) * 1.2;
      // Curved arc — sweep flag varies by source/target order so
      // out- and in- arcs don't overlap exactly.
      return `M${sx},${sy}A${dr},${dr} 0 0,1 ${tx},${ty}`;
    });
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

function drag(sim) {
  return d3.drag()
    .on('start', e => { if (!e.active) sim.alphaTarget(0.3).restart(); e.subject.fx = e.subject.x; e.subject.fy = e.subject.y; })
    .on('drag', e => { e.subject.fx = e.x; e.subject.fy = e.y; })
    .on('end',  e => { if (!e.active) sim.alphaTarget(0); e.subject.fx = null; e.subject.fy = null; });
}

// ---------------------------------------------------------------------------
// Stats pane
// ---------------------------------------------------------------------------
function renderStats(graph, ctx) {
  const md = graph.metadata || {};
  const counts = {};
  for (const e of graph.edges) {
    const t = e.marker_type || 'unknown';
    counts[t] = (counts[t] || 0) + 1;
  }
  const r = md.resolved_count || 0;
  const u = md.unresolved_count || 0;
  const total = r + u;
  const rate = total > 0 ? (100 * r / total).toFixed(1) : '0.0';

  const rows = [
    ['example', ctx.example],
    ['semantic backend', ctx.semantic],
    ['ocr candidates', ctx.ocr || '(none)'],
    ['markers', graph.edges.length],
    ['resolved', `${r} (${rate}%)`],
    ['unresolved', `${u}`],
    ['doc_hash', md.doc_hash || '—'],
    ['backend_versions', JSON.stringify(md.backend_versions || {})],
  ];

  const countRows = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `<tr><td>${k}</td><td class="num">${v}</td></tr>`).join('');

  els.tabStats.innerHTML = `
    ${rows.map(([k, v]) => `<div class="stat-row"><span class="stat-key">${k}</span><span class="stat-val">${v}</span></div>`).join('')}
    <table class="counts-table">
      <thead><tr><th>marker_type</th><th class="num">count</th></tr></thead>
      <tbody>${countRows}</tbody>
    </table>
  `;
}

// ---------------------------------------------------------------------------
// Docling structure pane
// ---------------------------------------------------------------------------
function renderStructure(doc) {
  if (!doc) {
    els.tabStructure.innerHTML = '<p style="color:#999">No docling.json for this example.</p>';
    return;
  }

  // The DoclingDocument layout has texts/pictures/tables collections plus
  // (in some schema versions) a structure tree. We walk the body recursively
  // when present, otherwise we list texts grouped by page.
  const lines = [];
  const texts = doc.texts || [];
  const pictures = doc.pictures || [];
  const tables = doc.tables || [];

  const byPage = new Map();
  const pageOf = (item) => {
    const prov = (item.prov || [])[0];
    return prov ? prov.page_no || prov.page : null;
  };

  for (const t of texts) {
    const page = pageOf(t) ?? '?';
    if (!byPage.has(page)) byPage.set(page, []);
    byPage.get(page).push({ kind: 'text', label: t.label || 'text', value: (t.text || '').slice(0, 120) });
  }
  for (const p of pictures) {
    const page = pageOf(p) ?? '?';
    if (!byPage.has(page)) byPage.set(page, []);
    byPage.get(page).push({ kind: 'figure', label: 'picture', value: (p.captions && p.captions[0]?.cref) || '' });
  }
  for (const t of tables) {
    const page = pageOf(t) ?? '?';
    if (!byPage.has(page)) byPage.set(page, []);
    byPage.get(page).push({ kind: 'table', label: 'table', value: '' });
  }

  const pages = [...byPage.keys()].sort((a, b) => Number(a) - Number(b));
  for (const page of pages) {
    lines.push(`<div class="struct-page">page ${page}</div>`);
    for (const item of byPage.get(page).slice(0, 60)) {
      const cls = item.label === 'section_header' ? 'heading' : item.kind;
      const txt = `${item.label}: ${item.value || ''}`.replace(/</g, '&lt;');
      lines.push(`<div class="struct-item ${cls}">${txt}</div>`);
    }
    if (byPage.get(page).length > 60) {
      lines.push(`<div class="struct-item">… ${byPage.get(page).length - 60} more</div>`);
    }
  }

  els.tabStructure.innerHTML =
    `<div class="structure-tree">${lines.join('') || '<em>empty docling document</em>'}</div>`;
}

// ---------------------------------------------------------------------------
// Markers pane
// ---------------------------------------------------------------------------
function renderMarkers(graph) {
  const rows = graph.edges.slice(0, 200).map(e => {
    const cls = e.resolved ? 'resolved' : 'unresolved';
    const target = e.target ? ` → ${e.target.replace(/^.+:/, '')}` : '';
    const safe = (e.label || '').replace(/</g, '&lt;');
    return `<div class="marker-row ${cls}">
      <span class="marker-type">${e.marker_type}</span>
      <span class="marker-text">${safe}${target}</span>
    </div>`;
  }).join('');
  const overflow = graph.edges.length > 200
    ? `<p style="color:#999">… ${graph.edges.length - 200} more (truncated)</p>` : '';
  els.tabMarkers.innerHTML = rows + overflow;
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
loadManifest().catch(err => setStatus(`error: ${err.message}`));
