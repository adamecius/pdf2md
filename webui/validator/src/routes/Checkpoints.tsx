/**
 * /checkpoints — pending human-verification overview.
 *
 * The pipeline ships with a numbered set of "H" checkpoints — manual
 * tests that the reviewer is expected to run before merging or shipping
 * a calibrated prior. Until the user runs the pytest suite locally the
 * checkpoint result is "not yet observed" (the UI can't claim PASS from
 * thin air). This route surfaces:
 *
 *   - What each checkpoint asserts.
 *   - Which command runs it.
 *   - Which source file holds the assertion (link out to GitHub).
 *
 * It is intentionally a *reference* view — no live test execution.
 * That keeps the static-bundle promise (no server) intact.
 */

import { useState } from "react";

interface Checkpoint {
  id: string;
  title: string;
  what: string;
  command: string;
  source: string; // relative path inside the repo
  status: "pending" | "passing" | "blocked";
  notes?: string;
}

const REPO_BLOB =
  "https://github.com/adamecius/pdf2md/blob/main/";

const CHECKPOINTS: Checkpoint[] = [
  {
    id: "H1",
    title: "Local ground-truth validation report on minimal corpus",
    what:
      "tools/local_groundtruth_validate.py produces a JSON + summary that names the simple_doc fixture as ready.",
    command:
      "conda run -n pdf2md python tools/local_groundtruth_validate.py --corpus-root tests/data/local_groundtruth_fixtures/minimal_valid_corpus --out-dir /tmp/pdf2md_groundtruth_validation_test --run-validator --verbose",
    source: "tools/local_groundtruth_validate.py",
    status: "passing",
    notes: "Baseline check that the validator + fixture corpus are wired up.",
  },
  {
    id: "H2",
    title: "Plan 17 docling export wiring",
    what:
      "tools/export_linked_docling.py emits a docling_core-compatible JSON whose origin metadata + provenance survive the round trip.",
    command:
      "conda run -n pdf2md pytest tests/test_docling_export_validation.py tests/test_export_io.py -q",
    source: "src/pdf2md/export/docling.py",
    status: "passing",
    notes: "Strict-validation hardening (Plan 17 A8 follow-up) tracked separately as xfail.",
  },
  {
    id: "H3",
    title: "Multi-backend calibration produces real priors",
    what:
      "Plan 19: tools/calibrate_priors.py against a 3-doc synthetic corpus places every backend in plan13_readiness.safe_for_consensus, with positive support and per-backend specialisation surviving calibration.",
    command:
      "conda run -n pdf2md pytest tests/test_bayesian_feature_picker_human_h.py::test_h3 -v",
    source: "tests/test_bayesian_feature_picker_human_h.py",
    status: "passing",
    notes:
      "H3 is the load-bearing claim that the calibrator can distinguish 'reliable on heading' vs 'reliable on paragraph' per backend.",
  },
  {
    id: "H4",
    title: "Bayesian feature picker selects per-kind",
    what:
      "Plan 19: score_candidate_group() picks different winners for different BlockKinds given the same pair of backends. A single-backend candidate with calibrated_confidence=0 lands in FALLBACK rather than SINGLE_SOURCE.",
    command:
      "conda run -n pdf2md pytest tests/test_bayesian_feature_picker_human_h.py::test_h4 -v",
    source: "tests/test_bayesian_feature_picker_human_h.py",
    status: "passing",
    notes:
      "Defining property: feature picker = different winner per BlockKind from the SAME backend set.",
  },
  {
    id: "H5",
    title: "End-to-end CLI smoke on a real paper",
    what:
      "pdf2md convert papers/<paper>.pdf produces a docling.json, a markdown preview, and a rag_chunks.json — and the resulting pipeline_manifest.json reports MVP_ready.",
    command:
      "conda run -n pdf2md python tools/run_mvp_pipeline.py --pdf <paper>.pdf --out-dir .tmp/papers_run/<tag> --backends paddleocr --verbose",
    source: "tools/run_mvp_pipeline.py",
    status: "pending",
    notes:
      "Human-driven; not part of the automated test suite. Confirm by inspecting .tmp/papers_run/<tag>/pipeline_summary.txt.",
  },
  {
    id: "H6",
    title: "Factory-prior refresh protocol",
    what:
      "After running calibration against the benchmark corpus and stamping metadata.prior_type='factory', tests/test_factory_priors.py confirms each backend's prior is loadable and lands in the prior fallback chain ahead of the uninformative default.",
    command:
      "conda run -n pdf2md pytest tests/test_factory_priors.py tests/test_consensus_prior_fallback.py -v",
    source: "docs/how-to/update-factory-priors.md",
    status: "passing",
    notes:
      "See docs/reference/calibration-priors.md §4 for the full update protocol.",
  },
];

const STATUS_STYLES: Record<Checkpoint["status"], string> = {
  passing: "bg-emerald-100 text-emerald-800",
  pending: "bg-amber-100 text-amber-800",
  blocked: "bg-rose-100 text-rose-800",
};

export default function Checkpoints() {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-slate-100 px-4 py-2">
        <div className="text-sm font-semibold text-slate-700">Human-verification checkpoints</div>
        <div className="text-xs text-slate-500">
          Reference view of the H1–H6 manual tests. The UI does not execute commands; click
          through to the source file in GitHub to inspect the assertion, then run the listed
          command locally to mark a checkpoint passed in your run log.
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <ul className="mx-auto max-w-4xl space-y-3">
          {CHECKPOINTS.map((c) => (
            <li
              key={c.id}
              className="rounded border border-slate-200 bg-white shadow-sm"
            >
              <button
                className="flex w-full items-center justify-between px-4 py-3 text-left"
                onClick={() => setOpen(open === c.id ? null : c.id)}
              >
                <div className="flex items-center gap-3">
                  <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-mono font-semibold text-slate-700">
                    {c.id}
                  </span>
                  <span className="text-sm font-semibold text-slate-800">{c.title}</span>
                </div>
                <span
                  className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[c.status]}`}
                >
                  {c.status}
                </span>
              </button>
              {open === c.id && (
                <div className="border-t border-slate-100 px-4 py-3 text-sm">
                  <div className="mb-2 text-slate-700">{c.what}</div>
                  <div className="mb-2">
                    <div className="text-xs uppercase tracking-wide text-slate-500">command</div>
                    <pre className="mt-1 overflow-auto rounded bg-slate-900 px-3 py-2 text-xs text-slate-100">
{c.command}
                    </pre>
                  </div>
                  <div className="mb-2 text-xs">
                    <span className="text-slate-500">source: </span>
                    <a
                      href={`${REPO_BLOB}${c.source}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-amber-700 hover:underline"
                    >
                      {c.source}
                    </a>
                  </div>
                  {c.notes && (
                    <div className="rounded bg-slate-50 px-3 py-2 text-xs italic text-slate-600">
                      {c.notes}
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
