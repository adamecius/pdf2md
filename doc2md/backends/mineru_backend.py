"""Optional MineruBackend backend stub for offline/local experimentation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from doc2md.backends.base import ExtractionBackend, OptionalBackendUnavailable
from doc2md.ir import DocumentIR


class MineruBackend(ExtractionBackend):
    """Optional backend intended for offline/local experimentation only."""

    name = "mineru"

    def available(self) -> bool:
        return importlib.util.find_spec("mineru") is not None

    def extract(
        self,
        input_path: Path,
        output_dir: Path | None = None,
        options: dict[str, Any] | None = None,
    ) -> DocumentIR:
        if not self.available():
            raise OptionalBackendUnavailable(
                f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
                "Install its dependencies to use it."
            )
        raise RuntimeError(
            f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
            "This backend stub is not implemented yet."
        )
