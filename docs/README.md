# pdf2md Documentation

This directory is the operator manual for `pdf2md`. It follows the
[Diataxis](https://diataxis.fr/) structure:

| Section | Purpose | Read it when... |
|---------|---------|-----------------|
| [`getting-started.md`](getting-started.md) | Install + convert one PDF | You're new and want to see the package working. |
| [`tutorials/`](tutorials/) | Guided, end-to-end walkthroughs | You're learning the package and want to follow along step by step. |
| [`how-to/`](how-to/) | Task-oriented recipes | You know what you need to do and want the shortest path. |
| [`reference/`](reference/) | Contracts, schemas, CLI flags | You're looking up exact behaviour. |
| [`explanation/`](explanation/) | Architecture and design rationale | You want to understand *why* the pipeline is the way it is. |

**Source-of-truth files outside this directory:**

- [`../README.md`](../README.md) — public entry point, project overview.
- [`../project.md`](../project.md) — durable architecture description.
- [`../ROADMAP.md`](../ROADMAP.md) — product roadmap and phases.
- [`../history.md`](../history.md) — completed-milestone log.
- [`../current_plan.md`](../current_plan.md) — active execution contract for agents.
- [`../agent.md`](../agent.md) — LLM-agent governance protocol.

Files under `docs/` are intended for operators and contributors. They
must not duplicate the canonical sources above — they link to them
instead.

---

## Tutorials

Learning-oriented. Follow them in order.

1. [01 — Set up backends](tutorials/01-setup-backends.md)
2. [02 — Convert your first PDF](tutorials/02-first-conversion.md)
3. [03 — Calibrate consensus priors on the LaTeX ground-truth corpus](tutorials/03-calibrate-priors-on-corpus.md)
4. [04 — Batch processing and multi-backend consensus](tutorials/04-batch-processing.md)

## How-to guides

Recipes for specific tasks.

- [Install external ground-truth datasets](how-to/install-external-datasets.md)
- [Update factory-shipped calibration priors](how-to/update-factory-priors.md)
- [Troubleshoot local runs](how-to/troubleshoot-local-runs.md)

## Reference

Authoritative descriptions of contracts and CLI surfaces.

- [Calibration priors and the three-level fallback](reference/calibration-priors.md)
- [External datasets registry](reference/datasets-registry.md)
- [Export formats (Docling, RAG, Markdown)](reference/export-formats.md)

## Explanation

Why the pipeline is shaped this way.

- [Pipeline stages](explanation/pipeline-stages.md)
