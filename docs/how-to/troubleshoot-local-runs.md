# How to troubleshoot local pipeline runs

Common error signatures and the fix for each. If your symptom isn't
listed, file an issue with the full error and the
`pipeline_manifest.json` from the failing run.

## Toolchain

| Symptom | Likely cause | Fix |
|---|---|---|
| `lualatex: not found` or `LuaTeX 1.17.0 or newer is required` despite a working TeX Live install | Old `/usr/bin/lualatex` ahead on PATH | The compile tool discovers the newest TeX Live automatically; pass `--texlive-bin-dir /usr/local/texlive/<year>/bin/<arch>` if discovery still misses it. |

## paddleocr

| Symptom | Likely cause | Fix |
|---|---|---|
| `libcudnn.so.8: cannot open shared object` from paddleocr | Wrong cuDNN version | `pip install "nvidia-cudnn-cu11>=8.9,<9.0"` and set `LD_LIBRARY_PATH` per [`backend/paddleocr/README.md`](../../backend/paddleocr/README.md). |
| `error: (Unimplemented) ConvertPirAttribute2RuntimeAttribute` | paddle 3.1+ PIR/oneDNN bug | Downgrade to `paddlepaddle-gpu==3.0.0`. |
| Paddleocr produces output then `stdout.log` not found | Backend script `rmtree`s its `--out-dir` | Already fixed; ensure `extra_args = ["--keep-output"]` is set in `pdf2md.backends.toml` under `[backends.paddleocr]`. |

## Docling export validation

| Symptom | Likely cause | Fix |
|---|---|---|
| `docling_core` validation errors on `origin.binary_hash` / `origin.filename` | Pre-Plan-17 export | Pull `main` with PR #101 merged; rerun. |
| `docling_core` validation errors on `pictures[*].metadata`, `tables[*].text`, `prov.charspan`, `bbox.coord_origin` | Plan 17-A8 follow-up still open | Marked xfail in the test suite; not blocking the rest of the pipeline. |

## Reference paths

When debugging, the per-stage tools are individually invokable for
isolating which stage failed:

- **MVP runner** — `tools/run_mvp_pipeline.py`
- **Backend smoke (Plan 9)** — `tools/backend_smoke.py`
- **Connector PageExtractionIR validation (Plan 10)** —
  `tools/validate_connectors_page_ir.py`
- **Entity validation (Plan 11)** — `tools/validate_entity_proposals.py`
- **Vocabulary alignment (Plan 12 hard gate)** —
  `tools/vocabulary_alignment_check.py`
- **Calibration priors (Plan 12)** — `tools/calibrate_priors.py`
- **Weighted consensus (Plan 13)** — `tools/build_consensus.py`
- **LinkedStructure (Plan 14)** — `tools/build_linked_structure.py`
- **Docling export (Plan 15)** — `tools/export_linked_docling.py`
- **LaTeX corpus compile** — `tools/compile_latex_groundth.py`

For the milestone log of completed stages and what each plan
delivered, see [`../../history.md`](../../history.md).
