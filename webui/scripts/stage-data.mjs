#!/usr/bin/env node
/**
 * Stage repo artefacts into webui/validator/public/api/ for the static build.
 *
 * In dev mode, vite.config.ts mounts a /api middleware that reads files from
 * the repo root on demand and synthesises directory listings. For a static
 * production build (GitHub Pages), that middleware is not available — we
 * therefore copy the artefacts the SPA reads into validator/public/api/
 * AND generate `_index.json` files for every directory the SPA tries to
 * list at runtime.
 *
 * What we ship in the static bundle:
 *
 *   - groundtruth/corpus/latex/<doc>/*.docling.json     ground-truth trees
 *   - groundtruth/corpus/latex/<doc>/meta.toml          per-doc metadata
 *   - groundtruth/corpus/latex/<doc>/*.pdf              compiled PDFs (if
 *                                                       present locally /
 *                                                       in CI)
 *   - src/pdf2md/data/factory_priors/*.json             factory priors
 *
 * Plus per-doc synthetic backend + consensus IR, *derived from the
 * ground-truth* .docling.json and clearly marked `demo_synthesized:true`
 * in the metadata. These let the Compare view's consensus + backend
 * panels render with shape-correct content even on the static deploy
 * (where no real pipeline has been run). They are NOT a substitute
 * for real backend output — they are equivalent in shape, identical
 * in content to the ground truth, and exist to demonstrate the UI.
 *
 * What we deliberately exclude:
 *
 *   - .tmp/papers_run/                                   operator-local; not in git
 *   - External corpora under groundtruth/external/      opt-in, not in git
 *
 * Usage:
 *
 *   node webui/scripts/stage-data.mjs              # from anywhere
 *
 * Idempotent: rerunning replaces the staged directory.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..");
const PUBLIC_API = path.resolve(HERE, "..", "validator", "public", "api");

// Whitelist of (repo-relative source dir → glob-ish file filter). Each entry
// is copied recursively. Files that match `keep` are copied; everything else
// is skipped.
const STAGE = [
  {
    src: "groundtruth/corpus/latex",
    keep: (rel) =>
      rel.endsWith(".docling.json") ||
      rel.endsWith(".docling_groundtruth_meta.json") ||
      rel.endsWith("meta.toml") ||
      rel.endsWith(".pdf"),
  },
  {
    src: "src/pdf2md/data/factory_priors",
    keep: (rel) => rel.endsWith(".json"),
  },
];

// Demo backends synthesised from the ground-truth tree, so the
// per-backend tabs and consensus panel in the Compare view have content
// to render on the static deploy.
const DEMO_BACKENDS = ["paddleocr", "mineru", "deepseek"];

const DOCLING_LABEL_TO_KIND = {
  title: "heading",
  section_header: "heading",
  heading: "heading",
  text: "paragraph",
  paragraph: "paragraph",
  caption: "caption",
  table: "table",
  formula: "formula",
  equation: "formula",
  footnote: "footnote",
  list: "list",
  list_item: "list_item",
  page_number: "page_number",
  picture: "figure",
  figure: "figure",
};

function rmrf(dir) {
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
}

function mkdirp(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function walk(dir) {
  const out = [];
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const stat = fs.statSync(full);
    if (stat.isDirectory()) {
      out.push({ name, is_dir: true, full });
      out.push(...walk(full).map((e) => ({ ...e, name: path.join(name, e.name) })));
    } else {
      out.push({ name, is_dir: false, full });
    }
  }
  return out;
}

function copyOne(src, dst, keep) {
  if (!fs.existsSync(src)) {
    console.warn(`[stage-data] missing source dir, skipping: ${src}`);
    return 0;
  }
  let copied = 0;
  for (const entry of walk(src)) {
    if (entry.is_dir) continue;
    if (!keep(entry.name)) continue;
    const target = path.join(dst, entry.name);
    mkdirp(path.dirname(target));
    fs.copyFileSync(entry.full, target);
    copied++;
  }
  return copied;
}

/**
 * Walk every directory under `root` and write a `_index.json` listing the
 * direct children (matching the dev middleware's `[{name, is_dir}]` shape).
 * Skips the `_index.json` itself from each listing.
 */
