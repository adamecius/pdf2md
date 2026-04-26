"""Deterministic backend adapter that emits minimal DocIR."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pymupdf

from doc2md.backends.base import ExtractionBackend
from doc2md.ir import (
    BackendRun,
    BlockIR,
    DocumentIR,
    MediaRef,
    PageIR,
    Provenance,
    make_block_id,
    make_document_id,
    make_media_id,
    make_page_id,
)
from doc2md.models import Strategy
from doc2md.profiler import profile_document
from doc2md.router import route_document
from doc2md.strategies.deterministic import DeterministicStrategy


class DeterministicBackend(ExtractionBackend):
    """Backend that reuses the deterministic lane to produce DocIR."""

    name = "deterministic"
    version = "0.1"

    def available(self) -> bool:
        return True

    def extract(
        self,
        input_path: Path,
        output_dir: Path | None = None,
        options: dict[str, Any] | None = None,
    ) -> DocumentIR:
        opts = options or {}
        source = Path(input_path)
        text_threshold = float(opts.get("text_threshold", 0.8))

        profile = profile_document(source)
        route_document(profile, text_threshold=text_threshold)

        warnings: list[str] = []
        pages: list[PageIR] = []
        blocks: list[BlockIR] = []
        media: list[MediaRef] = []

        strategy_runner: DeterministicStrategy | None = None
        if output_dir is not None:
            strategy_runner = DeterministicStrategy(output_dir=Path(output_dir))

        with pymupdf.open(str(source)) as pdf:
            for page_profile in profile.pages:
                page_index = page_profile.page_number
                page = pdf[page_index]
                page_strategy = page_profile.strategy.name.lower() if page_profile.strategy else None

                page_ir = PageIR(
                    page_id=make_page_id(page_index),
                    page_index=page_index,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=int(page.rotation),
                    strategy=page_strategy,
                )

                if page_profile.strategy != Strategy.DETERMINISTIC:
                    warn = (
                        f"page {page_index + 1} routed to {page_strategy}; "
                        "backend only processes deterministic pages"
                    )
                    page_ir.warnings.append(warn)
                    warnings.append(warn)
                    pages.append(page_ir)
                    continue

                text = page.get_text("text").strip()
                order = 0
                if text:
                    text_block_id = make_block_id(page_index, order, text=text)
                    text_block = BlockIR(
                        block_id=text_block_id,
                        type="paragraph",
                        role="body",
                        text=text,
                        markdown=text,
                        page_indexes=[page_index],
                        order=order,
                        provenance=[
                            Provenance(
                                backend=self.name,
                                backend_version=self.version,
                                strategy="deterministic",
                                page_index=page_index,
                            )
                        ],
                    )
                    blocks.append(text_block)
                    page_ir.block_ids.append(text_block_id)
                    order += 1

                if strategy_runner is not None:
                    page_result = strategy_runner.process_page(page, page_index)
                    if page_result.error:
                        warn = f"page {page_index + 1}: {page_result.error}"
                        page_ir.warnings.append(warn)
                        warnings.append(warn)

                    for image_ref in page_result.media:
                        media_id = make_media_id(page_index, "image", image_ref.index_in_page)
                        media.append(
                            MediaRef(
                                media_id=media_id,
                                type="image",
                                path=image_ref.relative_path,
                                page_index=page_index,
                                width=image_ref.width_px,
                                height=image_ref.height_px,
                            )
                        )
                        media_block_id = make_block_id(page_index, order, text=image_ref.relative_path)
                        media_block = BlockIR(
                            block_id=media_block_id,
                            type="image",
                            role="figure",
                            markdown=f"![]({image_ref.relative_path})",
                            page_indexes=[page_index],
                            order=order,
                            media_refs=[media_id],
                            provenance=[
                                Provenance(
                                    backend=self.name,
                                    backend_version=self.version,
                                    strategy="deterministic",
                                    page_index=page_index,
                                )
                            ],
                        )
                        blocks.append(media_block)
                        page_ir.block_ids.append(media_block_id)
                        order += 1

                pages.append(page_ir)

        status = "ok" if not warnings else "partial"
        run = BackendRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            backend=self.name,
            backend_version=self.version,
            options=opts,
            status=status,
            errors=list(warnings),
            raw_output_dir=str(output_dir) if output_dir is not None else None,
        )

        return DocumentIR(
            schema_version="0.1",
            document_id=make_document_id(str(source)),
            source_path=str(source),
            pages=pages,
            blocks=blocks,
            media=media,
            backend_runs=[run],
            metadata={"text_threshold": text_threshold},
            warnings=warnings,
        )
