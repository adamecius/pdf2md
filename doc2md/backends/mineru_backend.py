"""Optional MinerU backend adapter with lazy runtime dependency loading."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from doc2md.backends.base import ExtractionBackend, OptionalBackendUnavailable
from doc2md.ir import DocumentIR


class MineruBackend(ExtractionBackend):
    """Optional backend intended for offline/local experimentation only."""

    name = "mineru"
    version = "experimental"
    _REQUIRED_MODULES = ("mineru", "magic_pdf")

    @classmethod
    def _missing_dependencies(cls) -> list[str]:
        """Return unresolved required MinerU module names."""

        missing: list[str] = []
        for module_name in cls._REQUIRED_MODULES:
            try:
                __import__(module_name)
            except ImportError:
                missing.append(module_name)
        return missing

    def available(self) -> bool:
        return not self._missing_dependencies()

    @staticmethod
    def _install_guidance() -> str:
        return (
            "Install MinerU in a dedicated environment, for example:\n"
            "  pip install \"mineru[all]\" magic-pdf"
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
        if not self.available():
            missing_csv = ", ".join(missing)
            raise OptionalBackendUnavailable(
                f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
                f"Missing dependencies: {missing_csv}. {self._install_guidance()}"
            )

        # Import only after dependency checks so deterministic default flow is unaffected.
        try:
            importlib.import_module("magic_pdf.data.data_reader_writer")
            importlib.import_module("magic_pdf.model.doc_analyze_by_custom_model")
            importlib.import_module("magic_pdf.pipe.OCRPipe")
        except Exception as exc:  # pragma: no cover - guarded by integration environments
            raise RuntimeError(
                "MinerU dependencies are installed but runtime import failed. "
                "Use a dedicated MinerU environment."
            ) from exc

        raise RuntimeError(
            f"{self.__class__.__name__} is optional and intended for offline/local experimentation. "
            "MinerU runtime integration is not finalized yet; use deterministic backend by default."
        )
