# GLM backend (local build wrapper)

This folder contains a **local build wrapper** for the GLM backend in the `pdf2md` project.

## Scripts in this backend

- `setup_env.py` → creates the backend environment (default: `pdf2md-glm`).
- `setup.py` → if present in your local branch, use it as installer/orchestrator (checks env existence and installs requirements).
- `delete_env.py` → if present in your local branch, use it to remove the backend environment.
- `pdf2md_glm.py` → standardized PDF→Markdown OCR/API interface (already tested; do not modify).

## Recommended workflow

From this folder (`backend/glm`):

1. **Set up environment first**
   ```bash
   python setup_env.py --manager conda --env-name pdf2md-glm
   ```

2. **Run conversion/API flow**
   ```bash
   python pdf2md_glm.py -i /path/to/file.pdf --api
   ```

3. **Delete environment (if you have `delete_env.py`)**
   ```bash
   python delete_env.py
   ```

## Upstream package / project links

- GLM / Zhipu AI platform: https://open.bigmodel.cn/
- API references (platform docs): https://open.bigmodel.cn/dev/howuse/glm-4

## License notes

- This wrapper code is licensed under this repository's license.
- GLM platform usage is governed by Zhipu AI terms and API policies.
- Any Python dependencies installed in the environment keep their own open-source licenses.
