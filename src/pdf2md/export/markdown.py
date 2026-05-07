"""Build human-readable markdown previews from LinkedStructure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pdf2md.models.linked import LinkedNode, LinkedNodeType, LinkedStructure


@dataclass(frozen=True)
class MarkdownExportSettings:
    include_page_numbers: bool = False
    include_headers_footers: bool = False
    include_unresolved_warnings: bool = True


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _text(node: LinkedNode) -> str:
    return (node.text or str(node.metadata.get("title") or "")).strip()


def build_markdown_preview(*, linked: LinkedStructure, settings: MarkdownExportSettings = MarkdownExportSettings()) -> tuple[str, list[str]]:
    parts: list[str] = []
    warnings: list[str] = []
    for node in sorted(linked.nodes, key=lambda n: (n.order, n.id)):
        ntype = node.node_type
        text = _text(node)
        if ntype == LinkedNodeType.DOCUMENT:
            continue
        if ntype == LinkedNodeType.PAGE_NUMBER and not settings.include_page_numbers:
            continue
        if ntype in {LinkedNodeType.HEADER, LinkedNodeType.FOOTER} and not settings.include_headers_footers:
            continue
        if _value(node.status) == "unresolved" and settings.include_unresolved_warnings:
            warnings.append(f"unresolved_node_emitted:{node.id}")
            parts.append(f"<!-- unresolved:{node.id} -->")
        if not text and ntype not in {LinkedNodeType.FIGURE, LinkedNodeType.TABLE}:
            warnings.append(f"markdown_empty_node:{node.id}")
            continue
        if ntype == LinkedNodeType.TITLE:
            parts.append(f"# {text}")
        elif ntype == LinkedNodeType.SECTION:
            level = int(node.metadata.get("level", 2)) if str(node.metadata.get("level", 2)).isdigit() else 2
            parts.append(f"{'#' * max(2, min(level, 6))} {text}")
        elif ntype == LinkedNodeType.LIST_ITEM:
            parts.append(f"- {text}")
        elif ntype == LinkedNodeType.EQUATION:
            parts.append(f"```math\n{text}\n```")
        elif ntype == LinkedNodeType.TABLE:
            parts.append(text or "[Table]")
        elif ntype == LinkedNodeType.FIGURE:
            parts.append(text or "[Figure]")
        elif ntype == LinkedNodeType.CAPTION:
            parts.append(f"*{text}*")
        elif ntype == LinkedNodeType.FOOTNOTE:
            parts.append(f"[^]: {text}")
        elif ntype == LinkedNodeType.REFERENCE_ITEM:
            parts.append(f"- {text}")
        elif ntype == LinkedNodeType.TOC_ENTRY:
            parts.append(text)
        elif ntype == LinkedNodeType.UNKNOWN:
            parts.append(f"<!-- unknown:{node.id} -->\n{text}")
        else:
            parts.append(text)
    return "\n\n".join(part for part in parts if part).strip() + "\n", warnings
