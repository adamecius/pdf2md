# PaddleOCR wrapper (stable public path)

Activate environment:
```bash
conda activate pdf2md-paddleocr
```

Run from repo root:
```bash
python backend/paddleocr/pdf2md_paddleocr.py -i backend/paddleocr/test_visual.pdf
```

Run from backend folder:
```bash
python pdf2md_paddleocr.py -i test_visual.pdf
```

This wrapper delegates to PaddleOCR 3.x CLI:
```bash
paddleocr ocr -i <pdf> --save_path <out_dir>
```

The wrapper then extracts text from generated JSON files and writes Markdown.

Device mapping:
- `auto` -> PaddleOCR default (no explicit flag)
- `cpu` -> `--device cpu`
- `cuda` -> `--device gpu:0`

Notes:
- API mode is not implemented.
- `--allow-download` is not implemented.
- Exploratory scripts are archived under `legacy/initial_tests/`.
