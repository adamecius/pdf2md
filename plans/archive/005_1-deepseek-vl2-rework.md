# Plan 005_1 — DeepSeek-VL2 install rework (match extraction-backend pattern)

## Status: finished
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

Plan 005_0 shipped `backend/semantic/deepseek_vl2/` with a two-file
install kit (`env.yaml`, `smoke_test.py`). The documented install path
**fails at model load** (verified 2026-05-24):

```text
env_not_ready: model load failed: The checkpoint you are trying to
load has model type `deepseek_vl_v2` but Transformers does not
recognize this architecture.
```

Three things compound the failure:

1. Stock `transformers` (4.45–4.57) does **not** register the
   `deepseek_vl_v2` architecture — even with `trust_remote_code=True`.
2. The official `deepseek-vl2` python package
   (`pip install git+https://github.com/deepseek-ai/DeepSeek-VL2.git`)
   registers the architecture but **over-pins**
   `torch==2.0.1` + `transformers==4.38.2`. Forcing those pins
   conflicts with the env's CUDA 12.x torch.
3. Required transitive deps (`timm`, `xformers`, `attrdict`) are not
   in `env.yaml`. Installing them via `pip install timm xformers
   attrdict` after `--no-deps` bumps torch to 2.12, which then
   breaks the conda `torchvision=0.19` binary with
   `operator torchvision::nms does not exist`.

The root cause is that **the semantic backends never adopted the
extraction-backend install pattern** the rest of the project uses.

## 2. The project's existing install pattern

Every existing OCR backend under `backend/<name>/` (paddleocr, mineru,
deepseek, glm) ships a **five-file install kit**:

```text
backend/<name>/
├── environment.yml          # minimal conda spec (python + system deps)
├── requirements.txt         # pip deps
├── setup_env.py             # thin wrapper around `conda env create -f environment.yml`
├── setup.py                 # main installer — HW preflight, conda+venv,
│                            #   upstream-repo clone/wheels, constraints, verify
├── delete_env.py            # companion teardown
└── …                        # backend-specific runner + README
```

[backend/deepseek/setup.py](../backend/deepseek/setup.py)
(~300 LOC) is the closest existing analogue. It:

1. Creates a conda env with `python=3.12.9` + pip.
2. Installs `cuda-toolkit=11.8` from `nvidia/label/cuda-11.8.0`.
3. Writes a `cuda-11.8.sh` activation script.
4. Clones `https://github.com/deepseek-ai/DeepSeek-OCR-2.git`.
5. Downloads `vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl`.
6. Installs `torch==2.6.0 + torchvision==0.21.0 --index-url …/whl/cu118`.
7. Writes a `deepseek-ocr2-constraints.txt` (`numpy==2.2.6`) and
   uses `pip install -r requirements.txt -c constraints.txt` to
   keep numpy from being upgraded by transitive deps.
8. Installs flash-attn 2.7.3 from source with `--no-build-isolation`.
9. Verifies: `import torch, numpy, transformers, tokenizers, vllm,
   flash_attn` and prints versions.

This pattern handles **every single failure mode** I hit on the VL2
install. The fix is to apply the same pattern to
`backend/semantic/deepseek_vl2/`.

## 3. Goal

Make DeepSeek-VL2 install in the exact same shape as the four
extraction backends. After this plan:

```bash
# Standard pdf2md install — identical shape to backend/deepseek/setup.py:
python backend/semantic/deepseek_vl2/setup.py

# Or step-by-step:
python backend/semantic/deepseek_vl2/setup_env.py --manager conda
python backend/semantic/deepseek_vl2/setup.py --skip-env-create
```

The smoke test (`smoke_test.py`), the loader (`vlm_client.py`), and
the in-tree adapter (`src/pdf2md/semantic/vlm_adapter.py` — Plan 006_0)
do not change — they continue to call `AutoModelForCausalLM
.from_pretrained(...)` with `trust_remote_code=True`, which works once
the `deepseek_vl2` package is properly installed.

## 4. File layout (5-file kit)

```text
backend/semantic/deepseek_vl2/
├── environment.yml          # NEW (replaces env.yaml — match extraction-backend filename)
├── requirements.txt         # NEW — full pip list, ordered
├── setup_env.py             # NEW — bootstrap, identical shape to backend/deepseek/setup_env.py
├── setup.py                 # NEW — main installer (see §5)
├── delete_env.py            # NEW — companion teardown
├── vlm_client.py            # UNCHANGED
├── prompt_templates.py      # UNCHANGED
├── smoke_test.py            # UNCHANGED
└── README.md                # REWRITE — short, points at setup.py
```

