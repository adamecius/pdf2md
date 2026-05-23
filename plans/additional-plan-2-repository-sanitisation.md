# Additional Plan 2 — Repository Sanitisation and Legacy Removal

Status:
draft

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

Linked ROADMAP phase:
Phase 0 — Repository hygiene and public presentation

Current roadmap estimate:
Post-MVP. No ROADMAP.md percentage change until human approval.

Note:
This plan removes legacy artefacts, untracked virtual environments, dead code,
and orphan files from the repository. It improves the public presentation on
GitHub and adds baseline tooling configuration. It does not change any active
pipeline logic.

The repository currently tracks 18,531 files, of which 17,816 (96%) belong to
a committed Python virtual environment (.venv-mineru/). The git objects
directory is 305MB. Root-level scripts, old plan drafts, schema examples, and
a duplicate package directory clutter the top level. Several internal modules
under `utils/`, `adapters/`, `renderers/`, and `models/document.py` are
superseded by the current staged pipeline but still have test coverage.

This plan separates work into safe deletions (no imports anywhere) and
controlled deprecation (still imported by some tests).

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Additional Plan 2 of the post-MVP implementation sequence.

Previous plan:
Plan 18 — Single-Document Pipeline Orchestrator

Required previous plan status:
human_verified

Next plan after completion:
Additional Plan 3 — Docstrings, Type Annotations, and Linter Configuration

Branch name:
additional-plan-2-repository-sanitisation

---

## 1. Purpose

This plan makes the public repository clean, navigable, and professional by
removing files that should never have been tracked, deleting dead legacy
artefacts, deprecating superseded modules, consolidating scattered
documentation, and adding baseline developer tooling.

After this plan:

- `git clone` downloads ~700 files instead of ~18,500.
- The repository root contains only files that belong there.
- Legacy modules are clearly marked and isolated.
- `.gitignore` prevents future accidents.
- `pyproject.toml` includes ruff and mypy configuration.

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

README.md is the public entry point.

PLAN_TEMPLATE.md is the standard format for executable plans.

current_plan.md is the active execution contract for agents.

next_plan.md is the next planned execution contract.

history.md records completed milestones after human verification.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c additional-plan-2-repository-sanitisation
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. Do not modify files outside the whitelist.
4. Do not install or use undeclared dependencies.
5. Do not change ROADMAP.md progress.
6. Do not mark this plan human_verified or finished.

Main conda environment:

```text
pdf2md
```

This plan does not require backend environments.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Remove `.venv-mineru/` from git tracking.
2. Delete dead root-level scripts and legacy plan files.
3. Delete orphan directories (`.current/`, `pdf2md/`, `schema_examples/`).
4. Relocate superseded root-level documentation to `docs/archive/`.
5. Move superseded internal modules to `src/pdf2md/_legacy/`.
6. Mark legacy-dependent tests with a pytest marker.
7. Update `.gitignore` to prevent future accidents.
8. Add ruff and mypy baseline configuration to `pyproject.toml`.
9. Consolidate `scripts/` shell scripts into `docs/archive/` or delete.
10. Clean up `tests/temp_tests/` — relocate or mark as legacy.

Out of scope:

1. Writing new docstrings or type annotations (Additional Plan 3).
2. Rewriting tests that depend on legacy modules.
3. Modifying any active pipeline module logic.
4. Git history rewriting (BFG / filter-repo). The `.venv-mineru/` blobs
   remain in git history; only tracking is removed. History cleanup is a
   separate manual operation documented in this plan but not executed by
   the agent.
5. Modifying backend wrappers under `backend/`.

Hard constraints:

1. The agent must not modify files outside the whitelist.
2. The agent must not break any currently passing test that does NOT depend
   on legacy modules.
3. Legacy-dependent tests must still pass (they import from `_legacy/`
   after the move).
4. The agent must not delete `models/document.py` — it moves to `_legacy/`.
5. Human verification is required before merge.

Allowed Python dependencies:

```text
ruff (dev dependency, not runtime)
mypy (dev dependency, not runtime)
```

