import { Link, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { listDatasets } from "./lib/datasets";
import type { DatasetEntry } from "@pdf2md/shared";
import Compare from "./routes/Compare";
import Priors from "./routes/Priors";
import Checkpoints from "./routes/Checkpoints";

const navLinkBase = "rounded px-2 py-1 text-xs font-semibold transition-colors";
const navLinkInactive = "text-slate-500 hover:bg-slate-100 hover:text-slate-800";
const navLinkActive = "bg-amber-100 text-amber-800";

function Layout(props: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-4 border-b border-slate-300 bg-white px-4 py-2 shadow-sm">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-lg font-semibold text-slate-800">
            pdf2md validator
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `${navLinkBase} ${isActive ? navLinkActive : navLinkInactive}`
              }
            >
              welcome
            </NavLink>
            <NavLink
              to="/priors"
              className={({ isActive }) =>
                `${navLinkBase} ${isActive ? navLinkActive : navLinkInactive}`
              }
            >
              priors
            </NavLink>
            <NavLink
              to="/checkpoints"
              className={({ isActive }) =>
                `${navLinkBase} ${isActive ? navLinkActive : navLinkInactive}`
              }
            >
              checkpoints
            </NavLink>
          </nav>
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
  const isProd = import.meta.env.PROD;
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-8 text-slate-700">
      <section>
        <h2 className="mt-0 text-xl font-semibold">pdf2md validator</h2>
        <p className="text-sm">
          Static, no-server SPA for inspecting <code>pdf2md</code> pipeline
          outputs. Three top-level views:
        </p>
        <ul className="mt-3 space-y-2 text-sm">
          <li>
            <Link to="/compare/" className="font-semibold text-amber-700 hover:underline">
              compare
            </Link>{" "}
            — pick a document from the dropdown to see PDF + ground-truth tree +
            consensus IR + per-backend output side-by-side.
          </li>
          <li>
            <Link to="/priors" className="font-semibold text-amber-700 hover:underline">
              priors
            </Link>{" "}
            — calibration prior viewer (the factory priors shipped with the
            package, plus their status / support / calibrated-confidence per
            BlockKind &amp; EntityType).
          </li>
          <li>
            <Link to="/checkpoints" className="font-semibold text-amber-700 hover:underline">
              checkpoints
            </Link>{" "}
            — the H1–H6 human-verification reference: what each manual test
            asserts and the command to run it locally.
          </li>
        </ul>
      </section>

      <section className="rounded border border-slate-200 bg-slate-50 p-4 text-sm">
        <h3 className="mt-0 mb-2 text-sm font-semibold text-slate-800">
          Data sources
        </h3>
        <ul className="list-disc space-y-1 pl-6">
          <li>
            <code>[groundtruth]</code> documents come from{" "}
            <code>groundtruth/corpus/latex/</code>.
          </li>
          <li>
            <code>[papers_run]</code> documents come from{" "}
            <code>.tmp/papers_run/</code>{" "}
            {isProd ? "(not bundled in the static deploy — run locally)" : "(local pipeline runs)"}.
          </li>
          <li>
            Factory priors come from{" "}
            <code>src/pdf2md/data/factory_priors/</code>.
          </li>
        </ul>
      </section>

      {isProd && (
        <section className="rounded border border-amber-300 bg-amber-50 p-4 text-sm">
          <h3 className="mt-0 mb-2 text-sm font-semibold text-amber-900">
            Demo mode (GitHub Pages)
          </h3>
          <p className="mb-2">
            This deploy ships a snapshot of the ground-truth corpus and the
            factory priors. The PDFs themselves are not in git, so the PDF
            panel may show "PDF failed to load" — compile the corpus locally
            via <code>tools/compile_latex_groundth.py</code> for the full
            experience.
          </p>
          <p>
            For consensus / per-backend output, run the local pipeline (
            <code>tools/run_mvp_pipeline.py</code>) and use{" "}
            <code>npm --workspace validator run dev</code> from the repo.
          </p>
        </section>
      )}
    </div>
  );
}

function ComparePlaceholder() {
  return (
    <div className="mx-auto max-w-xl p-8 text-sm text-slate-600">
      Pick a document from the dropdown above to open its compare view.
    </div>
  );
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/compare/" element={<ComparePlaceholder />} />
        <Route path="/compare/:docId" element={<Compare />} />
        <Route path="/priors" element={<Priors />} />
        <Route path="/checkpoints" element={<Checkpoints />} />
      </Routes>
    </Layout>
  );
}
