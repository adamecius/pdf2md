"""Markdown exporter derived from canonical DocIR blocks."""

from __future__ import annotations

from pathlib import Path

from doc2md.ir.schema import BlockIR, DocumentIR


def _sort_key(block: BlockIR) -> tuple[int, int, str]:
    first_page = min(block.page_indexes) if block.page_indexes else 0
    return (first_page, block.order, block.block_id)


def _render_equation_block(block: BlockIR) -> str:
    latex = (block.latex or "").strip()
    if latex:
        if "\n" in latex or len(latex) > 80:
            return f"$$\n{latex}\n$$"
        return f"$$ {latex} $$"
    return (block.markdown or block.text or "").strip()


def _render_table_block(block: BlockIR) -> str:
    if block.html:
        return block.html.strip()
    if block.markdown:
        return block.markdown.strip()
    return (block.text or "").strip()


def _render_block(block: BlockIR) -> str:
    if block.type == "equation":
        return _render_equation_block(block)
    if block.type == "table":
        return _render_table_block(block)
    return (block.markdown or block.text or "").strip()


def export_markdown(doc: DocumentIR) -> str:
    """Export DocIR into deterministic Markdown.

    Rendering rules:
    - Use ``block.markdown`` when present, otherwise ``block.text``.
    - Equations prefer ``latex`` in ``$$`` blocks.
    - Tables prefer ``html``, then markdown, then plain text.
    - Include page separators as HTML comments.
    - Skip blocks where ``include_in_rag`` is false.
    """

    ordered_pages = sorted(doc.pages, key=lambda page: page.page_index)
    blocks_by_page: dict[int, list[BlockIR]] = {page.page_index: [] for page in ordered_pages}
    for block in sorted(doc.blocks, key=_sort_key):
        if not block.include_in_rag:
            continue
        if not block.page_indexes:
            continue
        first_page = min(block.page_indexes)
        if first_page in blocks_by_page:
            blocks_by_page[first_page].append(block)

    lines: list[str] = []
    for page in ordered_pages:
        if lines:
            lines.append("")
        lines.append(f"<!-- page {page.page_index + 1} -->")

        page_blocks = blocks_by_page.get(page.page_index, [])
        for block in page_blocks:
            rendered = _render_block(block)
            if not rendered:
                continue
            lines.append("")
            lines.append(rendered)

    if not lines:
        return ""
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(doc: DocumentIR, path: str | Path) -> None:
    """Export DocIR to Markdown and write it to disk."""

    output = export_markdown(doc)
    Path(path).write_text(output, encoding="utf-8")
