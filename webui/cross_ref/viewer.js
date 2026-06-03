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
  tabAdjudicate: $('#tab-adjudicate'),
  tabDocument: $('#tab-document'),
};

let manifest = null;
let docling = null;        // cached per example so we don't refetch
let lastExample = null;
let simulation = null;
let currentGraph = null;
let adjudications = new Map();
let adjudicateLimits = new Map();
let adjudicationImportHistory = [];
let doclingIndex = null;   // { items:[{selfRef,page,text,label}], byPage:Map }
let selectedMarkerId = null;

const REF_TYPES = [
  'figure', 'table', 'equation', 'theorem', 'definition', 'proof',
  'corollary', 'example', 'section', 'chapter', 'bibliography', 'footnote',
];
const VIEWER_VERSION = '008_4';
const ADJUDICATOR_KEY = 'pdf2md.cross_ref.adjudicator';

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

  currentGraph = graph;
  adjudications = new Map();
  adjudicateLimits = new Map();
  adjudicationImportHistory = [];
  selectedMarkerId = null;
  doclingIndex = buildDoclingIndex(docling);

  renderGraph(graph);
  renderStats(graph, { example: ex, semantic: sem, ocr });
  renderStructure(docling);
  renderDocument(graph);
  renderMarkers(graph);
  renderAdjudicate(graph);

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
  markers_section: 11,
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
  markers_section: '#b9a7e7',
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

  // Three link forces: containment backbone, page-sequence spine,
  // and cross-reference arcs. The spine has a longer distance (~110)
  // and high strength so adjacent pages line up in reading order; the
  // containment force is stiff + short; the cross-ref force is loose
  // + long so it curves on top of the layout rather than fighting it.
  const containmentLinks = links.filter(d => d.edge_kind === 'contains');
  const sequenceLinks = links.filter(d => d.edge_kind === 'page_sequence');
  const crossRefLinks = links.filter(
    d => d.edge_kind !== 'contains' && d.edge_kind !== 'page_sequence'
  );

  simulation = d3.forceSimulation(nodes)
    .force('link_contain', d3.forceLink(containmentLinks).id(d => d.id).distance(45).strength(0.9))
    .force('link_sequence', d3.forceLink(sequenceLinks).id(d => d.id).distance(110).strength(0.6))
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

  // Page-sequence spine — dashed blue lines connecting adjacent pages
  // in reading order. Visually distinct from both containment (lighter)
  // and cross-ref (curved + colored).
  const sequenceLine = els.chart.append('g').attr('class', 'links-sequence')
    .selectAll('line').data(sequenceLinks).join('line')
    .attr('class', 'link page-sequence')
    .attr('stroke', '#5a8fcb')
    .attr('stroke-width', 1.6)
    .attr('stroke-dasharray', '6 4')
    .attr('stroke-opacity', 0.85);

  // Cross-reference arcs — thicker, colored by resolved status,
  // drawn as Bézier paths so they curve gracefully across the
  // hierarchy instead of cutting through it.
  const xrefPath = els.chart.append('g').attr('class', 'links-xref')
    .selectAll('path').data(crossRefLinks).join('path')
    .attr('class', d => 'link xref ' + (d.resolved ? 'resolved' : 'unresolved'))
    .attr('fill', 'none')
    .attr('stroke', d => d.resolved ? '#2ca02c' : '#d62728')
    .attr('stroke-opacity', d => d.resolved ? 0.55 : 0.7)
    .attr('stroke-width', 1.4)
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      const srcId = (d.source && d.source.id) || d.source;
      const tgtId = (d.target && d.target.id) || d.target;
      const edge = (currentGraph?.edges || []).find(e => e.source === srcId && e.target === tgtId);
      if (!edge) return;
      highlightMarkerEverywhere(edge);
      const loc = locateMarker(edge);
      highlightDoclingItem(loc ? loc.item.selfRef : null, { scroll: true });
    });

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
    sequenceLine
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



