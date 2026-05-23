"""Dataset manifest generation (Additional Plan 1, Task A3).

For each downloaded dataset, this module writes:

- ``groundtruth/external/<dataset>/dataset.json`` — dataset-level metadata.
- ``groundtruth/external/<dataset>/manifest.jsonl`` — one JSON line per
  discovered root file.
- ``groundtruth/manifest/external_datasets.json`` — global index of every
  dataset the user has touched.

Manifest generation is deterministic: outputs are sorted by id and
relative path so re-running on the same input produces byte-identical
files. No compilation is performed here — Plan 18 owns compile state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pdf2md.datasets.registry import DatasetEntry, get_dataset

MANIFEST_SCHEMA_VERSION = 1
DATASET_SCHEMA_NAME = "pdf2md.ExternalDatasetMeta"
MANIFEST_ENTRY_SCHEMA_NAME = "pdf2md.ExternalDatasetManifestEntry"
INDEX_SCHEMA_NAME = "pdf2md.ExternalDatasetIndex"

NOT_RUN = "not_run"

INSTALLED = "installed"
MISSING = "missing"
MANIFEST_ONLY = "manifest_only"


@dataclass(frozen=True)
class ManifestEntry:
    """One root file inside an installed dataset."""

    id: str
    dataset: str
    root_file: str
    source_type: str
    has_media: bool
    compile_status: str
    features: list[str]
    recommended_engine: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sanitize_id_component(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return out or "root"


def _discover_root_files(upstream: Path, entry: DatasetEntry) -> list[Path]:
    """Find root files relative to ``upstream`` using the dataset's rules."""

    if entry.root_files:
        out: list[Path] = []
        for rel in entry.root_files:
            candidate = upstream / rel
            if candidate.is_file():
                out.append(candidate)
        return sorted(out)

    hits: set[Path] = set()
    for pattern in entry.root_globs:
        for match in upstream.glob(pattern):
            if match.is_file():
                hits.add(match)
    return sorted(hits)


