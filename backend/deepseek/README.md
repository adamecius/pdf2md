# DeepSeek backend (local build)

This folder contains a **local build wrapper** for the DeepSeek OCR backend in the `pdf2md` project.

## Scripts in this backend

- `setup_env.py` → creates the backend environment (default: `pdf2md-deepseek`).
- `delete_env.py` → removes the backend environment created for this backend.
- `setup.py` → installer/orchestrator; checks whether the environment already exists, prints hints when it does, and installs required dependencies.
- `pdf2md_deepseek.py` → standardized PDF→Markdown OCR interface (already tested; do not modify).

## Recommended workflow

From this folder (`backend/deepseek`):

1. **Set up/install first**
   ```bash
   python setup.py
   ```
   or create only the environment:
   ```bash
   python setup_env.py --manager conda --env-name pdf2md-deepseek
   ```

2. **Run conversion**
   ```bash
   python pdf2md_deepseek.py -i /path/to/file.pdf
   ```

3. **Delete the environment (when needed)**
   ```bash
   python delete_env.py
   ```

## Upstream package / project links

- DeepSeek OCR project: https://github.com/deepseek-ai/DeepSeek-OCR-2
- DeepSeek organization: https://github.com/deepseek-ai

## License notes

- This backend wrapper is part of this repository and follows this repository's licensing terms.
- The upstream DeepSeek OCR project has its own license and terms; review them directly in the upstream repository before distribution/commercial use.
- Transitive dependencies installed by `setup.py`/`setup_env.py` (PyTorch, CUDA wheels, etc.) each have their own licenses.
