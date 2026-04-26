"""Optional MinerU backend adapter with lazy runtime dependency loading."""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from doc2md.backends.base import ExtractionBackend, OptionalBackendUnavailable
from doc2md.ir import (
    BackendRun,
    BlockIR,
    DocumentIR,
    PageIR,
    Provenance,
    make_block_id,
    make_document_id,
    make_page_id,
)


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

    @staticmethod
    def _load_markdown_from_output(raw_output_dir: Path) -> str:
        """Return merged Markdown content from MinerU output files."""

        markdown_files = sorted(raw_output_dir.rglob("*.md"))
        if not markdown_files:
            return ""
        # Prefer deterministic ordering, then append for multi-file outputs.
        parts = [path.read_text(encoding="utf-8", errors="replace").strip() for path in markdown_files]
        return "\n\n".join(part for part in parts if part).strip()

    @staticmethod
    def _build_minimal_docir(
        input_path: Path,
        markdown: str,
        output_dir: Path | None,
        options: dict[str, Any],
        warnings: list[str] | None = None,
    ) -> DocumentIR:
        """Build minimal DocIR from backend-level Markdown."""

        warning_list = list(warnings or [])
        page = PageIR(
            page_id=make_page_id(0),
            page_index=0,
            strategy="mineru",
            warnings=warning_list.copy(),
        )

        blocks: list[BlockIR] = []
        if markdown.strip():
            block_id = make_block_id(0, 0, text=markdown)
            page.block_ids.append(block_id)
            blocks.append(
                BlockIR(
                    block_id=block_id,
                    type="paragraph",
                    role="body",
                    text=markdown,
                    markdown=markdown,
                    page_indexes=[0],
                    order=0,
                    provenance=[
                        Provenance(
                            backend="mineru",
                            backend_version=MineruBackend.version,
                            strategy="mineru",
                            page_index=0,
                            warnings=warning_list.copy(),
                        )
                    ],
                )
            )

        run = BackendRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            backend="mineru",
            backend_version=MineruBackend.version,
            options=options,
            status="ok" if markdown.strip() else "partial",
            errors=warning_list.copy(),
            raw_output_dir=str(output_dir) if output_dir is not None else None,
        )

        return DocumentIR(
            schema_version="0.1",
            document_id=make_document_id(str(input_path)),
            source_path=str(input_path),
            pages=[page],
            blocks=blocks,
            backend_runs=[run],
            metadata={"adapter": "mineru_cli_bridge"},
            warnings=warning_list,
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
        opts = dict(options or {})
        source = Path(input_path)
        raw_output_dir = Path(output_dir) if output_dir is not None else source.parent / f"{source.stem}_mineru"
        raw_output_dir.mkdir(parents=True, exist_ok=True)

        # Use module invocation for environment consistency.
        command = [
            sys.executable,
            "-m",
            "mineru",
            "--path",
            str(source),
            "--output",
            str(raw_output_dir),
        ]
        if opts.get("mineru_lang"):
            command.extend(["--lang", str(opts["mineru_lang"])])

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr_tail = (exc.stderr or "").strip().splitlines()[-1:] or [""]
            message = stderr_tail[0] if stderr_tail[0] else "unknown MinerU CLI failure"
            raise RuntimeError(
                f"{self.__class__.__name__} failed to run MinerU CLI: {message}"
            ) from exc

        markdown = self._load_markdown_from_output(raw_output_dir)
        warnings: list[str] = []

        if not markdown:
            json_files = sorted(raw_output_dir.rglob("*.json"))
            if json_files:
                # Keep a small machine-readable hint for downstream debugging.
                preview_file = json_files[0]
                preview = preview_file.read_text(encoding="utf-8", errors="replace")
                try:
                    payload = json.loads(preview)
                    markdown = json.dumps(payload, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    markdown = preview
            warnings.append("mineru output did not include markdown; used JSON/raw fallback")

        return self._build_minimal_docir(source, markdown, raw_output_dir, opts, warnings)
