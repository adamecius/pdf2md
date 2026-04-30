from __future__ import annotations

from pdf2md.models import Block, Document


def render_block(block: Block) -> str:
    if block.type == "heading":
        level = block.level or 1
        return f"{'#' * level} {block.text or ''}".rstrip()
    if block.type == "paragraph":
        return block.text or ""
    if block.type == "table":
        return block.text or ""
    if block.type == "formula":
        content = block.text or ""
        return f"$$\n{content}\n$$"
    if block.type == "image":
        media_id = block.media_id or block.id
        return f"[image:{media_id}]"
    if block.type == "caption":
        return f"*{block.text or ''}*"
    return block.text or ""


def render_markdown(document: Document) -> str:
    ordered = document.ordered_blocks()
    lines = [render_block(block) for block in ordered]
    return "\n\n".join(lines).strip() + "\n"
