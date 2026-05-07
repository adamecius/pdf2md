"""Repository test package marker and import bootstrap.

Ensures imports such as ``tests.docling_groundtruth`` resolve to this checkout
rather than to unrelated third-party packages named ``tests``.  It also makes
this repository's src-layout package importable for whole-suite pytest runs
without requiring an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (ROOT, SRC):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
