# Legacy Modules

These modules are superseded by the current staged pipeline:

| Legacy module          | Replaced by                        |
|------------------------|------------------------------------|
| consensus_report.py    | consensus/factory.py + consensus/reporting.py |
| semantic_linker.py     | linking/builder.py + linking/extract.py |
| media_materializer.py  | export/io.py                       |
| semantic_document_builder.py | export/docling.py             |
| docling_adapter.py     | export/docling.py + export/io.py   |
| adapters_base.py       | connectors/common.py               |
| backends_base.py       | backends/runner.py                 |
| renderers_markdown.py  | export/markdown.py                 |
| models_document.py     | models/ir.py (PageExtractionIR, ConsensusIR) |
| pipeline_convert.py    | pipeline/orchestrator.py (Plan 18) |

These modules and their tests will be removed after all dependent
tests are migrated.
