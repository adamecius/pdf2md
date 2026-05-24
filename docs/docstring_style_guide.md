# Docstring Style Guide

This guide documents the docstring, type-annotation, and lint conventions
used in `src/pdf2md/`. It is the canonical reference for the conventions
enforced by Additional Plan 3.

The conventions apply to every `.py` file under `src/pdf2md/` except
`src/pdf2md/_legacy/` (legacy modules are scheduled for removal).

`tools/`, `backend/`, and `tests/` are out of scope for this guide.

---

## 1. Format choice

The project uses **Google-style** docstrings.

Three formats exist in the wider Python ecosystem: Sphinx/reST,
NumPy, and Google. Google-style is chosen because:

- It is readable as plain text (no rendering required).
- It is compact for short functions, which the project favours.
- It is supported by Sphinx (via napoleon), mkdocs, and every major
  IDE.

PEP 727 (a proposal for "Documentation Metadata in Typing") was
withdrawn in October 2024. There is no current PEP for in-code
metadata beyond PEP 257.

---

## 2. Module docstrings

Every module must begin with a docstring.

Use a single triple-quoted line for focused modules:

```python
"""Scoring for page-local consensus candidate groups."""
```

Use a multi-line docstring for complex modules. The first line is a
short summary, followed by a blank line and one or more paragraphs:

```python
"""Filesystem I/O for calibration inputs and outputs.

This module handles discovery of calibration documents, loading of
truth files with Docling-to-BlockKind normalisation, and writing of
prior output files.
"""
```

`__init__.py` files get a one-line docstring describing the
subpackage:

```python
"""Calibration: backend prior generation from ground truth."""
```

---

## 3. Function and method docstrings

Public functions and methods use a Google-style docstring with the
following sections (in order, each optional except the summary):

1. **Summary** — imperative one-line description.
2. **Optional descriptive paragraph(s)** — context, algorithm notes,
   invariants.
3. **Args:** — parameters and what they mean.
4. **Returns:** — what the function produces.
5. **Raises:** — exceptions in the normal contract.

Example:

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
    calibration priors, and entity-level priors. Selects the
    highest-scoring candidate or marks the group as unresolved if
    the margin is within the configured threshold.

    Args:
        group: The candidate group containing blocks from different
            backends that were matched to the same logical region.
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

### Section formatting rules

