# Verify Backend Installs and Document Setup

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

## Why this exists

The backend install sandbox now reports successful dependency installation and import smoke tests for `core`, `mineru`, and `paddleocr_vl`. The next useful step is to turn those observations into repository behavior: backend availability checks should match what the sandbox proved, tests should cover the optional backend contracts without requiring heavy packages in the default environment, and README setup guidance should explain how to install the project with each backend.

## Scope

In scope:
- Review `sandbox/backend-installs/summary.md` and backend logs for install results.
- Move the install-validation entrypoint under an `install_scripts/` directory while preserving a compatibility wrapper.
- Align `MineruBackend` and `PaddleOcrVlBackend` availability checks with the dependency sets validated by the sandbox.
- Register the optional backend stubs so they can be created by backend ID without importing heavy packages.
- Add lightweight pytest tests for backend availability, registry behavior, and install-script structure.
- Add README instructions for core, MinerU, PaddleOCR-VL, and sandbox validation.

Out of scope:
- Implementing real MinerU or PaddleOCR-VL extraction.
- Downloading models or validating extraction quality.
- Committing generated sandbox environments, logs, reports, or caches.
- Adding optional backend packages to `requirements.txt`.

## Current known state

`sandbox/backend-installs/summary.md` reports `Installation succeeded: yes` and `Import smoke tests: yes` for all three backend IDs as of 2026-04-25 21:39 CEST. The `mineru` log shows `mineru import ok` and `magic_pdf import skipped: not installed`, which means `magic_pdf` should not be a hard availability requirement for the current stub. The `paddleocr_vl` log shows both `paddleocr` and `paddle` import successfully, which means both should be part of the availability contract.

The current install-check script lives at `scripts/check_backend_installs.sh`. The user asked that any installation script be called `install_scripts`, so the durable entrypoint will move to `install_scripts/check_backend_installs.sh`, with `scripts/check_backend_installs.sh` kept as a small compatibility wrapper.

## Target behavior

After completion:

    cd /home/jgarcia/pdf2md/pdf2md
    bash install_scripts/check_backend_installs.sh core
    bash install_scripts/check_backend_installs.sh mineru
    bash install_scripts/check_backend_installs.sh paddleocr_vl

will remain the canonical sandbox validation flow. Existing calls to:

    bash scripts/check_backend_installs.sh core

will still work through a wrapper.

Default tests will validate backend contracts without requiring `mineru`, `paddleocr`, or `paddlepaddle` in the active environment. The README will show how to install the lightweight core and optional backend environments separately.

## Design and decisions

The backend install summary proves installability and importability only. It does not prove that the optional backend stubs can extract documents, because those adapters intentionally still raise a not-implemented error after their dependencies are available.

`MineruBackend.available()` should require `mineru`. `magic_pdf` remains a best-effort module that may exist in some MinerU distributions but was not present in the successful sandbox install. `PaddleOcrVlBackend.available()` should require both `paddleocr` and `paddle`, because both are installed and imported by the sandbox smoke test.

The registry can register optional backend stub constructors because importing the stub modules does not import heavy optional packages. This makes `create_backend("mineru")` and `create_backend("paddleocr_vl")` observable without changing default runtime dependencies.

## Milestones

### Milestone 1 - Script naming and compatibility

Files:
- `install_scripts/check_backend_installs.sh`
- `scripts/check_backend_installs.sh`
- `docs/backends.md`
- `tests/test_backend_install_sandbox.py`

Work:
Move the real install-check script under `install_scripts/`, keep a compatibility wrapper in `scripts/`, and update docs/tests to use the new canonical path.

Validation:

    cd /home/jgarcia/pdf2md/pdf2md
    bash -n install_scripts/check_backend_installs.sh
    bash -n scripts/check_backend_installs.sh

Expected result:
Both scripts have valid Bash syntax.

### Milestone 2 - Backend contract tests and availability fixes

Files:
- `doc2md/backends/mineru_backend.py`
- `doc2md/backends/paddleocr_vl_backend.py`
- `doc2md/backends/registry.py`
- `tests/test_optional_backend_contracts.py`

Work:
Align availability checks with the sandbox import smoke tests, register optional backend stubs by backend ID, and test those contracts with monkeypatched import discovery.

Validation:

    cd /home/jgarcia/pdf2md/pdf2md
    sandbox/backend-installs/core/venv/bin/python -m pytest -p no:cacheprovider tests/test_optional_backend_contracts.py

Expected result:
The focused backend contract tests pass without installing optional backend packages in the active environment.

### Milestone 3 - README setup guidance

Files:
- `README.md`
- `docs/backends.md`

Work:
Document core installation, optional backend installs, and the sandbox install-verification command. Keep the guidance clear that installability is not extraction-quality validation.

Validation:

    cd /home/jgarcia/pdf2md/pdf2md
    grep -q "install_scripts/check_backend_installs.sh" README.md

Expected result:
README references the canonical install validation script.

### Milestone 4 - Full validation

Files:
- Tests and docs from prior milestones.

Work:
Run syntax checks and the project test suite using the sandbox core environment that already contains project test dependencies.