def _detect_media(root_file: Path, upstream: Path) -> bool:
    """Return True if the root file's directory has any image/media asset."""

    parent = root_file.parent
    media_exts = {".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".tiff"}
    for sibling in parent.iterdir():
        if sibling.is_file() and sibling.suffix.lower() in media_exts and sibling != root_file:
            return True
    return False


def _features_for(root_file: Path) -> list[str]:
    """Cheap heuristic feature tagging based on the .tex source."""

    try:
        text = root_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    features: list[str] = []
    if "\\addbibresource" in text or "\\bibliography{" in text:
        features.append("bibliography")
    if "\\begin{figure" in text or "\\includegraphics" in text:
        features.append("figures")
    if "\\begin{tabular" in text or "\\begin{table" in text:
        features.append("tables")
    if "\\begin{equation" in text or "\\[" in text or "$$" in text:
        features.append("equations")
    if "\\footnote" in text:
        features.append("footnotes")
    if "\\section" in text or "\\chapter" in text:
        features.append("structured_headings")
    return sorted(set(features))


def _manifest_entry_id(dataset_id: str, root_file: Path, upstream: Path) -> str:
    rel = root_file.relative_to(upstream).with_suffix("")
    pieces = [_sanitize_id_component(p) for p in rel.parts]
    return "-".join([dataset_id, *pieces])


def generate_dataset_manifest(
    *,
    dataset_dir: Path,
    name_or_alias: str | None = None,
    source_url: str | None = None,
    ref: str | None = None,
    resolved_commit: str | None = None,
) -> dict[str, Any]:
    """Write ``dataset.json`` and ``manifest.jsonl`` for one installed dataset.

    Returns the dataset-level metadata dict that was written, so callers
    can chain into :func:`update_global_index` without re-reading from
    disk.
    """

    dataset_dir = Path(dataset_dir)
    upstream = dataset_dir / "upstream"
    if not upstream.is_dir():
        raise FileNotFoundError(
            f"Cannot generate manifest: {upstream} is missing or not a directory."
        )

    entry = get_dataset(name_or_alias or dataset_dir.name)
    root_files = _discover_root_files(upstream, entry)

    dataset_meta: dict[str, Any] = {
        "schema_name": DATASET_SCHEMA_NAME,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "id": entry.id,
        "source_url": source_url if source_url is not None else entry.url,
        "ref": ref if ref is not None else entry.default_ref,
        "resolved_commit": resolved_commit,
        "licence": entry.licence,
        "installed_at": _utc_now(),
        "upstream_path": str(upstream),
        "root_file_count": len(root_files),
        "compile_status": NOT_RUN,
    }
    dataset_json = dataset_dir / "dataset.json"
    dataset_json.write_text(json.dumps(dataset_meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_jsonl = dataset_dir / "manifest.jsonl"
    with manifest_jsonl.open("w", encoding="utf-8") as fh:
        for root_file in root_files:
            entry_id = _manifest_entry_id(entry.id, root_file, upstream)
            payload: dict[str, Any] = {
                "schema_name": MANIFEST_ENTRY_SCHEMA_NAME,
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "id": entry_id,
                "dataset": entry.id,
                "root_file": str(root_file.relative_to(dataset_dir).as_posix()),
                "source_type": entry.source_type,
                "has_media": _detect_media(root_file, upstream),
                "compile_status": NOT_RUN,
                "features": _features_for(root_file),
            }
            if entry.recommended_engine:
                payload["recommended_engine"] = entry.recommended_engine
            fh.write(json.dumps(payload, sort_keys=True) + "\n")

    return dataset_meta


def update_global_index(
    *,
    index_path: Path,
    dataset_meta: dict[str, Any] | None = None,
    external_root: Path | None = None,
) -> dict[str, Any]:
    """Refresh ``groundtruth/manifest/external_datasets.json``.

    The index lists every dataset directory under ``external_root`` plus
    any previously recorded entries — entries whose dataset directory no
    longer exists are reported with ``status = "missing"``. When called
    with ``dataset_meta`` from a fresh install, that dataset is upserted
    as ``status = "installed"``.
    """

    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if index_path.is_file():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    datasets: dict[str, dict[str, Any]] = {}
    for old in existing.get("datasets", []):
        if isinstance(old, dict) and isinstance(old.get("id"), str):
            datasets[old["id"]] = old

    if external_root is not None:
        external_root = Path(external_root)
        if external_root.is_dir():
            for child in external_root.iterdir():
                if not child.is_dir():
                    continue
                upstream = child / "upstream"
                dj = child / "dataset.json"
                if dj.is_file():
                    try:
                        meta = json.loads(dj.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        meta = None
                    if isinstance(meta, dict):
                        datasets[child.name] = {
                            "id": meta.get("id", child.name),
                            "path": str(child),
                            "source_url": meta.get("source_url"),
                            "ref": meta.get("ref"),
                            "resolved_commit": meta.get("resolved_commit"),
                            "status": INSTALLED if upstream.is_dir() else MANIFEST_ONLY,
                            "compile_status": meta.get("compile_status", NOT_RUN),
                        }

    if dataset_meta is not None:
        ds_id = dataset_meta.get("id")
        if isinstance(ds_id, str):
            datasets[ds_id] = {
                "id": ds_id,
                "path": str(Path(dataset_meta.get("upstream_path", "")).parent or ""),
                "source_url": dataset_meta.get("source_url"),
                "ref": dataset_meta.get("ref"),
                "resolved_commit": dataset_meta.get("resolved_commit"),
                "status": INSTALLED,
                "compile_status": dataset_meta.get("compile_status", NOT_RUN),
            }

    # Mark anything whose directory no longer exists.
    for ds_id, payload in list(datasets.items()):
        path = payload.get("path")
        if path and not Path(path).exists():
            payload["status"] = MISSING
            datasets[ds_id] = payload

    out = {
        "schema_name": INDEX_SCHEMA_NAME,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "datasets": [datasets[i] for i in sorted(datasets)],
    }
    index_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "NOT_RUN",
    "INSTALLED",
    "MISSING",
    "MANIFEST_ONLY",
    "ManifestEntry",
    "generate_dataset_manifest",
    "update_global_index",
]
