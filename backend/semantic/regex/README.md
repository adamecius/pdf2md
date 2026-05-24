# Regex / heuristic semantic backend

Deterministic pattern-based detector for cross-reference markers in
already-extracted plain text. The lightest of the three semantic
backends planned by Plan 005.

## What it detects

| Marker type | Examples |
|---|---|
| `figure` | `Figure 3`, `Fig. 3.2`, `Figures 1 and 2` |
| `table` | `Table 3`, `Tables 1 and 2` |
| `equation` | `Eq. 3`, `Equation 3.2`, `(3.2)` |
| `bibliography` | `[15]`, `[12, 13]`, `[12-14]`, `(Smith, 2020)`, `(Smith et al. 2020)` |
| `section` | `Section 3`, `Sec. 3.2` |
| `chapter` | `Chapter 5` |
| `theorem` | `Theorem 3.2` |
| `definition` | `Definition 1.1` |
| `proof` | `Proof of Theorem 3.2` |
| `corollary` | `Corollary 4.1` |
| `example` | `Example 2.3` |
| `footnote` | `footnote 3`, `fn. 3` |

The patterns are tuned for English-language scientific writing.
Other languages and typographic conventions will need separate
patterns.

## Install

Nothing to install — stdlib only.

The backend runs in any Python ≥ 3.10 environment, including the
main `pdf2md` conda env.

## Run the smoke test

```bash
conda activate pdf2md   # or any Python 3.10+ shell

python backend/semantic/regex/smoke_test.py \
    --text tests/data/semantic_fixtures/sample_text.txt \
    --out-dir /tmp/regex_smoke
```

Expected:

```text
regex smoke: <N> markers, <M> distinct types, ... ms, out=/tmp/regex_smoke/regex_smoke_result.json
exit code 0
```

Plan 005 acceptance requires `M ≥ 3`.

## Output shape

`regex_smoke_result.json` is a single JSON object:

```jsonc
{
  "backend": "regex",
  "backend_version": "0.1.0",
  "input_path": "tests/data/semantic_fixtures/sample_text.txt",
  "input_chars": 487,
  "elapsed_ms": 0.32,
  "markers": [
    {"marker_type": "figure", "marker_text": "Figure 3", "char_offset": [12, 20]},
    {"marker_type": "bibliography", "marker_text": "[15]", "char_offset": [55, 59]}
  ],
  "counts_by_type": {"figure": 1, "bibliography": 1}
}
```

## Library use

Plan 005 keeps this backend standalone. The module that does the work
is `patterns.py`:

```python
from backend.semantic.regex import patterns

hits = patterns.find_markers("See Figure 3 and [15].")
for h in hits:
    print(h.marker_type, h.marker_text, h.char_offset)
```

Plan 006 will wrap this in the `SemanticBackend` interface under
`src/pdf2md/semantic/regex_adapter.py`. Until then, do not import
this module from `src/pdf2md/`.

## Limitations

- Bibliography author-year matcher is intentionally conservative —
  it requires the closing paren and a 4-digit year. It will miss
  more exotic forms like `Smith and Jones 2020a`.
- No span-overlap heuristics yet: when two distinct phrases sit
  side-by-side (`Figure 3 and Table 4`) the regex covers both
  separately rather than as a compound reference.
- Detection only — no resolution to a target item. Resolution is
  Plan 006 territory.