Allowed external tools:

```text
git rm --cached — to untrack .venv-mineru without deleting from disk
```

---

## 5. File whitelist and forbidden files

### Files the agent must DELETE (git rm):

```text
.venv-mineru/                              (git rm -r --cached; add to .gitignore)
compare_pre_docling_groundtruth.py         (dead — no imports anywhere)
latex_to_pre_docling_groundtruth.py        (dead — no imports anywhere)
plan5.md                                   (legacy plan draft)
patch.plan                                 (legacy patch notes)
patch.plan8.md                             (legacy patch notes)
.current/                                  (ad-hoc consensus output for one document)
pdf2md/__init__.py                         (orphan — real package is src/pdf2md/)
pdf2md/                                    (empty after __init__.py removal)
schema_examples/                           (schemas from a pre-IR format)
```

### Files the agent must RELOCATE:

```text
README_latex_docling_groundtruth.md        → docs/archive/README_latex_docling_groundtruth.md
run_latex_docling_backends.sh              → docs/archive/run_latex_docling_backends.sh
generate_latex_docling_groundtruth.py      → docs/archive/generate_latex_docling_groundtruth.py
validate_latex_docling_groundtruth.py      → docs/archive/validate_latex_docling_groundtruth.py
scripts/local_build_docling_fixtures.sh    → docs/archive/local_build_docling_fixtures.sh
scripts/local_validate_docling_fixtures.sh → docs/archive/local_validate_docling_fixtures.sh

src/pdf2md/utils/consensus_report.py       → src/pdf2md/_legacy/consensus_report.py
src/pdf2md/utils/semantic_linker.py        → src/pdf2md/_legacy/semantic_linker.py
src/pdf2md/utils/media_materializer.py     → src/pdf2md/_legacy/media_materializer.py
src/pdf2md/utils/semantic_document_builder.py → src/pdf2md/_legacy/semantic_document_builder.py
src/pdf2md/utils/docling_adapter.py        → src/pdf2md/_legacy/docling_adapter.py
src/pdf2md/utils/__init__.py               → (delete after moves; utils/ becomes empty)
src/pdf2md/adapters/base.py                → src/pdf2md/_legacy/adapters_base.py
src/pdf2md/adapters/__init__.py            → (delete)
src/pdf2md/backends/base.py                → src/pdf2md/_legacy/backends_base.py
src/pdf2md/renderers/markdown.py           → src/pdf2md/_legacy/renderers_markdown.py
src/pdf2md/renderers/__init__.py           → (delete)
src/pdf2md/models/document.py              → src/pdf2md/_legacy/models_document.py
src/pdf2md/pipeline/convert.py             → src/pdf2md/_legacy/pipeline_convert.py

tests/temp_tests/                          → tests/_legacy_temp/
```

### Files the agent may CREATE:

```text
src/pdf2md/_legacy/__init__.py
src/pdf2md/_legacy/README.md
docs/archive/README.md
```

### Files the agent may MODIFY:

```text
.gitignore
pyproject.toml
src/pdf2md/models/__init__.py              (remove document.py imports)
src/pdf2md/cli/main.py                     (remove convert_pdf import)
tests/test_consensus_report.py             (update imports to _legacy)
tests/test_media_materializer.py           (update imports to _legacy)
tests/test_docling_adapter.py              (update imports to _legacy)
tests/test_semantic_linker.py              (update imports to _legacy)
tests/test_semantic_document_builder.py    (update imports to _legacy)
tests/test_groundtruth_regressions.py      (update imports to _legacy)
tests/test_groundtruth_e2e.py              (update imports to _legacy)
tests/test_mock_backend_schema.py          (update imports to _legacy)
tests/test_models_and_rendering.py         (update imports to _legacy)
run_log.md
```

### Forbidden files (must not be modified):

