## pdf2md wrapper entrypoint (added)

After activating the DeepSeek backend environment:

```bash
python backend/deepseek/pdf2md_deepseek.py -i test.pdf
```

Default output: `test.md` in the current directory (or next to the input when run from elsewhere).

### Local-first behavior
- Local model is required by default.
- Provide it with `--model-path /path/to/model` or `PDF2MD_DEEPSEEK_MODEL=/path/to/model`.
- No silent download is performed.
- API mode is not automatically enabled.

---

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
