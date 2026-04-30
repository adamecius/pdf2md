# DeepSeek-OCR-2 environment setup

This README defines a reproducible setup for **DeepSeek-OCR-2** on a CUDA 11.8 GPU machine using Torch 2.6.0.

The recommended setup is:

```text
Conda environment + NVIDIA CUDA 11.8 toolkit inside Conda + pip packages
```

Do not rely on the system CUDA compiler. On many servers `/usr/bin/nvcc` may point to an older CUDA version, for example CUDA 11.5. That is enough to break `flash-attn`.

## Target stack

```text
Python:          3.12.9
CUDA toolkit:    11.8
Torch:           2.6.0+cu118
torchvision:     0.21.0
torchaudio:      2.6.0
vLLM:            0.8.5+cu118
FlashAttention:  2.7.3
Model:           deepseek-ai/DeepSeek-OCR-2
```

## Why this order matters

The official DeepSeek-OCR-2 install is short, but on a real GPU workstation the order matters.

The correct pipeline is:

```text
1. Create or activate the environment.
2. Install CUDA 11.8 toolkit inside the Conda environment.
3. Export CUDA_HOME, PATH, and LD_LIBRARY_PATH to the Conda environment.
4. Clone DeepSeek-OCR-2.
5. Install PyTorch CUDA 11.8 wheels.
6. Download and install the vLLM 0.8.5 CUDA 11.8 wheel.
7. Install DeepSeek-OCR-2 requirements with a NumPy constraint.
8. Install flash-attn.
9. Verify CUDA, Torch, NumPy, Transformers, vLLM, and FlashAttention.
```

The critical point is that `flash-attn` builds native CUDA code. The PyTorch wheel includes CUDA runtime libraries, but it does not provide the CUDA compiler that FlashAttention needs.

Therefore, in Conda mode, this setup installs:

```bash
conda install -y -c nvidia/label/cuda-11.8.0 cuda-toolkit
```

Then it forces:

```bash
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
```

This makes `nvcc -V` resolve to the Conda CUDA 11.8 compiler instead of the system compiler.

## Why NumPy is pinned

The official `requirements.txt` leaves NumPy unpinned:

```text
numpy
```

On recent systems, pip may install a too-new NumPy version, for example `numpy 2.4.4`. That can conflict with packages pulled by vLLM, such as `numba` and `mistral-common`.

This setup pins:

```text
numpy==2.2.6
```

That version satisfies the important constraints:

```text
numba requires numpy < 2.3
mistral-common requires numpy < 2.4
```

So the effective OCR-2 requirements used here are:

```text
transformers==4.46.3
tokenizers==0.20.3
PyMuPDF
img2pdf
einops
easydict
addict
Pillow
numpy==2.2.6
```

## Expected vLLM conflict

You may still see:

```text
vllm 0.8.5+cu118 requires tokenizers>=0.21.1
vllm 0.8.5+cu118 requires transformers>=4.51.1
```

For the official one-environment DeepSeek-OCR-2 setup, this is expected.

The OCR-2 repository pins:

```text
transformers==4.46.3
tokenizers==0.20.3
```

The official README says this vLLM versus Transformers conflict can be ignored when vLLM and Transformers code are run in the same environment.

Do not ignore these problems:

```text
nvcc is CUDA 11.5
CUDA_HOME points to /usr
numpy is 2.4.4
torch.cuda.is_available() is False
flash-attn import fails
```

## Files

Use the installer:

```text
setup_deepseek_ocr2.sh
```

By default it creates a Conda environment named:

```text
deepseek-ocr2
```

You can override the environment name with:

```bash
--envname my-env-name
```

You can choose the environment flavour with:

```bash
--envflavor conda
--envflavor venv
```

Default:

```bash
--envflavor conda
```

The recommended and tested path is Conda.

## Install with Conda, recommended

```bash
chmod +x setup_deepseek_ocr2.sh

./setup_deepseek_ocr2.sh \
  --envname deepseek-ocr2 \
  --envflavor conda
```

The script will:

```text
1. Create the Conda environment.
2. Install the NVIDIA CUDA 11.8 toolkit into the environment.
3. Configure CUDA_HOME to point to the Conda environment.
4. Clone https://github.com/deepseek-ai/DeepSeek-OCR-2.git.
5. Download the vLLM 0.8.5 CUDA 11.8 wheel.
6. Install Torch 2.6.0 CUDA 11.8.
7. Install vLLM.
8. Install OCR-2 requirements with NumPy pinned to 2.2.6.
9. Build and install flash-attn 2.7.3.
10. Run verification checks.
```

## Install with a custom environment name

```bash
./setup_deepseek_ocr2.sh \
  --envname ocr2-prod \
  --envflavor conda
```

Then activate it later with:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate ocr2-prod
```

## Install into a Python venv

This is supported, but not recommended for your server unless the host already has a valid CUDA toolkit.

```bash
./setup_deepseek_ocr2.sh \
  --envname .venv-deepseek-ocr2 \
  --envflavor venv
```

The venv route requires one of the following:

```text
CUDA_HOME points to a valid CUDA 11.8 toolkit
or
/usr/local/cuda-11.8 exists
or
nvcc on PATH is already CUDA 11.8 or newer
```

If your system only has `/usr/bin/nvcc` from CUDA 11.5, use Conda mode.

## Manual Conda installation

The installer is preferred, but the manual sequence is:

```bash
source ~/miniconda3/etc/profile.d/conda.sh

conda create -n deepseek-ocr2 python=3.12.9 pip -y
conda activate deepseek-ocr2

conda install -y -c nvidia/label/cuda-11.8.0 cuda-toolkit

export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

which nvcc
nvcc -V
```

You should see CUDA 11.8 from inside the Conda environment.

Then:

```bash
mkdir -p ~/models/deepseek-ocr2
cd ~/models/deepseek-ocr2

git clone https://github.com/deepseek-ai/DeepSeek-OCR-2.git
cd DeepSeek-OCR-2

python -m pip install --upgrade pip setuptools wheel packaging ninja

python -m pip install \
  torch==2.6.0 \
  torchvision==0.21.0 \
  torchaudio==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu118
```

Download the vLLM wheel:

```bash
curl -fL \
  -o vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl \
  "https://github.com/vllm-project/vllm/releases/download/v0.8.5/vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl"
```

Install it:

```bash
python -m pip install ./vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl
```

Install OCR-2 requirements with a NumPy constraint:

```bash
cat > /tmp/deepseek-ocr2-constraints.txt <<'EOF'
numpy==2.2.6
EOF

python -m pip install -r requirements.txt -c /tmp/deepseek-ocr2-constraints.txt
python -m pip install numpy==2.2.6
```

Install FlashAttention:

```bash
MAX_JOBS=4 python -m pip install flash-attn==2.7.3 --no-build-isolation --no-cache-dir
```

If the machine runs out of memory during compilation:

```bash
MAX_JOBS=2 python -m pip install flash-attn==2.7.3 --no-build-isolation --no-cache-dir
```

## Make CUDA 11.8 persistent in the Conda environment

The installer does this automatically. Manually:

```bash
mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"

cat > "$CONDA_PREFIX/etc/conda/activate.d/cuda-11.8.sh" <<'EOF'
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
EOF
```

Then test:

```bash
conda deactivate
conda activate deepseek-ocr2

which nvcc
nvcc -V
```

Expected:

```text
Cuda compilation tools, release 11.8
```

## Verify the environment

Run:

```bash
python - <<'PY'
import os
import torch
import numpy
import transformers
import tokenizers

print("CUDA_HOME:", os.environ.get("CUDA_HOME"))
print("torch:", torch.__version__)
print("torch cuda:", torch.version.cuda)
print("cuda available:", torch.cuda.is_available())
print("numpy:", numpy.__version__)
print("transformers:", transformers.__version__)
print("tokenizers:", tokenizers.__version__)

try:
    import vllm
    print("vllm:", vllm.__version__)
except Exception as e:
    print("vllm import failed:", repr(e))

try:
    import flash_attn
    print("flash-attn:", flash_attn.__version__)
except Exception as e:
    print("flash-attn import failed:", repr(e))