```text
ROADMAP.md
README.md
project.md
PLAN_TEMPLATE.md
src/pdf2md/consensus/*
src/pdf2md/connectors/*
src/pdf2md/calibration/*
src/pdf2md/linking/*
src/pdf2md/export/*
src/pdf2md/models/ir.py
src/pdf2md/models/entities.py
src/pdf2md/models/priors.py
src/pdf2md/models/linked.py
src/pdf2md/models/export.py
src/pdf2md/models/semantic_document.py
src/pdf2md/backends/runner.py
src/pdf2md/config.py
src/pdf2md/local/*
src/pdf2md/conventions/*
src/pdf2md/testing/*
backend/*
tools/*
groundtruth/*
```

---

## 6. Agent tasks

### Task A1 — Remove .venv-mineru from tracking

Title:
Untrack committed virtual environment

Goal:
Remove `.venv-mineru/` from git tracking without deleting it from disk, and
prevent re-addition via `.gitignore`.

Files allowed:

```text
.gitignore
.venv-mineru/ (git rm --cached only)
```

Implementation requirements:

1. Run `git rm -r --cached .venv-mineru/`.
2. Add the following to `.gitignore`:

   ```text
   # Virtual environments — never track
   .venv*/
   venv*/
   .env/
   env/
   ```

3. Also add these missing entries to `.gitignore`:

   ```text
   # IDE
   .idea/
   .vscode/
   *.swp
   *.swo
   *~

   # OS
   .DS_Store
   Thumbs.db

   # Distribution / packaging
   dist/
   build/
   *.egg-info/
   *.egg

   # Coverage
   htmlcov/
   .coverage
   .coverage.*
   ```

4. Verify with `git status` that `.venv-mineru/` appears as deleted (from
   tracking) and that the files still exist on disk.

Automated tests required:

```bash
git ls-files .venv-mineru/ | wc -l    # must be 0
test -d .venv-mineru                  # must still exist on disk
```

Expected output:
`.venv-mineru/` untracked. `.gitignore` updated.

Completion evidence:
`git diff --cached --stat` showing ~17,816 deletions. `.gitignore` diff.

Human verification required:
yes (see checkpoint H1)

---

### Task A2 — Delete dead root-level files

Title:
Remove legacy scripts, orphan plans, and dead directories

Goal:
Delete files at the repository root that have no imports, no references, and
no active purpose.

Files allowed:

```text
compare_pre_docling_groundtruth.py
latex_to_pre_docling_groundtruth.py
plan5.md
patch.plan
patch.plan8.md
.current/
pdf2md/
schema_examples/
```

Implementation requirements:

1. Delete each file with `git rm`:

   ```bash
   git rm compare_pre_docling_groundtruth.py
   git rm latex_to_pre_docling_groundtruth.py
   git rm plan5.md
   git rm patch.plan
   git rm patch.plan8.md
   git rm -r .current/
   git rm -r pdf2md/
   git rm -r schema_examples/
   ```

2. Verify none of these files are imported by any `.py` file under `src/`
   or `tests/` before deleting. (Pre-verified during plan creation: none
   are imported.)

3. The `scripts/` directory becomes empty after Task A3. Delete it with
   `git rm -r scripts/`.

Automated tests required:

```bash
conda run -n pdf2md pytest tests/ -q --ignore=tests/temp_tests --ignore=tests/_legacy_temp -x
```

All currently passing tests that don't depend on legacy utils must still pass.

Expected output:
Root directory is clean.

Completion evidence:
`git rm` output. `ls` of root showing only legitimate files.

Human verification required:
no

---

### Task A3 — Relocate legacy documentation and scripts

Title:
Move superseded docs and scripts to docs/archive/

Goal:
Preserve legacy documentation and scripts for reference without cluttering
the root or active directories.

Files allowed:

```text
docs/archive/README.md                     (create)
docs/archive/README_latex_docling_groundtruth.md
docs/archive/run_latex_docling_backends.sh
docs/archive/generate_latex_docling_groundtruth.py
docs/archive/validate_latex_docling_groundtruth.py
docs/archive/local_build_docling_fixtures.sh
docs/archive/local_validate_docling_fixtures.sh
scripts/                                   (delete after moving)
README_latex_docling_groundtruth.md         (delete from root)
run_latex_docling_backends.sh               (delete from root)
generate_latex_docling_groundtruth.py       (delete from root)
validate_latex_docling_groundtruth.py       (delete from root)
```

