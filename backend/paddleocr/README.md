> Legacy setup snapshots are preserved under `backend/paddleocr/legacy/` (previous requirements/environment/setup helper).

# pdf2md PaddleOCR backend
Run: `python backend/paddleocr/pdf2md_paddleocr.py -i test.pdf` -> `test.md`.
Wrapper rasterises PDF pages then OCRs images locally using PaddleOCR.
No API mode implemented.
