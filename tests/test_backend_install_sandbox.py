"""Structural tests for the optional backend install sandbox."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "install_scripts" / "check_backend_installs.sh"
WRAPPER_SCRIPT = ROOT / "scripts" / "check_backend_installs.sh"


def test_sandbox_directory_is_ignored() -> None:
    gitignore_lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    normalized = {line.strip() for line in gitignore_lines}
    assert "sandbox/" in normalized or "sandbox" in normalized


def test_backend_install_script_exists_and_names_backends() -> None:
    assert INSTALL_SCRIPT.exists()
    assert WRAPPER_SCRIPT.exists()

    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    for backend_id in ("core", "mineru", "paddleocr_vl"):
        assert backend_id in script


def test_backend_install_script_uses_only_backend_install_sandbox_paths() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert 'BASE_DIR="${ROOT_DIR}/sandbox/backend-installs"' in script
    assert 'LOG_DIR="${BASE_DIR}/logs"' in script
    assert 'SUMMARY_FILE="${BASE_DIR}/summary.md"' in script
    assert 'PIP_CACHE_DIR="${BASE_DIR}/pip-cache"' in script
    assert 'PYTHONPYCACHEPREFIX="${BASE_DIR}/pycache"' in script

    sandbox_references = re.findall(r"(?<![A-Za-z0-9_./-])sandbox/[A-Za-z0-9_./-]+", script)
    assert sandbox_references
    assert all(
        reference == "sandbox/backend-installs"
        or reference.startswith("sandbox/backend-installs/")
        for reference in sandbox_references
    )


def test_legacy_backend_install_script_delegates_to_install_scripts() -> None:
    wrapper = WRAPPER_SCRIPT.read_text(encoding="utf-8")

    assert "install_scripts/check_backend_installs.sh" in wrapper
