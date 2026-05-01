#!/usr/bin/env python3
"""Delete the pdf2md-deepseek environment.

What it does:

1. Looks for a Conda environment named pdf2md-deepseek.
2. Looks for local venv folders:
   - .venv
   - pdf2md-deepseek
   - .venv-pdf2md-deepseek
3. If the script is currently running inside one of those environments,
   it re-runs itself with system Python outside the environment.
4. Deletes the matching Conda env and/or venv.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ENV_NAME = "pdf2md-deepseek"
VENV_CANDIDATES = [
    Path(".venv"),
    Path(ENV_NAME),
    Path(f".venv-{ENV_NAME}"),
]


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if check and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed


def which(name: str) -> str | None:
    return shutil.which(name)


def conda_envs() -> list[Path]:
    if which("conda") is None:
        return []

    completed = run(["conda", "env", "list", "--json"], check=False)
    if completed.returncode != 0:
        return []

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []

    return [Path(path).resolve() for path in data.get("envs", [])]


def find_conda_env() -> Path | None:
    for env_path in conda_envs():
        if env_path.name == ENV_NAME:
            return env_path
    return None


def looks_like_venv(path: Path) -> bool:
    path = path.resolve()
    return (
        (path / "pyvenv.cfg").exists()
        or (path / "bin" / "activate").exists()
        or (path / "bin" / "python").exists()
    )


def find_venvs() -> list[Path]:
    found: list[Path] = []

    for candidate in VENV_CANDIDATES:
        path = candidate.expanduser().resolve()
        if path.exists() and looks_like_venv(path):
            found.append(path)

    # Also detect active venv if it has the target name.
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        path = Path(virtual_env).resolve()
        if path.name in {ENV_NAME, ".venv", f".venv-{ENV_NAME}"} and looks_like_venv(path):
            if path not in found:
                found.append(path)

    return found


def current_prefix() -> Path:
    return Path(sys.prefix).resolve()


def current_conda_prefix() -> Path | None:
    prefix = os.environ.get("CONDA_PREFIX")
    if not prefix:
        return None
    return Path(prefix).resolve()


def inside_target_env(conda_path: Path | None, venvs: list[Path]) -> bool:
    prefix = current_prefix()
    conda_prefix = current_conda_prefix()

    if conda_path and (prefix == conda_path or conda_prefix == conda_path):
        return True

    for venv in venvs:
        if prefix == venv:
            return True

    return False


def find_outside_python() -> str:
    candidates = [
        "/usr/bin/python3",
        "/usr/local/bin/python3",
    ]

    current_python = Path(sys.executable).resolve()

    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and path.resolve() != current_python:
            return str(path)

    python3 = which("python3")
    if python3 and Path(python3).resolve() != current_python:
        return python3

    raise SystemExit(
        "ERROR: running inside the target environment, but no outside python3 was found."
    )


def rerun_outside_if_needed(conda_path: Path | None, venvs: list[Path]) -> None:
    if os.environ.get("PDF2MD_DEEPSEEK_DELETE_REEXEC") == "1":
        return

    if not inside_target_env(conda_path, venvs):
        return

    outside_python = find_outside_python()
    env = os.environ.copy()

    env.pop("VIRTUAL_ENV", None)
    env.pop("CONDA_PREFIX", None)
    env.pop("CONDA_DEFAULT_ENV", None)

    env["PDF2MD_DEEPSEEK_DELETE_REEXEC"] = "1"

    script = Path(__file__).resolve()
    print(f"Currently running inside {ENV_NAME}. Re-running with outside Python: {outside_python}")

    completed = subprocess.run([outside_python, str(script)], env=env)
    raise SystemExit(completed.returncode)


def delete_conda_env(conda_path: Path | None) -> None:
    if conda_path is None:
        print(f"Conda env not found: {ENV_NAME}")
        return

    if which("conda") is None:
        print("Conda env was detected, but conda is not available on PATH.")
        print(f"Manual deletion may be needed: {conda_path}")
        return

    print(f"Deleting Conda env: {ENV_NAME} at {conda_path}")
    run(["conda", "env", "remove", "-n", ENV_NAME, "-y"], check=True)


def delete_venvs(venvs: list[Path]) -> None:
    if not venvs:
        print("No matching venv found.")
        return

    for venv in venvs:
        if not venv.exists():
            continue
        if not looks_like_venv(venv):
            print(f"Skipping, not a venv: {venv}")
            continue

        print(f"Deleting venv: {venv}")
        shutil.rmtree(venv)


def main() -> None:
    print(f"Target environment: {ENV_NAME}")

    conda_path = find_conda_env()
    venvs = find_venvs()

    rerun_outside_if_needed(conda_path, venvs)

    delete_conda_env(conda_path)
    delete_venvs(venvs)

    print("Done.")


if __name__ == "__main__":
    main()
