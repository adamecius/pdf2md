#!/usr/bin/env python3
"""Bootstrap the pdf2md-deepseek-vl2 environment from environment.yml.

Thin wrapper that mirrors the shape of backend/<extraction>/setup_env.py.
For the full install workflow (env create + torch wheels + constraints
+ deepseek-vl2 source pkg + verify), use setup.py instead.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap pdf2md-deepseek-vl2 environment (env-create step only).",
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
    # backend folder is `deepseek_vl2`; conda env conventional name uses dashes.
    env = args.env_name or "pdf2md-" + here.name.replace("_", "-")

    if args.manager == "conda":
        cmd = ["conda", "env", "create", "-n", env, "-f", str(yml)]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)
    else:
        venv_dir = Path(env)
        print(f"Running: {sys.executable} -m venv {venv_dir}")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