PY
```

Expected core values:

```text
torch: 2.6.0+cu118
torch cuda: 11.8
cuda available: True
numpy: 2.2.6
transformers: 4.46.3
tokenizers: 0.20.3
flash-attn: 2.7.3
```

`pip check` may still report the vLLM conflict with Transformers and Tokenizers. That is expected for the official shared environment.

## vLLM inference

Edit the config first:

```text
DeepSeek-OCR2-master/DeepSeek-OCR2-vllm/config.py
```

Set:

```text
INPUT_PATH
OUTPUT_PATH
```

Then run image OCR:

```bash
cd ~/models/deepseek-ocr2/DeepSeek-OCR-2/DeepSeek-OCR2-master/DeepSeek-OCR2-vllm
python run_dpsk_ocr2_image.py
```

Run PDF OCR:

```bash
cd ~/models/deepseek-ocr2/DeepSeek-OCR-2/DeepSeek-OCR2-master/DeepSeek-OCR2-vllm
python run_dpsk_ocr2_pdf.py
```

Run benchmark batch evaluation:

```bash
cd ~/models/deepseek-ocr2/DeepSeek-OCR-2/DeepSeek-OCR2-master/DeepSeek-OCR2-vllm
python run_dpsk_ocr2_eval_batch.py
```

## Transformers inference

Repository script:

```bash
cd ~/models/deepseek-ocr2/DeepSeek-OCR-2/DeepSeek-OCR2-master/DeepSeek-OCR2-hf
python run_dpsk_ocr2.py
```

Minimal direct example:

```python
from transformers import AutoModel, AutoTokenizer
import torch
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

model_name = "deepseek-ai/DeepSeek-OCR-2"

tokenizer = AutoTokenizer.from_pretrained(
    model_name,
    trust_remote_code=True
)

model = AutoModel.from_pretrained(
    model_name,
    _attn_implementation="flash_attention_2",
    trust_remote_code=True,
    use_safetensors=True
)

model = model.eval().cuda().to(torch.bfloat16)

prompt = "<image>\\n<|grounding|>Convert the document to markdown. "
image_file = "your_image.jpg"
output_path = "your/output/dir"

res = model.infer(
    tokenizer,
    prompt=prompt,
    image_file=image_file,
    output_path=output_path,
    base_size=1024,
    image_size=768,
    crop_mode=True,
    save_results=True,
)

print(res)
```

## Main prompts

Document to Markdown:

```text
<image>
<|grounding|>Convert the document to markdown.
```

Free OCR:

```text
<image>
Free OCR.
```

## Troubleshooting

### Conda says `Run 'conda init' before 'conda activate'`

For the current shell, use:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate deepseek-ocr2
```

You can run `conda init` later if you want future shells to activate Conda automatically.

### FlashAttention says CUDA must be 11.7 or above

Check:

```bash
which nvcc
nvcc -V
echo "$CUDA_HOME"
```

If you see:

```text
/usr/bin/nvcc
Cuda compilation tools, release 11.5
CUDA_HOME unset
```

then FlashAttention is using the wrong compiler.

Fix in Conda mode:

```bash
conda activate deepseek-ocr2
conda install -y -c nvidia/label/cuda-11.8.0 cuda-toolkit

export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

which nvcc
nvcc -V
```

Then reinstall:

```bash
MAX_JOBS=4 python -m pip install flash-attn==2.7.3 --no-build-isolation --no-cache-dir
```

### NumPy conflict after requirements install

Fix:

```bash
python -m pip install numpy==2.2.6
```

Then verify:

```bash
python - <<'PY'
import numpy
print(numpy.__version__)
PY
```

### vLLM Transformers conflict

This one can be ignored in the official shared DeepSeek-OCR-2 environment:

```text
vllm 0.8.5+cu118 requires tokenizers>=0.21.1
vllm 0.8.5+cu118 requires transformers>=4.51.1
```

Do not try to fix this by upgrading Transformers unless you intentionally want to diverge from the OCR-2 repository requirements.

### CUDA is not available in Torch

Check:

```bash
nvidia-smi
python - <<'PY'
import torch
print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
PY
```

If `nvidia-smi` fails, fix the host NVIDIA driver first.