Implementation requirements:

1. Create `docs/archive/` directory.

2. `git mv` each file to `docs/archive/`.

3. Create `docs/archive/README.md`:

   ```markdown
   # Archived Scripts and Documentation

   These files are from earlier development phases and are preserved for
   reference. They are not part of the active pipeline.

   The active pipeline modules are under `src/pdf2md/` and the active
   tools are under `tools/`.

   ## Contents

   - `README_latex_docling_groundtruth.md` — original LaTeX ground-truth
     harness documentation.
   - `generate_latex_docling_groundtruth.py` — original fixture generator.
   - `validate_latex_docling_groundtruth.py` — original fixture validator.
   - `run_latex_docling_backends.sh` — original bash orchestrator.
   - `local_build_docling_fixtures.sh` — local fixture build script.
   - `local_validate_docling_fixtures.sh` — local fixture validation script.
   ```

4. Delete `scripts/` directory after moving its contents.

Automated tests required:

```text
none (documentation only)
```

Expected output:
Root is clean. `docs/archive/` has legacy files.

Completion evidence:
`git mv` output. `ls docs/archive/`.

Human verification required:
no

---

### Task A4 — Move superseded modules to _legacy/

Title:
Relocate legacy utils, adapters, renderers, and old model to _legacy package

Goal:
Move superseded internal modules to `src/pdf2md/_legacy/` with a clear
deprecation notice, preserving import paths for existing tests.

Files allowed:

```text
src/pdf2md/_legacy/__init__.py             (create)
src/pdf2md/_legacy/README.md               (create)
src/pdf2md/_legacy/consensus_report.py     (moved from utils/)
src/pdf2md/_legacy/semantic_linker.py      (moved from utils/)
src/pdf2md/_legacy/media_materializer.py   (moved from utils/)
src/pdf2md/_legacy/semantic_document_builder.py (moved from utils/)
src/pdf2md/_legacy/docling_adapter.py      (moved from utils/)
src/pdf2md/_legacy/adapters_base.py        (moved from adapters/)
src/pdf2md/_legacy/backends_base.py        (moved from backends/)
src/pdf2md/_legacy/renderers_markdown.py   (moved from renderers/)
src/pdf2md/_legacy/models_document.py      (moved from models/)
src/pdf2md/_legacy/pipeline_convert.py     (moved from pipeline/)
src/pdf2md/utils/                          (delete after moving)
src/pdf2md/adapters/                       (delete after moving)
src/pdf2md/renderers/                      (delete after moving)
src/pdf2md/models/__init__.py              (modify: remove document.py imports)
src/pdf2md/models/document.py              (delete after copy to _legacy)
src/pdf2md/pipeline/convert.py             (delete after copy to _legacy)
src/pdf2md/cli/main.py                     (modify: remove convert_pdf import)
```

Implementation requirements:

1. Create `src/pdf2md/_legacy/__init__.py` with:

   ```python
   """Superseded modules preserved for backward compatibility.

   These modules are from earlier development phases. The active pipeline
   uses modules under consensus/, connectors/, calibration/, linking/,
   and export/. These legacy modules will be removed in a future version.
   """
   ```

2. Create `src/pdf2md/_legacy/README.md`:

   ```markdown
   # Legacy Modules

   These modules are superseded by the current staged pipeline:

   | Legacy module          | Replaced by                        |
   |------------------------|------------------------------------|
   | consensus_report.py    | consensus/factory.py + consensus/reporting.py |
   | semantic_linker.py     | linking/builder.py + linking/extract.py |
   | media_materializer.py  | export/io.py                       |
   | semantic_document_builder.py | export/docling.py             |
   | docling_adapter.py     | export/docling.py + export/io.py   |
   | adapters_base.py       | connectors/common.py               |
   | backends_base.py       | backends/runner.py                 |
   | renderers_markdown.py  | export/markdown.py                 |
   | models_document.py     | models/ir.py (PageExtractionIR, ConsensusIR) |
   | pipeline_convert.py    | pipeline/orchestrator.py (Plan 18) |

   These modules and their tests will be removed after all dependent
   tests are migrated.
   ```

