"""Text normalization helpers for DocIR content."""

from __future__ import annotations

import unicodedata


def normalise_text(text: str) -> str:
    """Apply lightweight, stable normalization to extracted text.

    Rules:
    - unicode NFKC normalization
    - normalize newlines to ``\n``
    - trim trailing spaces on each line
    - collapse runs of 2+ blank lines down to 1
    - strip leading/trailing overall whitespace
    """

    value = unicodedata.normalize("NFKC", text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in value.split("\n")]

    collapsed: list[str] = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 1:
                collapsed.append(line)
            continue
        blank_count = 0
        collapsed.append(line)

    return "\n".join(collapsed).strip()