function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function nodeById(graph) {
  return new Map((graph.nodes || []).map(n => [n.id, n]));
}

function markerPageNo(node) {
  if (!node) return null;
  if (node.page_no != null) return node.page_no;
  if (node.page != null) return node.page;
  return null;
}

function graphSchemaVersion(graph) {
  return graph.schema_version || (graph.metadata && graph.metadata.schema_version) || 'unknown';
}

function adjudicatorName() {
  return (document.getElementById('adjudicator-name')?.value || '').trim();
}

function nowIso() {
  return new Date().toISOString();
}

function serializeAdjudicationStore(graph) {
  return {
    schema_name: 'pdf2md.MarkerAdjudication',
    schema_version: '1.0.0',
    generated_at: nowIso(),
    document_id: graph.document_id,
    adjudicator: adjudicatorName(),
    adjudications: [...adjudications.values()].sort((a, b) => a.marker_id.localeCompare(b.marker_id)),
    metadata: {
      graph_schema_version: graphSchemaVersion(graph),
      viewer_version: VIEWER_VERSION,
      import_history: adjudicationImportHistory,
    },
  };
}

function validateImportedAdjudicationDocument(payload, graph) {
  if (!payload || payload.schema_name !== 'pdf2md.MarkerAdjudication' || payload.schema_version !== '1.0.0') {
    throw new Error('not a pdf2md.MarkerAdjudication 1.0.0 file');
  }
  if (payload.document_id !== graph.document_id) {
    throw new Error(`document_id mismatch: ${payload.document_id} != ${graph.document_id}`);
  }
  if (!Array.isArray(payload.adjudications)) {
    throw new Error('adjudications must be an array');
  }
  for (const item of payload.adjudications) {
    if (!item.marker_id || !REF_TYPES.includes(item.marker_type) || !item.decision || !item.decided_at) {
      throw new Error(`invalid adjudication row for marker ${item.marker_id || '(missing id)'}`);
    }
    if (!['resolve', 'reclassify', 'noise', 'rule_hint'].includes(item.decision)) {
      throw new Error(`invalid decision for marker ${item.marker_id}`);
    }
  }
}

function decisionSummary(item) {
  if (!item) return '';
  if (item.decision === 'resolve') return `resolve → ${item.target_entity_id || '—'}`;
  if (item.decision === 'reclassify') return `reclassify → ${item.corrected_type || '—'}`;
  if (item.decision === 'rule_hint') return `rule_hint: ${item.rule_hint || '—'}`;
  return 'noise';
}

function baseMarkerRecord(graph, edge) {
  const nodes = nodeById(graph);
  const source = nodes.get(edge.source) || {};
  return {
    marker_id: edge.source,
    marker_type: edge.marker_type || source.type || 'bibliography',
    label: edge.label || source.label || '',
    source_ref: source.source_ref || '',
    char_offset: Array.isArray(source.char_offset) ? source.char_offset : [0, 0],
    page_no: markerPageNo(source),
    backend: source.backend || '',
  };
}

// ---------------------------------------------------------------------------
// Document pane + marker-in-context (Plan 008_5)
// ---------------------------------------------------------------------------
function buildDoclingIndex(doc) {
  if (!doc || !Array.isArray(doc.texts)) return null;
  const items = [];
  const byPage = new Map();
  for (const t of doc.texts) {
    const prov = (t.prov || [])[0] || {};
    const page = prov.page_no ?? prov.page ?? null;
    const item = { selfRef: t.self_ref || '', page, text: t.text || '', label: t.label || 'text' };
    items.push(item);
    const key = page == null ? '?' : String(page);
    if (!byPage.has(key)) byPage.set(key, []);
    byPage.get(key).push(item);
  }
  return { items, byPage };
}

// Parse the 1-based page number a marker points at, e.g.
// "marker:3:#/document/pages/7:Eq. (15)" -> 7.
function markerPage(edge) {
  const m = /\/pages\/(\d+)/.exec(edge.source || '');
  return m ? Number(m[1]) : null;
}

