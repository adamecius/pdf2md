import { Link, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { listDatasets } from "./lib/datasets";
import type { DatasetEntry } from "@pdf2md/shared";
import Compare from "./routes/Compare";

function Layout(props: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-slate-300 bg-white px-4 py-2 shadow-sm">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-lg font-semibold text-slate-800">
            pdf2md validator
          </Link>
          <span className="text-xs text-slate-500">phase 1 / compare</span>
        </div>
        <DocPicker />
      </header>
      <main className="flex-1 overflow-hidden">{props.children}</main>
    </div>
  );
}

function DocPicker() {
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const navigate = useNavigate();
  const params = useParams<{ docId?: string }>();

  useEffect(() => {
    listDatasets()
      .then(setDatasets)
      .catch((e) => console.error("listDatasets failed", e));
  }, []);

  return (
    <select
      className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
      value={params.docId ?? ""}
      onChange={(e) => navigate(`/compare/${encodeURIComponent(e.target.value)}`)}
    >
      <option value="" disabled>
        — pick a document —
      </option>
      {datasets.map((d) => (
        <option key={d.id} value={d.id}>
          [{d.source}] {d.label}
        </option>
      ))}
    </select>
  );
}

function Welcome() {
  return (
    <div className="prose mx-auto max-w-2xl p-8 text-slate-700">
      <h2 className="mt-0 text-xl font-semibold">Welcome</h2>
      <p>
        Pick a document from the dropdown to open its compare view. The
        validator reads JSON straight from the repo via the Vite dev
        middleware — there is no separate backend.
      </p>
      <ul className="list-disc pl-6 text-sm">
        <li>
          <code>[groundtruth]</code> docs come from{" "}
          <code>groundtruth/corpus/latex/</code>.
        </li>
        <li>
          <code>[papers_run]</code> docs come from{" "}
          <code>.tmp/papers_run/</code> (whatever the pipeline last
          wrote there).
        </li>
      </ul>
    </div>
  );
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/compare/:docId" element={<Compare />} />
      </Routes>
    </Layout>
  );
}
