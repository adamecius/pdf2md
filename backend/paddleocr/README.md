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

## Upstream package / project links

- PaddleOCR docs: https://www.paddleocr.ai/
- PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR

## License notes

- This wrapper is covered by this repository's license.
- PaddleOCR is an upstream project with its own license (Apache-2.0 in upstream repo at time of writing).
- Dependencies installed for this backend may use mixed open-source licenses; verify before redistribution.
