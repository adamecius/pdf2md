"""Markdown assembler for page-level strategy outputs."""

from dataclasses import dataclass
from pathlib import Path

from doc2md.models import PageResult


@dataclass
class Assembler:
    """Combine page-level results into a single Markdown document."""

    output_dir: Path
    stem: str

    def assemble(self, page_results: list[PageResult]) -> tuple[Path, dict[str, int]]:
        """Write markdown file and return output path with basic stats."""

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{self.stem}.md"

        ordered = sorted(page_results, key=lambda p: p.page_number)
        markdown = "\n\n".join(page.markdown for page in ordered if page.markdown)
        output_path.write_text(markdown, encoding="utf-8")

        stats = {
            "pages": len(ordered),
            "chars": len(markdown),
            "media": sum(len(page.media) for page in ordered),
        }
        return output_path, stats
