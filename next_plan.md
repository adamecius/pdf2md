# Plan 8 - Local ground-truth corpus generation and validation

Status: ready to implement after Plan 7 acceptance  
Repo: `pdf2md`  
Owner: local acceptance layer  
Sequence: plan 8 of 12. It validates the LaTeX, LuaLaTeX and LaTeXML ground-truth corpus before any backend is run.

---

## 0. Repository review and current status

Plan 7 is present on `main` as implementation, not only as a plan. The code defines `PreflightSettings`, `PreflightReport`, `check_latexml_executable`, CLI checks, conda environment checks, and report writing in `src/pdf2md/local/preflight.py`. The implementation already contains the tolerant LaTeXML probe that accepts a LaTeXML version banner from stderr even when `latexml --version` exits non-zero. It also sets `optional_backends=()` by default, which correctly excludes `glm` from local acceptance testing.

The Plan 7 CLI exists at:

```text
tools/local_groundtruth_preflight.py
```

and its default `--optional-backends` value is empty.

The Plan 7 tests exist at:

```text
tests/test_local_preflight.py
```

and explicitly test:

```text
- tolerant LaTeXML stderr version handling
- missing LaTeXML executable handling
- default backend scope excludes glm
- expected environment fixtures have optional_backends = []
```

The fixture:

```text
tests/data/local_preflight_fixtures/expected_environment.full.json
```

also correctly lists only:

```text
mineru
paddleocr
deepseek
```

as required backends and has:

```json
"optional_backends": []
```

Important repository note:

`current_plan.md` on `main` still contains stale Plan 7 text that mentions `glm` as an expected backend environment and optional backend. The implementation itself has already corrected this. Since the README and current plan documents are not the source of truth for local acceptance, Plan 8 should not touch `current_plan.md` or README files. Documentation can be rebuilt later.

---

## 0.1 Repository working protocol for the agent

Before implementing Plan 8, the agent must start from a clean, updated `main`.

Required sequence:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-8-groundtruth-validation
```

Rules:

```text
- Do not work directly on main.
- Do not start implementation before fetching and pulling latest main.
- If git status is not clean before creating the branch, stop and report the uncommitted files.
- Do not modify README files.
- Do not modify current_plan.md.
- Do not modify run_log.md.
- The final report must include branch name, changed files, pytest commands, local validation command, and whitelist confirmation.
```

---

## 0.2 Conda environment protocol

The main repository conda environment is:

```text
pdf2md
```

All Plan 8 repository-level commands must run from this environment.

Use:

```bash
conda activate pdf2md
```

or non-interactively:

```bash
conda run -n pdf2md python <command>
```

Plan 8 does not execute backend OCR/model scripts. Backend environments are not used in Plan 8.

Plans 8 to 12 continue to ignore `glm` until it is implemented.

---

## 1. Purpose

Plan 8 validates that the LaTeX ground-truth corpus can be generated or discovered locally, and that its structural artefacts are present and coherent.

It answers this question:

```text
Can the local ground-truth corpus be generated, inspected, and validated before running any OCR backend?
```

Plan 8 does not run MinerU, PaddleOCR, DeepSeek, or GLM. It only deals with ground truth.

---

## 2. Scope

Plan 8 checks:

```text
LaTeX source discovery
LuaLaTeX/PDF artefact discovery
LaTeXML XML artefact discovery
Docling ground-truth JSON discovery when present
ground-truth metadata discovery when present
legacy pre-Docling ground-truth contract discovery when present
existing generator CLI execution
existing validator CLI execution
local report writing
strict and non-strict behaviour
```

Plan 8 may call existing scripts:

```text
generate_latex_docling_groundtruth.py
validate_latex_docling_groundtruth.py
```

but it must not patch them by default.

If a generic defect is found in those scripts, the agent must stop, report it, and only patch the responsible file if the fix is explicitly in scope and has a targeted unit test. The default Plan 8 implementation should avoid modifying the existing generator and validator.

---

## 3. Hard constraints

```text
- No new mandatory runtime dependencies.
- No OCR execution.
- No backend model execution.
- No backend connector execution on real backend outputs.
- No calibration, consensus, linking, or export execution.
- No modifications to Plans 1 to 7 contracts.
- No modifications to backend wrappers.
- No modifications to README files.
- No modifications to current_plan.md.
- No modifications to run_log.md.
- Do not use README as the ground truth for behaviour.
- Use this conversation and accepted Plans 1 to 7 as the source of truth.
- Treat missing local corpus artefacts as local corpus-not-ready, not as unit-test failures.
- Create unit tests only for generic repository logic added in Plan 8.
```

---

## 4. File whitelist

The reviewer rejects the plan if files outside this whitelist are modified.

```text
src/pdf2md/local/__init__.py
src/pdf2md/local/groundtruth.py