function writeIndexJsons(root) {
  if (!fs.existsSync(root)) return 0;
  let written = 0;
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    const entries = fs
      .readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.name !== "_index.json")
      .map((e) => ({ name: e.name, is_dir: e.isDirectory() }));
    fs.writeFileSync(path.join(dir, "_index.json"), JSON.stringify(entries, null, 2));
    written++;
    for (const e of entries) {
      if (e.is_dir) stack.push(path.join(dir, e.name));
    }
  }
  return written;
}

/**
 * Build per-page PageExtractionIR objects from a parsed DoclingDocument.
 * Each `texts[i]` becomes a paragraph/heading/caption/etc block; each
 * `pictures[i]` becomes a `figure`; each `tables[i]` becomes a `table`.
 *
 * Mostly deterministic — we do introduce a small per-backend perturbation
 * (random subset, kind drift on a few blocks) so the three backends look
 * visually distinct from each other and from the ground truth in the
 * comparison panel. The intent is "demo of how the UI looks with backend
 * disagreement", not real OCR output.
 */
function synthesiseBackendPages(docId, docling, backend) {
  // Deterministic seed per (docId, backend) — same input always produces
  // the same synthesised output.
  let seed = 0;
  for (const ch of `${docId}|${backend}`) seed = ((seed << 5) - seed + ch.charCodeAt(0)) | 0;
  function rand() {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 0xffffffff;
  }

  const pagesByNo = new Map();

  function pageBucket(pageNo) {
    if (!pagesByNo.has(pageNo)) {
      pagesByNo.set(pageNo, {
        schema_name: "pdf2md.PageExtractionIR",
        schema_version: "1.0.0",
        document_id: docId,
        backend,
        backend_version: "demo-synthesised",
        page_no: pageNo,
        page_size: { width: 595, height: 842 },
        blocks: [],
        metadata: { demo_synthesized: true, source: "ground-truth-derived" },
      });
    }
    return pagesByNo.get(pageNo);
  }

  let order = 0;
  function pushBlock(srcId, label, text, prov) {
    // Skip ~15% of blocks at random — simulates real backends missing some.
    if (rand() < 0.15) return;
    const kind = DOCLING_LABEL_TO_KIND[label] ?? label ?? "unknown";
    // ~10% kind drift to a similar kind — simulates classification noise.
    const driftedKind = rand() < 0.1 && kind === "paragraph" ? "caption" : kind;
    const pageNo = prov?.[0]?.page_no ?? 1;
    const bbox = prov?.[0]?.bbox
      ? {
          l: prov[0].bbox.l,
          t: prov[0].bbox.t,
          r: prov[0].bbox.r,
          b: prov[0].bbox.b,
          coord_origin: "topleft",
        }
      : null;
    pageBucket(pageNo).blocks.push({
      id: `${backend}/${docId}/p${pageNo}/b${order++}/${srcId.replace(/[^a-zA-Z0-9_]/g, "_")}`,
      backend,
      page_no: pageNo,
      kind: driftedKind,
      bbox,
      order,
      text,
      confidence: 0.7 + rand() * 0.3,
      metadata: { demo_synthesized: true, derived_from: srcId },
    });
  }

  for (const t of docling.texts ?? []) {
    pushBlock(t.self_ref, t.label, t.text ?? t.orig ?? "", t.prov);
  }
  for (const p of docling.pictures ?? []) {
    pushBlock(p.self_ref, "figure", "(picture)", p.prov);
  }
  for (const tb of docling.tables ?? []) {
    pushBlock(tb.self_ref, "table", "(table)", tb.prov);
  }

  return [...pagesByNo.values()].sort((a, b) => a.page_no - b.page_no);
}

