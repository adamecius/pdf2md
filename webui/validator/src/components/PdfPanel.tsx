/**
 * PDF panel — renders the PDF via react-pdf (pdf.js) and overlays
 * coloured bboxes per block. Hover a bbox -> propagate the block id to
 * the parent (cross-panel highlight).
 */

import { useEffect, useMemo, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import type { BBox } from "@pdf2md/shared";

// pdf.js worker — bundled by Vite via the ?url import below.
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

export interface BlockOverlay {
  id: string;
  page_no: number;
  bbox: BBox | null | undefined;
  kind: string;
  colour: string; // tailwind colour OR raw hex
}

export interface PdfPanelProps {
  pdfPath: string;
  overlays: BlockOverlay[];
  highlightedId: string | null;
  onHover: (id: string | null) => void;
}

const KIND_HEX: Record<string, string> = {
  heading: "#2563eb",
  paragraph: "#64748b",
  caption: "#a855f7",
  formula: "#dc2626",
  figure: "#16a34a",
  table: "#ea580c",
  list_item: "#0891b2",
  list: "#0891b2",
  footnote: "#7c3aed",
  header: "#94a3b8",
  footer: "#94a3b8",
  page_number: "#94a3b8",
  reference: "#facc15",
  bibitem: "#facc15",
  code: "#475569",
  unknown: "#9ca3af",
};

export default function PdfPanel({
  pdfPath,
  overlays,
  highlightedId,
  onHover,
}: PdfPanelProps) {
  const [numPages, setNumPages] = useState(0);
  const [width, setWidth] = useState(600);

  // Pages keyed by page_no -> overlay list
  const overlaysByPage = useMemo(() => {
    const m = new Map<number, BlockOverlay[]>();
    for (const o of overlays) {
      if (!o.bbox) continue;
      const list = m.get(o.page_no) ?? [];
      list.push(o);
      m.set(o.page_no, list);
    }
    return m;
  }, [overlays]);

  useEffect(() => {
    const el = document.getElementById("pdf-panel-host");
    if (el) {
      const update = () => setWidth(el.clientWidth - 16);
      update();
      const ro = new ResizeObserver(update);
      ro.observe(el);
      return () => ro.disconnect();
    }
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
        PDF
        <span className="ml-2 text-xs font-normal text-slate-500">
          {pdfPath.replace(/^\/api\//, "")}
        </span>
      </div>
      <div
        id="pdf-panel-host"
        className="flex-1 overflow-auto bg-slate-200 p-2"
      >
        <Document
          file={pdfPath}
          onLoadSuccess={(d) => setNumPages(d.numPages)}
          onLoadError={(e) => console.error("pdf load failed", e)}
          loading={<div className="p-4 text-sm text-slate-500">loading PDF…</div>}
          error={<div className="p-4 text-sm text-red-600">PDF failed to load</div>}
        >
          {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNo) => (
            <PdfPageWithOverlays
              key={pageNo}
              pageNo={pageNo}
              width={width}
              overlays={overlaysByPage.get(pageNo) ?? []}
              highlightedId={highlightedId}
              onHover={onHover}
            />
          ))}
        </Document>
      </div>
    </div>
  );
}

function PdfPageWithOverlays({
  pageNo,
  width,
  overlays,
  highlightedId,
  onHover,
}: {
  pageNo: number;
  width: number;
  overlays: BlockOverlay[];
  highlightedId: string | null;
  onHover: (id: string | null) => void;
}) {
  const [pageWidth, setPageWidth] = useState<number | null>(null);
  const [pageHeight, setPageHeight] = useState<number | null>(null);

  return (
    <div className="relative mx-auto mb-3 shadow" style={{ width }}>
      <Page
        pageNumber={pageNo}
        width={width}
        onLoadSuccess={(p) => {
          setPageWidth(p.width);
          setPageHeight(p.height);
        }}
        renderAnnotationLayer={false}
        renderTextLayer={false}
      />
      {pageWidth !== null && pageHeight !== null && (
        <div
          className="absolute inset-0"
          style={{ width, height: (width / pageWidth) * pageHeight }}
        >
          {overlays.map((o) => {
            if (!o.bbox) return null;
            const scaleX = width / pageWidth;
            const scaleY = ((width / pageWidth) * pageHeight) / pageHeight;
            const left = o.bbox.l * scaleX;
            const top = o.bbox.t * scaleY;
            const w = (o.bbox.r - o.bbox.l) * scaleX;
            const h = (o.bbox.b - o.bbox.t) * scaleY;
            const colour = KIND_HEX[o.kind] ?? "#9ca3af";
            const isHi = highlightedId === o.id;
            return (
              <div
                key={o.id}
                className="bbox-overlay"
                style={{
                  left,
                  top,
                  width: w,
                  height: h,
                  borderColor: colour,
                  outline: isHi ? "2px solid #f59e0b" : undefined,
                  zIndex: isHi ? 10 : 1,
                }}
                onMouseEnter={() => onHover(o.id)}
                onMouseLeave={() => onHover(null)}
                title={`${o.kind} — ${o.id}`}
              >
                <span className="bbox-overlay-label" style={{ color: colour }}>
                  {o.kind}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