- **Args:** lines wrap at four spaces of indentation for continuation
  lines (eight spaces total relative to the docstring's left edge).
- **Returns:** describes the value, not the type. The type is in the
  annotation.
- **Raises:** lists only exceptions that callers must handle. Internal
  programming errors raised via `assert` are not documented.
- Omit a section entirely if it has nothing to say (do not write
  `Args: None.`).

### Style rules

- Summary uses present tense ("Compute…", "Return…", "Build…"), not
  past or progressive ("Computes" is also acceptable when the function
  name reads as a noun).
- Summary fits on one line (~80 chars). If it doesn't, the function
  is doing too much or being described too literally.
- Describe contract, not implementation. "Returns the highest-scoring
  candidate" is good; "Iterates over candidates and tracks the
  maximum" is implementation leak.
- Reference other functions by their fully qualified path if not in
  the same module: `pdf2md.consensus.scoring.score_candidate_group`.

---

## 4. Class and dataclass docstrings

Classes use a Summary + Attributes section:

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

### Pydantic models

For Pydantic `BaseModel` subclasses, use a class docstring with an
Attributes section. Do **not** also add per-field `#:` comments —
they duplicate `Field(..., description=...)` content where present.

```python
class CalibrationPriorDocument(BaseModel):
    """Calibrated per-backend confidence priors.

    Attributes:
        schema_name: Fixed marker for the JSON schema.
        backend: Backend identifier.
        per_block_kind: Per-BlockKind precision/recall metrics.
        per_entity_type: Per-EntityType metrics.
        status: Calibration status (calibrated, uninformative, ...).
    """
```

### Protocols and ABCs

For abstract base classes and `typing.Protocol`s, document the
contract every implementer must satisfy. Each abstract method also
gets a docstring describing its contract.

---

## 5. Private functions

Private functions (prefixed with `_`) are documented selectively:

- **One-line docstring** if the function is non-obvious (e.g.
  contains a regex, performs a multi-step transform, or has a side
  effect not implied by its name) or longer than ~10 lines.
- **No docstring** for trivial single-expression helpers
  (`def _is_empty(x): return not x`).

```python
def _tokens(text: str | None) -> set[str]:
    """Extract lowercase word tokens from text."""
    return set(re.findall(r"[\w]+", normalise_text(text)))
```

Private functions still get full type annotations.

---

## 6. Dunder methods

Do not write docstrings for `__init__`, `__repr__`, `__str__`,
`__eq__`, `__hash__`, `__len__`, or other standard dunders unless
their behaviour is non-standard.

If a dunder's behaviour is non-standard, document the deviation.

---

## 7. Type annotations

### PEP versions in scope

| PEP  | Subject      | How we apply it |
|------|--------------|-----------------|
| 8    | Style        | Enforced via ruff (E, W, F rules) |
| 257  | Docstrings   | Module, class, public function (this guide) |
| 484  | Type hints   | Every function carries a return annotation |
| 585  | Generics     | `list[X]`, `dict[K, V]`, `tuple[X, ...]` |
| 604  | Unions       | `X \| Y` and `X \| None` (not `Union`/`Optional`) |
| 727  | Withdrawn    | Not used |

### Conventions

- Every module starts with `from __future__ import annotations` (this
  permits forward references and lazy evaluation of annotations
  without quoting).
- Every function has a return annotation, including `-> None`.
- Parameters are annotated. Self/cls are not annotated.
- Prefer concrete types over `Any`. Use `Any` only when the value is
  truly opaque at the boundary (e.g. raw JSON before validation).
- Use `Sequence`, `Mapping`, `Iterable`, `Iterator` from
  `collections.abc` for parameter types when the function does not
  need a concrete list/dict.
- Use `TypedDict` or pydantic models when a `dict` has a fixed shape.

### Examples

```python
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

def load_priors(
    paths: Iterable[Path],
    *,
    backend_aliases: Mapping[str, str] | None = None,
) -> dict[str, CalibrationPriorDocument]:
    """Load calibration prior JSONs from disk."""
    ...
```

---

## 8. Linter and type checker

Ruff and mypy are declared in `pyproject.toml`. They must pass with
zero errors on `src/pdf2md/` (excluding `_legacy/`).

### Ruff

```bash
# Lint check
ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/

# Apply auto-fixable rules
ruff check src/pdf2md/ --exclude src/pdf2md/_legacy/ --fix
```

The active rule set is configured in `pyproject.toml` under
`[tool.ruff.lint]`. Adding a new rule is a deliberate change — do
not silently broaden the rule set in a feature PR.

Targeted ignores are allowed per-line with a same-line justification:

```python
x = some_call()  # noqa: B007 — loop var consumed by upstream API
```

Blanket file or directory ignores require a rationale recorded in
`run_log.md` and a comment at the suppression site.

### Mypy

```bash
mypy src/pdf2md/ --exclude _legacy
```

Type errors are fixed by edits to the code, not by silencing them.
A `# type: ignore[error-code]` is allowed only with a same-line
justification:

```python
result = framework_call()  # type: ignore[misc] — upstream lacks stubs
```

The `error-code` form (rather than bare `# type: ignore`) is
required so future readers know which check was suppressed.

---

## 9. What this guide does not cover

- Tests under `tests/` (separate scope; test names already describe
  intent).
- CLI scripts under `tools/` (separate scope; they use argparse and
  follow a different convention).
- Backend wrappers under `backend/` (each backend has its own
  upstream conventions).
- Legacy modules under `src/pdf2md/_legacy/` (scheduled for removal).

---

## 10. References

- PEP 8 — Style Guide for Python Code
- PEP 257 — Docstring Conventions
- PEP 484 — Type Hints
- PEP 585 — Type Hinting Generics in Standard Collections
- PEP 604 — Allow writing union types as `X | Y`
- Google Python Style Guide §3.8 — Comments and Docstrings
- Sphinx napoleon — Google-style docstring parser
