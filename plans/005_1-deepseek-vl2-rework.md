# Plan 005_1 — DeepSeek-VL2 install rework (currently broken)

## Status: draft
## Date: 2026-05-24
## Depends on: Plan 005_0 (archived as M20)

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Branch name (when activated):
plan-005-1-deepseek-vl2-rework

---

## 1. Problem statement

Plan 005_0 shipped `backend/semantic/deepseek_vl2/{env.yaml, vlm_client.py,
prompt_templates.py, smoke_test.py, README.md}` with the documented
install path:

```bash
conda env create -f backend/semantic/deepseek_vl2/env.yaml
conda run -n pdf2md-deepseek-vl2 python backend/semantic/deepseek_vl2/smoke_test.py \
    --image <page>.png --out-dir /tmp/vlm_smoke
```

This was verified end-to-end on 2026-05-24 and **fails at model load**:

```text
env_not_ready: model load failed: The checkpoint you are trying to load
has model type `deepseek_vl_v2` but Transformers does not recognize
this architecture.
```

Root cause: stock `transformers` does not register the `deepseek_vl_v2`
architecture, even with `trust_remote_code=True`. The model can only
be loaded after `pip install git+https://github.com/deepseek-ai/DeepSeek-VL2.git`,
which pins:

| Pin       | Conflict with current env       |
|-----------|---------------------------------|
| `torch==2.0.1`            | env ships pytorch 2.6 (CUDA 12.1) |
| `transformers==4.38.2`    | env ships transformers 4.51-4.57   |
| `timm>=0.9.16`            | not in current env.yaml             |
| `xformers>=0.0.21`        | not in current env.yaml             |
| `attrdict`                | not in current env.yaml             |

Attempting `pip install --no-deps` plus a separate `pip install timm
xformers attrdict` works around the pins for the deepseek-vl2 install,
but `xformers` then upgrades torch to 2.12 which breaks the conda
`torchvision=0.19` binary with `operator torchvision::nms does not exist`.

## 2. Two viable redesign paths

### Path A — pin deepseek-vl2's exact dep set in an isolated env

Match the upstream pins exactly:

```yaml
# backend/semantic/deepseek_vl2/env.yaml (rewrite)
name: pdf2md-deepseek-vl2
channels: [pytorch, nvidia, conda-forge, defaults]
dependencies:
  - python=3.10
  - pip
  - pytorch=2.0.1
  - pytorch-cuda=11.8       # NB: not 12.1
  - torchvision=0.15.*
  - pip:
      - transformers==4.38.2
      - accelerate>=0.27,<0.30
      - timm>=0.9.16
      - xformers>=0.0.21
      - attrdict
      - sentencepiece
      - einops
      - "deepseek-vl2 @ git+https://github.com/deepseek-ai/DeepSeek-VL2.git"
```

Trade-offs:
- ✅ Matches upstream's tested configuration.
- ⚠️  CUDA 11.8 — needs an older NVIDIA driver compatibility check on
   modern A6000 / RTX 40-series hosts running CUDA 12.x system drivers
   (usually fine, since CUDA is forward-compatible at the driver layer).
- ❌ Inconsistent with the rest of the project's CUDA 12.x toolchain.
- ❌ Locks the VLM env to an old PyTorch — future model upgrades will
   need a fresh env rebuild.

### Path B — migrate to a stock-transformers-supported VLM

Swap DeepSeek-VL2 for a model that's natively supported by
modern `transformers`:

| Candidate          | Params  | License      | Inference notes                          |
|--------------------|---------|--------------|------------------------------------------|
| Qwen2-VL-7B-Instruct | 7B    | Apache 2.0   | Native AutoModelForVision2Seq            |
| LLaVA-OneVision-7B   | 7B    | Apache 2.0   | Native, multi-image support              |
| InternVL2-8B         | 8B    | MIT          | Native, strong on document images        |
| Phi-3.5-Vision       | 4.2B  | MIT          | Native, smaller GPU footprint            |

Trade-offs:
- ✅ Single conda env on modern CUDA 12.x, no `--no-deps` hacks.
- ✅ All four candidates are stable, well-maintained, larger user base.
- ⚠️  `vlm_client.py` + `prompt_templates.py` need a model-specific
   rewrite (chat template format, image-token placement).
- ⚠️  `backend/semantic/deepseek_vl2/` should be renamed
   (e.g. `backend/semantic/vlm/` with the selected model in env.yaml).
- ❌ Benchmark scores from Plan 007 against the existing fixture
   set are not directly comparable across models — Plan 007's eval
   harness will report the new model's marker_f1 separately.

## 3. Recommendation

Path B (`Qwen2-VL-7B-Instruct`) is preferred:

1. Aligns with the project's CUDA 12.x default.
2. No vendored-source workaround — `pip install transformers qwen-vl-utils`
   is sufficient.
3. The marker-detection prompt is portable between VLMs; the work to
   port is a few hundred lines of `vlm_client.py` + the new processor
   call.
4. Plan 007's evaluation harness already supports per-backend scoring,
   so we don't lose the ability to compare the new VLM against regex.

If preserving the `deepseek-vl2-small` choice is important for
benchmark continuity, Path A is the fallback — but it commits us to a
maintenance burden for an old torch.

## 4. Out of scope

- Replacing GROBID. (Plan 005_2 handles that separately.)
- Re-running Plan 007's benchmark on the new VLM. (Subsequent plan.)
- Any change to the `SemanticBackend` ABC in `src/pdf2md/semantic/base.py`
  — the existing subprocess pattern works for any VLM.

## 5. Evidence

The install-broken state was verified end-to-end on 2026-05-24 by
running:

```bash
conda env create -f backend/semantic/deepseek_vl2/env.yaml
/home/jgarcia/miniconda3/envs/pdf2md-deepseek-vl2/bin/python \
    backend/semantic/deepseek_vl2/smoke_test.py \
    --image /tmp/sample_page-01.png --out-dir /tmp/vlm_smoke
```

→ `env_not_ready: model load failed: ... Transformers does not recognize
this architecture`.

The follow-up `pip install --no-deps deepseek-vl2 + timm + xformers + attrdict`
sequence then breaks torchvision at runtime (verified).

## 6. Promotion

This plan stays in `plans/` (not yet promoted to `current_plan.md`)
until the human reviewer chooses Path A or Path B. The notes in
`backend/semantic/deepseek_vl2/env.yaml` and
`backend/semantic/deepseek_vl2/README.md` flag the install as
**known broken** so users discover the issue at the right time.
