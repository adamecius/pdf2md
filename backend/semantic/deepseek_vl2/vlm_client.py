"""Thin wrapper around DeepSeek-VL2 for cross-reference marker detection.

Plan 005 keeps this minimal: load the model, run one page image through
it, get a JSON string back, parse it. No batching, no caching, no model
quantisation — those belong to Plan 006 / 007.

The module imports ``torch`` and ``transformers`` at the top level on
purpose: this module is only ever imported inside the
``pdf2md-deepseek-vl2`` conda env (see ``env.yaml``). It must NEVER be
imported from the main ``pdf2md`` env or from ``src/pdf2md/``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch  # type: ignore[import-not-found]
from PIL import Image  # type: ignore[import-not-found]

# Use the upstream DeepSeek-VL2 classes directly. The `deepseek_vl_v2`
# architecture is NOT registered in transformers' AutoModel registry —
# `AutoModelForCausalLM.from_pretrained(..., trust_remote_code=True)`
# fails with "Transformers does not recognize this architecture" because
# the registration lookup happens before the remote code can run. The
# upstream `deepseek_vl2` python package (installed by setup.py) provides
# `DeepseekVLV2ForCausalLM` + `DeepseekVLV2Processor` as the canonical
# load classes — this is exactly the pattern documented in the
# DeepSeek-VL2 README.
from deepseek_vl2.models import (  # type: ignore[import-not-found]
    DeepseekVLV2ForCausalLM,
    DeepseekVLV2Processor,
)

import prompt_templates


DEFAULT_MODEL_ID = "deepseek-ai/deepseek-vl2-small"


@dataclass(frozen=True)
class VlmSettings:
    """Inference settings for the DeepSeek-VL2 smoke test.

    Attributes:
        model_id: Hugging Face model id.
        device: Torch device string (``"cuda"`` / ``"cpu"``).
        max_new_tokens: Generation cap.
        temperature: Sampling temperature. Use 0.0 for deterministic
            output (greedy decoding).
        dtype: Torch dtype for the model weights. Defaults to bfloat16
            on CUDA, float32 on CPU.
    """

    model_id: str = DEFAULT_MODEL_ID
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    max_new_tokens: int = 512
    temperature: float = 0.0
    dtype: torch.dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32


def _strip_to_json(raw: str) -> str:
    """Trim model output down to the first JSON object substring.

    DeepSeek-VL2 sometimes wraps the JSON in a code fence or appends a
    trailing explanation. We strip the fence and snip out the first
    balanced ``{...}`` block.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def load_model(settings: VlmSettings) -> tuple[Any, Any]:
    """Load the DeepSeek-VL2 model and processor onto ``settings.device``.

    First call downloads the weights from Hugging Face (~5.6 GB for
    ``deepseek-vl2-small``).

    Returns:
        ``(model, processor)`` — both already on the target device.
    """
    processor = DeepseekVLV2Processor.from_pretrained(settings.model_id)
    model = DeepseekVLV2ForCausalLM.from_pretrained(
        settings.model_id,
        torch_dtype=settings.dtype,
    )
    model = model.to(settings.device).eval()
    return model, processor


def extract_markers(
    image_path: Path,
    *,
    model: Any,
    processor: Any,
    settings: VlmSettings,
) -> dict:
    """Run one page image through DeepSeek-VL2 and return parsed markers.

    Args:
        image_path: Path to a PNG / JPEG image of a single PDF page.
        model: A loaded DeepSeek-VL2 model (see :func:`load_model`).
        processor: The matching processor.
        settings: Inference settings.

    Returns:
        A dict ``{"raw_text", "markers", "parse_error"}``. ``markers`` is
        a list of ``{"marker_type", "marker_text"}`` dicts (possibly
        empty). ``parse_error`` is ``None`` when JSON parsing succeeded
        and a short error string otherwise — the raw text is always
        kept so the smoke test can audit prompt-output failures.
    """
    image = Image.open(image_path).convert("RGB")
    messages = prompt_templates.build_messages()

    # DeepSeek-VL2 has a non-standard inference flow (see
    # deepseek_vl2/serve/inference.py and the upstream README):
    #   1. processor(conversations=..., images=..., force_batchify=True)
    #      returns a `BatchCollateOutput` dataclass, NOT a dict.
    #   2. The dataclass has a `.to(device, dtype=...)` method that moves
    #      images + input_ids together.
    #   3. The model's `prepare_inputs_embeds(**prepare_inputs)` builds
    #      the multi-modal embedding from the image and text tokens.
    #   4. `model.language.generate(inputs_embeds=...)` runs the LLM.
    prepare_inputs = processor(
        conversations=messages,
        images=[image],
        force_batchify=True,
    ).to(settings.device, dtype=settings.dtype)

    with torch.no_grad():
        inputs_embeds = model.prepare_inputs_embeds(**prepare_inputs)
        gen = model.language.generate(
            inputs_embeds=inputs_embeds,
            attention_mask=prepare_inputs.attention_mask,
            pad_token_id=processor.tokenizer.eos_token_id,
            bos_token_id=processor.tokenizer.bos_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
            max_new_tokens=settings.max_new_tokens,
            do_sample=settings.temperature > 0.0,
            temperature=max(settings.temperature, 1e-5),
            use_cache=True,
        )

    raw = processor.tokenizer.decode(gen[0].cpu().tolist(), skip_special_tokens=True)

    json_str = _strip_to_json(raw)
    try:
        payload = json.loads(json_str)
        markers = payload.get("markers", []) if isinstance(payload, dict) else []
        # Filter to dicts with the two required keys, drop anything else.
        markers = [
            {"marker_type": str(m["marker_type"]), "marker_text": str(m["marker_text"])}
            for m in markers
            if isinstance(m, dict) and "marker_type" in m and "marker_text" in m
        ]
        parse_error = None
    except json.JSONDecodeError as exc:
        markers = []
        parse_error = f"json decode failed: {exc}"

    return {
        "raw_text": raw,
        "markers": markers,
        "parse_error": parse_error,
    }
