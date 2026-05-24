# pdf2md Web UIs

This directory holds the frontend(s) that support **human validation** of
pdf2md outputs. Today it ships one app: **`validator/`**, a static SPA
that lets a human compare PDFs against ground truth, consensus, and each
backend's per-block output side-by-side.

A future `viewer/` (separate sub-app, separate PR) will offer the
"upload a paper, see its Docling graph" public flow.

---

## Hard isolation from the `pdf2md` Python package

- The `pdf2md` wheel built from the repo's [pyproject.toml](../pyproject.toml)
  does **not** include this directory.
- This directory imports **zero** Python code. It reads JSON / PDF
  artefacts the pipeline already writes to disk.
- The future `viewer/server/` will be its **own** Python project with
  its own `pyproject.toml`, calling `pdf2md convert` via subprocess —
  not via Python import.

---

## Directory layout

```text
webui/
├── package.json          npm workspaces: shared, validator
├── README.md             you are here
├── .gitignore            node_modules / dist / etc.
│
├── shared/               TS types + shared components
│   ├── package.json
│   └── src/
│       ├── index.ts
│       └── types.ts      mirrors src/pdf2md/models/* (hand-rolled)
│
└── validator/            Phase 1 — human validation SPA
    ├── package.json
    ├── vite.config.ts    serves /api/* from the repo root
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── lib/
        │   ├── api.ts          fetch helpers
        │   └── datasets.ts     dataset discovery
        ├── components/
        │   ├── DocSelector.tsx
        │   ├── PdfPanel.tsx    pdf.js + bbox overlay
        │   └── BlockTree.tsx   docling-style tree renderer
        └── routes/
            └── Compare.tsx     4-panel: PDF | truth | consensus | backend
```

---

## Requirements

- **Node.js ≥ 18** (Vite 5 requires it)
- **npm ≥ 9** (workspaces v3)

Verify:

```bash
node --version  # v18 or later
npm  --version  # 9 or later
```

If your system Node is older, the simplest fix is
[`nvm`](https://github.com/nvm-sh/nvm):

```bash
nvm install 20
nvm use 20
```

---

## Quickstart

```bash
# from the repo root
cd webui
npm install               # installs validator + shared
npm run dev               # starts the validator at http://localhost:5173/
```

Open the URL. Pick a ground-truth fixture from the dropdown
(populated from `groundtruth/corpus/latex/`). Each compare panel
fetches its data from `/api/*`, served by the Vite middleware in
[validator/vite.config.ts](validator/vite.config.ts) directly from
the repo root (no separate backend process).

To compare a paper run (e.g. `.tmp/papers_run/example01/`), add the
tag to the source list in
[validator/src/lib/datasets.ts](validator/src/lib/datasets.ts).

---

## Build for sharing

The `build` script first runs `stage-data` (copies the repo artefacts
the SPA reads at runtime into `validator/public/api/` and writes
`_index.json` manifests for each directory), then runs Vite's static
build.

```bash
cd webui
npm run build                      # validator/dist/ is the static bundle
npm run preview                    # serve dist/ at http://localhost:4173/
```

The resulting `dist/` is fully self-contained — `dist/api/` carries
the JSON the SPA fetches at runtime, so the deploy needs **no backend**
of any kind.

What ships in the static bundle (see `webui/scripts/stage-data.mjs` for
the source-of-truth filter list):

| Path                                       | Source                                            |
|--------------------------------------------|---------------------------------------------------|
| `api/groundtruth/corpus/latex/<doc>/*.json`| ground-truth `.docling.json` + meta               |
| `api/src/pdf2md/data/factory_priors/*.json`| factory priors (paddleocr / mineru / deepseek)    |
| `api/**/_index.json`                       | per-directory manifests (replace dynamic listing) |

What does **not** ship in the static bundle (intentionally):

- `.tmp/papers_run/` — operator-local pipeline runs.
- Compiled PDFs from `groundtruth/corpus/latex/<doc>/*.pdf` — not in git.
  The PDF panel degrades gracefully ("PDF failed to load").
- External corpora under `groundtruth/external/` — opt-in, not in git.

---

## Deploy to GitHub Pages

A GitHub Actions workflow is wired up at
[`.github/workflows/deploy-validator.yml`](../.github/workflows/deploy-validator.yml).

It:

1. Triggers on pushes to `main` that touch `webui/**`,
   `groundtruth/corpus/latex/**`,
   `src/pdf2md/data/factory_priors/**`, or the workflow file itself.
2. Runs `npm run build:pages` (stages data + `vite build` with
   `VITE_BASE=/<repo>/`).
3. Uploads `webui/validator/dist/` as a Pages artifact.
4. Deploys it to the `github-pages` environment.

### One-time GitHub setup

1. Go to **Settings → Pages** on the repo on GitHub.
2. Under **Source**, select **GitHub Actions** (not "Deploy from a branch").
3. Push the workflow file (this PR does that). The next push to `main`
   that touches a watched path will publish to
   `https://<owner>.github.io/<repo>/`.
4. Trigger a first deploy manually via the **Actions** tab →
   "Deploy validator to GitHub Pages" → **Run workflow**.

### Local dry-run

To verify the production bundle before pushing:

```bash
cd webui
VITE_BASE=/pdf2md/ npm run build:pages
npm run preview                    # http://localhost:4173/pdf2md/
```

The preview server respects the base path, so the URL matches what
GitHub Pages will serve.

---

## What the validator covers

Three routes live in the SPA today:

- **`/compare/:docId`** — four-panel view:
  1. PDF (pdf.js) with bbox overlays per block
  2. Ground-truth Docling tree
  3. Consensus IR tree
  4. Per-backend tabs (paddleocr / deepseek / mineru)
  Block hover propagates a cross-panel highlight.
- **`/priors`** — calibration prior viewer. Reads the factory priors
  shipped at `src/pdf2md/data/factory_priors/<backend>.json` and shows
  per-BlockKind / EntityType / RelationType / calibration-key metrics
  (precision, recall, F1, calibrated confidence, status).
- **`/checkpoints`** — H1–H6 human-verification reference. Each
  checkpoint lists what it asserts, the exact command to run it, the
  source file the assertion lives in, and current status. The UI does
  not execute commands — keeping the static-bundle (no-server) promise
  intact.

---

## TypeScript type fidelity

`shared/src/types.ts` is hand-rolled to mirror the Pydantic models
under [src/pdf2md/models/](../src/pdf2md/models/). When a model
changes, update the TS type alongside it.

If/when the surface grows, switch to generated TS via a
`tools/export_json_schema.py` + `json-schema-to-typescript` pipeline.
That's a separate follow-up.
