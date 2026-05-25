# Additional Plan 3 — PEP Compliance: Docstrings, Type Annotations, and Linter Enforcement

Status:
finished

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
Phase 0 — Repository hygiene and code quality

Current roadmap estimate:
Post-MVP. No ROADMAP.md percentage change until human approval.

Note:
This plan brings all active modules into compliance with PEP 257 (docstring
conventions), PEP 484/585/604 (type annotations), and PEP 8 (style) using
the ruff and mypy configuration established in Additional Plan 2.

PEP 727 (Documentation Metadata in Typing) was withdrawn in October 2024.
The current Python standard for documentation remains PEP 257 docstrings
with a consistent content format. This plan adopts Google-style docstrings
because they are compact, readable without rendering, and compatible with
Sphinx, mkdocs, and IDE tooltips.

This plan does NOT touch `_legacy/` modules or `_legacy_temp/` tests.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
Additional Plan 3 of the post-MVP implementation sequence.

Previous plan:
Additional Plan 2 — Repository Sanitisation and Legacy Removal

Required previous plan status:
human_verified

Next plan after completion:
TBD

Branch name:
additional-plan-3-pep-compliance

---

## 1. Purpose

This plan ensures every active module, class, and public function in
`src/pdf2md/` has PEP 257-compliant docstrings, complete return type
annotations, and passes ruff and mypy without errors.

Current state (measured against active modules only, excluding `_legacy/`):

- 16 modules without module-level docstrings.
- 31 modules with module-level docstrings (one-line PEP 257 style).
- ~40 public functions without return type annotations.
- 0 public functions with Google-style parameter/return docstrings.
- No ruff or mypy enforcement (configuration exists from Additional Plan 2
  but has never been run).

After this plan:

- Every `.py` file under `src/pdf2md/` (except `_legacy/`) has a module
  docstring.
- Every public function and method has a Google-style docstring with Args,
  Returns, and Raises sections where applicable.
- Every function has a return type annotation.
- `ruff check src/pdf2md/` passes with zero errors.
- `mypy src/pdf2md/` passes with zero errors (excluding `_legacy/`).

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap.

project.md is the durable architecture description.

README.md is the public entry point.

PLAN_TEMPLATE.md is the standard format for executable plans.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c additional-plan-3-pep-compliance
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. Do not modify files outside the whitelist.
4. Do not change ROADMAP.md progress.
5. Do not mark this plan human_verified or finished.
6. Do not change any module's runtime behaviour. All changes are
   documentation, annotations, and formatting only.

Main conda environment:

```text
pdf2md
```

This plan does not require backend environments.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Module-level docstrings for all active modules.
2. Google-style function/method docstrings for all public functions.
3. Return type annotations for all functions missing them.
4. Ruff lint fixes across active source code.
5. Mypy type error resolution across active source code.
6. A docstring style guide committed to docs/.

Out of scope:

1. `src/pdf2md/_legacy/` modules — not touched.
2. `tests/_legacy_temp/` — not touched.
3. `backend/` wrapper scripts — not touched.
4. `tools/` standalone scripts — not touched (they use argparse, not
   the package API).
5. Runtime behaviour changes of any kind.
6. Refactoring or restructuring code.
7. Adding new tests (existing tests must continue to pass).

Hard constraints:

1. No runtime behaviour change. Every diff must be docstring, annotation,
   whitespace, or import ordering only.
2. All currently passing tests must continue to pass.
3. Private functions (prefixed with `_`) get docstrings only if they are
   complex (>10 lines or non-obvious logic). Simple private helpers may
   be skipped.
4. Dataclass and Pydantic model fields get docstrings via class-level
   docstrings with an Attributes section, not per-field comments.

Allowed Python dependencies:

```text
ruff (dev — already configured in Additional Plan 2)
mypy (dev — already configured in Additional Plan 2)
```

---

## 5. File whitelist and forbidden files

The agent may modify only these files:

```text
src/pdf2md/**/*.py                (all active modules, excluding _legacy/)
docs/docstring_style_guide.md     (create)
pyproject.toml                    (minor ruff/mypy config adjustments only)
run_log.md
```

The agent must NOT modify:

```text
src/pdf2md/_legacy/*
tests/_legacy_temp/*
tests/**/*.py                    (no test changes — only source docstrings)
backend/*
tools/*
groundtruth/*
ROADMAP.md
README.md
project.md
PLAN_TEMPLATE.md
```

---

## 6. Agent tasks

### Task A1 — Docstring style guide

Title:
Create docs/docstring_style_guide.md

Goal:
Establish the project's docstring standard so all contributors and agents
follow the same format.

