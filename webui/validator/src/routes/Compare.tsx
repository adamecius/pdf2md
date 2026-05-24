/**
 * /compare/:docId — four-panel side-by-side view.
 *
 *   ┌────────────┬──────────┬──────────┬───────────────┐
 *   │            │ ground   │ consensus│ per-backend   │
 *   │   PDF      │ truth    │ IR       │ tabs:         │
 *   │  (pdf.js)  │ tree     │ tree     │ paddleocr,    │
 *   │ + overlays │          │          │ deepseek,     │
 *   │            │          │          │ mineru        │
 *   └────────────┴──────────┴──────────┴───────────────┘
 *
 * The PDF and the three trees are linked: hovering a block in any
 * panel highlights the corresponding entries across all panels via a
 * shared `highlightedId` state.
 */

import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import type {
  BBox,
  ConsensusIR,
  DatasetEntry,
  DoclingDocument,
  DoclingText,
  PageExtractionIR,
} from "@pdf2md/shared";
import BlockTree, { type BlockNode } from "../components/BlockTree";
import PdfPanel, { type BlockOverlay } from "../components/PdfPanel";
import { assetUrl, listDir, tryFetchJson } from "../lib/api";
import { listDatasets } from "../lib/datasets";

// ---------------------------------------------------------------------------
// Loaders
// ---------------------------------------------------------------------------

interface CompareData {
  dataset: DatasetEntry;
  truth: DoclingDocument | null;
  consensus: ConsensusIR | null;
  backends: Record<string, PageExtractionIR[]>;
}

async function loadCompare(docId: string): Promise<CompareData> {
  // Re-discover the dataset entry (cheap, runs in parallel with the others).
  const datasets = await listDatasets();
  const dataset = datasets.find((d) => d.id === docId);
  if (!dataset) {
    throw new Error(`document not found: ${docId}`);
  }

  // Ground-truth docling JSON.
  const truth = await tryFetchJson<DoclingDocument>(dataset.doclingPath);

  // Consensus IR (only exists for papers_run; for groundtruth nothing yet).
  let consensus: ConsensusIR | null = null;
  if (dataset.source === "papers_run") {
    const tag = dataset.id.slice("run:".length);
    consensus = await tryFetchJson<ConsensusIR>(
      `/api/.tmp/papers_run/${tag}/consensus/consensus_ir.json`,
    );
  }

  // Per-backend pages. Two layouts to handle:
  //   - groundtruth calibration: .tmp/calibration_corpus/<doc>/<backend>/pages/*.json
  //   - papers_run:              .tmp/papers_run/<tag>/connector/<backend>/pages/*.json
  const backends: Record<string, PageExtractionIR[]> = {};
  if (dataset.source === "papers_run") {
    const tag = dataset.id.slice("run:".length);
    for (const backend of dataset.backends) {
      backends[backend] = await loadPages(
        `/api/.tmp/papers_run/${tag}/connector/${backend}`,
      );
    }
  } else {
    const name = dataset.id.slice("gt:".length);
    // Probe the calibration corpus path; ignore failure quietly.
    for (const backend of ["paddleocr", "deepseek", "mineru"]) {
      const pages = await loadPages(
        `/api/.tmp/calibration_corpus/${name}/${backend}`,
      );
      if (pages.length) backends[backend] = pages;
    }
  }

  return { dataset, truth, consensus, backends };
}

async function loadPages(connectorRoot: string): Promise<PageExtractionIR[]> {
  const dir = await listDir(`${connectorRoot}/pages`);
  if (!dir) return [];
  const pages: PageExtractionIR[] = [];
  for (const entry of dir.filter((e) => !e.is_dir && e.name.endsWith(".json"))) {
    const page = await tryFetchJson<PageExtractionIR>(
      `${connectorRoot}/pages/${entry.name}`,
    );
    if (page) pages.push(page);
  }
  return pages.sort((a, b) => a.page_no - b.page_no);
}

// ---------------------------------------------------------------------------
// Adapters that turn each source into BlockNode[] for the tree renderer
// ---------------------------------------------------------------------------