Validation:

    cd /home/jgarcia/pdf2md/pdf2md
    bash -n install_scripts/check_backend_installs.sh
    bash -n scripts/check_backend_installs.sh
    PYTHONPYCACHEPREFIX=sandbox/backend-installs/pycache sandbox/backend-installs/core/venv/bin/python -m pytest -p no:cacheprovider

Expected result:
Syntax checks pass and pytest passes from the isolated core sandbox environment.

## Validation

Final validation commands:

    cd /home/jgarcia/pdf2md/pdf2md
    bash -n install_scripts/check_backend_installs.sh
    bash -n scripts/check_backend_installs.sh
    PYTHONPYCACHEPREFIX=sandbox/backend-installs/pycache sandbox/backend-installs/core/venv/bin/python -m pytest -p no:cacheprovider

If the active global Python still lacks pytest, that is not a blocker because the project should not require modifying the developer environment just to run this follow-on validation.

## Risks and rollback notes

The main risk is overstating what the sandbox proves. The README and docs must say that the successful installs prove dependency installability and import smoke tests, not backend extraction quality. The optional backend stubs still intentionally raise a not-implemented error when extraction is attempted with dependencies available.

Rollback is safe: move the script back from `install_scripts/`, remove the compatibility wrapper, revert the backend availability and registry changes, and remove the new tests/docs additions.

## Progress

- [x] 2026-04-25 21:42 CEST - Created follow-on ExecPlan after reviewing sandbox success summary and logs.
- [x] 2026-04-25 21:44 CEST - Moved canonical installer-validation script to `install_scripts/check_backend_installs.sh` and kept `scripts/check_backend_installs.sh` as a wrapper.
- [x] 2026-04-25 21:45 CEST - Aligned MinerU and PaddleOCR-VL availability contracts with the sandbox smoke tests and registered both optional backends.
- [x] 2026-04-25 21:46 CEST - Added backend contract tests and updated install-sandbox structural tests.
- [x] 2026-04-25 21:47 CEST - Updated `README.md` and `docs/backends.md` with backend install guidance.
- [x] 2026-04-25 21:48 CEST - Ran focused and full validation from the sandbox core venv.

## Surprises & Discoveries

- 2026-04-25 21:42 CEST - Successful MinerU install did not install `magic_pdf`; the smoke test skipped it and still passed.
- 2026-04-25 21:42 CEST - Current `MineruBackend.available()` requires `magic_pdf`, so it does not match the verified install result.
- 2026-04-25 21:42 CEST - Current `PaddleOcrVlBackend.available()` checks `paddleocr` but not `paddle`, while the install script validates both.
- 2026-04-25 21:46 CEST - The first structural regex for sandbox path checks was too broad and captured a Markdown backtick in help text; narrowing the regex to path characters fixed the test without weakening the sandbox-root assertion.

## Decision Log

- 2026-04-25 21:42 CEST - Treat `install_scripts/check_backend_installs.sh` as the canonical installer-validation entrypoint and keep the old `scripts/` path as a compatibility wrapper.
- 2026-04-25 21:42 CEST - Tests will simulate optional dependency presence with monkeypatching instead of requiring heavy packages in the default pytest environment.
- 2026-04-25 21:45 CEST - Register optional backend stubs in `doc2md.backends.registry` because importing those stub modules does not import heavy backend dependencies.
- 2026-04-25 21:45 CEST - Use `paddleocr_vl` as the PaddleOCR-VL backend ID to match the sandbox backend ID and install command.

## Outcomes & Retrospective

- Reviewed `sandbox/backend-installs/summary.md` and backend logs. All three backend install sandboxes report successful dependency installation and successful import smoke tests.
- Added the canonical installer-validation script at `install_scripts/check_backend_installs.sh`; the old `scripts/check_backend_installs.sh` command still delegates to it.
- Updated backend contracts so `MineruBackend.available()` requires `mineru`, while `PaddleOcrVlBackend.available()` requires both `paddleocr` and `paddle`.
- Registered `mineru` and `paddleocr_vl` optional backend stubs in the backend registry without adding optional packages to `requirements.txt`.
- Added backend contract tests and updated install-sandbox structural tests.
- Added README backend install instructions for core, MinerU, PaddleOCR-VL, and sandbox validation.
- Validation run:

    cd /home/jgarcia/pdf2md/pdf2md
    bash -n install_scripts/check_backend_installs.sh
    bash -n scripts/check_backend_installs.sh
    bash install_scripts/check_backend_installs.sh --help
    bash scripts/check_backend_installs.sh --help
    PYTHONPYCACHEPREFIX=sandbox/backend-installs/pycache sandbox/backend-installs/core/venv/bin/python -m pytest -p no:cacheprovider tests/test_optional_backend_contracts.py tests/test_backend_install_sandbox.py -q
    PYTHONPYCACHEPREFIX=sandbox/backend-installs/pycache sandbox/backend-installs/core/venv/bin/python -m pytest -p no:cacheprovider

- Final test result: `42 passed, 1 xfailed in 1.18s`.
