/**
 * /priors — calibration prior viewer.
 *
 * Reads the factory priors that ship with the package and renders each
 * backend's per-BlockKind, per-EntityType, per-RelationType, and
 * per-calibration-key metrics. Operators land here to answer "what
 * confidence does the factory prior assign to <backend>'s <kind>
 * detection?" without leaving the browser.
 *
 * Data source:
 *   /api/src/pdf2md/data/factory_priors/<backend>.json   (read-only)
 *
 * Visible in the deployed bundle because the staging script
 * (webui/scripts/stage-data.mjs) copies the factory priors into
 * validator/public/api/.
 */

import { useEffect, useMemo, useState } from "react";
import type {
  CalibrationMetric,
  CalibrationPriorDocument,
  CalibrationStatus,
} from "@pdf2md/shared";
import { listDir, tryFetchJson } from "../lib/api";

interface BackendPriorRow {
  backend: string;
  doc: CalibrationPriorDocument | null;
  level: "factory" | "uninformative" | "missing";
}

function statusBadge(status: CalibrationStatus): string {
  switch (status) {
    case "calibrated":
      return "bg-emerald-100 text-emerald-800";
    case "underpowered":
      return "bg-amber-100 text-amber-800";
    case "uninformative":
      return "bg-slate-200 text-slate-700";
    case "no_samples":
    default:
      return "bg-rose-100 text-rose-800";
  }
}

function priorLevel(doc: CalibrationPriorDocument | null): "factory" | "uninformative" | "missing" {
  if (!doc) return "missing";
  const md = (doc.metadata ?? {}) as Record<string, unknown>;
  const source = String(md["source"] ?? "");
  if (source.includes("uninformative")) return "uninformative";
  return "factory";
}

function MetricTable({
  title,
  metrics,
}: {
  title: string;
  metrics: CalibrationMetric[];
}) {
  if (!metrics.length) return null;
  return (
    <div className="mb-4">
      <h4 className="mb-1 text-sm font-semibold text-slate-700">{title}</h4>
      <div className="overflow-hidden rounded border border-slate-200">
        <table className="w-full text-xs">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="px-2 py-1 text-left">key</th>
              <th className="px-2 py-1 text-right">support</th>
              <th className="px-2 py-1 text-right">precision</th>
              <th className="px-2 py-1 text-right">recall</th>
              <th className="px-2 py-1 text-right">F1</th>
              <th className="px-2 py-1 text-right">cal_conf</th>
              <th className="px-2 py-1 text-center">status</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={`${m.target}:${m.key}`} className="border-t border-slate-100">
                <td className="px-2 py-1 font-mono">{m.key}</td>
                <td className="px-2 py-1 text-right">{m.support}</td>
                <td className="px-2 py-1 text-right">{m.precision.toFixed(3)}</td>
                <td className="px-2 py-1 text-right">{m.recall.toFixed(3)}</td>
                <td className="px-2 py-1 text-right">{m.f1.toFixed(3)}</td>
                <td className="px-2 py-1 text-right font-semibold">
                  {m.calibrated_confidence.toFixed(3)}
                </td>
                <td className="px-2 py-1 text-center">
                  <span className={`rounded px-2 py-0.5 ${statusBadge(m.status)}`}>{m.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Priors() {
  const [rows, setRows] = useState<BackendPriorRow[]>([]);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const dir = await listDir("/api/src/pdf2md/data/factory_priors");
      const candidates = (dir ?? [])
        .filter((e) => !e.is_dir && e.name.endsWith(".json"))
        .map((e) => e.name.replace(/\.json$/, ""));
      const out: BackendPriorRow[] = [];
      for (const backend of candidates) {
        const doc = await tryFetchJson<CalibrationPriorDocument>(
          `/api/src/pdf2md/data/factory_priors/${backend}.json`,
        );
        out.push({ backend, doc, level: priorLevel(doc) });
      }
      setRows(out);
      if (out.length) setActive(out[0].backend);
    })();
  }, []);

  const activeRow = useMemo(
    () => rows.find((r) => r.backend === active) ?? null,
    [rows, active],
  );

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-slate-100 px-4 py-2">
        <div className="text-sm font-semibold text-slate-700">Calibration priors</div>
        <div className="text-xs text-slate-500">
          Factory priors loaded by{" "}
          <code className="rounded bg-slate-200 px-1">pdf2md.models.priors.load_factory_prior</code>
          . Per-backend metrics: precision, recall, F1, calibrated confidence (beta-smoothed),
          and status.
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="p-4 text-sm text-slate-500">loading priors…</div>
      ) : (
        <div className="grid h-[calc(100%-50px)] grid-cols-12">
          <div className="col-span-3 overflow-auto border-r border-slate-200 bg-white">
            <ul>
              {rows.map((r) => (
                <li key={r.backend}>
                  <button
                    onClick={() => setActive(r.backend)}
                    className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm ${
                      active === r.backend ? "bg-amber-50 font-semibold text-amber-800" : "hover:bg-slate-50"
                    }`}
                  >
                    <span>{r.backend}</span>
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        r.level === "factory"
                          ? "bg-emerald-100 text-emerald-700"
                          : r.level === "uninformative"
                          ? "bg-slate-200 text-slate-600"
                          : "bg-rose-100 text-rose-700"
                      }`}
                    >
                      {r.level}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div className="col-span-9 overflow-auto bg-slate-50 p-4">
            {activeRow ? (
              <>
                <div className="mb-3 text-sm text-slate-600">
                  Backend{" "}
                  <code className="rounded bg-slate-200 px-1 font-semibold">{activeRow.backend}</code>{" "}
                  · schema{" "}
                  <code className="rounded bg-slate-200 px-1">
                    {activeRow.doc?.schema_name ?? "—"}
                  </code>{" "}
                  · default conf{" "}
                  <code className="rounded bg-slate-200 px-1">
                    {activeRow.doc?.default_confidence?.toFixed(2) ?? "—"}
                  </code>
                </div>
                {activeRow.doc ? (
                  <>
                    <MetricTable
                      title="block_kind_priors"
                      metrics={activeRow.doc.block_kind_priors ?? []}
                    />
                    <MetricTable
                      title="entity_type_priors"
                      metrics={activeRow.doc.entity_type_priors ?? []}
                    />
                    <MetricTable
                      title="relation_type_priors"
                      metrics={activeRow.doc.relation_type_priors ?? []}
                    />
                    <MetricTable
                      title="calibration_key_priors"
                      metrics={activeRow.doc.calibration_key_priors ?? []}
                    />
                  </>
                ) : (
                  <div className="text-sm text-slate-500">
                    No factory prior for this backend.
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-slate-500">Pick a backend on the left.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