tools/local_groundtruth_validate.py

tests/test_local_groundtruth_validation.py

tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.tex
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.pdf.placeholder
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.latexml.xml
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.docling.json
tests/data/local_groundtruth_fixtures/minimal_valid_corpus/simple_doc/simple_doc.docling_groundtruth_meta.json

tests/data/local_groundtruth_fixtures/legacy_valid_corpus/legacy_doc/input/legacy_doc.tex
tests/data/local_groundtruth_fixtures/legacy_valid_corpus/legacy_doc/input/legacy_doc.pdf.placeholder
tests/data/local_groundtruth_fixtures/legacy_valid_corpus/legacy_doc/groundtruth/source_groundtruth_ir.json
tests/data/local_groundtruth_fixtures/legacy_valid_corpus/legacy_doc/groundtruth/expected_semantic_contract.json
tests/data/local_groundtruth_fixtures/legacy_valid_corpus/legacy_doc/groundtruth/expected_docling_contract.json
tests/data/local_groundtruth_fixtures/legacy_valid_corpus/legacy_doc/groundtruth/provenance_manifest.json

tests/data/local_groundtruth_fixtures/broken_corpus/missing_xml_doc/missing_xml_doc.tex
tests/data/local_groundtruth_fixtures/broken_corpus/missing_xml_doc/missing_xml_doc.pdf.placeholder
```

Explicit non-whitelist files:

```text
README.md
README_latex_docling_groundtruth.md
current_plan.md
run_log.md
pyproject.toml

generate_latex_docling_groundtruth.py
validate_latex_docling_groundtruth.py

src/pdf2md/models/ir.py
src/pdf2md/models/entities.py
src/pdf2md/models/priors.py
src/pdf2md/models/linked.py
src/pdf2md/models/export.py

src/pdf2md/local/preflight.py

