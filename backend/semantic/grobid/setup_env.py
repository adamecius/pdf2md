#!/usr/bin/env python3
"""Bootstrap the pdf2md-grobid environment from environment.yml.

Thin wrapper that mirrors the shape of backend/<extraction>/setup_env.py.
For the full install workflow (env create + tarball download + Gradle
build + launcher + verify), use setup.py instead.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap pdf2md-grobid environment (env-create step only).",
    )
    parser.add_argument(
        "--manager",
        choices=["conda", "venv"],
        default="conda",
    )
    parser.add_argument("--env-name", help="Override env name / venv directory.")
    parser.add_argument("--python", default="3.11")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    yml = here / "environment.yml"
    env = args.env_name or "pdf2md-" + here.name

    if args.manager == "conda":
        cmd = ["conda", "env", "create", "-n", env, "-f", str(yml)]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)
    else:
        venv_dir = Path(env)
        print(f"Running: {sys.executable} -m venv {venv_dir}")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
        print(
            "\nVenv created. NB: GROBID requires Java ≥17 on PATH. "
            "Venv mode does NOT install openjdk — the system Java must "
            "satisfy this. Use `--manager conda` for an all-in-one install.",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