Files allowed:

```text
docs/docstring_style_guide.md
```

Implementation requirements:

1. Document the project's docstring conventions:

   **Module docstrings** — PEP 257 one-line for focused modules, multi-line
   for complex modules:

   ```python
   """Scoring for page-local consensus candidate groups."""
   ```

   ```python
   """Filesystem I/O for calibration inputs and outputs.

   This module handles discovery of calibration documents, loading of
   truth files with Docling-to-BlockKind normalisation, and writing
   of prior output files.
   """
   ```

   **Function docstrings** — Google-style:

   ```python
   def score_candidate_group(
       *,
       group: CandidateGroup,
       priors_by_backend: dict[str, CalibrationPriorDocument],
       entities_by_backend: dict[str, EntityProposalDocument],
       settings: ConsensusScoringSettings = ConsensusScoringSettings(),
   ) -> GroupScore:
       """Score candidates in a group and select the consensus winner.

       Computes a weighted score for each candidate block using text
       overlap, bbox IoU, reading order, block kind agreement, backend
       calibration priors, and entity-level priors. Selects the highest-
       scoring candidate or marks the group as unresolved if the margin
       is within the configured threshold.

       Args:
           group: The candidate group containing blocks from
               different backends that were matched to the same
               logical region.
           priors_by_backend: Calibration prior documents keyed by
               backend name.
           entities_by_backend: Entity proposal documents keyed by
               backend name.
           settings: Scoring weights and thresholds.

       Returns:
           A GroupScore with the selected candidate, agreement score,
           selection mode, and per-candidate score breakdown.

       Raises:
           ValueError: If the group contains zero candidates.
       """
   ```

   **Class/dataclass docstrings** — Summary plus Attributes:

   ```python
   @dataclass(frozen=True)
   class ConsensusScoringSettings:
       """Weights and thresholds for consensus candidate scoring.

       Attributes:
           text_weight: Weight for token overlap score.
           bbox_weight: Weight for bounding box IoU score.
           min_agreement_score: Minimum score to accept a candidate.
       """

       text_weight: float = 0.35
       bbox_weight: float = 0.15
       min_agreement_score: float = 0.50
   ```

   **Private functions** — One-line docstring if complex; skip if trivial:

   ```python
   def _tokens(text: str | None) -> set[str]:
       """Extract lowercase word tokens from text."""
       return set(re.findall(r"[\w]+", normalise_text(text)))
   ```

2. Document type annotation conventions:

   - Use PEP 604 union syntax: `X | Y` not `Union[X, Y]`.
   - Use PEP 585 lowercase generics: `list[X]`, `dict[K, V]`, `tuple[X, ...]`.
   - Use `from __future__ import annotations` in every module (already
     present in most modules).
   - Always annotate return types, including `-> None`.
   - Use `Any` sparingly; prefer concrete types or TypedDict.

3. Document ruff and mypy enforcement:

   ```bash
   # Lint check
   ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/

   # Auto-fix safe issues
   ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/ --fix

   # Type check
   mypy src/pdf2md/ --exclude src/pdf2md/_legacy/
   ```

Automated tests required:

```text
none (documentation only)
```

Human verification required:
no

---

### Task A2 — Module-level docstrings

Title:
Add module docstrings to all active modules missing them

Goal:
Every `.py` file under `src/pdf2md/` (except `_legacy/` and `__init__.py`)
has a PEP 257-compliant module docstring.

Files allowed:

```text
src/pdf2md/config.py
src/pdf2md/conventions/determine_convention.py
src/pdf2md/conventions/latex_groundtruth.py
src/pdf2md/conventions/schemas.py
src/pdf2md/conventions/normalizer.py
src/pdf2md/conventions/reporting.py
src/pdf2md/conventions/rules.py
src/pdf2md/conventions/alignment.py
src/pdf2md/models/semantic_document.py
src/pdf2md/cli/main.py
src/pdf2md/backends/runner.py
src/pdf2md/testing/fixtures.py
src/pdf2md/testing/mock_backend_ir.py
```

Note: `models/document.py`, `backends/base.py`, `pipeline/convert.py`,
`adapters/base.py`, and `renderers/markdown.py` are moved to `_legacy/`
by Additional Plan 2. If Additional Plan 2 has not yet been executed
when this plan runs, add docstrings to those files as well, but mark
them with a `.. deprecated::` notice.

Implementation requirements:

1. Each module docstring must be one concise line describing the module's
   purpose, matching the style already used in the codebase:

   ```python
   """TOML configuration loader for backend orchestration."""
   ```