// Marker labels (e.g. "Eq. (15)", "FIG. 4", "Theorem 2") don't always appear
// verbatim in the rendered text, so we also try the bracket/paren core and the
// trailing number. Returns the matched substring used (for <mark>), or null.
function labelVariants(label) {
  const out = [label];
  const bracket = label.match(/[([]\s*[\w.\-]+\s*[)\]]/);
  if (bracket) out.push(bracket[0]);
  const trailing = label.match(/[A-Za-z.]+\s*([\d]+(?:\.[\d]+)*)$/);
  if (trailing) out.push(trailing[1]);
  return out.filter(v => v && v.length >= 2);
}

function findInPool(pool, variants) {
  for (const v of variants) {
    const hit = pool.find(it => it.text.includes(v));
    if (hit) return { item: hit, match: v };
  }
  return null;
}

// Find the docling text item that contains a marker's label (or a normalized
// variant), preferring the marker's own page. Returns {item, page, match}.
function locateMarker(edge) {
  if (!doclingIndex) return null;
  const label = (edge.label || '').trim();
  const page = markerPage(edge);
  const variants = label ? labelVariants(label) : [];
  const pools = [];
  if (page != null && doclingIndex.byPage.has(String(page))) pools.push(doclingIndex.byPage.get(String(page)));
  pools.push(doclingIndex.items); // document-wide fallback
  if (variants.length) {
    for (const pool of pools) {
      const found = findInPool(pool, variants);
      if (found) return { item: found.item, page, match: found.match };
    }
  }
  // No textual match: fall back to the first text item on the marker's page.
  if (page != null && doclingIndex.byPage.has(String(page))) {
    return { item: doclingIndex.byPage.get(String(page))[0], page, match: null };
  }
  return null;
}

// Return an escaped snippet of `text` centred on `label`, with the label
// wrapped in <mark>. When the label is absent, returns a leading slice.
function snippetWithMark(text, label, win = 160) {
  const idx = label ? text.indexOf(label) : -1;
  if (idx < 0) {
    const head = text.slice(0, win * 2);
    return escapeHtml(head) + (text.length > win * 2 ? '…' : '');
  }
  const start = Math.max(0, idx - win);
  const end = Math.min(text.length, idx + label.length + win);
  const pre = (start > 0 ? '…' : '') + text.slice(start, idx);
  const mid = text.slice(idx, idx + label.length);
  const post = text.slice(idx + label.length, end) + (end < text.length ? '…' : '');
  return escapeHtml(pre) + '<mark>' + escapeHtml(mid) + '</mark>' + escapeHtml(post);
}

function renderDocument(graph) {
  const pane = els.tabDocument;
  if (!pane) return;
  if (!doclingIndex) {
    pane.innerHTML = '<p class="empty">No docling.json for this example — the document text is unavailable. Marker rows fall back to label-only.</p>';
    return;
  }
  const pages = [...doclingIndex.byPage.keys()].sort((a, b) => Number(a) - Number(b));
  const parts = ['<div class="doc-scroll">'];
  for (const page of pages) {
    parts.push(`<div class="doc-page-sep">page ${escapeHtml(page)}</div>`);
    for (const it of doclingIndex.byPage.get(page)) {
      const cls = it.label && it.label !== 'text' ? `doc-item ${escapeHtml(it.label)}` : 'doc-item';
      parts.push(
        `<p class="${cls}" data-self-ref="${escapeHtml(it.selfRef)}">` +
        (it.label && it.label !== 'text' ? `<span class="doc-label">${escapeHtml(it.label)}</span> ` : '') +
        escapeHtml(it.text) + '</p>'
      );
    }
  }
  parts.push('</div>');
  pane.innerHTML = parts.join('');
}

