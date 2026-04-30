# pdf2md GLM backend
Run: `python backend/glm/pdf2md_glm.py -i test.pdf --api`.

This wrapper is **API-only** (not local-first):
- Requires explicit `--api`
- Requires `ZHIPU_API_KEY` (preferred) or `GLM_API_KEY` (alias)
- Does not silently switch from local execution to API mode
