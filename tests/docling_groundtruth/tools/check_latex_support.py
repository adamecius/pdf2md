from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class LatexSupport:
    available: bool
    engine: str | None
    command: list[str] | None
    reason: str | None = None


def detect_latex_support() -> LatexSupport:
    if shutil.which("latexmk"):
        return LatexSupport(True, "latexmk", ["latexmk", "-pdf", "-interaction=nonstopmode"])
    if shutil.which("pdflatex"):
        return LatexSupport(True, "pdflatex", ["pdflatex", "-interaction=nonstopmode"])
    if shutil.which("tectonic"):
        return LatexSupport(True, "tectonic", ["tectonic"])
    return LatexSupport(False, None, None, "No supported LaTeX engine found (latexmk/pdflatex/tectonic)")
