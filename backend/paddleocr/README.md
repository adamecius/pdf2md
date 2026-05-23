# PaddleOCR backend (local build)

This folder contains a **local build wrapper** for the PaddleOCR backend in the `pdf2md` project.

## Scripts in this backend

- `setup_env.py` → creates the backend environment (default: `pdf2md-paddleocr`).
- `setup.py` → if present in your local branch, use it as installer/orchestrator (checks env existence and installs requirements).
- `delete_env.py` → if present in your local branch, use it to remove the backend environment.
- `pdf2md_paddleocr.py` → standardized PDF→Markdown OCR interface (already tested; do not modify).

## Recommended workflow

From this folder (`backend/paddleocr`):

1. **Set up environment first**
   ```bash
   python setup_env.py --manager conda --env-name pdf2md-paddleocr
   ```

2. **Run conversion**
   ```bash
   python pdf2md_paddleocr.py -i /path/to/file.pdf
   ```

3. **Delete environment (if you have `delete_env.py`)**
   ```bash
   python delete_env.py
   ```

## GPU vs CPU runtime

PP-StructureV3 (the default pipeline) is roughly **17× faster on GPU** than
on CPU for OCR-bound workloads. Indicative wall clock on a 27-page input PDF:

- CPU (paddlepaddle 3.0.0):                     ~10 minutes
- GPU (paddlepaddle-gpu 3.0.0 cu118, RTX A6000): ~35 seconds

If you have CUDA available, install the GPU build:

```bash
# Replace the CPU paddlepaddle with the matching GPU build.
conda run -n pdf2md-paddleocr pip uninstall -y paddlepaddle
conda run -n pdf2md-paddleocr pip install --no-deps paddlepaddle-gpu==3.0.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# paddle 3.0.0 cu118 needs cuDNN 8 and cuBLAS 11 (not bundled with the wheel).
conda run -n pdf2md-paddleocr pip install \
    "nvidia-cudnn-cu11>=8.9,<9.0" \
    "nvidia-cublas-cu11" \
    "nvidia-cuda-nvrtc-cu11"

# Restore the small CPU deps that --no-deps stripped above.
conda run -n pdf2md-paddleocr pip install decorator astor
```

When invoking the backend, set `device = "gpu:0"` (or `auto`) and point
`LD_LIBRARY_PATH` at the cuDNN / cuBLAS / nvrtc directories from the
nvidia wheels above — see the commented `[backends.paddleocr.env]` block
in `pdf2md.backends.example.toml`.

**Version pinning note.** Paddle 3.1+ ships cuDNN 9 but introduces an
oneDNN PIR-to-runtime conversion bug for
`pir::ArrayAttribute<pir::DoubleAttribute>` that crashes both PPStructureV3
and PP-OCRv5. Paddle **3.0.0** is the preferred local build until upstream
fixes the issue.

## Upstream package / project links

- PaddleOCR docs: https://www.paddleocr.ai/
- PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR

## License notes

- This wrapper is covered by this repository's license.
- PaddleOCR is an upstream project with its own license (Apache-2.0 in upstream repo at time of writing).
- Dependencies installed for this backend may use mixed open-source licenses; verify before redistribution.
