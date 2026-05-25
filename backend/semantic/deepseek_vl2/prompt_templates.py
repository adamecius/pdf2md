"""Prompts for DeepSeek-VL2 semantic-marker detection on a page image.

Plan 005 only requires structured JSON with ≥1 detected marker. The
prompts here ask DeepSeek-VL2 to return a strict JSON object so the
smoke test can parse it without freeform post-processing.

Plan 006 will iterate on these prompts based on benchmark results from
Plan 007.

Prompt evolution (each version was driven by an end-to-end benchmark
on the arxiv example PDFs, with deepseek-OCR entities as candidates):

- v1: example-laced prompt — the model echoed the `e.g. "Figure 3"`,
  `"[15]"`, `"Theorem 3.2"` examples verbatim regardless of page
  content. example01: 4/25 resolved (16%), most markers fake.
- v2: stripped the example strings, kept the full type list. Real
  surface forms emerged (`"FIG. 1"`, `"[7]"`, `"Eq. (15)"`). example01:
  6/27 resolved (22.2%), but still 3 hallucinated math types on a
  physics paper.
- v3: added "ONLY emit if the word appears literally" guards on
  math types. **Backfired** — small VLMs don't reliably follow
  conditional exclusion rules; listing the types in the prompt at all
  primes the model to find them. example01: 7/47 resolved (14.9%),
  with 17 hallucinated math markers (5 theorems, 5 corollaries, 5
  examples, 4 definitions, 3 proofs on a paper that has none).
- v4 (current): the **default** prompt omits math-style types
  entirely; they're available behind the opt-in `MATH_TYPES_BLOCK`
  that callers append for known math/CS papers via
  ``build_messages(include_math_types=True)``. example01 (physics,
  default prompt): **17 markers, 0 hallucinations**, 4/17 resolved
  (23.5% — best). example02 (math paper, with math types):
  59 markers, 4/59 resolved (6.8%) — the math-type detection works,
  but the OCR side doesn't have many of those as candidates yet.
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


USER_PROMPT_TEMPLATE = """Look at the page image. Find every visible cross-reference marker — a literal piece of text that points to a numbered or labelled element of the document. Read the actual text on the page; do not guess.

Allowed marker_type values:

- "figure"        a reference to a figure (any "Figure N" / "Fig. N" form)
- "table"         a reference to a table
- "equation"      a reference to an equation by number, including bare parenthesised numbers like the equation-number printed next to the equation
- "bibliography"  a citation key: either bracketed numbers, or author-year, or superscript citation
- "footnote"      a footnote marker (small superscript number, dagger, etc.)
- "section"       a reference to a section
- "chapter"       a reference to a chapter

Return JSON with this exact shape:

{{
  "markers": [
    {{"marker_type": "<one of the above>", "marker_text": "<the exact surface text as it appears on the page>"}}
  ]
}}

Rules:

1. **Verbatim**: copy the surface text exactly as it appears on the page — keep capitalisation, punctuation, brackets, and numbering ("FIG. 3", "[2]", "(11)", "Eq. (5.4)" — NEVER normalise to "Figure 3" / "15" / "Eq. 5.4").
2. **Literally visible**: only emit a marker whose surface text is currently visible on this page image. Do not infer markers from context, prior pages, or document type.
3. **No empty-type entries**: if a marker type has zero occurrences on this page, do not emit any entry of that type. Returning a short list is correct.
4. **Empty pages are valid**: if the page has no markers at all (e.g. a pure-image figure page or a blank page), return {{"markers": []}}.
"""


# Opt-in extension. Append this to USER_PROMPT_TEMPLATE for known
# math/CS papers (where these labels are common). DO NOT enable by
# default — small VLMs hallucinate these types on documents that
# contain none, and listing the types in the prompt at all primes the
# model to emit them. The benchmark showed v3 (which included these
# types with "ONLY emit if literally visible" guards) produced 5
# theorems / 5 corollaries / 5 examples on a physics paper that has
# none.
MATH_TYPES_BLOCK = """
This document is known to contain formal math content. Additionally
detect:

- "theorem"       "Theorem N", "Theorem N.M"
- "definition"    "Definition N", "Definition N.M"
- "proof"         "Proof of Theorem N", "Proof N.M"
- "corollary"     "Corollary N", "Corollary N.M"
- "example"       "Example N", "Example N.M" (numbered label, NOT prose mentions)
"""


def build_messages(
    page_image_token: str = "<image>",
    *,
    include_math_types: bool = False,
) -> list[dict]:
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
        include_math_types: Set ``True`` for documents known to contain
            theorems / definitions / proofs / corollaries / examples
            (formal math / theoretical CS papers). Off by default —
            see :data:`MATH_TYPES_BLOCK` for the rationale.

    Returns:
        A list of ``{"role", "content"}`` dicts suitable for the
        DeepSeek-VL2 processor's ``__call__(conversations=...)`` path.
    """
    user_prompt = USER_PROMPT_TEMPLATE
    if include_math_types:
        user_prompt = user_prompt + MATH_TYPES_BLOCK
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"{page_image_token}\n\n{user_prompt}",
        },
        # Empty assistant turn — required by DeepseekVLV2Processor in
        # inference mode. The processor appends an EOS to this turn and
        # strips it; the model's generated text takes its place.
        {"role": "assistant", "content": ""},
    ]
