# How to install an external ground-truth dataset

`pdf2md` ships with a synthetic LaTeX corpus committed in-tree. For
evaluation and calibration against richer material, you can download
opt-in external corpora via the `pdf2md datasets` CLI.

**Reference:** the full registry schema, install layout, and dataset
descriptions are in [`../reference/datasets-registry.md`](../reference/datasets-registry.md).

## Browse the registry

```bash
pdf2md datasets list
```

The three current entries are `tlc3-examples` (alias `tlc3`),
`latex-cookbook` (alias `cookbook`), and `arxiv-curated` (placeholder).

## Install

```bash
# Default location (groundtruth/external/<name>/upstream/):
pdf2md datasets install tlc3-examples

# Pick a custom output root or git ref:
pdf2md datasets install tlc3 --output /tmp/external --ref main

# See the plan without touching anything:
pdf2md datasets install tlc3 --dry-run

# Replace an existing install:
pdf2md datasets install tlc3 --force

# Install everything currently available:
pdf2md datasets install all
```

## Verify

```bash
pdf2md datasets status
```

Reports `installed`, `missing`, `not_installed`, and `not_available`
entries. The global index lives at
`groundtruth/manifest/external_datasets.json` (git-ignored).

## Re-manifest without re-downloading

If the upstream files are already on disk and you only want to refresh
`dataset.json` + `manifest.jsonl` (e.g. after a registry change):

```bash
pdf2md datasets install tlc3-examples --manifest-only
```

## What you cannot do (yet)

- **Compile** the downloaded LaTeX. `--compile`, `--limit`, and
  `--engine` are reserved flags that exit with a deferral message.
  Compilation is a future plan.
- Use installed datasets as **canonical acceptance fixtures**. They
  are evaluation candidates, not approved fixtures.

## See also

- [`../reference/datasets-registry.md`](../reference/datasets-registry.md)
  — registry schema, the per-dataset descriptors, and on-disk layout.