3. Move each file with `git mv`. For files that change names (e.g.
   `adapters/base.py` → `_legacy/adapters_base.py`), use `git mv` then
   rename, or `cp` + `git rm` + `git add`.

4. Adjust internal imports within moved modules if they reference each
   other. For example, `adapters/base.py` imports
   `from pdf2md.models import Document` — update to
   `from pdf2md._legacy.models_document import Document`.

5. Update `src/pdf2md/models/__init__.py`:
   - Remove `from .document import BBox, Block, Document, Flag, Page, SourceRef`
   - Remove those names from `__all__`
   - Keep all other imports (ir, entities, priors, linked, export) unchanged

6. Update `src/pdf2md/cli/main.py`:
   - Remove `from pdf2md.pipeline.convert import convert_pdf`
   - Update the `convert` command to not reference `convert_pdf`
   - If Plan 18 is not yet merged, make the convert command print
     "Pipeline orchestrator not implemented yet. See Plan 18." instead
     of referencing the old placeholder.

7. Delete now-empty directories: `utils/`, `adapters/`, `renderers/`.

8. Move `tests/temp_tests/` to `tests/_legacy_temp/`:
   ```bash
   git mv tests/temp_tests tests/_legacy_temp
   ```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

All tests NOT in `_legacy_temp` must pass. This verifies that moving modules
didn't break active pipeline tests.

Expected output:
`src/pdf2md/utils/`, `src/pdf2md/adapters/`, `src/pdf2md/renderers/` no
longer exist. `src/pdf2md/_legacy/` contains the moved modules.

Completion evidence:
`git mv` output, test results, import verification.

Human verification required:
no

---

### Task A5 — Update legacy-dependent test imports

Title:
Repoint test imports from old paths to _legacy paths

Goal:
Update all test files that import from `pdf2md.utils`, `pdf2md.adapters`,
`pdf2md.renderers`, or `pdf2md.models.document` to import from
`pdf2md._legacy` instead.

Files allowed:

```text
tests/test_consensus_report.py
tests/test_media_materializer.py
tests/test_docling_adapter.py
tests/test_semantic_linker.py
tests/test_semantic_document_builder.py
tests/test_groundtruth_regressions.py
tests/test_groundtruth_e2e.py
tests/test_mock_backend_schema.py
tests/test_models_and_rendering.py
tests/_legacy_temp/conftest.py
tests/_legacy_temp/test_ashcroft_pipeline_contract.py
tests/_legacy_temp/test_docling_adapter_edge_cases.py
```

Implementation requirements:

1. In each test file, replace import paths:
   - `from pdf2md.utils import X` → `from pdf2md._legacy import X`
     (adjust submodule paths as needed)
   - `from pdf2md.utils.consensus_report import X` →
     `from pdf2md._legacy.consensus_report import X`
   - `from pdf2md.models import Block, Document, Page` →
     `from pdf2md._legacy.models_document import Block, Document, Page`
   - `from pdf2md.renderers.markdown import render_markdown` →
     `from pdf2md._legacy.renderers_markdown import render_markdown`
   - `from pdf2md.adapters.base import Adapter` →
     `from pdf2md._legacy.adapters_base import Adapter`

2. For `tests/_legacy_temp/conftest.py`, update the `run_cli` calls that
   use `-m pdf2md.utils.X` to use `-m pdf2md._legacy.X`. Ensure the
   legacy modules have `if __name__ == "__main__"` blocks if they are
   called as CLI scripts.

3. Add a `legacy` pytest marker to all affected test files:

   ```python
   import pytest
   pytestmark = pytest.mark.legacy
   ```

4. Register the marker in `pyproject.toml`:

   ```toml
   [tool.pytest.ini_options]
   markers = [
       "legacy: tests for superseded modules (will be removed)",
   ]
   ```

Automated tests required:

```bash
conda run -n pdf2md pytest tests/ -q -x
```

ALL tests (including legacy) must pass with updated imports.

```bash
conda run -n pdf2md pytest tests/ -q -m "not legacy" -x
```

Non-legacy tests must also pass independently.

Expected output:
All tests pass. Legacy tests are marked and filterable.

Completion evidence:
Test output for both commands. Diff of import changes.

Human verification required:
yes (see checkpoint H2)

---

### Task A6 — Add tooling configuration

Title:
Add ruff and mypy baseline config to pyproject.toml

Goal:
Establish linter and type checker configuration so future code follows
consistent standards.

Files allowed:

```text
pyproject.toml
```

Implementation requirements:

1. Add ruff configuration:

   ```toml
   [tool.ruff]
   target-version = "py311"
   line-length = 120

   [tool.ruff.lint]
   select = [
       "E",      # pycodestyle errors
       "W",      # pycodestyle warnings
       "F",      # pyflakes
       "I",      # isort
       "UP",     # pyupgrade
       "B",      # flake8-bugbear
       "SIM",    # flake8-simplify
       "RUF",    # ruff-specific
   ]
   ignore = [
       "E501",   # line too long (handled by formatter)
       "B008",   # do not perform function calls in argument defaults (typer pattern)
   ]

   [tool.ruff.lint.isort]
   known-first-party = ["pdf2md"]
   ```

2. Add mypy configuration:

   ```toml
   [tool.mypy]
   python_version = "3.11"
   warn_return_any = true
   warn_unused_configs = true
   ignore_missing_imports = true
   exclude = [
       "src/pdf2md/_legacy/",
       "tests/_legacy_temp/",
       "docs/archive/",
   ]
   ```

3. Add optional dev dependencies:

   ```toml
   [project.optional-dependencies]
   dev = [
       "ruff>=0.4",
       "mypy>=1.10",
       "pytest>=8",
   ]
   ```

4. Do NOT run ruff fix or mypy on the entire codebase in this plan.
   The configuration is baseline only. Fixing lint issues is Additional Plan 3.

Automated tests required:

```bash
conda run -n pdf2md python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"
```

Verify pyproject.toml is valid TOML.

Expected output:
`pyproject.toml` has ruff, mypy, and dev deps configured.

Completion evidence:
Diff of pyproject.toml.

Human verification required:
no

---

## 7. Human verification checkpoints

### Checkpoint H1

Title:
Verify .venv-mineru is untracked and .gitignore is correct

Purpose:
Confirm that the virtual environment is no longer tracked, the files still
exist on disk, and .gitignore prevents re-addition.

Required environment:
pdf2md

Preconditions:
Task A1 is complete. Changes are staged but not yet committed.

Commands:

```bash
git ls-files .venv-mineru/ | wc -l
test -d .venv-mineru && echo "exists on disk" || echo "MISSING"
echo ".venv-test-ignore" > .venv-test-ignore
git check-ignore .venv-test-ignore
rm .venv-test-ignore
```

Verification procedure:

1. `git ls-files .venv-mineru/ | wc -l` must return 0.
2. `.venv-mineru/` must still exist on disk.
3. `.venv-test-ignore` must be ignored by git (verifying the pattern works).
4. Review `.gitignore` additions for completeness.

Pass criteria:

```text
Zero tracked files under .venv-mineru/.
Directory exists on disk.
.gitignore correctly matches .venv* patterns.
```

Fail criteria:

```text
Any files still tracked under .venv-mineru/.
Directory was deleted from disk.
.gitignore pattern doesn't match test file.
```

Evidence to record:

```text
Output of git ls-files count.
Output of disk existence check.
Output of git check-ignore.
```

---

### Checkpoint H2

Title:
Verify all tests pass after import migration

Purpose:
Confirm that legacy tests still pass with updated import paths and that
non-legacy tests are unaffected.

Required environment:
pdf2md

Preconditions:
Tasks A1–A5 are complete.

Commands:

