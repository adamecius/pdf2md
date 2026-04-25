"""Optional MinerU backend adapter with lazy runtime dependency loading."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

from doc2md.backends.base import ExtractionBackend, OptionalBackendUnavailable
from doc2md.ir import DocumentIR


class MineruBackend(ExtractionBackend):
    """Optional backend intended for offline/local experimentation only."""

    name = "mineru"
    version = "experimental"
    _REQUIRED_MODULES = ("mineru",)

    @classmethod
    def _missing_dependencies(cls) -> list[str]:
        """Return unresolved required MinerU module names."""

        return [
            module_name
            for module_name in cls._REQUIRED_MODULES
            if importlib.util.find_spec(module_name) is None
        ]

    def available(self) -> bool:
        return not self._missing_dependencies()

    @staticmethod
    def _install_guidance() -> str:
        return (
            "Install MinerU in a dedicated environment, for example:\n"
            "  pip install -r requirements.txt pytest mineru"
        )

    def extract(
        self,
        input_path: Path,
        output_dir: Path | None = None,
        options: dict[str, Any] | None = None,
    ) -> DocumentIR:
        """Extract via MinerU when available.

        MinerU integration remains experimental and is intentionally lazy-loaded.
        """

        missing = self._missing_dependencies()
        if missing or not self.available():
            missing_csv = ", ".join(missing or self._REQUIRED_MODULES)
            raise OptionalBackendUnavailable(
                f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
                f"Missing dependencies: {missing_csv}. {self._install_guidance()}"
            )

        # Import only after dependency checks so deterministic default flow is unaffected.
        importlib.import_module("mineru")

        raise RuntimeError(
            f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
            "MinerU runtime integration is not finalized yet; use deterministic backend by default."
        )