const DOCLING_LABEL_TO_KIND: Record<string, string> = {
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

function truthToBlocks(doc: DoclingDocument | null): BlockNode[] {
  if (!doc) return [];
  const out: BlockNode[] = [];
  for (const t of doc.texts ?? []) {
    out.push({
      id: t.self_ref,
      kind: DOCLING_LABEL_TO_KIND[t.label] ?? t.label ?? "unknown",
      page_no: t.prov?.[0]?.page_no ?? 1,
      text: t.text ?? t.orig ?? "",
      level: t.level,
    });
  }
  for (const p of doc.pictures ?? []) {
    out.push({
      id: p.self_ref,
      kind: "figure",
      page_no: p.prov?.[0]?.page_no ?? 1,
      text: "(picture)",
    });
  }
  for (const tb of doc.tables ?? []) {
    out.push({
      id: tb.self_ref,
      kind: "table",
      page_no: tb.prov?.[0]?.page_no ?? 1,
      text: "(table)",
    });
  }
  return out;
}

function consensusToBlocks(ir: ConsensusIR | null): BlockNode[] {
  if (!ir) return [];
  const out: BlockNode[] = [];
  for (const page of ir.pages) {
    for (const b of page.blocks) {
      out.push({
        id: b.id,
        kind: b.kind,
        page_no: b.page_no,
        text: b.text ?? "",
        metadata: { selection_mode: b.selection_mode, agreement_score: b.agreement_score },
      });
    }
  }
  return out;
}

function backendToBlocks(pages: PageExtractionIR[] | undefined): BlockNode[] {
  if (!pages) return [];
  const out: BlockNode[] = [];
  for (const p of pages) {
    for (const b of p.blocks) {
      out.push({
        id: b.id,
        kind: b.kind,
        page_no: b.page_no,
        text: b.text ?? "",
      });
    }
  }
  return out;
}

function bboxFromTruth(t: DoclingText): BBox | null {
  const prov = t.prov?.[0];
  if (!prov?.bbox) return null;
  return {
    l: prov.bbox.l,
    t: prov.bbox.t,
    r: prov.bbox.r,
    b: prov.bbox.b,
    coord_origin: "topleft",
  };
}

// ---------------------------------------------------------------------------
// Route component
// ---------------------------------------------------------------------------

export default function Compare() {
  const { docId } = useParams<{ docId: string }>();
  const [data, setData] = useState<CompareData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeBackend, setActiveBackend] = useState<string | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) return;
    setData(null);
    setError(null);
    setActiveBackend(null);
    loadCompare(docId)
      .then((d) => {
        setData(d);
        const backendNames = Object.keys(d.backends);
        if (backendNames.length) setActiveBackend(backendNames[0]);
      })
      .catch((e) => setError(String(e)));
  }, [docId]);

  const truthBlocks = useMemo(() => truthToBlocks(data?.truth ?? null), [data]);
  const consensusBlocks = useMemo(() => consensusToBlocks(data?.consensus ?? null), [data]);
  const backendBlocks = useMemo(
    () => backendToBlocks(activeBackend ? data?.backends[activeBackend] : undefined),
    [data, activeBackend],
  );

  // Overlays drawn on the PDF — use consensus when available, else backend, else truth.
  const overlays: BlockOverlay[] = useMemo(() => {
    if (!data) return [];
    const useConsensus = data.consensus !== null;
    if (useConsensus) {
      const out: BlockOverlay[] = [];
      for (const page of data.consensus!.pages) {
        for (const b of page.blocks) {
          out.push({
            id: b.id,
            page_no: b.page_no,
            bbox: b.bbox ?? null,
            kind: b.kind,
            colour: b.kind,
          });
        }
      }
      return out;
    }
    if (activeBackend && data.backends[activeBackend]) {
      const out: BlockOverlay[] = [];
      for (const p of data.backends[activeBackend]) {
        for (const b of p.blocks) {
          out.push({ id: b.id, page_no: b.page_no, bbox: b.bbox ?? null, kind: b.kind, colour: b.kind });
        }
      }
      return out;
    }
    // Truth-only overlay (docling.json bboxes may be empty for synthetic corpus)
    if (data.truth) {
      const out: BlockOverlay[] = [];
      for (const t of data.truth.texts ?? []) {
        const bbox = bboxFromTruth(t);
        if (bbox) {
          out.push({
            id: t.self_ref,
            page_no: t.prov?.[0]?.page_no ?? 1,
            bbox,
            kind: DOCLING_LABEL_TO_KIND[t.label] ?? "unknown",
            colour: "unknown",
          });
        }
      }
      return out;
    }
    return [];
  }, [data, activeBackend]);

  if (error) {
    return (
      <div className="p-4 text-sm text-red-700">
        <div className="font-semibold">Failed to load {docId}</div>
        <div className="mt-1 font-mono text-xs">{error}</div>
      </div>
    );
  }
  if (!data) {
    return <div className="p-4 text-sm text-slate-500">loading…</div>;
  }

  return (
    <div className="grid h-full grid-cols-12 gap-0 overflow-hidden">
      {/* PDF panel (5 cols) */}
      <div className="col-span-5 border-r border-slate-300 bg-white">
        <PdfPanel
          pdfPath={assetUrl(data.dataset.pdfPath)}
          overlays={overlays}
          highlightedId={highlightedId}
          onHover={setHighlightedId}
        />
      </div>

      {/* Ground-truth tree */}
      <div className="col-span-3 border-r border-slate-300 bg-white">
        <BlockTree
          title="Ground truth (docling)"
          subtitle={data.dataset.doclingPath.replace(/^\/api\//, "")}
          blocks={truthBlocks}
          highlightedId={highlightedId}
          onHover={setHighlightedId}
          emptyMessage="No ground-truth Docling JSON for this dataset."
        />
      </div>

      {/* Consensus tree */}
      <div className="col-span-2 border-r border-slate-300 bg-white">
        <BlockTree
          title="Consensus IR"
          subtitle={
            data.consensus
              ? `${data.consensus.page_count} pages · ${data.consensus.backends?.length ?? 0} backends`
              : "—"
          }
          blocks={consensusBlocks}
          highlightedId={highlightedId}
          onHover={setHighlightedId}
          emptyMessage="No consensus IR (groundtruth-only dataset, or pipeline not yet run)."
        />
      </div>

      {/* Per-backend tabs */}
      <div className="col-span-2 bg-white">
        <div className="flex border-b border-slate-200 bg-slate-100 text-xs">
          {Object.keys(data.backends).length === 0 && (
            <div className="px-3 py-2 text-slate-500">no backends</div>
          )}
          {Object.keys(data.backends).map((b) => (
            <button
              key={b}
              onClick={() => setActiveBackend(b)}
              className={`px-3 py-2 ${
                activeBackend === b
                  ? "border-b-2 border-amber-500 font-semibold text-amber-700"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              {b}
            </button>
          ))}
        </div>
        <div className="h-[calc(100%-30px)]">
          <BlockTree
            title={activeBackend ?? "Backend"}
            subtitle={
              activeBackend && data.backends[activeBackend]
                ? `${data.backends[activeBackend].length} pages`
                : ""
            }
            blocks={backendBlocks}
            highlightedId={highlightedId}
            onHover={setHighlightedId}
            emptyMessage="No backend output for this dataset."
          />
        </div>
      </div>
    </div>
  );
}