function synthesiseConsensus(docId, docling, backends) {
  let seed = 0;
  for (const ch of docId) seed = ((seed << 5) - seed + ch.charCodeAt(0)) | 0;
  function rand() {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 0xffffffff;
  }

  const pagesByNo = new Map();
  let order = 0;

  function pageBucket(pageNo) {
    if (!pagesByNo.has(pageNo)) pagesByNo.set(pageNo, { page_no: pageNo, blocks: [] });
    return pagesByNo.get(pageNo);
  }

  function pushBlock(srcId, label, text, prov) {
    const kind = DOCLING_LABEL_TO_KIND[label] ?? label ?? "unknown";
    const pageNo = prov?.[0]?.page_no ?? 1;
    const bbox = prov?.[0]?.bbox
      ? {
          l: prov[0].bbox.l,
          t: prov[0].bbox.t,
          r: prov[0].bbox.r,
          b: prov[0].bbox.b,
          coord_origin: "topleft",
        }
      : null;
    // Pick a selection_mode plausibly: AGREED most of the time, single source
    // sometimes, fallback occasionally.
    const r = rand();
    const selection =
      r < 0.7 ? "agreed" : r < 0.9 ? "single_source" : r < 0.97 ? "fallback" : "unresolved";
    pageBucket(pageNo).blocks.push({
      id: `consensus/${docId}/p${pageNo}/b${order++}/${srcId.replace(/[^a-zA-Z0-9_]/g, "_")}`,
      page_no: pageNo,
      kind,
      bbox,
      text,
      selection_mode: selection,
      agreement_score: 0.5 + rand() * 0.5,
      candidate_ids: backends.map((b) => `${b}-candidate-${order}`),
      metadata: { demo_synthesized: true, derived_from: srcId },
    });
  }

  for (const t of docling.texts ?? []) {
    pushBlock(t.self_ref, t.label, t.text ?? t.orig ?? "", t.prov);
  }
  for (const p of docling.pictures ?? []) {
    pushBlock(p.self_ref, "figure", "(picture)", p.prov);
  }
  for (const tb of docling.tables ?? []) {
    pushBlock(tb.self_ref, "table", "(table)", tb.prov);
  }

  const pages = [...pagesByNo.values()].sort((a, b) => a.page_no - b.page_no);
  return {
    schema_name: "pdf2md.ConsensusIR",
    schema_version: "1.0.0",
    document_id: docId,
    page_count: pages.length,
    pages,
    backends: backends.map((b) => ({ backend: b, block_count: 0 })),
    conflicts: [],
    warnings: ["demo_synthesized: derived from ground truth"],
    metadata: { demo_synthesized: true, source: "ground-truth-derived" },
  };
}

/**
 * For each staged ground-truth doc, synthesise per-backend pages and a
 * consensus IR under `_demo_run/`. The Compare route already probes
 * `.tmp/calibration_corpus/<doc>/<backend>/pages/` (groundtruth flow) and
 * `.tmp/papers_run/<tag>/connector/<backend>/` (paper_run flow); we add a
 * third probe to `<corpus>/.demo/<doc>/` and surface it in the dataset
 * descriptor with a clear `synthesized: true` flag (handled UI-side).
 *
 * To avoid touching the Compare loader logic, we slot the synthesised
 * backend pages under `.tmp/calibration_corpus/<doc>/<backend>/pages/`
 * (the path the existing groundtruth flow already probes), and we slot
 * the synthesised consensus under `.tmp/papers_run/demo:<doc>/...` —
 * but that path conflicts with paper_run discovery. So instead we write
 * the consensus next to the per-backend pages under
 * `.tmp/calibration_corpus/<doc>/_consensus/consensus_ir.json` and
 * teach the loader to look for it there.
 */
function synthesiseDemoData(corpusStagedRoot) {
  if (!fs.existsSync(corpusStagedRoot)) return 0;
  const docDirs = fs
    .readdirSync(corpusStagedRoot, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name);

  // Compute target root for synthesised demo data.
  const demoRoot = path.join(PUBLIC_API, ".tmp", "calibration_corpus");
  mkdirp(demoRoot);

  let docsTouched = 0;
  let backendFiles = 0;
  let consensusFiles = 0;

  for (const docId of docDirs) {
    // Locate the ground-truth docling JSON for this doc. It is named
    // <doc-name>.docling.json (the doc dir name is the doc id).
    const doclingPath = path.join(corpusStagedRoot, docId, `${docId}.docling.json`);
    if (!fs.existsSync(doclingPath)) continue;
    let docling;
    try {
      docling = JSON.parse(fs.readFileSync(doclingPath, "utf-8"));
    } catch (e) {
      console.warn(`[stage-data] failed to parse ${doclingPath}: ${e}`);
      continue;
    }

    const docOut = path.join(demoRoot, docId);
    mkdirp(docOut);

    // Per-backend pages.
    for (const backend of DEMO_BACKENDS) {
      const pages = synthesiseBackendPages(docId, docling, backend);
      const backendDir = path.join(docOut, backend, "pages");
      mkdirp(backendDir);
      for (const page of pages) {
        const pageFile = path.join(
          backendDir,
          `page_${String(page.page_no).padStart(4, "0")}.json`,
        );
        fs.writeFileSync(pageFile, JSON.stringify(page, null, 2));
        backendFiles++;
      }
    }

    // Consensus IR.
    const consensus = synthesiseConsensus(docId, docling, DEMO_BACKENDS);
    fs.writeFileSync(
      path.join(docOut, "consensus_ir.json"),
      JSON.stringify(consensus, null, 2),
    );
    consensusFiles++;

    docsTouched++;
  }

  console.log(
    `[stage-data] synthesised demo data for ${docsTouched} docs: ` +
      `${backendFiles} backend-page files, ${consensusFiles} consensus IRs`,
  );
  return backendFiles + consensusFiles;
}

