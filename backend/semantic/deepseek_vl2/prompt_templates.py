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
    "prose outside the JSON. NEVER invent markers that are not literally "
    "visible on the page — if the page has no markers of a given type, "
    "do not emit any of that type."
)


# The marker-type descriptions are intentionally **abstract** — small
# VLMs (this includes deepseek-vl2-small) have a strong tendency to
# echo concrete `e.g.` examples back into the output regardless of what
# the page actually contains. Earlier versions of this prompt listed
# example strings like "Figure 3", "Eq. (3.2)", "[15]" and the model
# returned exactly those strings for every page it processed. The fix
# is to describe the SHAPE without offering surface strings the model
# could copy.
USER_PROMPT_TEMPLATE = """Look at the page image. Find every visible cross-reference marker — a literal piece of text that points to a numbered or labelled element of the document. Read the actual text on the page; do not guess.

Allowed marker_type values:

- "figure"        a reference to a figure (any "Figure N" / "Fig. N" form)
- "table"         a reference to a table
- "equation"      a reference to an equation by number, including bare parenthesised numbers like the equation-number printed next to the equation
- "bibliography"  a citation key: either bracketed numbers, or author-year, or superscript citation
- "footnote"      a footnote marker (small superscript number, dagger, etc.)
- "theorem"       a reference to a theorem
- "definition"    a reference to a definition
- "proof"         a reference to a specific proof
- "section"       a reference to a section
- "chapter"       a reference to a chapter

Return JSON with this exact shape:

{{
  "markers": [
    {{"marker_type": "<one of the above>", "marker_text": "<the exact surface text as it appears on the page>"}}
  ]
}}

Rules:
- Only include markers whose surface text is literally present on the page.
- Use the surface text VERBATIM, including capitalisation, punctuation, and brackets ("FIG. 3", "[2]", "(11)" — not "Figure 3" or "15").
- If a marker type has no occurrence on this page, do not emit any entry of that type.
- If the page has no markers at all, return {{"markers": []}}.
"""


def build_messages(page_image_token: str = "<image>") -> list[dict]:
    """Return a chat-formatted message list for DeepSeek-VL2.

    The DeepSeek-VL2 processor expects a list of ``{role, content}``
    dicts where:

    - The ``user`` turn carries the page image token (``<image>`` by
      default) and the natural-language prompt.
    - The conversation MUST end with an empty ``assistant`` turn — the
      processor uses that to mark where the generated reply starts and
      strips the trailing EOS token in inference mode. Without it, the
      processor raises ``AssertionError: input_ids[-1] == self.eos_id``.

    Args:
        page_image_token: The processor's expected image placeholder.
            DeepSeek-VL2 uses ``"<image>"`` in the official examples.

    Returns:
        A list of ``{"role", "content"}`` dicts suitable for the
        DeepSeek-VL2 processor's ``__call__(conversations=...)`` path.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"{page_image_token}\n\n{USER_PROMPT_TEMPLATE}",
        },
        # Empty assistant turn — required by DeepseekVLV2Processor in
        # inference mode. The processor appends an EOS to this turn and
        # strips it; the model's generated text takes its place.
        {"role": "assistant", "content": ""},
    ]