The old `env.yaml` is **removed** (renamed to `environment.yml`).

## 5. `setup.py` design

Single Python file, ~350 LOC, structured like
[backend/deepseek/setup.py](../backend/deepseek/setup.py):

### 5.1 Constants

```python
DEFAULT_ENV_NAME    = "pdf2md-deepseek-vl2"
DEFAULT_PYTHON_VER  = "3.11"

DEEPSEEK_REPO_URL   = "https://github.com/deepseek-ai/DeepSeek-VL2.git"
DEEPSEEK_REPO_REF   = None              # follow main; None = no checkout step

# Match upstream's tested config:
TORCH_VERSION       = "2.0.1"
TORCH_CUDA_VARIANT  = "cu118"           # pyproject pins torch==2.0.1; cu118 wheels available
TORCHVISION_VERSION = "0.15.2"          # paired with torch 2.0.1
TRANSFORMERS_VERSION = "4.38.2"

# Constraints file forces these to win over the source pkg's pyproject pins:
INLINE_REQUIREMENTS = [
    "torch==2.0.1",
    "torchvision==0.15.2",
    f"transformers=={TRANSFORMERS_VERSION}",
    "accelerate>=0.27,<0.30",
    "sentencepiece",
    "einops",
    "timm>=0.9.16",
    "xformers>=0.0.21,<0.0.22",        # paired with torch 2.0
    "attrdict",
    "pillow>=10.0",
]

MIN_VRAM_MB = 16_000
MIN_RAM_GB  = 16
MIN_DISK_GB = 30                        # 5.6 GB model + ~10 GB env + headroom
```

### 5.2 Preflight `check_*()` functions

Same `CheckResult` dataclass as paddleocr/mineru/deepseek:

- `check_os()` — Linux/macOS/Windows gate.
- `check_python_version()` — ≥3.10 for `setup.py` itself.
- `check_nvidia_gpu()` — VRAM ≥16 GB (or warn + offer `--device cpu`).
- `check_cuda_version()` — system driver ≥11.8 (driver, not toolkit).
- `check_ram()`, `check_disk()`.

### 5.3 Env creation

- `create_conda_env(env_name, python_ver)` — `conda create -n
  pdf2md-deepseek-vl2 python=3.11 pip -y`. Does NOT install
  cuda-toolkit (the cu118 PyTorch wheels include their own CUDA
  runtime; this is the documented DeepSeek-VL2 path).
- `create_venv_env(env_name, python_exe)` — venv fallback.

### 5.4 Repo clone (optional, off by default)

- `--clone-repo` flag: clones `https://github.com/deepseek-ai/DeepSeek-VL2`
  into `~/models/deepseek-vl2/` for users who want the inference
  examples. Not required for the smoke test.

### 5.5 PyTorch install

- `install_torch(env_name, ...)` — pip-installs
  `torch==2.0.1 torchvision==0.15.2` with `--index-url
  https://download.pytorch.org/whl/cu118`. Mirrors
  `backend/deepseek/setup.py` exactly.

### 5.6 Constraints + pip install

- Write a constraints file under `${CONDA_PREFIX}/share/deepseek-vl2/
  constraints.txt` containing the lines from `INLINE_REQUIREMENTS`.
- `pip install -r requirements.txt -c constraints.txt`.
- `pip install --no-deps git+https://github.com/deepseek-ai/DeepSeek-VL2.git
  -c constraints.txt`. The `--no-deps` is **required** — without it,
  the source pkg's `torch==2.0.1, transformers==4.38.2`
  resolution-with-conflicts message stalls pip for minutes.

### 5.7 Verify

```python
def verify_install(env_name):
    """End-to-end check: import deepseek_vl2, instantiate processor,
    confirm the architecture is registered."""
    code = (
        "import torch, transformers, deepseek_vl2;"
        "print('torch', torch.__version__);"
        "print('transformers', transformers.__version__);"
        "from deepseek_vl2.models import DeepseekVLV2ForCausalLM, DeepseekVLV2Processor;"
        "print('OK:', DeepseekVLV2ForCausalLM, DeepseekVLV2Processor)"
    )
    conda_run(env_name, ["python", "-c", code])
```

Optional `--smoke-image PATH`: if supplied, also runs
`python backend/semantic/deepseek_vl2/smoke_test.py --image <path>
--out-dir /tmp/vlm_smoke` and prints the result.

### 5.8 CLI flags

