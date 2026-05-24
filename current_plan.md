# Additional Plan 1: External Ground-Truth Dataset Downloaders

## Status: active
## Date: 2026-05-24
## Depends on: Plan 008_0 (human_verified, archived as M23)

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Branch name:
plan-add1-external-dataset-downloaders

Source plan:
plans/additional_plan-1-external-dataset-downloaders.md

---

## 1. Goal

Add an opt-in CLI workflow that lets users download, position, and
manifest selected external LaTeX source corpora for later local
compilation and backend evaluation. The Plans 004-008 semantic chain
is complete; this Additional Plan extends the ground-truth surface
with third-party datasets without changing any backend, pipeline, or
existing semantic-layer code.

Five agent tasks per the source plan:

- **A1** — Dataset registry (`src/pdf2md/datasets/registry.py`).
- **A2** — Git downloader with atomic positioning
  (`src/pdf2md/datasets/downloader.py`).
- **A3** — Manifest generator (`src/pdf2md/datasets/manifest.py`).
- **A4** — Typer subcommand group integrated into
  `src/pdf2md/cli/main.py`.
- **A5** — Documentation under `docs/datasets.md`.

Three datasets are registered:

- **tlc3-examples** — The LaTeX Companion 3rd ed. fixtures (LPPL-1.3c).
- **latex-cookbook** — Realistic multi-file project (MIT).
- **arxiv-curated** — Placeholder; not downloadable in this plan.

## 2. Hard constraints

- Tests MUST NOT require network access. Use local temp git repos
  (`git init` + `git commit` inside `tmp_path`) for downloader tests.
- `git` is the only external tool used; agent must check
  `shutil.which("git")` and fail clearly if missing.
- No env-modifying commands; no `pip install`; no `conda env create`.
- `groundtruth/corpus/` is forbidden — only `groundtruth/external/` and
  `groundtruth/manifest/` may be touched (and only via `.gitkeep` files
  at agent-mode time; real downloads happen at user-invocation time).
- `pyproject.toml` is forbidden — `typer` is already a declared
  dependency; no new packages introduced.

## 3. Acceptance criteria

- [ ] `pdf2md datasets list` lists tlc3-examples, latex-cookbook,
      arxiv-curated with id / aliases / licence / status (A1, A4).
- [ ] `pdf2md datasets install tlc3 --dry-run` exits 0 and creates no
      files (A2, A4).
- [ ] `pdf2md datasets install latex-cookbook --dry-run` exits 0 and
      creates no files (A2, A4).
- [ ] `pdf2md datasets install arxiv-curated` prints "not yet
      available" and exits 0 (A4).
- [ ] `pdf2md datasets status` reads
      `groundtruth/manifest/external_datasets.json` (or reports an
      empty status when absent) and exits 0 (A3, A4).
- [ ] `--compile`/`--limit`/`--engine` flags print
      "Not implemented in Plan 17. See Plan 18." and exit 0 (A4).
- [ ] All four pytest files pass and no regressions:
      `pytest tests/test_dataset_registry.py
       tests/test_dataset_downloader.py
       tests/test_dataset_manifest.py
       tests/test_dataset_cli.py -q` → green;
      `pytest tests/ -q --ignore=tests/_legacy_temp -x` stays ≥1002.
- [ ] `docs/datasets.md` exists and documents the workflow.

---

## File whitelist

```text
src/pdf2md/datasets/__init__.py
src/pdf2md/datasets/registry.py
src/pdf2md/datasets/downloader.py
src/pdf2md/datasets/manifest.py
src/pdf2md/datasets/cli.py
src/pdf2md/cli/main.py
groundtruth/external/.gitkeep
groundtruth/manifest/.gitkeep
tests/test_dataset_registry.py
tests/test_dataset_downloader.py
tests/test_dataset_manifest.py
tests/test_dataset_cli.py
tests/data/fake_repo/.gitkeep
docs/datasets.md
current_plan.md
run_log.md
```

## Forbidden files

```text
README.md
ROADMAP.md
project.md
next_plan.md
history.md
PLAN_TEMPLATE.md
agent.md
backend/**/*
src/pdf2md/consensus/**/*
src/pdf2md/linking/**/*
src/pdf2md/export/**/*
src/pdf2md/pipeline/**/*
src/pdf2md/models/**/*
src/pdf2md/semantic/**/*
src/pdf2md/connectors/**/*
src/pdf2md/calibration/**/*
src/pdf2md/local/**/*
src/pdf2md/conventions/**/*
src/pdf2md/_legacy/**/*
src/pdf2md/testing/**/*
groundtruth/corpus/**/*
groundtruth/corpus_*
generate_latex_docling_groundtruth.py
validate_latex_docling_groundtruth.py
pyproject.toml
plans/**/*
docs/!(datasets.md)
webui/**/*
tools/**/*
```

## Allowed dependencies

```text
none — stdlib only (subprocess, pathlib, json, shutil, tempfile, hashlib, re)
typer                — already required by pdf2md.cli.main
pydantic             — already required
pytest               — already required
```

## Allowed environment-modifying commands

```text
none in agent mode

(`git` is invoked as a read-only subprocess in downloader.py and only
when the user runs `pdf2md datasets install` at runtime — never by the
agent during implementation.)
```

## 4. Human verification checkpoints

### Checkpoint H1 — CLI dry-run + listing (network-free)

```bash
conda run -n pdf2md pdf2md datasets list
conda run -n pdf2md pdf2md datasets install tlc3 --dry-run
conda run -n pdf2md pdf2md datasets install latex-cookbook --dry-run
conda run -n pdf2md pdf2md datasets install arxiv-curated
```

Pass criteria:

```text
All four commands exit 0.
list shows all three registered datasets with licences + status.
Dry-runs create no files under groundtruth/external/.
arxiv-curated prints "not yet available".
```

### Checkpoint H2 — Real install (network-required, human only)

```bash
conda run -n pdf2md pdf2md datasets install tlc3 \
    --output /tmp/pdf2md_test_datasets
conda run -n pdf2md pdf2md datasets status
```

Pass criteria per source plan §7 Checkpoint H2.

---

## PR_reviews

(none yet)

## Feedback

(none yet)
