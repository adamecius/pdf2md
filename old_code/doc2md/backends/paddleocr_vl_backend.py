"""Optional PaddleOCR-VL backend for offline/local experimentation."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from typing import Any

import pymupdf

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
        opts = options or {}

        # Lazy import after dependency checks.
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            use_angle_cls=True,
            lang=str(opts.get("paddle_lang", "en")),
            show_log=bool(opts.get("paddle_show_log", False)),
        )

        source = Path(input_path)
        base_output = Path(output_dir) if output_dir is not None else source.parent / f"{source.stem}_paddleocr_vl"
        images_dir = base_output / "paddleocr_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        pages: list[PageIR] = []
        blocks: list[BlockIR] = []
        warnings: list[str] = []

        with pymupdf.open(str(source)) as pdf:
            for page_index, page in enumerate(pdf):
                page_ir = PageIR(
                    page_id=make_page_id(page_index),
                    page_index=page_index,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=int(page.rotation),
                    strategy="paddleocr_vl",
                )

                image_path = images_dir / f"page_{page_index + 1:04d}.png"
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), alpha=False)
                pix.save(str(image_path))

                ocr_result = ocr.ocr(str(image_path), cls=True) or []
                lines: list[str] = []
                for group in ocr_result:
                    if not group:
                        continue
                    for item in group:
                        if not isinstance(item, (list, tuple)) or len(item) < 2:
                            continue
                        text_info = item[1]
                        if isinstance(text_info, (list, tuple)) and text_info:
                            line_text = str(text_info[0]).strip()
                            if line_text:
                                lines.append(line_text)

                page_text = "\n".join(lines).strip()
                if not page_text:
                    warn = f"page {page_index + 1}: OCR returned no text"
                    warnings.append(warn)
                    page_ir.warnings.append(warn)

                block_id = make_block_id(page_index, 0, text=page_text)
                page_ir.block_ids.append(block_id)
                blocks.append(
                    BlockIR(
                        block_id=block_id,
                        type="paragraph",
                        role="body",
                        text=page_text,
                        markdown=page_text,
                        page_indexes=[page_index],
                        order=0,
                        provenance=[
                            Provenance(
                                backend=self.name,
                                backend_version=self.version,
                                strategy="paddleocr_vl",
                                page_index=page_index,
                                warnings=page_ir.warnings.copy(),
                            )
                        ],
                    )
                )
                pages.append(page_ir)

        run = BackendRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            backend=self.name,
            backend_version=self.version,
            options=opts,
            status="ok" if not warnings else "partial",
            errors=warnings.copy(),
            raw_output_dir=str(base_output),
        )

        return DocumentIR(
            schema_version="0.1",
            document_id=make_document_id(str(source)),
            source_path=str(source),
            pages=pages,
            blocks=blocks,
            backend_runs=[run],
            metadata={"adapter": "paddleocr_vl_basic"},
            warnings=warnings,
        )
