# MinerU backend (local build)

This folder contains a **local build wrapper** for the MinerU OCR backend in the `pdf2md` project.

## Scripts in this backend

- `setup_env.py` → creates the backend environment (default: `pdf2md-mineru`).
- `delete_env.py` → removes the backend environment created for this backend.
- `setup.py` → installer/orchestrator; checks environment existence, provides hints, and installs required packages.
- `pdf2md_mineru.py` → standardized PDF→Markdown OCR interface (already tested; do not modify).

## Recommended workflow

From this folder (`backend/mineru`):

1. **Set up/install first**
   ```bash
   python setup.py
   ```
   or create only the environment:
   ```bash
   python setup_env.py --manager conda --env-name pdf2md-mineru
   ```

2. **Run conversion**
   ```bash
   python pdf2md_mineru.py -i /path/to/file.pdf
   ```

3. **Delete the environment (when needed)**
   ```bash
   python delete_env.py
   ```

## Upstream package / project links

- MinerU docs: https://opendatalab.github.io/MinerU/
- MinerU package/project: https://github.com/opendatalab/MinerU

## License notes

- This backend wrapper follows this repository's license.
- MinerU itself is distributed under its own upstream license terms.
- Installed dependencies (CUDA/PyTorch ecosystem, OCR libs) are third-party components with their own licenses.
