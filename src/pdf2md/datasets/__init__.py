"""External ground-truth dataset downloaders (Additional Plan 1).

Public surface:

- :func:`pdf2md.datasets.registry.get_dataset`
- :func:`pdf2md.datasets.registry.list_datasets`
- :func:`pdf2md.datasets.downloader.download_dataset`
- :func:`pdf2md.datasets.manifest.generate_dataset_manifest`
- :func:`pdf2md.datasets.manifest.update_global_index`
"""

from __future__ import annotations

from pdf2md.datasets.registry import (
    DatasetEntry,
    DatasetStatus,
    get_dataset,
    list_datasets,
    resolve_alias,
)

__all__ = [
    "DatasetEntry",
    "DatasetStatus",
    "get_dataset",
    "list_datasets",
    "resolve_alias",
]
