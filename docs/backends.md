# Backend Dependency Validation

Optional backends can have large dependency trees and platform-specific wheels.
Use the local install sandbox to check whether those dependencies can be
installed without modifying your active Python environment.

## Install sandbox

Run checks from the repository root:

    bash install_scripts/check_backend_installs.sh core
    bash install_scripts/check_backend_installs.sh mineru
    bash install_scripts/check_backend_installs.sh paddleocr_vl

You can also run every known backend in one pass:

    bash install_scripts/check_backend_installs.sh all

For compatibility with the first sandbox plan, this wrapper still works:

    bash scripts/check_backend_installs.sh core

The script creates isolated virtual environments below:

    sandbox/backend-installs/core
    sandbox/backend-installs/mineru
    sandbox/backend-installs/paddleocr_vl

Logs are written to:

    sandbox/backend-installs/logs/core.log
    sandbox/backend-installs/logs/mineru.log
    sandbox/backend-installs/logs/paddleocr_vl.log

The aggregate report is:

    sandbox/backend-installs/summary.md

The repository ignores `sandbox/`, so generated environments, logs, caches, and
reports should stay local and should not be committed.

## What the check installs

`core` installs `requirements.txt` and `pytest`.

`mineru` installs `requirements.txt`, `pytest`, and `mineru`.

`paddleocr_vl` installs `requirements.txt`, `pytest`, `paddleocr`, and
`paddlepaddle`.

The script uses Python `venv` and calls the sandboxed Python executable
directly. It does not activate or modify your global Python, system Python, or
current development environment. Set `PYTHON_BIN=/path/to/python` if you want to
choose the Python interpreter used to create the sandbox venvs.

## What the check proves

This validates dependency installability and import smoke tests only. It does
not validate backend extraction quality, routing behavior, OCR accuracy, layout
detection, or Markdown fidelity.

The smoke tests only import modules:

- `core`: `fitz`, `yaml`, and `doc2md`
- `mineru`: `mineru`, plus `magic_pdf` when that module is available
- `paddleocr_vl`: `paddleocr` and `paddle`

The current backend stubs use the same availability contracts:

- `mineru` is considered available when `mineru` imports. `magic_pdf` is
  optional because the successful sandbox install did not include it.
- `paddleocr_vl` is considered available only when both `paddleocr` and
  `paddle` import.

No heavyweight model downloads are part of this script.

If package downloads are blocked by network policy or a package is unavailable
for your platform, the command exits with a failure, writes the pip output to
the backend log, and records the failure in `sandbox/backend-installs/summary.md`.