```bash
conda run -n pdf2md pytest tests/ -q -x 2>&1 | tail -20
conda run -n pdf2md pytest tests/ -q -m "not legacy" -x 2>&1 | tail -20
conda run -n pdf2md pytest tests/ -q -m "legacy" -x 2>&1 | tail -20
```

Verification procedure:

1. Run all tests. Record pass/fail counts.
2. Run non-legacy tests only. Verify all pass.
3. Run legacy tests only. Verify all pass.
4. Verify that `src/pdf2md/utils/` does not exist.
5. Verify that `src/pdf2md/adapters/` does not exist.
6. Verify that `src/pdf2md/renderers/` does not exist.
7. Verify that `src/pdf2md/_legacy/` exists and contains the moved modules.
8. Verify that root directory no longer contains legacy scripts.

Pass criteria:

```text
All tests pass.
Legacy marker correctly filters tests.
Deleted directories are gone.
_legacy/ contains expected modules.
Root is clean.
```

Fail criteria:

```text
Any test fails.
Legacy marker is not registered.
Deleted directories still exist.
Active pipeline modules were modified.
```

Evidence to record:

```text
Test output (all, non-legacy, legacy).
ls src/pdf2md/ (top-level directories).
ls of repository root.
```

---

### Checkpoint H3

Title:
Verify repository root presentation

Purpose:
Confirm the repository looks clean and professional on GitHub.

Required environment:
Any (visual inspection of file listing)

Commands:

```bash
ls -la $(git ls-files | sed 's|/.*||' | sort -u)
```

Verification procedure:

1. Review root-level file listing. It should contain only:

   ```text
   .codex
   .github/
   .gitignore
   .python-version
   backend/
   CLA.md
   configs/
   CONTRIBUTING.md
   current_plan.md
   docs/
   groundtruth/
   history.md
   LICENSE
   next_plan.md
   NOTICE
   pdf2md.backends.example.toml
   pdf2md.consensus.example.toml
   PLAN_TEMPLATE.md
   plans/
   project.md
   pyproject.toml
   README.md
   ROADMAP.md
   run_log.md
   src/
   tests/
   tools/
   ```

2. Verify the following are GONE from root:
   - `compare_pre_docling_groundtruth.py`
   - `latex_to_pre_docling_groundtruth.py`
   - `generate_latex_docling_groundtruth.py`
   - `validate_latex_docling_groundtruth.py`
   - `run_latex_docling_backends.sh`
   - `plan5.md`, `patch.plan`, `patch.plan8.md`
   - `README_latex_docling_groundtruth.md`
   - `schema_examples/`
   - `.current/`
   - `pdf2md/`
   - `scripts/`

Pass criteria:

```text
Root contains only the expected files listed above.
No legacy scripts or orphan directories remain.
```

Fail criteria:

```text
Any legacy file remains at root.
Any expected file is missing.
```

Evidence to record:

```text
Output of ls showing root contents.
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/ -q -x
conda run -n pdf2md pytest tests/ -q -m "not legacy" -x
conda run -n pdf2md pytest tests/ -q -m "legacy" -x
```

Failure classes:

repository_defect:
An import was broken by the move, a file was deleted that was still needed,
or the _legacy package is not importable.

test_expectation_wrong:
A test expectation references an old path that was not updated.

import_path_error:
A moved module has internal imports that were not updated.

human_procedure_error:
The human ran the wrong command.

Failure handling:

If failure_class is repository_defect:
The agent must fix the broken import or restore the file.

If failure_class is import_path_error:
The agent must update the internal import in the _legacy module.

---

## 9. Checkpoints, push policy, and hand-off

Checkpoint C0: Plan ready

```text
status is active
file whitelist is complete
all delete/move operations are listed
```

Checkpoint C1: Agent implementation complete

```text
all tasks attempted
all automated tests run
no forbidden files modified
status set to human_verification_required
```

Checkpoint C2: Human verification complete

```text
all checkpoints passed
status set to human_verified
```

Push and PR policy:

```text
The agent may push the branch and open a draft PR.
The agent must not merge to main.
The PR diff should show ~17,800+ file deletions (mostly .venv-mineru).
```