2. For complex modules (>100 lines or multiple public functions), use a
   multi-line docstring with a blank line after the summary:

   ```python
   """Convention normalisation for OCR backend outputs.

   Applies configured normalisation rules to raw backend text to handle
   known OCR conventions (ligatures, whitespace, encoding quirks) before
   text comparison in the consensus stage.
   """
   ```

3. `__init__.py` files: add a one-line docstring if missing, describing
   the subpackage purpose.

Automated tests required:

```bash
conda run -n pdf2md python -c "
import ast, pathlib, sys
missing = []
for p in pathlib.Path('src/pdf2md').rglob('*.py'):
    if '_legacy' in str(p) or '__pycache__' in str(p):
        continue
    tree = ast.parse(p.read_text())
    if not ast.get_docstring(tree):
        missing.append(str(p))
if missing:
    print('Missing module docstrings:')
    for m in sorted(missing): print(f'  {m}')
    sys.exit(1)
print(f'All modules have docstrings.')
"
```

Human verification required:
no

---

### Task A3 — Return type annotations

Title:
Add return type annotations to all public functions

Goal:
Every function and method in active modules has a return type annotation.

Files allowed:

```text
src/pdf2md/**/*.py (excluding _legacy/)
```

Implementation requirements:

1. Add return type annotations to all functions missing them. The known
   gaps are approximately 40 functions across these subpackages:

   - `consensus/` (factory, grouping, reporting, scoring, io)
   - `export/` (reporting, io, docling)
   - `linking/` (extract, reporting, io, builder)
   - `conventions/` (determine_convention, alignment)
   - `models/` (priors, semantic_document)
   - `cli/` (main)
   - `backends/` (runner)
   - `calibration/` (metrics, io, vocabulary)
   - `testing/` (fixtures, mock_backend_ir)
   - `local/` (entity_proposal_validation)

2. Use concrete return types wherever possible:

   ```python
   def build_consensus_ir(...) -> ConsensusRunResult:
   def group_page_candidates(...) -> list[CandidateGroup]:
   def build_consensus_report(...) -> dict[str, Any]:
   def _load_json(path: Path) -> Any:
   ```

3. For functions returning `None`, annotate explicitly: `-> None`.

4. For private functions, add annotations for consistency but do not
   spend time on complex generic types for trivial helpers.

5. Ensure `from __future__ import annotations` is present at the top of
   every modified file.

Automated tests required:

```bash
conda run -n pdf2md python -c "
import ast, pathlib, sys
unannotated = []
for p in pathlib.Path('src/pdf2md').rglob('*.py'):
    if '_legacy' in str(p) or '__pycache__' in str(p):
        continue
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is None and not node.name.startswith('__'):
                unannotated.append(f'{p}:{node.lineno}:{node.name}')
if unannotated:
    print(f'{len(unannotated)} functions without return annotations:')
    for u in sorted(unannotated)[:20]: print(f'  {u}')
    if len(unannotated) > 20: print(f'  ... and {len(unannotated)-20} more')
    sys.exit(1)
print('All functions have return annotations.')
"
```

Also run the full test suite to verify no behaviour was changed:

```bash
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

Human verification required:
no

---

### Task A4 — Function docstrings for public API

Title:
Add Google-style docstrings to all public functions and classes

Goal:
Every public function, method, and class in active modules has a docstring
with summary, Args, Returns, and Raises sections as applicable.

Files allowed:

```text
src/pdf2md/**/*.py (excluding _legacy/)
```

Implementation requirements:

1. Add docstrings following the style guide from Task A1.

2. Prioritise by subpackage in this order (highest-impact first):

   a. `models/` — data model classes (ir.py, entities.py, priors.py,
      linked.py, export.py). Document Attributes for dataclasses and
      Pydantic models.

   b. `consensus/` — core pipeline logic (factory.py, grouping.py,
      scoring.py, io.py, reporting.py). Document the scoring algorithm,
      grouping logic, and I/O contracts.

   c. `connectors/` — backend connector (common.py). Document the
      raw-to-IR conversion and entity recognition.

   d. `calibration/` — calibration matching and metrics (matching.py,
      metrics.py, io.py, vocabulary.py). Document the matching
      algorithm and smoothed precision.

   e. `linking/` — linked structure (builder.py, extract.py, io.py,
      resolvers.py, reporting.py).

   f. `export/` — Docling/RAG/Markdown export (docling.py, rag.py,
      markdown.py, io.py, reporting.py).

   g. `backends/` — runner.py, config.py.

   h. `cli/` — main.py.

   i. `local/`, `conventions/`, `testing/` — support modules.

3. Private functions (`_` prefix) with >10 lines or non-obvious logic
   get a one-line docstring. Trivial private helpers may be skipped.

4. Do not add docstrings to `__init__`, `__repr__`, `__str__`,
   `__eq__`, or other dunder methods unless their behaviour is
   non-standard.

5. Pydantic models: use class docstring with Attributes section.
   Do not add per-field `#:` comments (they are redundant with Field
   descriptions where present).

