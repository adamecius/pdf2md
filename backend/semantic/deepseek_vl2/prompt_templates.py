"""Prompts for DeepSeek-VL2 semantic-marker detection on a page image.

Plan 005 only requires structured JSON with ≥1 detected marker. The
prompts here ask DeepSeek-VL2 to return a strict JSON object so the
smoke test can parse it without freeform post-processing.

Plan 006 will iterate on these prompts based on benchmark results from
Plan 007.
"""

from __future__ import annotations


SYSTEM_PROMPT = (
    "You are a careful annotator of scientific document pages. "
    "Detect cross-reference markers in the page image and return ONLY a "
    "JSON object that matches the requested schema. Do not write any "
    "prose outside the JSON."
)


USER_PROMPT_TEMPLATE = """Look at this scientific document page and identify every cross-reference marker.

Marker types you may emit:
- "figure"        e.g. "Figure 3", "Fig. 2"
- "table"         e.g. "Table 1"
- "equation"      e.g. "Eq. (3.2)", "(7)"
- "bibliography"  e.g. "[15]", "(Smith, 2020)"
- "footnote"      e.g. "footnote 3", superscript numerals
- "theorem"       e.g. "Theorem 3.2"
- "definition"    e.g. "Definition 1.1"
- "proof"         e.g. "Proof of Theorem 3.2"
- "section"       e.g. "Section 4", "Sec. 2.3"
- "chapter"       e.g. "Chapter 5"

Return JSON with this exact shape:

{{
  "markers": [
    {{"marker_type": "<one of the above>", "marker_text": "<exact surface text>"}}
  ]
}}

Do not invent markers that are not visible on the page. If you see no
markers, return {{"markers": []}}.
"""


def build_messages(page_image_token: str = "<image>") -> list[dict]:
    """Return a chat-formatted message list for DeepSeek-VL2.

    The exact image-token convention depends on the DeepSeek-VL2
    processor; we pass it through as a literal substring that the
    caller's processor will replace with the encoded image.

    Args:
        page_image_token: The processor's expected image placeholder.
            DeepSeek-VL2 uses ``"<image>"`` in the official examples.

    Returns:
        A list of ``{"role", "content"}`` dicts suitable for the
        ``transformers`` chat template.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"{page_image_token}\n\n{USER_PROMPT_TEMPLATE}",
        },
    ]