- `--manager {conda,venv}` (default `conda`).
- `--env-name NAME` (default `pdf2md-deepseek-vl2`).
- `--python VER` (default `3.11`).
- `--skip-env-create`, `--skip-checks`, `--skip-verify`.
- `--clone-repo`, `--workdir PATH` (default `~/models/deepseek-vl2`).
- `--smoke-image PATH` (optional verify step).
- `--check-only` (run §5.2 and exit 0).
- `--max-jobs N` (parallelism for any source build).

## 6. `environment.yml`

```yaml
name: pdf2md-deepseek-vl2
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - pip
```

That's it — `setup.py` does the heavy lifting (pip-installs torch
with the right CUDA index URL, then the rest). This matches
`backend/deepseek/environment.yml` (also minimal).

## 7. `requirements.txt`

```text
# DeepSeek-VL2 working set — pinned to the upstream-tested combination.
# torch / torchvision / transformers come from setup.py via index URLs
# and the constraints file. This file lists only "leaf" deps.
accelerate>=0.27,<0.30
sentencepiece
einops
timm>=0.9.16
xformers>=0.0.21,<0.0.22
attrdict
pillow>=10.0
```

## 8. `setup_env.py` (thin wrapper)

Identical shape to
[backend/deepseek/setup_env.py](../backend/deepseek/setup_env.py):

```python
#!/usr/bin/env python3
"""Setup pdf2md-deepseek-vl2 environment (thin wrapper around environment.yml)."""
import argparse, subprocess, sys
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manager', choices=['conda', 'venv'], default='conda')
    p.add_argument('--env-name')
    p.add_argument('--python', default='3.11')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    yml  = here / 'environment.yml'
    env  = args.env_name or 'pdf2md-' + here.name.replace('_', '-')
    if args.manager == 'conda':
        cmd = ['conda', 'env', 'create', '-n', env, '-f', str(yml)]
    else:
        v = Path(env)
        subprocess.check_call([sys.executable, '-m', 'venv', str(v)])
        cmd = None
    if cmd:
        subprocess.check_call(cmd)

if __name__ == '__main__':
    raise SystemExit(main())
```

## 9. `delete_env.py`

Copy `backend/deepseek/delete_env.py` and swap the constant
`ENV_NAME = "pdf2md-deepseek"` → `"pdf2md-deepseek-vl2"`. Same
external behaviour.

## 10. README rewrite

Short, points at `setup.py`. Drops the long manual install table
that the current README has. Drops the "Status: install broken"
banner I added in PR #119 — after this plan, the install works.

## 11. Acceptance criteria

- [ ] `python backend/semantic/deepseek_vl2/setup.py --check-only`
      exits 0 on a Linux host with an RTX A6000.
- [ ] `python backend/semantic/deepseek_vl2/setup.py` end-to-end:
      (a) creates `pdf2md-deepseek-vl2` conda env;
      (b) installs `torch==2.0.1` cu118 wheels;
      (c) installs `requirements.txt` against the constraints file;
      (d) installs `deepseek-vl2 @ git+…` with `--no-deps`;
      (e) verify-step imports `DeepseekVLV2ForCausalLM` cleanly.
- [ ] `conda run -n pdf2md-deepseek-vl2 python
      backend/semantic/deepseek_vl2/smoke_test.py
      --image /tmp/sample_page.png --out-dir /tmp/vlm_smoke` exits 0
      with `markers ≥ 1`.
- [ ] `python backend/semantic/deepseek_vl2/delete_env.py` cleanly
      removes the env.
- [ ] `pytest tests/test_semantic_*.py -q` still green: 20 passed.

## 12. Risk and fallback

The pinned `torch==2.0.1 cu118` set is old. On hosts with CUDA driver
13.x (which this dev host has — `nvidia-smi` reports `CUDA Version:
13.0`), the cu118 wheels should still work — CUDA is forward-
compatible at the driver layer. If a future driver breaks them, the
fallback is to upgrade to `torch==2.4 cu121` plus matching
`xformers==0.0.26` and `transformers==4.45` — this combination has
been reported to work with `deepseek-vl2` by other downstream users
(unverified by this project).

## 13. Out of scope

- GROBID rework. (See Plan 005_2.)
- Replacing DeepSeek-VL2 with another VLM. (If Path A in this plan
  proves too brittle long-term, a follow-up plan would replace the
  model — Qwen2-VL-7B-Instruct is the leading candidate. **Not
  attempted in this plan.**)
- Changing the `SemanticBackend` ABC — `vlm_adapter.py` runs the
  smoke_test subprocess pattern, which is portable across model
  choices.

## 14. Promotion

Promote to `current_plan.md` only after the human reviewer signs off
on this revised design.