Automated tests required:

```bash
conda run -n pdf2md python -c "
import ast, pathlib, sys
missing = []
for p in pathlib.Path('src/pdf2md').rglob('*.py'):
    if '_legacy' in str(p) or '__pycache__' in str(p):
        continue
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith('_'):
                continue
            if not ast.get_docstring(node):
                missing.append(f'{p}:{node.lineno}:{node.name}')
        elif isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node):
                missing.append(f'{p}:{node.lineno}:{node.name}')
if missing:
    print(f'{len(missing)} public symbols without docstrings:')
    for m in sorted(missing)[:20]: print(f'  {m}')
    if len(missing) > 20: print(f'  ... and {len(missing)-20} more')
    sys.exit(1)
print('All public symbols have docstrings.')
"
```

```bash
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

Human verification required:
yes (see checkpoint H1)

---

### Task A5 — Ruff and mypy enforcement

Title:
Run ruff fix and resolve mypy errors on active codebase

Goal:
`ruff check` and `mypy` pass cleanly on all active modules.

Files allowed:

```text
src/pdf2md/**/*.py (excluding _legacy/)
pyproject.toml (minor config adjustments if needed)
```

Implementation requirements:

1. Run ruff auto-fix:

   ```bash
   ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/ --fix
   ```

2. Review and manually fix any remaining ruff errors that auto-fix
   cannot resolve.

3. Run mypy:

   ```bash
   mypy src/pdf2md/ --exclude _legacy
   ```

4. Fix type errors. Common expected issues:
   - Missing return statements in branches.
   - `dict` vs `dict[str, Any]` ambiguities.
   - Pydantic model_dump/model_validate signatures.
   - `Any` in function signatures where concrete types are possible.

5. If a mypy error requires significant refactoring to fix, add a
   `# type: ignore[error-code]` with a comment explaining why, and
   document it in run_log.md. Do not refactor code in this plan.

6. Verify ruff and mypy pass cleanly:

   ```bash
   ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/
   mypy src/pdf2md/ --exclude _legacy
   ```

   Both must exit with code 0.

Automated tests required:

