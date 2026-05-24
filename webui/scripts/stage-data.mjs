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
 *   - src/pdf2md/data/factory_priors/*.json             factory priors
 *
 * What we deliberately exclude:
 *
 *   - .tmp/papers_run/                                   operator-local; not in git
 *   - Compiled PDFs (groundtruth/corpus/latex/<doc>/*.pdf) — most are not in
 *     git; the PdfPanel degrades gracefully when the PDF 404s.
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
      rel.endsWith(".pdf"), // ship a PDF if it happens to be in git
  },
  {
    src: "src/pdf2md/data/factory_priors",
    keep: (rel) => rel.endsWith(".json"),
  },
];

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

  const indexCount = writeIndexJsons(PUBLIC_API);
  console.log(`[stage-data] wrote _index.json in ${indexCount} directories`);
  console.log(`[stage-data] total artefacts staged: ${totalFiles} files`);
}

main();