src/pdf2md/connectors/*
src/pdf2md/calibration/*
src/pdf2md/consensus/*
src/pdf2md/linking/*
src/pdf2md/export/*

backend/*
tools/calibrate_priors.py
tools/build_consensus.py
tools/build_linked_structure.py
tools/export_linked_docling.py
tools/local_groundtruth_preflight.py
```

Rationale:

Plan 8 adds a local diagnostic wrapper around the existing ground-truth generation and validation surface. It should not rewrite the generator, validator, backend layer, or previous pipeline stages.

---

## 5. Files to be touched and associated tests

| File | New or touched | Why it is needed | Associated test |
|---|---|---|---|
| `src/pdf2md/local/groundtruth.py` | new | Local ground-truth report models, document discovery, layout inspection, command construction, report writing | `tests/test_local_groundtruth_validation.py` |
| `tools/local_groundtruth_validate.py` | new | CLI for Plan 8 local validation | `tests/test_local_groundtruth_validation.py` |
| `tests/test_local_groundtruth_validation.py` | new | Unit tests for Plan 8 logic, mocked only | It is the test file |
| `tests/data/local_groundtruth_fixtures/*` | new | Minimal filesystem layouts for target, legacy and broken corpora | `tests/test_local_groundtruth_validation.py` |
| `src/pdf2md/local/__init__.py` | optional touch | Only if exports are needed | `test_groundtruth_module_imports` |

Do not touch `generate_latex_docling_groundtruth.py` or `validate_latex_docling_groundtruth.py` in this plan unless the user explicitly approves a separate targeted fix.

---

## 6. New module

File:

```text
src/pdf2md/local/groundtruth.py
```

### 6.1 Enums

```python
class GroundtruthStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
```

```python
class GroundtruthFailureClass(str, Enum):
    CORPUS_MISSING = "corpus_missing"
    DOCUMENT_MISSING = "document_missing"
    TEX_MISSING = "tex_missing"
    PDF_MISSING = "pdf_missing"
    LATEXML_XML_MISSING = "latexml_xml_missing"
    DOCLING_JSON_MISSING = "docling_json_missing"
    DOCLING_META_MISSING = "docling_meta_missing"
    LEGACY_CONTRACT_MISSING = "legacy_contract_missing"
    COMMAND_FAILED = "command_failed"
    COMMAND_TIMEOUT = "command_timeout"
    INVALID_JSON = "invalid_json"
    SCHEMA_MISMATCH = "schema_mismatch"
    PERMISSION_ERROR = "permission_error"
```

```python
class GroundtruthLayout(str, Enum):
    TARGET_DOCLING = "target_docling"
    LEGACY_PRE_DOCLING = "legacy_pre_docling"
    MIXED = "mixed"
    UNKNOWN = "unknown"
```

---

### 6.2 Models

```python
class GroundtruthCheck(BaseModel):
    id: str
    label: str
    status: GroundtruthStatus
    failure_class: GroundtruthFailureClass | None
    path: str | None
    command: list[str] | None
    returncode: int | None
    stdout_snippet: str | None
    stderr_snippet: str | None
    message: str
    metadata: dict[str, Any]
```

```python
class GroundtruthDocumentReport(BaseModel):
    document_id: str
    layout: GroundtruthLayout
    corpus_ready: bool
    checks: list[GroundtruthCheck]
    warnings: list[str]
    metadata: dict[str, Any]
```

```python
class GroundtruthValidationReport(BaseModel):
    schema_name: Literal["pdf2md.LocalGroundtruthValidationReport"]
    schema_version: Literal["1.0.0"]
    corpus_root: str
    corpus_ready: bool
    document_count: int
    documents_ready: int
    documents_failed: int
    generation_ran: bool
    validator_ran: bool
    documents: list[GroundtruthDocumentReport]
    checks: list[GroundtruthCheck]
    warnings: list[str]
    metadata: dict[str, Any]
```

Validation:

```text
- document ids are unique.
- check ids are unique inside each document report.
- corpus_ready is true only when all required checks pass.
- document_count == len(documents).
- documents_ready and documents_failed match document corpus_ready values.
```

---

## 7. Public API

```python
@dataclass(frozen=True)
class GroundtruthValidationSettings:
    corpus_root: Path = Path("groundtruth/corpus/latex")
    batch: str | None = None
    run_generator: bool = False
    run_validator: bool = True
    require_target_docling: bool = True
    accept_legacy_pre_docling: bool = True
    timeout_seconds: int = 120
```

```python
def discover_groundtruth_documents(
    *,
    corpus_root: Path,
    batch: str | None = None,
) -> list[Path]:
    ...
```

```python
def inspect_groundtruth_document(
    *,
    document_dir: Path,
    require_target_docling: bool,
    accept_legacy_pre_docling: bool,
) -> GroundtruthDocumentReport:
    ...
```

```python
def build_generator_command(
    *,
    corpus_root: Path,
    compile_pdf: bool,
    verbose: bool,
) -> list[str]:
    ...
```

```python
def build_validator_command(
    *,
    corpus_root: Path,
    batch: str | None,
    verbose: bool,
) -> list[str]:
    ...
```

```python
def run_local_command(
    *,
    check_id: str,
    label: str,
    command: list[str],
    timeout_seconds: int,
) -> GroundtruthCheck:
    ...
```

```python
def build_groundtruth_validation_report(
    *,
    settings: GroundtruthValidationSettings,
    verbose: bool = False,
) -> GroundtruthValidationReport:
    ...
```

```python
def write_groundtruth_validation_report(
    *,
    report: GroundtruthValidationReport,
    out_dir: Path,
) -> Path:
    ...
```

---

## 8. Corpus layout rules

Plan 8 supports two layouts.

### 8.1 Target Docling layout

A document directory is target-layout ready when it contains:

```text
<doc_id>.tex
<doc_id>.pdf
<doc_id>.latexml.xml or <doc_id>.xml
<doc_id>.docling.json
<doc_id>.docling_groundtruth_meta.json
```

Accepted alternatives:

```text
input/<doc_id>.tex
input/<doc_id>.pdf
groundtruth/<doc_id>.latexml.xml
groundtruth/<doc_id>.docling.json
groundtruth/<doc_id>.docling_groundtruth_meta.json
```

The target layout is the desired long-term ground-truth form.

### 8.2 Legacy pre-Docling layout

A document directory is legacy-ready when it contains:

```text
input/<doc_id>.tex
input/<doc_id>.pdf
groundtruth/source_groundtruth_ir.json
groundtruth/expected_semantic_contract.json
groundtruth/expected_docling_contract.json
groundtruth/provenance_manifest.json
```

The legacy layout is accepted only when:

```text
accept_legacy_pre_docling = true
```

If `require_target_docling = true`, a legacy-only document should pass with warning, not fail, unless the user requested strict target Docling mode.

### 8.3 Unknown layout

If neither layout is satisfied:

```text
corpus_ready = false
```

with explicit checks showing which artefacts are missing.

---

## 9. CLI tool

File:

```text
tools/local_groundtruth_validate.py
```

Required CLI:

```bash
conda run -n pdf2md python tools/local_groundtruth_validate.py   --corpus-root groundtruth/corpus/latex   --out-dir groundtruth/runs/local_groundtruth_validation   --run-validator   --verbose
```

Required options:

```text
--corpus-root PATH                 default groundtruth/corpus/latex
--batch TEXT                       optional
--out-dir PATH                     required
--run-generator                    call generate_latex_docling_groundtruth.py
--compile                          passed to generator when --run-generator is used
--run-validator / --no-validator   default --run-validator
--require-target-docling           default true
--accept-legacy-pre-docling        default true
--strict                           exit 1 if corpus_ready is false
--timeout-seconds INT              default 120
--verbose
```

Exit codes:

```text
0 = report written.
1 = invalid CLI arguments, strict mode with corpus_ready false, or unexpected repository error.
```

Non-strict mode must write a report even when the corpus is not ready.

Outputs:

```text
<out-dir>/groundtruth_validation_report.json
<out-dir>/groundtruth_validation_summary.txt
```

---

## 10. Tests as milestones

File:

```text
tests/test_local_groundtruth_validation.py
```

Expected count: about 28 tests.

Required tests:

```text
test_groundtruth_status_enum_values
test_groundtruth_failure_class_enum_values
test_groundtruth_layout_enum_values
test_groundtruth_check_minimal_construction
test_document_report_rejects_duplicate_check_ids
test_validation_report_rejects_duplicate_document_ids
test_validation_report_counts_documents
test_discover_groundtruth_documents_finds_flat_docs
test_discover_groundtruth_documents_finds_batch_docs
test_inspect_target_docling_layout_passes
test_inspect_legacy_pre_docling_layout_passes_when_accepted
test_inspect_legacy_pre_docling_layout_warns_when_target_required
test_inspect_broken_layout_reports_missing_xml
test_inspect_broken_layout_reports_missing_docling_json
test_build_generator_command_uses_pdf2md_python_surface
test_build_validator_command_includes_batch_when_given
test_run_local_command_passes_on_returncode_zero
test_run_local_command_records_nonzero_returncode
test_run_local_command_records_timeout
test_build_report_does_not_run_generator_when_disabled
test_build_report_runs_generator_when_enabled_with_mock
test_build_report_runs_validator_when_enabled_with_mock
test_non_strict_report_can_be_written_when_corpus_not_ready
test_write_groundtruth_validation_report_writes_json_and_summary
test_cli_help_exits_zero
test_cli_writes_report_with_mocked_builder
test_cli_strict_returns_one_when_corpus_not_ready
test_fixtures_are_valid_json
```

No unit test should run real `lualatex`, `latexml`, existing generator script, or existing validator script. Mock subprocess calls.

---

## 11. Acceptance criteria

### 11.1 Branch protocol

Implementation must be on:

```text
plan-8-groundtruth-validation
```

after:

```bash
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-8-groundtruth-validation
```

### 11.2 Unit tests pass

```bash
conda run -n pdf2md pytest tests/test_local_groundtruth_validation.py -q
```

No skip. No xfail.

### 11.3 Plan 7 still passes

```bash
conda run -n pdf2md pytest tests/test_local_preflight.py -q
```

### 11.4 Plans 1 to 6 still pass

Run the established targeted tests for Plans 1 to 6.

### 11.5 Whole suite has no regression

```bash
conda run -n pdf2md pytest tests/ -q
```

### 11.6 Whitelist check

```bash
git diff --name-only main..HEAD
```

Must be a subset of the Plan 8 whitelist.

### 11.7 Local validation report is produced

Non-strict mode must write:

```text
groundtruth/runs/local_groundtruth_validation/groundtruth_validation_report.json
groundtruth/runs/local_groundtruth_validation/groundtruth_validation_summary.txt
```

even when the local corpus is incomplete.

### 11.8 Strict mode behaves correctly

If the corpus is ready:

```text
--strict exits 0
```

If required corpus artefacts are missing:

```text
--strict exits 1
```

---

## 12. Failure policy

### 12.1 Environment missing

Examples:

```text
lualatex missing
latexml missing
pdf2md env missing
```

Action:

```text
Return to Plan 7.
Do not patch Plan 8.
```

### 12.2 Corpus missing or incomplete

Examples:

```text
groundtruth/corpus/latex missing
no document directories
document missing PDF
document missing LaTeXML XML
document missing Docling JSON
```

Action:

```text
Report corpus-not-ready.
Do not create a unit test.
Do not patch pipeline code.
```

### 12.3 Repository defect

Examples:

```text
generator command construction is wrong
validator command construction is wrong
report cannot serialise
CLI strict mode has wrong exit code
document discovery misses valid layouts
```

Action:

```text
Create or update a targeted unit test in tests/test_local_groundtruth_validation.py.
Fix only the responsible Plan 8 file.
Rerun Plan 8 tests and affected previous tests.
```

### 12.4 Existing generator or validator bug

Examples:

```text
generate_latex_docling_groundtruth.py crashes due to bad CLI signature
validate_latex_docling_groundtruth.py cannot read its expected input
```

Default action:

```text
Report repository defect with command, stdout, stderr, and return code.
Do not modify the root generator or validator in Plan 8 by default.
```

If the user explicitly approves fixing the existing script, open a separate narrow fix with an associated test. Do not silently expand Plan 8.

---

## 13. What Plan 8 must not accidentally become

Bad:

```text
Run MinerU.
Run PaddleOCR.
Run DeepSeek.
Run GLM.
Run connectors on backend output.
Run calibration.
Run consensus.
Run linker.
Run exporter.
Tune OCR or linker parameters.
Patch README.
Patch current_plan.md.
Patch root generator scripts without explicit reason and test.
```

Good:

```text
Discover ground-truth documents.
Run or simulate ground-truth generator command.
Run or simulate validator command.
Check LaTeX/PDF/XML/Docling artefact presence.
Classify corpus readiness.
Write machine-readable and human-readable local reports.
```

---

## 14. Reviewer checklist

```text
1. Does the plan start from an updated main branch?
2. Does it run inside the pdf2md conda environment?
3. Does it ignore glm completely?
4. Does it avoid backend execution?
5. Does it avoid touching README, current_plan.md, and run_log.md?
6. Does every new file have a reason?
7. Does every new file have associated tests?
8. Are unit tests mocked and independent of local LaTeX/LaTeXML?
9. Does non-strict mode always write a report?
10. Does strict mode fail when the corpus is not ready?
11. Is git diff contained inside the whitelist?
```

---

## 15. Transition to Plan 9

Plan 9 starts only when Plan 8 has produced a ground-truth validation report and either:

```text
corpus_ready = true
```

or the user explicitly decides to proceed with known corpus limitations.

Plan 9 will then run real backend execution smoke checks against the validated ground-truth PDFs.

Plan 9 must continue to ignore `glm` until that backend is implemented.
