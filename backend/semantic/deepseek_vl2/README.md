# DeepSeek-VL2 semantic backend

DeepSeek-VL2 is a Vision-Language Model
([huggingface.co/deepseek-ai/deepseek-vl2-small](https://huggingface.co/deepseek-ai/deepseek-vl2-small))
that can look at a rendered page image and emit structured JSON. Plan 005
uses the `small` variant (~5.6 GB, fits a single 16 GB GPU) to detect
cross-reference markers on one page at a time.

Among the three semantic backends, DeepSeek-VL2 is the most flexible
(works on any page, including scanned scientific PDFs without text
layers) and the most expensive (GPU memory + a few seconds per page).

## Install

```bash
conda env create -f backend/semantic/deepseek_vl2/env.yaml
conda activate pdf2md-deepseek-vl2
```

This creates the `pdf2md-deepseek-vl2` env with:

| Dep | Pin | Channel |
|---|---|---|
| python | 3.11 | conda-forge |
| pytorch | 2.4.* | pytorch |
| pytorch-cuda | 12.1 | nvidia |
| torchvision | 0.19.* | pytorch |
| pillow | ≥10 | conda-forge |
| transformers | ≥4.45,<5 | pip |
| accelerate | ≥0.34 | pip |
| sentencepiece | ≥0.2 | pip |
| einops | ≥0.8 | pip |

Hardware requirements:

- NVIDIA GPU with ≥16 GB VRAM (8 GB works with CPU offload but is slow).
- CUDA 12.x driver. The conda env pins `pytorch-cuda=12.1`.
- ~6 GB free disk for the model weights (downloaded on first run).

The model is **not** pre-downloaded by the env. The first call to
`smoke_test.py` triggers a Hugging Face download to your `~/.cache/huggingface/`.

## Run the smoke test

```bash
conda run -n pdf2md-deepseek-vl2 python backend/semantic/deepseek_vl2/smoke_test.py \
    --image tests/data/<a_sample_page>.png \
    --out-dir /tmp/vlm_smoke
```

Expected output line:

```text
deepseek-vl2 smoke: <N> markers, load=<L> ms, infer=<I> ms, out=/tmp/vlm_smoke/vlm_smoke_result.json
```

Plan 005 H2 requires `N ≥ 1`.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | success — ≥1 marker extracted |
| 1 | repository defect — no markers detected on a page that has them |
| 2 | bad argument — image not found |
| 3 | `env_not_ready` — env missing dep, model load failed, no GPU, etc. |

A common failure during bring-up is `env_not_ready: model load failed:
CUDA out of memory`. Lower-VRAM hosts can pass `--device cpu` (much
slower) or switch to the `deepseek-vl2-tiny` model id, which is not
pinned by Plan 005 but should work with the same prompts.

## Output shape

`vlm_smoke_result.json`:

```jsonc
{
  "backend": "deepseek-vl2",
  "backend_version": "deepseek-ai/deepseek-vl2-small",
  "device": "cuda",
  "input_path": "tests/data/sample_page.png",
  "load_ms": 18420.0,
  "inference_ms": 3120.0,
  "markers": [
    {"marker_type": "figure", "marker_text": "Figure 3"},
    {"marker_type": "bibliography", "marker_text": "[15]"}
  ],
  "raw_text": "{\"markers\": [...]}",
  "parse_error": null
}
```

`raw_text` is preserved even on success so prompt drift can be
audited later. `parse_error` is non-null when the model returned
unparseable output (the smoke test still exits 0 if the parsed
marker list is non-empty).

## Library use

```python
# Only valid inside the pdf2md-deepseek-vl2 env.
from backend.semantic.deepseek_vl2 import vlm_client

settings = vlm_client.VlmSettings()  # cuda + bf16 by default
model, processor = vlm_client.load_model(settings)
out = vlm_client.extract_markers(
    Path("page.png"), model=model, processor=processor, settings=settings,
)
print(out["markers"])
```

Plan 006 will wrap this in the `SemanticBackend` interface under
`src/pdf2md/semantic/vlm_adapter.py`. Until then, do not import this
module from `src/pdf2md/`. The main `pdf2md` env does not have `torch`
or `transformers` pinned and the import will fail there.

## Limitations

- Model output is non-deterministic across hardware even at
  `temperature=0` because of CUDA kernel non-determinism. The smoke
  test does not enforce exact-marker equality; only count ≥ 1.
- Prompt is intentionally narrow (the marker-type vocabulary in
  `prompt_templates.py`). It will not detect marker types that are
  not listed. Plan 006 will expand the vocabulary.
- One page per call. Multi-page batching is Plan 006 work.
- No fallback to CPU when CUDA fails — we report `env_not_ready`
  and let the operator decide.
