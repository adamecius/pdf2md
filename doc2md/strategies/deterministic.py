"""Deterministic extraction strategy using the PDF text layer."""

from pathlib import Path

import pymupdf

from doc2md.models import MediaRef, PageResult, Strategy


class DeterministicStrategy:
    """Extract text and embedded raster images from a page."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.media_dir = output_dir / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def process_page(self, page: pymupdf.Page, page_number: int) -> PageResult:
        """Process one page and return page markdown plus media references."""

        raw_text = page.get_text("text").strip()
        markdown_parts = [f"<!-- page {page_number + 1} -->"]
        if raw_text:
            markdown_parts.append(raw_text)

        media: list[MediaRef] = []
        notes: list[str] = []

        for index, image_tuple in enumerate(page.get_images(full=True), start=1):
            xref = image_tuple[0]
            try:
                image_data = page.parent.extract_image(xref)
                ext = image_data.get("ext", "bin")
                width = int(image_data.get("width", 0))
                height = int(image_data.get("height", 0))
                image_bytes = image_data["image"]
            except Exception as exc:  # continue page processing on image failures
                notes.append(f"image {index} extraction failed: {exc}")
                continue

            file_name = f"img_p{page_number + 1}_{index:03d}.{ext}"
            file_path = self.media_dir / file_name
            file_path.write_bytes(image_bytes)

            rel_path = f"media/{file_name}"
            media.append(
                MediaRef(
                    relative_path=rel_path,
                    page_number=page_number,
                    index_in_page=index,
                    width_px=width,
                    height_px=height,
                )
            )
            markdown_parts.append(f"![]({rel_path})")

        return PageResult(
            page_number=page_number,
            markdown="\n\n".join(markdown_parts).strip(),
            media=media,
            strategy=Strategy.DETERMINISTIC,
            error="; ".join(notes) if notes else None,
        )