/**
 * Per-doc availability manifest. The DocPicker reads this once to drive
 * its status badges and filter dropdown, avoiding N HEAD probes per doc
 * on page load.
 *
 * Shape:
 *
 *   {
 *     groundtruth: {
 *       "<doc>": {
 *         hasPdf: bool,
 *         hasDocling: bool,
 *         hasBackends: string[],         // list of backends with pages
 *         hasConsensus: bool,
 *         demo_synthesized: bool         // backend+consensus were synthed
 *       },
 *       ...
 *     }
 *   }
 */
function writeAvailabilityManifest(corpusStagedRoot, demoRoot) {
  const groundtruth = {};
  if (fs.existsSync(corpusStagedRoot)) {
    for (const docId of fs.readdirSync(corpusStagedRoot)) {
      const docPath = path.join(corpusStagedRoot, docId);
      if (!fs.statSync(docPath).isDirectory()) continue;
      const doclingPath = path.join(docPath, `${docId}.docling.json`);
      const pdfPath = path.join(docPath, `${docId}.pdf`);
      const demoDocPath = path.join(demoRoot, docId);
      const backends = [];
      if (fs.existsSync(demoDocPath)) {
        for (const sub of fs.readdirSync(demoDocPath)) {
          const subPath = path.join(demoDocPath, sub);
          if (fs.statSync(subPath).isDirectory() && fs.existsSync(path.join(subPath, "pages"))) {
            backends.push(sub);
          }
        }
        backends.sort();
      }
      groundtruth[docId] = {
        hasPdf: fs.existsSync(pdfPath),
        hasDocling: fs.existsSync(doclingPath),
        hasBackends: backends,
        hasConsensus: fs.existsSync(path.join(demoDocPath, "consensus_ir.json")),
        demo_synthesized: backends.length > 0,
      };
    }
  }
  const manifest = { groundtruth };
  fs.writeFileSync(
    path.join(PUBLIC_API, "_availability.json"),
    JSON.stringify(manifest, null, 2),
  );
  return Object.keys(groundtruth).length;
}

function main() {
  console.log(`[stage-data] repo root: ${REPO_ROOT}`);
  console.log(`[stage-data] target:    ${PUBLIC_API}`);
  rmrf(PUBLIC_API);
  mkdirp(PUBLIC_API);

  let totalFiles = 0;
  for (const { src, keep } of STAGE) {
    const fullSrc = path.join(REPO_ROOT, src);
    const fullDst = path.join(PUBLIC_API, src);
    const n = copyOne(fullSrc, fullDst, keep);
    console.log(`[stage-data] ${src}: ${n} files`);
    totalFiles += n;
  }

  // Synthesise per-doc backend pages + consensus IR from the staged
  // docling JSONs. Marked demo_synthesized in the metadata.
  const corpusStagedRoot = path.join(PUBLIC_API, "groundtruth", "corpus", "latex");
  totalFiles += synthesiseDemoData(corpusStagedRoot);

  // Emit the per-doc availability manifest the DocPicker consumes.
  const demoRoot = path.join(PUBLIC_API, ".tmp", "calibration_corpus");
  const docsInManifest = writeAvailabilityManifest(corpusStagedRoot, demoRoot);
  console.log(`[stage-data] availability manifest: ${docsInManifest} docs`);

  const indexCount = writeIndexJsons(PUBLIC_API);
  console.log(`[stage-data] wrote _index.json in ${indexCount} directories`);
  console.log(`[stage-data] total artefacts staged: ${totalFiles} files`);
}

main();
