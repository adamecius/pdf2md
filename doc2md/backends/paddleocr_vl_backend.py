"""Optional PaddleOCR-VL backend for offline/local experimentation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from doc2md.backends.base import ExtractionBackend, OptionalBackendUnavailable
from doc2md.ir import DocumentIR


class PaddleOcrVlBackend(ExtractionBackend):
    """Optional backend intended for offline/local experimentation only."""

    name = "paddleocr_vl"
    version = "0.1"
    _OPTIONAL_DEPS = ("paddleocr", "paddle")

    @classmethod
    def _missing_dependencies(cls) -> list[str]:
        """Return unresolved PaddleOCR-VL dependency module names."""

        return [
            module_name
            for module_name in cls._OPTIONAL_DEPS
            if importlib.util.find_spec(module_name) is None
        ]

    def available(self) -> bool:
        return not self._missing_dependencies()

    def _load_optional_dependencies(self) -> None:
        """Import optional dependencies only when the backend is invoked."""

        missing = self._missing_dependencies()
        if missing or not self.available():
            missing_csv = ", ".join(missing or self._OPTIONAL_DEPS)
            raise OptionalBackendUnavailable(
                f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
                f"Install dependencies ({missing_csv}) to use it."
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
