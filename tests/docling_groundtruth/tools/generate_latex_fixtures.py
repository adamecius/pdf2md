from __future__ import annotations

import subprocess
from pathlib import Path

from .check_latex_support import detect_latex_support


def generate_pdf(tex_path: Path, output_pdf: Path) -> bool:
    support = detect_latex_support()
    if not support.available:
        return False

    abs_tex = tex_path.resolve()
    abs_out = output_pdf.resolve()
    if not abs_tex.exists():
        raise FileNotFoundError(f"LaTeX source not found: {abs_tex}")

    workdir = abs_out.parent
    workdir.mkdir(parents=True, exist_ok=True)

    if support.engine == "latexmk":
        cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", f"-outdir={workdir}", str(abs_tex)]
        runs = [cmd]
    elif support.engine == "pdflatex":
        cmd = ["pdflatex", "-interaction=nonstopmode", f"-output-directory={workdir}", str(abs_tex)]
        runs = [cmd, cmd]  # second pass for references
    elif support.engine == "tectonic":
        cmd = ["tectonic", "-o", str(workdir), str(abs_tex)]
        runs = [cmd]
    else:
        raise RuntimeError(f"Unsupported LaTeX engine: {support.engine}")

    for cmd in runs:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"PDF generation failed with engine={support.engine}, returncode={proc.returncode}\n"
                f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
            )

    produced = workdir / f"{abs_tex.stem}.pdf"
    if produced.exists() and produced != abs_out:
        produced.replace(abs_out)

    return abs_out.exists() and abs_out.stat().st_size > 0
