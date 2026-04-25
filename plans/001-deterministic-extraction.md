# Deterministic extraction: first end-to-end PDF -> Markdown

## Why this exists

The project needs a first fully working path that proves the architecture with real behavior, not only profiling and routing. After this milestone, a user will be able to run `python -m doc2md <input.pdf> -o <out>/` on a structurally suitable PDF and obtain a real Markdown file on disk, with extracted text page by page and embedded raster images saved under `media/` and referenced from the Markdown.

This milestone deliberately stops before OCR, layout detection, hybrid execution, and visual fallback. The goal is to make the deterministic lane real, observable, and testable, while preserving the profiler-first routing philosophy.

## Scope

### In scope

- Normalize package layout so the repository follows the current architecture conventions.
- Keep `python -m doc2md <input.pdf>` as the canonical entry point.
- Preserve or adapt the existing profiler and router so they work with the normalized package layout.
- Add shared result models for deterministic execution and assembly.
- Implement `doc2md/strategies/deterministic.py` as the real deterministic execution path.
- Extract embedded raster images in the deterministic lane and write them under `<output>/media/`.
- Implement an assembler that writes one Markdown file per input document.
- Wire the CLI to execute deterministic pages for real and warn clearly about skipped hybrid or visual pages.
- Add at least minimal `pytest` coverage plus one manual end-to-end smoke test.

### Out of scope

- OCR engines
- YOLO or any layout detector
- real hybrid execution
- real visual execution
- benchmarking framework
- YAML-driven model selection or registry patterns
- perfect Markdown reconstruction of layout, tables, or diagrams
- rasterization of vector graphics

## Current known state

The repository already has the core design intent settled. Input is PDF only. The page is the unit of work. Routing must happen from structural PDF signals before fallback, not from a subjective judgment of extracted text afterwards. The profiler and router logic already exist conceptually and may already be partially implemented in the current working tree, but the deterministic lane is still incomplete.

The active repository conventions require package execution through `python -m doc2md`, a profiler package exported through `doc2md/profiler/__init__.py`, and strategy modules under `doc2md/strategies/`. This plan therefore treats package normalization as part of the milestone instead of assuming the current tree already matches the target layout.

Known routing expectations that must remain true after this milestone:

- `POOR` font encoding quality still routes to `VISUAL`.
- `SUSPECT` font encoding quality may still route to `DETERMINISTIC` or `HYBRID` when `char_sample_valid` is true.
- `image_coverage_ratio` is the primary discriminator for deterministic versus hybrid suitability; `text_area_ratio` may be reported but should not become the main routing gate.

Known product limitation that remains acceptable in this milestone: vector diagrams may survive only as missing graphics while their extractable text remains present. This milestone does not claim perfect document fidelity.

## Target behavior

After this milestone:

1. `python -m doc2md tests/fixtures/year10-maths.pdf -o /tmp/doc2md_out/ -vv` runs end to end without import errors.
2. The CLI prints profiler and router information as before.
3. Pages routed to `DETERMINISTIC` are processed by a real strategy implemented in `doc2md/strategies/deterministic.py`.
4. The tool writes `/tmp/doc2md_out/year10-maths.md`.
5. Embedded raster images found on deterministically processed pages are written under `/tmp/doc2md_out/media/` and referenced from the Markdown.
6. If any page routes to `HYBRID` or `VISUAL`, the CLI warns that those pages are skipped because those strategies are not implemented yet.
7. `pytest -q` passes with at least small import and router tests.

## Design and decisions

### Package layout

The target layout for this milestone is:

    .
    ├── AGENTS.md
    ├── .agent/
    │   └── PLANS.md
    ├── docs/
    │   └── architecture.md
    ├── plans/
    │   └── 001-deterministic-extraction.md
    ├── doc2md/
    │   ├── __main__.py
    │   ├── cli.py
    │   ├── models.py
    │   ├── router.py
    │   ├── assembler.py
    │   ├── profiler/
    │   │   ├── __init__.py
    │   │   └── analyzer.py
    │   └── strategies/
    │       ├── __init__.py
    │       └── deterministic.py
    └── tests/

If the working tree still uses a flat `doc2md/profiler.py`, normalize it to `doc2md/profiler/analyzer.py` and re-export the public entry point from `doc2md/profiler/__init__.py`. Keep the router module separate. Keep `doc2md/strategies/__init__.py` minimal.

