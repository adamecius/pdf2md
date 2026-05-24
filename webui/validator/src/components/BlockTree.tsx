/**
 * Generic tree renderer for the three "block list" panels in the
 * compare view (truth, consensus, per-backend). Each block has at
 * least an id, kind, page_no and text; the hover handlers wire up
 * cross-panel highlighting.
 */

import { useMemo } from "react";

export interface BlockNode {
  id: string;
  kind: string;
  page_no: number;
  text?: string | null;
  level?: number;          // for headings — optional indent hint
  metadata?: Record<string, unknown>;
}

export interface BlockTreeProps {
  title: string;
  subtitle?: string;
  blocks: BlockNode[];
  highlightedId: string | null;
  onHover: (id: string | null) => void;
  emptyMessage?: string;
}

const KIND_COLOUR: Record<string, string> = {
  heading: "text-blue-700",
  paragraph: "text-slate-700",
  caption: "text-purple-700",
  formula: "text-red-700",
  figure: "text-green-700",
  table: "text-orange-700",
  list_item: "text-cyan-700",
  list: "text-cyan-700",
  footnote: "text-violet-700",
  header: "text-slate-500",
  footer: "text-slate-500",
  page_number: "text-slate-500",
  reference: "text-yellow-700",
  bibitem: "text-yellow-700",
  code: "text-slate-600",
  unknown: "text-slate-400",
};

function shorten(text: string, n: number): string {
  if (text.length <= n) return text;
  return text.slice(0, n - 1) + "…";
}

export default function BlockTree({
  title,
  subtitle,
  blocks,
  highlightedId,
  onHover,
  emptyMessage,
}: BlockTreeProps) {
  const grouped = useMemo(() => {
    const map = new Map<number, BlockNode[]>();
    for (const b of blocks) {
      const list = map.get(b.page_no) ?? [];
      list.push(b);
      map.set(b.page_no, list);
    }
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  }, [blocks]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-slate-100 px-3 py-2">
        <div className="text-sm font-semibold text-slate-700">{title}</div>
        {subtitle && (
          <div className="text-xs text-slate-500">{subtitle}</div>
        )}
        <div className="text-[10px] text-slate-400">{blocks.length} blocks</div>
      </div>
      <div className="flex-1 overflow-auto px-3 py-2 font-mono text-xs">
        {blocks.length === 0 && (
          <div className="text-slate-400">
            {emptyMessage ?? "(no blocks)"}
          </div>
        )}
        {grouped.map(([page, items]) => (
          <div key={page} className="mb-3">
            <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-400">
              page {page}
            </div>
            {items.map((b) => {
              const colour = KIND_COLOUR[b.kind] ?? "text-slate-700";
              const indent = b.level ? Math.min(b.level - 1, 5) : 0;
              const isHi = highlightedId === b.id;
              return (
                <div
                  key={b.id}
                  data-block-highlight={isHi ? "true" : undefined}
                  onMouseEnter={() => onHover(b.id)}
                  onMouseLeave={() => onHover(null)}
                  className="cursor-default rounded px-1 py-0.5 hover:bg-amber-50"
                  style={{ paddingLeft: `${indent * 12 + 4}px` }}
                  title={b.text ?? ""}
                >
                  <span className={`mr-2 font-semibold ${colour}`}>
                    {b.kind}
                  </span>
                  <span className="text-slate-600">
                    {shorten(b.text ?? "", 80)}
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
