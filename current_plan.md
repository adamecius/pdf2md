# Current plan

## Goal

Create a repository tool at `tools/compile_latex_groundth.py` that compiles every LaTeX ground-truth fixture under:

- `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`

For each selected fixture, the tool must produce both:

- `groundtruth/corpus/latex/<doc_id>/<doc_id>.pdf`
- `groundtruth/corpus/latex/<doc_id>/<doc_id>.latexml.xml`

The PDF must be produced with LuaLaTeX because this is the LaTeX engine selected for the tagged, semantically richer PDF path. The XML sidecar must be produced with LaTeXML because it preserves a source-derived semantic representation that can later be used for validation, inspection, and comparison.

The script must not edit `.tex` sources. It must be deterministic, idempotent, hash-gated, and explicit about missing external tools. If required TeX tooling is unavailable, it must print a clear `HUMAN TASK` block and exit with code `42` rather than installing anything.

This plan intentionally treats the PDF and XML as two separate witnesses:

- the LuaLaTeX PDF is the rendered ground-truth target;
- the LaTeXML XML is a semantic sidecar;
- the `.tex` source remains the authoring source of truth.


## Whitelist

Files the agent may create, modify, or delete under this plan. Anything else is forbidden.

- `tools/compile_latex_groundth.py`
- `tests/test_compile_latex_groundth.py`
- `groundtruth/corpus/latex/**/*.pdf` generated or updated output only
- `groundtruth/corpus/latex/**/*.latexml.xml` generated or updated output only
- `groundtruth/corpus/latex/**/*.latexml.log` generated or updated output only
- `groundtruth/corpus/latex/**/build.log` generated or updated output only
- `groundtruth/corpus/latex/**/*.synctex.gz` generated or updated output only
- `run_log.md`

Explicitly forbidden under this plan:

- editing any `groundtruth/corpus/latex/**/*.tex` source file;
- editing any `groundtruth/corpus/latex/**/*.bib` source file;
- editing `project.md`, `history.md`, `agent.md`, or this plan in agent mode;
- committing temporary TeX auxiliary files such as `.aux`, `.out`, `.toc`, `.bcf`, `.bbl`, `.blg`, `.fls`, `.fdb_latexmk`, `.run.xml`, or `.log` except for the explicitly whitelisted `build.log` and `.latexml.log`.


## Dependencies

Python packages:

- none.

External system tools allowed:

- `lualatex`
- `latexml`
- `biber`, only when a bibliography run is required

The agent must not install TeX Live, MacTeX, LaTeXML, Perl packages, operating-system packages, or any other external dependency. Missing required tools must be handled by the script as a user-facing environment problem with exit code `42`.

Read-only validation tools such as `python`, `pytest`, `compileall`, and `git status` are allowed as normal repository validation commands.


## Tasks

### T1 — Implement the dual LuaLaTeX and LaTeXML compiler tool

Create `tools/compile_latex_groundth.py`.

The script must provide this CLI:

    python tools/compile_latex_groundth.py \
      --corpus-root groundtruth/corpus/latex \
      [--doc <doc_id>] \
      [--force]

Behaviour:

- Default `--corpus-root` to `groundtruth/corpus/latex`.
- Discover fixture directories matching `groundtruth/corpus/latex/<doc_id>/`.
- For each selected fixture, require `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex`.
- If `--doc <doc_id>` is provided, process only that document and fail clearly if it does not exist.
- Process documents in sorted order for deterministic output.
- Never modify `.tex` or `.bib` inputs.
- Use a temporary output directory outside the committed corpus tree for TeX auxiliary files, then copy only whitelisted final artefacts back into the document directory.
- Write one `build.log` per document in the document directory.
- Print a concise per-document summary to stdout.

Tool detection:

- Require `lualatex` before any PDF compilation.
- Require `latexml` before any XML conversion.
- Require `biber` only when bibliography processing is actually needed.
- If any required tool is missing, print a `HUMAN TASK` block that names the missing executable, explains that the script does not install dependencies, and exits `42`.

PDF stage:

- Run LuaLaTeX from the document directory so relative asset paths continue to resolve.
- Use a temporary output directory for auxiliary files.
- Invoke LuaLaTeX with:

    lualatex -interaction=nonstopmode -halt-on-error -file-line-error -recorder -synctex=1 -output-directory <tmpdir> <doc_id>.tex

- Run LuaLaTeX at least twice.
- After the first LuaLaTeX pass, if a `.bcf` file exists in the temporary output directory, run:

    biber --input-directory <tmpdir> --output-directory <tmpdir> <doc_id>

  Then run LuaLaTeX two more times.
- Copy the final `<doc_id>.pdf` back to the document directory.
- Copy `<doc_id>.synctex.gz` back if LuaLaTeX produced it.
- Fail the document if the final PDF is missing.
- Treat these as blocking PDF-stage failures:
  - process return code is non-zero;
  - log lines beginning with `! `;
  - missing input files;
  - undefined control sequences;
  - unresolved citations after the final pass;
  - unresolved references after the final pass.

XML stage:

- Run LaTeXML from the document directory.
- Invoke:

    latexml --destination=<doc_id>.latexml.xml --log=<doc_id>.latexml.log --documentid=<doc_id> <doc_id>.tex

- If an `assets/` directory exists beside the source `.tex`, include:

    --path=assets

