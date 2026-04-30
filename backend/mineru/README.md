# MinerU wrapper (stable public path)

Activate environment:
```bash
conda activate pdf2md-mineru
```

Run from repo root:
```bash
python backend/mineru/pdf2md_mineru.py -i backend/mineru/test_visual.pdf
```

Run from backend folder:
```bash
python pdf2md_mineru.py -i test_visual.pdf
```

This wrapper delegates to the official MinerU CLI:
```bash
mineru -p <input.pdf> -o <output_dir>
```

Notes:
- Local-first by default.
- `--api-url` is explicit; `--api` without `--api-url` fails.
- `--allow-download` is not implemented for this wrapper.
- Exploratory scripts are archived under `legacy/initial_tests/`.
