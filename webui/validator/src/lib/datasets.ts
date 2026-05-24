/**
 * Discovery of available documents for the compare view.
 *
 * Two sources today:
 *
 *   1. Ground-truth corpus under groundtruth/corpus/latex/<doc>/
 *      Each entry must have <doc>.docling.json and <doc>.pdf.
 *
 *   2. Paper runs under .tmp/papers_run/<tag>/
 *      Each entry must have raw/<backend>/<pdf>, connector/<backend>/,
 *      and consensus/consensus_ir.json.
 *
 * The Vite dev middleware exposes both prefixes under /api/.
 *
 * On the static (GitHub Pages) deploy, per-doc availability is read once
 * from `/api/_availability.json` written by `webui/scripts/stage-data.mjs`.
 * That avoids one HEAD probe per doc-per-backend-per-feature.
 */

import type { AvailabilityManifest, DatasetAvailability, DatasetEntry } from "@pdf2md/shared";
import { fetchJson, listDir, tryFetchJson } from "./api";

interface DirEntry {
  name: string;
  is_dir: boolean;
}

const EMPTY_AVAILABILITY: DatasetAvailability = {
  hasPdf: false,
  hasDocling: false,
  hasBackends: [],
  hasConsensus: false,
  demo_synthesized: false,
};

let _manifestCache: AvailabilityManifest | null | undefined;

async function fetchAvailabilityManifest(): Promise<AvailabilityManifest | null> {
  if (_manifestCache !== undefined) return _manifestCache;
  _manifestCache = await tryFetchJson<AvailabilityManifest>("/api/_availability.json");
  return _manifestCache;
}

/** Per-doc descriptor — what the UI knows about a single document. */
async function describeGroundtruth(
  name: string,
  manifest: AvailabilityManifest | null,
): Promise<DatasetEntry | null> {
  const base = `/api/groundtruth/corpus/latex/${name}`;
  const docling = `${base}/${name}.docling.json`;
  const pdf = `${base}/${name}.pdf`;
  // Sniff the docling.json to confirm it's a real document.
  const ok = await tryFetchJson<unknown>(docling);
  if (!ok) return null;
  const availability =
    manifest?.groundtruth?.[name] ?? {
      ...EMPTY_AVAILABILITY,
      hasDocling: true,
    };
  return {
    id: `gt:${name}`,
    label: name,
    pdfPath: pdf,
    doclingPath: docling,
    source: "groundtruth",
    backends: availability.hasBackends,
    availability,
  };
}

async function describePaperRun(tag: string): Promise<DatasetEntry | null> {
  const base = `/api/.tmp/papers_run/${tag}`;
  // Discover the input PDF.
  const inputDir = await listDir(`${base}/input`);
  if (!inputDir) return null;
  const pdfEntry = inputDir.find((e: DirEntry) => !e.is_dir && e.name.endsWith(".pdf"));
  if (!pdfEntry) return null;
  // Discover backends with connector output.
  const connectorDir = await listDir(`${base}/connector`);
  const backends = (connectorDir ?? [])
    .filter((e: DirEntry) => e.is_dir)
    .map((e: DirEntry) => e.name);
  return {
    id: `run:${tag}`,
    label: `${tag} (${pdfEntry.name})`,
    pdfPath: `${base}/input/${pdfEntry.name}`,
    doclingPath: `${base}/export/docling/docling.json`,
    source: "papers_run",
    backends,
    availability: {
      hasPdf: true,
      hasDocling: true,
      hasBackends: backends,
      hasConsensus: true,
      demo_synthesized: false,
    },
  };
}

export async function listDatasets(): Promise<DatasetEntry[]> {
  const out: DatasetEntry[] = [];
  const manifest = await fetchAvailabilityManifest();

  // Ground truth — list the corpus directory.
  const corpus = await listDir("/api/groundtruth/corpus/latex");
  if (corpus) {
    const docs = corpus.filter((e: DirEntry) => e.is_dir);
    const described = await Promise.all(docs.map((d) => describeGroundtruth(d.name, manifest)));
    for (const d of described) if (d) out.push(d);
  }

  // Paper runs — .tmp/papers_run/ may not exist on a fresh checkout (and
  // is intentionally absent from the static GitHub Pages bundle).
  const runs = await listDir("/api/.tmp/papers_run");
  if (runs) {
    const dirs = runs.filter((e: DirEntry) => e.is_dir);
    const described = await Promise.all(dirs.map((d) => describePaperRun(d.name)));
    for (const d of described) if (d) out.push(d);
  }

  // Sort: papers_run first (active investigations), then groundtruth alphabetically.
  return out.sort((a, b) => {
    if (a.source !== b.source) return a.source === "papers_run" ? -1 : 1;
    return a.label.localeCompare(b.label);
  });
}

export async function loadGroundtruthDocling(name: string) {
  return fetchJson(`/api/groundtruth/corpus/latex/${name}/${name}.docling.json`);
}