```bash
conda run -n pdf2md ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/
conda run -n pdf2md mypy src/pdf2md/ --exclude _legacy
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

Human verification required:
yes (see checkpoint H2)

---

## 7. Human verification checkpoints

### Checkpoint H1

Title:
Verify docstring quality on a sample of modules

Purpose:
Confirm that docstrings are accurate, follow the style guide, and add
value rather than being auto-generated boilerplate.

Required environment:
pdf2md

Preconditions:
Tasks A1–A4 are complete.

Commands:

```bash
conda run -n pdf2md python -c "import pdf2md.consensus.scoring; help(pdf2md.consensus.scoring.score_candidate_group)"
conda run -n pdf2md python -c "import pdf2md.connectors.common; help(pdf2md.connectors.common.connect_raw_dir)"
conda run -n pdf2md python -c "import pdf2md.calibration.matching; help(pdf2md.calibration.matching.match_blocks)"
```

Verification procedure:

1. Run each `help()` command. Read the displayed docstring.
2. Verify the docstring accurately describes what the function does.
3. Verify Args, Returns, and Raises sections are present and correct.
4. Verify the docstring is not generic boilerplate (e.g. "This function
   does what it says" is not acceptable).
5. Open `docs/docstring_style_guide.md` and verify the examples match
   the actual code.

Pass criteria:

```text
Each sampled function has a substantive docstring.
Args section lists all parameters with descriptions.
Returns section describes the return value.
Docstrings match the style guide.
```

Fail criteria:

```text
Any sampled function has a missing or boilerplate docstring.
Args section is incomplete or inaccurate.
Style guide examples don't match actual code.
```

Evidence to record:

```text
Paste help() output for each sampled function.
```

---

### Checkpoint H2

Title:
Verify ruff and mypy pass cleanly

Purpose:
Confirm zero lint and type errors on active source code.

Required environment:
pdf2md (with ruff and mypy installed)

Preconditions:
Task A5 is complete.

Commands:

```bash
conda run -n pdf2md pip install ruff mypy --break-system-packages 2>/dev/null
conda run -n pdf2md ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/
conda run -n pdf2md mypy src/pdf2md/ --exclude _legacy
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
```

Verification procedure:

1. Run ruff. Verify exit code 0 and no errors.
2. Run mypy. Verify exit code 0 and no errors (or only documented
   `type: ignore` with justification).
3. Run pytest. Verify all active tests pass.

Pass criteria:

```text
ruff exits 0 with no errors.
mypy exits 0 with no errors (or documented ignores only).
All active tests pass.
```

Fail criteria:

```text
ruff reports errors.
mypy reports errors without justification.
Any active test fails.
```

Evidence to record:

```text
Paste ruff output (should be empty or "All checks passed").
Paste mypy output.
Paste pytest summary line.
Count of type: ignore comments added (if any).
```

---

## 8. Test matrix and failure classification

Agent automated test matrix:

```bash
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp -x
conda run -n pdf2md ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/
conda run -n pdf2md mypy src/pdf2md/ --exclude _legacy
# AST-based docstring/annotation checks (from Tasks A2, A3, A4)
```

Failure classes:

repository_defect:
A docstring is inaccurate, a type annotation is wrong, or a runtime
behaviour change was introduced.

lint_error:
Ruff or mypy reports an error that was not resolved.

test_regression:
A test that previously passed now fails due to changes in this plan.

Failure handling:

If failure_class is repository_defect:
Fix the docstring or annotation.

If failure_class is lint_error:
Fix the lint issue or add a documented suppression.

If failure_class is test_regression:
Revert the change that caused the regression. This plan must not change
runtime behaviour.

---

## 9. Checkpoints, push policy, and hand-off

Push and PR policy:

```text
The agent may push the branch and open a draft PR.
The agent must not merge to main.
The PR diff should be documentation and annotation only — no logic changes.
```

---

## 10. Report templates and reviewer checklist

Agent report template:

```text
Plan: Additional Plan 3
Status:
Branch:
Commit or PR:
Files modified:
Modules with new docstrings:
Functions with new return annotations:
Functions with new docstrings:
Classes with new docstrings:
Ruff errors before:
Ruff errors after:
Mypy errors before:
Mypy errors after:
type: ignore comments added:
Tests run:
Tests passed:
Tests failed:
Blockers:
```

Reviewer checklist:

1. Did the agent modify only whitelisted files?
2. Are `_legacy/` modules untouched?
3. Are all changes documentation/annotation only (no logic changes)?
4. Do all active tests pass?
5. Does ruff pass with zero errors?
6. Does mypy pass with zero errors (or justified ignores)?
7. Are docstrings substantive (not boilerplate)?
8. Do docstrings follow Google-style format?
9. Are return type annotations concrete (not `Any` where avoidable)?
10. Is `from __future__ import annotations` present in all modified files?
11. Does the style guide match the implemented conventions?
12. Were sampled functions verified manually?

Status history:

```text
date — status — actor — note
```

Example:

```text
2026-05-24 — draft — human — Additional Plan 3 created for PEP compliance
```

---

## 11. Design notes

### Why Google-style docstrings?

Three common docstring formats exist: Sphinx/reST, NumPy, and Google.

- **Sphinx/reST** (`:param x: ...`) is verbose and hard to read without
  rendering. It is the oldest convention.
- **NumPy** (`Parameters\n----------`) is designed for scientific libraries
  with many parameters. It is vertically expensive for short functions.
- **Google** (`Args:\n    x: ...`) is compact, readable as plain text,
  and supported by Sphinx (via napoleon), mkdocs, and all major IDEs.

The project's existing code is compact and direct. Google-style matches
that aesthetic. The choice is consistent with PEP 257's recommendation
that docstrings be "useful" rather than "complete" — Google-style
encourages concise parameter descriptions rather than full-sentence
elaborations.

### PEP compliance summary

| PEP  | Status | Scope in this plan |
|------|--------|--------------------|
| 8    | Style  | Enforced via ruff (E, W rules) |
| 257  | Docstrings | Module, class, and function docstrings |
| 484  | Type hints | Return annotations, parameter types |
| 585  | Generics | `list[X]` not `List[X]` (via `__future__`) |
| 604  | Unions | `X \| Y` not `Union[X, Y]` (via `__future__`) |
| 727  | Withdrawn | Not applicable |

### What this plan does NOT change

- No function logic.
- No function signatures (except adding `-> ReturnType`).
- No import restructuring (beyond what ruff isort does).
- No test changes.
- No new tests.
- No dependency additions (ruff/mypy are dev-only).
- No changes to `_legacy/`, `backend/`, `tools/`, or `groundtruth/`.