function highlightDoclingItem(selfRef, { scroll = false } = {}) {
  if (!els.tabDocument) return;
  els.tabDocument.querySelectorAll('.doc-item.hit').forEach(el => el.classList.remove('hit'));
  if (!selfRef) return;
  // Inside a double-quoted attribute selector only the backslash and the
  // quote need escaping (NOT #, /, . etc.).
  const safe = String(selfRef).replace(/(["\\])/g, '\\$&');
  const el = els.tabDocument.querySelector(`.doc-item[data-self-ref="${safe}"]`);
  if (!el) return;
  el.classList.add('hit');
  if (scroll) {
    activateTab('document');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// Rank candidate targets for an unresolved marker: same type first, then same
// page, capped. Used for one-click resolve chips.
function rankCandidates(graph, edge, limit = 6) {
  const type = edge.marker_type;
  const page = markerPage(edge);
  const entityTypes = new Set(REF_TYPES);
  const ents = (graph.nodes || []).filter(n => entityTypes.has(n.type) && !(n.id || '').startsWith('marker:'));
  const scored = ents.map(e => {
    let score = 0;
    if (e.type === type) score += 100;
    const ep = markerPageNo(e);
    if (page != null && ep != null && Number(ep) === page) score += 10;
    return { e, score };
  });
  scored.sort((a, b) => b.score - a.score || String(a.e.label).localeCompare(String(b.e.label)));
  return scored.filter(s => s.score > 0).slice(0, limit).map(s => s.e);
}

// Highlight the graph link + endpoint for a marker target, and the document
// sentence, when a marker row is hovered/selected.
function highlightMarkerEverywhere(edge) {
  highlightDoclingItem(edge ? (locateMarker(edge)?.item.selfRef || null) : null);
  els.chart.selectAll('.link.xref').classed('hot', false);
  els.chart.selectAll('.node').classed('hot', false);
  if (!edge) return;
  els.chart.selectAll('.link.xref').classed('hot', d => d && d.source && (d.source.id || d.source) === edge.source);
  const endpoints = new Set([edge.source, edge.target].filter(Boolean));
  els.chart.selectAll('.node').classed('hot', d => d && endpoints.has(d.id));
}

function setAdjudication(graph, edge, decision, payload) {
  const base = baseMarkerRecord(graph, edge);
  const record = {
    ...base,
    decision,
    target_entity_id: null,
    corrected_type: null,
    rule_hint: null,
    decided_at: nowIso(),
  };
  if (decision === 'resolve') record.target_entity_id = payload.target_entity_id;
  if (decision === 'reclassify') record.corrected_type = payload.corrected_type;
  if (decision === 'rule_hint') record.rule_hint = payload.rule_hint;
  adjudications.set(base.marker_id, record);
  renderAdjudicate(graph);
}

function clearAdjudication(markerId) {
  adjudications.delete(markerId);
  if (currentGraph) renderAdjudicate(currentGraph);
}

function entityOptions(graph, markerType, selectedId) {
  const entityTypes = new Set(REF_TYPES);
  const entities = (graph.nodes || []).filter(n => entityTypes.has(n.type) && !(n.id || '').startsWith('marker:'));
  entities.sort((a, b) => {
    const aRank = a.type === markerType ? 0 : 1;
    const bRank = b.type === markerType ? 0 : 1;
    return aRank - bRank || String(a.type).localeCompare(String(b.type)) || String(a.label).localeCompare(String(b.label));
  });
  const opts = ['<option value="">resolve target…</option>'];
  for (const ent of entities) {
    const same = ent.type === markerType ? 'same' : 'other';
    const selected = ent.id === selectedId ? ' selected' : '';
    opts.push(`<option value="${escapeHtml(ent.id)}"${selected}>[${same}] ${escapeHtml(ent.type)} · ${escapeHtml(ent.label || ent.id)}</option>`);
  }
  return opts.join('');
}

function refTypeOptions(selected) {
  return '<option value="">correct type…</option>' + REF_TYPES
    .map(t => `<option value="${t}"${t === selected ? ' selected' : ''}>${t}</option>`).join('');
}

function renderAdjudicate(graph) {
  if (!els.tabAdjudicate) return;
  const nodes = nodeById(graph);
  const unresolved = (graph.edges || [])
    .filter(e => e.edge_kind ? e.edge_kind === 'cross_reference' : true)
    .filter(e => e.resolved === false)
    .map(e => ({ edge: e, source: nodes.get(e.source) || {} }))
    .sort((a, b) => String(a.edge.source).localeCompare(String(b.edge.source)));

  const groups = new Map();
  for (const row of unresolved) {
    const type = row.edge.marker_type || row.source.type || 'unknown';
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type).push(row);
  }

  const adjudicator = escapeHtml(localStorage.getItem(ADJUDICATOR_KEY) || '');
  let html = `<div class="adjudicate-header">
    <label>Adjudicator <input id="adjudicator-name" type="text" value="${adjudicator}" placeholder="name or handle"></label>
    <button id="export-adjudications" type="button">Export adjudications</button>
    <label class="import-label">Import adjudications <input id="import-adjudications" type="file" accept="application/json,.json"></label>
    <span id="adjudication-status" class="adjudication-status">${adjudications.size} adjudicated · ${unresolved.length} unresolved</span>
  </div>`;

  if (!unresolved.length) {
    html += '<p style="color:#999">No unresolved cross-reference edges in this graph.</p>';
    els.tabAdjudicate.innerHTML = html;
    wireAdjudicationHeader(graph);
    return;
  }

  for (const [type, rows] of [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    const limit = adjudicateLimits.get(type) || 200;
    const visible = rows.slice(0, limit);
    html += `<section class="adjudication-group"><h3>${escapeHtml(type)} <span>${rows.length}</span></h3>`;
    for (const { edge, source } of visible) {
      const markerId = edge.source;
      const existing = adjudications.get(markerId);
      const pageNo = markerPage(edge) ?? markerPageNo(source);
      const loc = locateMarker(edge);
      const context = loc
        ? `<p class="marker-context-text" title="from the document (docling)">${snippetWithMark(loc.item.text, loc.match || (edge.label || '').trim())}</p>`
        : `<p class="marker-context-text none">no document context found${doclingIndex ? '' : ' (no docling.json for this example)'}</p>`;
      const chips = rankCandidates(graph, edge).map(ent => {
        const sel = existing?.target_entity_id === ent.id ? ' chosen' : '';
        const same = ent.type === edge.marker_type ? ' same' : '';
        return `<button type="button" class="cand-chip${same}${sel}" data-action="resolve_chip" data-entity-id="${escapeHtml(ent.id)}" title="${escapeHtml(ent.id)}">${escapeHtml(ent.type)} · ${escapeHtml(ent.label || ent.id)}</button>`;
      }).join('');
      html += `<article class="adjudication-row ${existing ? 'adjudicated' : ''}" data-marker-id="${escapeHtml(markerId)}">
        <div class="adjudication-main">
          <div class="marker-head">
            <span class="marker-type badge">${escapeHtml(edge.marker_type || source.type || 'unknown')}</span>
            <strong class="marker-label">${escapeHtml(edge.label || source.label || '')}</strong>
            <span class="marker-conn unresolved">unresolved</span>
            <span class="marker-meta">page ${pageNo == null ? '—' : escapeHtml(pageNo)}</span>
            <button type="button" class="goto-doc" data-action="goto_doc" title="Show in document">show in document ↗</button>
          </div>
          ${context}
          ${existing ? `<div class="decision-summary"><span>${escapeHtml(existing.decision)}</span> ${escapeHtml(decisionSummary(existing))}</div>` : ''}
        </div>
        <div class="adjudication-controls">
          ${chips ? `<div class="cand-chips"><span class="cand-label">resolve to:</span>${chips}</div>` : ''}
          <div class="control-row">
            <select data-action="resolve" title="all entities">${entityOptions(graph, edge.marker_type || source.type, existing?.target_entity_id)}</select>
            <select data-action="reclassify">${refTypeOptions(existing?.corrected_type)}</select>
            <button type="button" data-action="noise">Noise</button>
            <input type="text" data-action="rule_hint_text" value="${escapeHtml(existing?.rule_hint || '')}" placeholder="rule hint">
            <button type="button" data-action="rule_hint">Save hint</button>
            <button type="button" data-action="clear" ${existing ? '' : 'disabled'}>Clear</button>
          </div>
        </div>
      </article>`;
    }
    if (rows.length > visible.length) {
      html += `<button class="show-more" type="button" data-action="show_more" data-marker-type="${escapeHtml(type)}">Show more (${rows.length - visible.length} hidden)</button>`;
    }
    html += '</section>';
  }
  els.tabAdjudicate.innerHTML = html;
  wireAdjudicationHeader(graph);
}

function wireAdjudicationHeader(graph) {
  document.getElementById('adjudicator-name')?.addEventListener('input', (event) => {
    localStorage.setItem(ADJUDICATOR_KEY, event.target.value);
  });
  document.getElementById('export-adjudications')?.addEventListener('click', () => exportAdjudications(graph));
  document.getElementById('import-adjudications')?.addEventListener('change', (event) => importAdjudications(event, graph));
}

els.tabAdjudicate?.addEventListener('change', (event) => {
  const control = event.target;
  const row = control.closest('.adjudication-row');
  if (!row || !currentGraph) return;
  const markerId = row.dataset.markerId;
  const edge = (currentGraph.edges || []).find(e => e.source === markerId);
  if (!edge) return;
  if (control.dataset.action === 'resolve' && control.value) {
    setAdjudication(currentGraph, edge, 'resolve', { target_entity_id: control.value });
  }
  if (control.dataset.action === 'reclassify' && control.value) {
    setAdjudication(currentGraph, edge, 'reclassify', { corrected_type: control.value });
  }
});

els.tabAdjudicate?.addEventListener('click', (event) => {
  const control = event.target.closest('[data-action]') || event.target;
  if (!currentGraph) return;
  if (control.dataset && control.dataset.action === 'show_more') {
    const type = control.dataset.markerType;
    adjudicateLimits.set(type, (adjudicateLimits.get(type) || 200) + 200);
    renderAdjudicate(currentGraph);
    return;
  }
  const row = event.target.closest('.adjudication-row');
  if (!row) return;
  const markerId = row.dataset.markerId;
  const edge = (currentGraph.edges || []).find(e => e.source === markerId);
  const action = control.dataset ? control.dataset.action : undefined;
  if (action === 'clear') {
    clearAdjudication(markerId);
  } else if (action === 'noise' && edge) {
    setAdjudication(currentGraph, edge, 'noise', {});
  } else if (action === 'rule_hint' && edge) {
    const text = row.querySelector('[data-action="rule_hint_text"]')?.value.trim();
    if (text) setAdjudication(currentGraph, edge, 'rule_hint', { rule_hint: text });
  } else if (action === 'resolve_chip' && edge) {
    setAdjudication(currentGraph, edge, 'resolve', { target_entity_id: control.dataset.entityId });
  } else if (action === 'goto_doc' && edge) {
    const loc = locateMarker(edge);
    highlightMarkerEverywhere(edge);
    highlightDoclingItem(loc ? loc.item.selfRef : null, { scroll: true });
  } else if (edge) {
    // Bare row click: select + cross-highlight (list <-> graph <-> text).
    selectedMarkerId = markerId;
    els.tabAdjudicate.querySelectorAll('.adjudication-row.selected').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');
    highlightMarkerEverywhere(edge);
  }
});

els.tabAdjudicate?.addEventListener('mouseover', (event) => {
  const row = event.target.closest('.adjudication-row');
  if (!row || !currentGraph) return;
  const edge = (currentGraph.edges || []).find(e => e.source === row.dataset.markerId);
  if (edge) highlightMarkerEverywhere(edge);
});

function exportAdjudications(graph) {
  const payload = serializeAdjudicationStore(graph);
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${graph.document_id || 'document'}.adjudications.json`.replace(/[\\/]/g, '_');
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function importAdjudications(event, graph) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const status = document.getElementById('adjudication-status');
  try {
    const payload = JSON.parse(await file.text());
    validateImportedAdjudicationDocument(payload, graph);
    let added = 0;
    let overwritten = 0;
    for (const item of payload.adjudications) {
      const current = adjudications.get(item.marker_id);
      if (!current) {
        adjudications.set(item.marker_id, item);
        added += 1;
      } else if (new Date(item.decided_at) >= new Date(current.decided_at)) {
        adjudications.set(item.marker_id, item);
        overwritten += 1;
      }
    }
    adjudicationImportHistory = [
      ...adjudicationImportHistory,
      ...((payload.metadata && payload.metadata.import_history) || []),
      { at: nowIso(), merged_from: file.name, added, overwritten },
    ];
    renderAdjudicate(graph);
    const newStatus = document.getElementById('adjudication-status');
    if (newStatus) newStatus.textContent = `imported ${file.name}: added ${added}, overwritten ${overwritten}`;
  } catch (err) {
    if (status) status.textContent = `import failed: ${err.message}`;
    alert(`Import failed: ${err.message}`);
  } finally {
    event.target.value = '';
  }
}

// ---------------------------------------------------------------------------
// Markers pane
// ---------------------------------------------------------------------------
function renderMarkers(graph) {
  const nodes = nodeById(graph);
  const rows = graph.edges.slice(0, 200).map(e => {
    const cls = e.resolved ? 'resolved' : 'unresolved';
    const targetNode = e.target ? nodes.get(e.target) : null;
    const targetLabel = targetNode ? (targetNode.label || e.target) : (e.target || '');
    const conn = e.resolved
      ? `<span class="marker-conn resolved">→ ${escapeHtml(targetNode ? targetNode.type + ' · ' : '')}${escapeHtml(targetLabel)}</span>`
      : `<span class="marker-conn unresolved">unresolved</span>`;
    const loc = locateMarker(e);
    const ctx = loc ? `<div class="marker-ctx">${snippetWithMark(loc.item.text, loc.match || (e.label || '').trim(), 90)}</div>` : '';
    return `<div class="marker-row ${cls}" data-marker-id="${escapeHtml(e.source)}">
      <div class="marker-row-head">
        <span class="marker-type badge">${escapeHtml(e.marker_type || 'unknown')}</span>
        <strong class="marker-text">${escapeHtml(e.label || '')}</strong>
        ${conn}
      </div>
      ${ctx}
    </div>`;
  }).join('');
  const overflow = graph.edges.length > 200
    ? `<p class="empty">… ${graph.edges.length - 200} more (truncated)</p>` : '';
  els.tabMarkers.innerHTML = rows + overflow;
}

els.tabMarkers?.addEventListener('click', (event) => {
  const row = event.target.closest('.marker-row');
  if (!row || !currentGraph) return;
  const edge = (currentGraph.edges || []).find(e => e.source === row.dataset.markerId);
  if (!edge) return;
  highlightMarkerEverywhere(edge);
  const loc = locateMarker(edge);
  highlightDoclingItem(loc ? loc.item.selfRef : null, { scroll: true });
});
els.tabMarkers?.addEventListener('mouseover', (event) => {
  const row = event.target.closest('.marker-row');
  if (!row || !currentGraph) return;
  const edge = (currentGraph.edges || []).find(e => e.source === row.dataset.markerId);
  if (edge) highlightMarkerEverywhere(edge);
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
loadManifest().catch(err => setStatus(`error: ${err.message}`));