Hand-off after human verification:

1. Archive as plans/archive/additional-plan-2-repository-sanitisation.md.
2. Append milestone to history.md.
3. Promote next_plan.md.

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan: Additional Plan 2
Status:
Branch:
Commit or PR:
Files deleted:
Files moved:
Files modified:
Forbidden files touched:
Tracked file count before:
Tracked file count after:
Tests run (all):
Tests run (non-legacy):
Tests run (legacy):
Tests passed:
Tests failed:
Blockers:
```

Reviewer checklist:

1. Did the agent modify only whitelisted files?
2. Did the agent avoid all forbidden files?
3. Is .venv-mineru/ untracked but still on disk?
4. Are all dead root files deleted?
5. Are legacy scripts in docs/archive/?
6. Is src/pdf2md/_legacy/ correctly structured?
7. Are legacy test imports updated?
8. Is the legacy pytest marker registered?
9. Do all tests pass?
10. Is pyproject.toml valid TOML?
11. Does ruff config target Python 3.11?
12. Is the repository root clean?
13. Are active pipeline modules untouched?
14. Is models/__init__.py updated (document.py imports removed)?
15. Is cli/main.py updated (convert_pdf import removed)?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-24 — draft — human — Additional Plan 2 created for repository sanitisation
```

---

## 11. Design notes

### Why not delete legacy modules outright?

Nine test files (1,283 lines total) import from `pdf2md.utils`, and some of
those tests verify behaviour of the old consensus report, semantic linker, and
docling adapter that may still be useful as regression baselines. Deleting the
modules would break these tests immediately.

Moving to `_legacy/` preserves test coverage while making the deprecation
explicit. Additional Plan 3 can decide whether to migrate the test coverage to the
current pipeline modules or remove it entirely.

### Why not rewrite git history?

Removing `.venv-mineru/` from tracking (`git rm --cached`) prevents new clones
from downloading the files on checkout. However, the binary blobs remain in
git history, inflating `git clone` size.

Rewriting history (with `git filter-repo` or BFG Repo-Cleaner) is a
destructive operation that invalidates all existing clones, forks, and open
PRs. It should be done as a manual one-time operation after this plan is
merged, documented here for reference:

```bash
# After merge, on a fresh clone:
pip install git-filter-repo
git filter-repo --path .venv-mineru/ --invert-paths
git push --force --all
git push --force --tags
```

This is explicitly out of scope for the agent.

### .gitignore additions rationale

The current `.gitignore` is minimal. The additions cover:

- Virtual environments (`.venv*/`, `venv*/`) — prevents any env from being
  tracked again.
- IDE files (`.idea/`, `.vscode/`) — common development artefacts.
- OS files (`.DS_Store`, `Thumbs.db`) — cross-platform noise.
- Distribution packaging (`dist/`, `build/`, `*.egg-info/`) — standard
  Python packaging artefacts.
- Coverage reports (`htmlcov/`, `.coverage`) — CI artefacts.

### Root file inventory after cleanup

```text
.codex                          — agent config
.github/                        — PR template
.gitignore                      — updated
.python-version                 — Python version pin
agent.md                        — agent governance protocol
backend/                        — backend wrappers
CLA.md                          — contributor licence
configs/                        — OCR convention configs
CONTRIBUTING.md                 — contribution guide
current_plan.md                 — active plan
docs/                           — documentation + archive
groundtruth/                    — ground-truth corpus
history.md                      — completed milestones
LICENSE                         — AGPL-3.0
next_plan.md                    — next plan placeholder
NOTICE                          — copyright notice
pdf2md.backends.example.toml    — example backend config
pdf2md.consensus.example.toml   — example consensus config
PLAN_TEMPLATE.md                — plan format template
plans/                          — all plans
project.md                      — architecture description
pyproject.toml                  — package config + tooling
README.md                       — public entry point
ROADMAP.md                      — product roadmap
run_log.md                      — agent run log
src/                            — main package
tests/                          — test suite
tools/                          — CLI tools for pipeline stages
```
