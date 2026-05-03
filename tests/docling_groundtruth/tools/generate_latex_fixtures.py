from __future__ import annotations

import subprocess
from pathlib import Path

from .check_latex_support import detect_latex_support


def generate_pdf(tex_path: Path, output_pdf: Path) -> bool:
    support = detect_latex_support()
    if not support.available:
        return False

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    workdir = output_pdf.parent
    if support.engine == "latexmk":
        cmd = support.command + [str(tex_path)]
    elif support.engine == "pdflatex":
        cmd = support.command + [f"-output-directory={workdir}", str(tex_path)]
    else:
        cmd = support.command + ["-o", str(output_pdf), str(tex_path)]

    subprocess.run(cmd, cwd=workdir, check=True, capture_output=True, text=True)
    if support.engine in {"latexmk", "pdflatex"}:
        produced = workdir / (tex_path.stem + ".pdf")
        if produced != output_pdf and produced.exists():
            produced.replace(output_pdf)
    return output_pdf.exists()
