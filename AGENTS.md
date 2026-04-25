# AGENTS.md

Guidance for coding agents (Codex, Claude, etc.) working on this repository. Human contributors should read `README.md`.

## Project purpose
`doc2md` converts PDF documents into Markdown through a staged pipeline.

Current product direction:
- Input is PDF only.
- The system should profile PDF structure with pure software first.
- The profiler decides whether a page is viable for deterministic extraction before any OCR/layout fallback is used.
- The natural unit of work is the page, not the whole document.
- The first milestone is a solid profiler + router + deterministic text lane.
- OCR, layout detection, hybrid extraction, benchmarking, and media handling are deferred unless the active plan explicitly includes them.

## Package and plan conventions
- Canonical entry point: `python -m doc2md <input.pdf>`
- Prefer package execution over a root `doc2md.py` script to avoid import-name collisions.
- If a thin root script is added later, it must delegate to the package and must not shadow imports.
- If `doc2md.profiler` is a package, export the intended public API from `doc2md/profiler/__init__.py`.
- Multi-step work should follow the ExecPlan format defined in `.agent/PLANS.md`.
- Concrete plans live under `plans/` with numeric prefixes.
- Naming convention for sequential plans: `00X-kebab-case-topic.md`.
- Naming convention for parallel-launch plans in the same wave: `00X_n-kebab-case-topic.md` (example: `003_1-mineru-backend.md`, `003_2-paddleocr-vl-backend.md`).
- Any `00X_n` plan must be independently executable, with explicit dependencies and merge touchpoints listed in its Scope and Milestones.
- Use US English in plan titles, headings, and user-facing wording (for example, "behavior" not "behaviour").
- The current baseline plan is `plans/001-deterministic-extraction.md` (implemented).
- The next architecture extension plan is `plans/002-docir-offline-foundations.md`.
- Backend expansion feasibility is documented in `plans/003-backend-feasibility-and-parallel-launch.md`.

## Architecture rules
1. Keep routing decisions separate from extraction logic.
   - `profiler` gathers structural signals.
   - `router` maps those signals to a strategy.
   - `strategies` execute the chosen work.
2. Prefer deterministic extraction when the PDF text layer is structurally trustworthy.
3. Do not decide fallback only by “the text looks bad after extraction”; use structural signals from the PDF beforehand.
4. Keep routing thresholds centralized and documented.
5. Use typed dataclasses or enums for shared models.
6. Avoid hidden magic. Emit a clear per-page profile and routing summary.
7. Make each milestone observable from the CLI.

## Current routing philosophy
For v1, evaluate each page using signals such as:
- whether a text layer exists
- whether fonts expose usable Unicode mappings
- whether text is rendered invisibly
- image coverage ratio
- font encoding quality
- a small character sample validity check

Heuristic intent:
- No trustworthy text layer -> visual lane later
- Trustworthy text layer and little visual-only content -> deterministic lane
- Mixed content with trustworthy text -> hybrid lane later

Important routing rules:
- Empirical evidence can override mild structural suspicion: if encoding quality is `SUSPECT` but the sampled extracted text is valid, the page may still route to the deterministic lane.
- `POOR` encoding quality should still force the visual lane.
- Do not use `text_area_ratio` as the primary discriminator between deterministic and hybrid. PyMuPDF text block boxes are compact and make that ratio misleadingly low on text-heavy pages. Use `image_coverage` as the main discriminator instead.

## Known current limitation
Vector graphics can contain meaningful diagrams while still producing zero raster image coverage. For the deterministic-only milestone, preserving extractable text is more important than preserving diagrams. Do not silently claim perfect document fidelity.


## Licensing and usage constraints
This repository is non-commercial, offline, and intended for free learning and personal document processing.

Dependency policy must reflect that intent:
- Optional integrations may use permissive, research, educational, or non-commercial-compatible licenses.
- License constraints should not block local experimentation.
- Heavy or restrictive backends must remain optional, lazy-loaded, and excluded from default tests.

## Environment conventions
Use a local `.venv` by default for Python runtime and package isolation. Conda is optional when contributors prefer conda-managed Python runtimes; continue using pip for Python packages inside either environment.

Recommended starting environment for the current milestone (default):
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pymupdf pyyaml pytest
```

Optional conda runtime setup:
```bash
conda create -n doc2md python=3.12 -y
conda activate doc2md
pip install --upgrade pip
pip install pymupdf pyyaml pytest
```

Do not add OCR or YOLO dependencies in the deterministic milestone.
Do not add runtime ML dependencies (torch, transformers, ultralytics) to the profiler or router. Those remain pure software.

## Expected repo layout
This is the target shape unless the active plan says otherwise:
```text
.
├── AGENTS.md
├── .agent/
│   └── PLANS.md
├── docs/
│   └── architecture.md
├── plans/
│   ├── 001-deterministic-extraction.md
│   └── 002-docir-offline-foundations.md
├── benchmarks/
│   └── omnidocbench/
├── doc2md/
│   ├── __main__.py
│   ├── cli.py
│   ├── models.py
│   ├── router.py
│   ├── profiler/
│   │   ├── __init__.py
│   │   └── analyzer.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   └── deterministic.py
│   ├── ir/
│   ├── backends/
│   └── exporters/
└── tests/
```

Note: keep this layout guidance intentionally high-level; do not over-specify future orchestration modules until implementation plans require them.

## Coding expectations
- Keep functions small and explicit.
- Document all non-obvious heuristics next to the code.
- Prefer standard library + PyMuPDF + PyYAML for the first working slice.
- Do not introduce a plugin registry unless the active plan needs it.
- No `print` for logging in library modules. `print` is acceptable only in `cli.py` for user-facing orchestration output.
- Comments in English, user-facing CLI messages in English, commit messages in English.
- Handle import boundaries cleanly.

## Validation expectations
Any substantial change should include the smallest relevant validation step and report the exact command used.

Minimum validation for the deterministic milestone:
```bash
python -m doc2md path/to/sample.pdf -vv
pytest -q
```

If no tests exist yet, add at least a small router or import smoke test.

## Done means
A change is done only when:
1. the CLI runs from the package entry point,
2. the profiler emits usable page-level signals,
3. the router produces deterministic/hybrid/visual decisions from those signals,
4. the deterministic lane can extract text from a structurally suitable PDF,
5. the commands used for validation are recorded in the response.

## ExecPlans
For multi-step or multi-file work, use an ExecPlan that follows `.agent/PLANS.md`.
- Create concrete plans under `plans/`.
- Keep the plan updated while working.
- Do not stop after one milestone and ask “what next?” unless blocked by a real ambiguity or missing input.
