"""Optional PaddleOCR-VL backend for offline/local experimentation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from doc2md.backends.base import ExtractionBackend, OptionalBackendUnavailable
from doc2md.ir import DocumentIR


class PaddleOcrVlBackend(ExtractionBackend):
    """Optional backend intended for offline/local experimentation only."""

    name = "paddleocr-vl"
    version = "0.1"
    _OPTIONAL_DEPS = ("paddleocr",)

    def available(self) -> bool:
        return all(importlib.util.find_spec(dep) is not None for dep in self._OPTIONAL_DEPS)

    def _load_optional_dependencies(self) -> None:
        """Import optional dependencies only when the backend is invoked."""

        if not self.available():
            missing = ", ".join(self._OPTIONAL_DEPS)
            raise OptionalBackendUnavailable(
                f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
                f"Install dependencies ({missing}) to use it."
            )

        # Keep runtime imports lazy so deterministic users avoid heavy backend costs.
        for dep in self._OPTIONAL_DEPS:
            __import__(dep)

    def extract(
        self,
        input_path: Path,
        output_dir: Path | None = None,
        options: dict[str, Any] | None = None,
    ) -> DocumentIR:
        self._load_optional_dependencies()
        raise RuntimeError(
            f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
            "This backend stub is not implemented yet."
        )
