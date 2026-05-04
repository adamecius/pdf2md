# Current plan

## Goal

Create `scripts/compile_corpus.py` — an idempotent compiler that turns the canonical corpus from Plan 1 into tagged PDFs using `lualatex` + `biber`.

## Scope and non-goals

In scope: new compilation script with hash gating, build.log, and explicit HUMAN TASK flagging if lualatex/biber are missing.

Out of scope: certification, pipeline updates, README changes.

## Whitelist

Create or write:
- `scripts/compile_corpus.py`                             (new, has CLI)

Modify: none

## Tasks

### T2 — `scripts/compile_corpus.py`

Walk the corpus (`groundtruth/corpus/latex/`), compile each fixture with `lualatex` (run twice + `biber` if `.bib` exists and is referenced).

**Critical requirement for missing tools:**
- At startup, check if `lualatex` and `biber` are available (use `shutil.which`).
- If either is missing, print the following exact block and exit gracefully (exit code 42):
HUMAN TASK: lualatex and/or biber not found on this system.
Please install a full TeX Live distribution that includes LuaLaTeX and biber:
https://www.tug.org/texlive/
After installation, verify with:
which lualatex
which biber
Then re-run:
python scripts/compile_corpus.py --corpus-root groundtruth/corpus/latex
text- Do NOT attempt to install anything or continue. Just flag and exit.

Capture `build.log`.  
Idempotent via SHA-256 hash of `.tex` + `.bib` + `assets/*` stored in the header of `build.log`.

CLI:

python scripts/compile_corpus.py --corpus-root groundtruth/corpus/latex [--doc <id>] [--force]

Exit 0 on full success. Exit 42 on HUMAN TASK (missing TeX tools). Exit non-zero with per-document summary on any other failure (parsed from `! ` lines, undefined references/citations).

Files: `scripts/compile_corpus.py`