- Fail the document if `<doc_id>.latexml.xml` is missing or empty.
- Treat LaTeXML fatal errors and non-zero exit codes as blocking failures.
- Treat LaTeXML warnings as non-blocking, but record them in `build.log`.

Hash gating:

- Compute one SHA-256 build hash per document.
- The hash must include:
  - `<doc_id>.tex`;
  - every `.bib` file in the document directory, sorted by relative path;
  - every file under `assets/`, sorted by relative path;
  - `lualatex --version` output;
  - `latexml --VERSION` output, falling back to `latexml --version` if needed;
  - `biber --version` output when biber is required;
  - a script schema string such as `compile_latex_groundth_v1_lualatex_latexml`.
- Store the hash near the top of `build.log`.
- Skip a document only when all of the following are true:
  - `--force` was not passed;
  - `build.log` contains the same build hash;
  - `<doc_id>.pdf` exists;
  - `<doc_id>.latexml.xml` exists and is non-empty.
- A skipped document must still be reported in stdout.

Source metadata check:

- If the source does not appear to contain `\DocumentMetadata` before `\documentclass`, record a warning in `build.log`.
- Do not edit the source to add metadata.
- This warning is not a blocking failure because the script is a compiler, not a source normaliser.

Exit behaviour:

- Exit `0` only when all selected documents were either successfully built or correctly skipped by hash gating.
- Exit `42` only for missing required external tools.
- Exit non-zero for compilation, conversion, validation, or argument errors.
- If more than one document is selected, continue processing remaining documents after a per-document compile failure, then exit non-zero at the end with a summary of failed documents.

Files: `tools/compile_latex_groundth.py`, `run_log.md`, and generated whitelisted artefacts under `groundtruth/corpus/latex/**`.


### T2 — Add automated tests for the compiler tool contract

Create `tests/test_compile_latex_groundth.py`.

The tests must avoid requiring a real TeX installation by using temporary directories and mocking subprocess execution where needed.

Required coverage:

- CLI help exits successfully without checking for TeX tools.
- Document discovery finds `groundtruth/corpus/latex/<doc_id>/<doc_id>.tex` and ignores unrelated directories.
- `--doc <doc_id>` restricts execution to one fixture.
- Missing `lualatex` or `latexml` produces exit code `42` and a `HUMAN TASK` message.
- The LuaLaTeX command includes `-interaction=nonstopmode`, `-halt-on-error`, `-file-line-error`, `-recorder`, `-synctex=1`, and `-output-directory`.
- The XML command invokes `latexml` with `--destination`, `--log`, and `--documentid`.
- `--path=assets` is passed when an `assets/` directory exists.
- A `.bcf` file after the first LuaLaTeX pass triggers `biber`.
- Matching build hash plus existing PDF and XML causes the document to be skipped unless `--force` is passed.
- Blocking LaTeX errors, unresolved citations, unresolved references, and LaTeXML fatal errors cause non-zero failure.
- The script never writes to or rewrites the `.tex` source in the test fixture.

Files: `tools/compile_latex_groundth.py`, `tests/test_compile_latex_groundth.py`, `run_log.md`.


### T3 — Validate the tool against repository fixtures where tooling is available

Run the tool against the repository corpus only if the required external tools are present in the execution environment.

If the tools are present, run:

    python tools/compile_latex_groundth.py --corpus-root groundtruth/corpus/latex

Then verify that each selected fixture has:

- `<doc_id>.pdf`
- `<doc_id>.latexml.xml`
- `build.log`

If the tools are missing, do not install them. Record the missing-tool result in `run_log.md` as an environmental blocker or human-required validation, with the script's `HUMAN TASK` output and exit code `42`.

Files: `run_log.md` and generated whitelisted artefacts under `groundtruth/corpus/latex/**`.


## Tests

Tests are automated by default unless explicitly tagged `human`.

### A1 — CLI help smoke test

command:

    python tools/compile_latex_groundth.py --help

pass: command exits `0`, prints CLI usage, and does not require `lualatex`, `latexml`, or `biber` to be installed.


### A2 — Unit test suite for compiler contract

command:

    PYTHONPATH=src python -m pytest tests/test_compile_latex_groundth.py

pass: all tests pass without requiring a real TeX installation.


### A3 — Python syntax compilation

command:

    python -m compileall tools/compile_latex_groundth.py tests/test_compile_latex_groundth.py

pass: both Python files compile without syntax errors.


### A4 — Actual corpus compile in TeX-capable environment

tag: human

command:

    python tools/compile_latex_groundth.py --corpus-root groundtruth/corpus/latex --force

pass: every selected corpus fixture either produces both PDF and XML successfully, or any failure is a real source/tooling issue recorded with the failing document ID and log path. Missing TeX or LaTeXML tools are acceptable only as a human-environment blocker with exit code `42`.


### A5 — Generated artefact inspection

tag: human

command:

    find groundtruth/corpus/latex -maxdepth 2 -type f \( \
      -name '*.pdf' -o \
      -name '*.latexml.xml' -o \
      -name 'build.log' \
    \) | sort

pass: for each compiled `<doc_id>`, the expected PDF, XML sidecar, and build log are present; no unexpected TeX auxiliary files are left in the corpus tree.


## Status

T1: pending
T2: pending
T3: pending


## PR_reviews

(Empty. Filled by review mode, one section per PR.)


## Feedback

(Empty. Filled by feedback mode in response to PR_reviews and human input.)