### Shared result models

Extend `doc2md/models.py` with two result dataclasses.

`MediaRef` describes one extracted raster image written to disk. It should include the relative path from the output directory, the page number, the image index within the page, and pixel dimensions.

`PageResult` is the transport object from a strategy to the assembler. It should include the page number, the Markdown text for that page, the list of `MediaRef` objects, the strategy used, and an optional error or warning string.

Suggested signatures:

    @dataclass
    class MediaRef:
        relative_path: str
        page_number: int
        index_in_page: int
        width_px: int
        height_px: int

    @dataclass
    class PageResult:
        page_number: int
        markdown: str
        media: list[MediaRef] = field(default_factory=list)
        strategy: Strategy | None = None
        error: str | None = None

### Deterministic strategy

Create `doc2md/strategies/deterministic.py` with a `DeterministicStrategy` class. It should accept the output directory at initialization and create `<output>/media/` lazily or eagerly with `exist_ok=True`.

Its main public method should process one PyMuPDF page and return a `PageResult`. The strategy should:

- call `page.get_text("text")` for the text layer,
- call `page.get_images(full=True)` to enumerate raster images,
- use `page.parent.extract_image(xref)` to recover the original bytes and extension,
- write each extracted image to a deterministic filename such as `media/img_p{page_number+1}_{index:03d}.{ext}`,
- build Markdown for the page that starts with `<!-- page N -->`, includes the extracted text, and appends one `![](<relative_path>)` line per extracted image.

If one image stream fails to extract, skip that image, record a note in the page-level error string, and continue processing the page.

### Assembler

Create `doc2md/assembler.py` with an `Assembler` class that accepts `output_dir` and `stem`. It should sort `PageResult` objects by `page_number`, concatenate their `markdown` with a blank line between pages, and write `<output_dir>/<stem>.md`.

The assembler should return both the path and a small stats dictionary such as:

    {
        "pages": <int>,
        "chars": <int>,
        "media": <int>
    }

The assembler does not extract media itself. It only writes the Markdown file and reports counts.

### CLI orchestration

Update `doc2md/cli.py` so that after profiling and routing, it opens the PDF once with PyMuPDF, processes deterministic pages through `DeterministicStrategy`, and assembles the resulting `PageResult` objects.

Hybrid and visual lanes remain stubs in this milestone, but the CLI must say so explicitly. The absence of those lanes must never silently produce a misleading “complete” success message.

### Tests

Add at least two minimal tests under `tests/`.

The first is an import or package smoke test proving the package layout is consistent and key imports resolve. The second is a pure router test using synthetic `PageProfile` values to lock the corrected routing behavior:

- `POOR` -> `VISUAL`
- `SUSPECT` plus valid sample does not automatically force `VISUAL`
- low image coverage with trustworthy text -> `DETERMINISTIC`

The manual smoke test on the fixture PDF remains required in addition to `pytest`.

## Milestones

### Milestone 1 - Normalize package layout and public imports

Files likely to change:

- `doc2md/__main__.py`
- `doc2md/cli.py`
- `doc2md/profiler/__init__.py`
- `doc2md/profiler/analyzer.py`
- optional cleanup of any obsolete flat `doc2md/profiler.py`
- `doc2md/strategies/__init__.py`

Work:

Normalize the package so the repository matches the current architecture conventions. Ensure `python -m doc2md` is the canonical entry point. Ensure `doc2md.profiler` exposes the intended public profiling function through `__init__.py`. Ensure the router import path remains stable after normalization.

Validation:

    python -m doc2md --help
    python -c "from doc2md.profiler import profile_document; print(profile_document.__name__)"

Success means the package imports cleanly and the public profiler API resolves from the package path.

### Milestone 2 - Add result models and real deterministic execution

Files likely to change:

- `doc2md/models.py`
- `doc2md/strategies/deterministic.py`
- `doc2md/strategies/__init__.py`
- `doc2md/assembler.py`

Work:

Add `MediaRef` and `PageResult` to `doc2md/models.py`. Implement `DeterministicStrategy` in `doc2md/strategies/deterministic.py`. Implement `Assembler` in `doc2md/assembler.py`. Keep the interfaces small and explicit.

Validation:

    python -c "from pathlib import Path; from doc2md.strategies.deterministic import DeterministicStrategy; s = DeterministicStrategy(Path('/tmp/doc2md_test')); print(s.media_dir)"
    python -c "from pathlib import Path; from doc2md.assembler import Assembler; a = Assembler(Path('/tmp/doc2md_test'), 'sample'); print(a.stem)"

