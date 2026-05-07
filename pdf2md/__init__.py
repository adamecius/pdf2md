# SPDX-License-Identifier: AGPL-3.0-or-later
"""Source-layout import shim for running repository commands without install."""

from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "pdf2md"
if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))

__all__ = ["__version__"]
__version__ = "0.1.0"
