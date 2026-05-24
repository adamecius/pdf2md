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

```bash
cd webui
npm run build
# validator/dist/ is the static bundle
```

The bundle expects `/api/*` to be served alongside it. The simplest
deploy is `npx serve validator/dist` next to a static snapshot of the
ground-truth / paper-run JSONs.

---

## What the validator covers (Phase 1)

- **/compare/:docId** — four-panel view:
  1. PDF (pdf.js) with bbox overlays per block
  2. Ground-truth Docling tree
  3. Consensus IR tree
  4. Per-backend tabs (paddleocr / deepseek / mineru)
- Block hover → cross-panel highlight
- Status badges flagging `prior_factory:` vs `prior_uninformative:`
- Direct link to the underlying JSON for debugging

Phase 2 (separate PR) adds:

- **/diff/:docId** — three-way diff with PASS/FAIL stamps for
  human-verification checkpoints H3 / H4 / H5.
- **/priors** — calibration prior viewer.

---

## TypeScript type fidelity

`shared/src/types.ts` is hand-rolled to mirror the Pydantic models
under [src/pdf2md/models/](../src/pdf2md/models/). When a model
changes, update the TS type alongside it.

If/when the surface grows, switch to generated TS via a
`tools/export_json_schema.py` + `json-schema-to-typescript` pipeline.
That's a separate follow-up.