Success means both modules import and their objects instantiate without error.

### Milestone 3 - Wire deterministic execution into the CLI

Files likely to change:

- `doc2md/cli.py`
- `doc2md/assembler.py`
- `doc2md/strategies/deterministic.py`

Work:

Replace the deterministic print stub in `run_pipeline` with real execution. Open the PDF once, process each deterministically routed page with `DeterministicStrategy`, collect `PageResult` objects, assemble them into a Markdown file, and print a final assembler summary. Keep hybrid and visual paths as explicit warnings only.

Validation:

    python -m doc2md tests/fixtures/year10-maths.pdf -o /tmp/doc2md_out/ -vv
    test -f /tmp/doc2md_out/year10-maths.md && echo OK
    head -30 /tmp/doc2md_out/year10-maths.md

Success means the Markdown file exists, begins with a page separator comment, and contains recognizable text from the fixture.

### Milestone 4 - Add minimal automated validation

Files likely to change:

- `tests/test_imports.py`
- `tests/test_router.py`
- optional small fixture notes under `tests/fixtures/`

Work:

Add a package import smoke test and a pure router unit test covering the corrected routing behavior. Keep the tests small and deterministic.

Validation:

    pytest -q

Success means both tests pass and the repository has a minimal automated guardrail for the deterministic milestone.

## Validation

From the repository root, in the project environment:

    conda create -n doc2md python=3.12 -y
    conda activate doc2md
    pip install pymupdf pyyaml pytest
    python -m doc2md tests/fixtures/year10-maths.pdf -o /tmp/doc2md_out/ -vv
    pytest -q

Expected observable results:

- the CLI exits with status 0,
- the profiler still reports the fixture PDF as structurally suitable for deterministic processing,
- `/tmp/doc2md_out/year10-maths.md` exists and is non-empty,
- if raster images are present on deterministically processed pages, files appear under `/tmp/doc2md_out/media/`,
- `pytest -q` reports success.

A reviewer should be able to open the Markdown output and read the document’s text in plain form. That behavior matters more than the internal class names.

## Risks and rollback notes

Import layout mistakes can make the package unrunnable. Fix layout and public imports before feature work.

Image extraction may surface duplicate or tiny decorative images. That is acceptable in this milestone as long as the filenames are deterministic and the behavior is documented.

`image_coverage_ratio` still misses vector drawings. That limitation remains acceptable for the deterministic-first slice and should not trigger router redesign in this plan.

If end-to-end output is poor on a supposedly deterministic PDF, inspect profiler signals and the raw extracted text before changing thresholds. Do not weaken the profiler-first routing principle just to fit one sample.

All file-writing steps should be safe to repeat. Re-running the tool should overwrite the Markdown file and any deterministically named media files without crashing.

## Progress

- [x] 2026-04-25: Normalized package surface (`doc2md/__init__.py` and canonical `doc2md/assembler.py`).
- [x] 2026-04-25: Added deterministic lane models (`MediaRef`, `PageResult`) and initial `DeterministicStrategy` implementation.
- [x] 2026-04-25: Wired deterministic execution + assembly into CLI for routed deterministic pages.
- [x] 2026-04-25: Added minimal automated tests (`tests/test_imports.py`, `tests/test_router.py`).
- [ ] Remaining: validate against a real sample PDF and refine output behavior for skipped HYBRID/VISUAL pages.

## Surprises & Discoveries

- 2026-04-25: Repository contained empty placeholder modules (`doc2md/strategies/deterministic.py` and others), so path normalization and first concrete implementations were needed before behavioral validation.

## Decision Log

- Use `doc2md/strategies/deterministic.py` instead of a flat `doc2md/deterministic.py`.
- Include extraction of embedded raster images in the deterministic lane and reference them from Markdown.
- Keep minimal `pytest` validation in scope for this milestone.
- Use `page.get_text("text")` for v1 deterministic extraction rather than introducing `pymupdf4llm`.
- 2026-04-25: Standardize on `doc2md/assembler.py` as the only assembly module path to match the active plan and avoid split references.

## Outcomes & Retrospective

- 2026-04-25 (interim): The codebase now has an executable deterministic lane path and minimal router/import tests, reducing risk for the next validation-focused iteration.
