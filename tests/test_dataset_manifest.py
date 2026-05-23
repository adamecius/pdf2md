"""Tests for dataset manifest generation (Additional Plan 1, Task A3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.datasets.manifest import (
    INSTALLED,
    MANIFEST_ONLY,
    MISSING,
    NOT_RUN,
    generate_dataset_manifest,
    update_global_index,
)


def _build_synthetic_tlc3(out_dir: Path) -> Path:
    dataset_dir = out_dir / "tlc3-examples"
    upstream = dataset_dir / "upstream"
    (upstream / "NORMAL").mkdir(parents=True)
    (upstream / "NORMAL" / "1-3-1.ltx").write_text(
        "\\documentclass{article}\n\\begin{document}\\section{x}\\end{document}\n"
    )
    (upstream / "NORMAL" / "1-3-2.ltx").write_text(
        "\\documentclass{article}\\begin{document}\\begin{figure}\\caption{c}\\end{figure}\\end{document}\n"
    )
    (upstream / "SPECIAL").mkdir()
    (upstream / "SPECIAL" / "10-5-1.ltx2").write_text(
        "\\documentclass{article}\\begin{document}\\section{y}\\footnote{f}\\end{document}\n"
    )
    return dataset_dir


def _build_synthetic_cookbook(out_dir: Path) -> Path:
    dataset_dir = out_dir / "latex-cookbook"
    upstream = dataset_dir / "upstream"
    upstream.mkdir(parents=True)
    (upstream / "cookbook.tex").write_text(
        "\\documentclass{book}\\addbibresource{r.bib}\\begin{document}cookbook\\end{document}\n"
    )
    (upstream / "image.pdf").write_bytes(b"%PDF-1.4\n")
    return dataset_dir


def test_generate_dataset_manifest_for_tlc3_writes_dataset_json_and_manifest(tmp_path: Path):
    dataset_dir = _build_synthetic_tlc3(tmp_path)
    meta = generate_dataset_manifest(
        dataset_dir=dataset_dir,
        name_or_alias="tlc3-examples",
        source_url="https://example.com/tlc3.git",
        ref="main",
        resolved_commit="deadbeef" * 5,
    )

    assert meta["id"] == "tlc3-examples"
    assert meta["compile_status"] == NOT_RUN
    assert meta["root_file_count"] == 3
    assert meta["resolved_commit"].startswith("deadbeef")

    dataset_json = dataset_dir / "dataset.json"
    manifest_jsonl = dataset_dir / "manifest.jsonl"
    assert dataset_json.is_file()
    assert manifest_jsonl.is_file()

    entries = [json.loads(line) for line in manifest_jsonl.read_text().splitlines() if line.strip()]
    assert len(entries) == 3
    ids = [e["id"] for e in entries]
    # Stable, dataset-prefixed, path-derived ids.
    assert all(i.startswith("tlc3-examples-") for i in ids)
    # Sorted deterministically.
    assert ids == sorted(ids)


def test_manifest_entries_have_expected_fields_and_features(tmp_path: Path):
    dataset_dir = _build_synthetic_tlc3(tmp_path)
    generate_dataset_manifest(dataset_dir=dataset_dir, name_or_alias="tlc3-examples")
    entries = [json.loads(line) for line in (dataset_dir / "manifest.jsonl").read_text().splitlines()]
    sample = next(e for e in entries if e["root_file"].endswith("1-3-2.ltx"))
    assert sample["source_type"] == "latex"
    assert sample["dataset"] == "tlc3-examples"
    assert sample["compile_status"] == NOT_RUN
    assert "figures" in sample["features"]
    assert sample["has_media"] is False
    # The footnote one
    foot = next(e for e in entries if e["root_file"].endswith("10-5-1.ltx2"))
    assert "footnotes" in foot["features"]


def test_generate_dataset_manifest_for_cookbook_uses_root_files_and_detects_media(tmp_path: Path):
    dataset_dir = _build_synthetic_cookbook(tmp_path)
    meta = generate_dataset_manifest(
        dataset_dir=dataset_dir,
        name_or_alias="latex-cookbook",
        resolved_commit="abc123",
    )
    assert meta["root_file_count"] == 1
    entries = [json.loads(line) for line in (dataset_dir / "manifest.jsonl").read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["root_file"] == "upstream/cookbook.tex"
    assert entries[0]["has_media"] is True
    assert "bibliography" in entries[0]["features"]
    assert entries[0]["recommended_engine"] == "lualatex"


def test_manifest_generation_is_deterministic_across_runs(tmp_path: Path):
    dataset_dir = _build_synthetic_tlc3(tmp_path)
    generate_dataset_manifest(dataset_dir=dataset_dir, name_or_alias="tlc3-examples")
    first = (dataset_dir / "manifest.jsonl").read_text()
    generate_dataset_manifest(dataset_dir=dataset_dir, name_or_alias="tlc3-examples")
    second = (dataset_dir / "manifest.jsonl").read_text()
    assert first == second


def test_update_global_index_creates_and_lists_datasets(tmp_path: Path):
    external = tmp_path / "external"
    dataset_dir = _build_synthetic_cookbook(external)
    meta = generate_dataset_manifest(dataset_dir=dataset_dir, name_or_alias="latex-cookbook")

    index = tmp_path / "manifest" / "external_datasets.json"
    payload = update_global_index(
        index_path=index, dataset_meta=meta, external_root=external
    )
    assert index.is_file()
    assert payload["schema_name"] == "pdf2md.ExternalDatasetIndex"
    ids = [d["id"] for d in payload["datasets"]]
    assert ids == ["latex-cookbook"]
    assert payload["datasets"][0]["status"] == INSTALLED


def test_update_global_index_marks_missing_when_directory_disappears(tmp_path: Path):
    external = tmp_path / "external"
    dataset_dir = _build_synthetic_cookbook(external)
    meta = generate_dataset_manifest(dataset_dir=dataset_dir, name_or_alias="latex-cookbook")
    index = tmp_path / "manifest" / "external_datasets.json"
    update_global_index(index_path=index, dataset_meta=meta, external_root=external)

    # Remove the dataset directory and re-index from a clean external_root.
    import shutil

    shutil.rmtree(dataset_dir)
    update_global_index(index_path=index, dataset_meta=None, external_root=external)
    payload = json.loads(index.read_text())
    assert payload["datasets"][0]["status"] == MISSING


def test_update_global_index_handles_existing_index_with_unknown_datasets(tmp_path: Path):
    index = tmp_path / "manifest" / "external_datasets.json"
    index.parent.mkdir(parents=True)
    index.write_text(
        json.dumps(
            {
                "schema_name": "pdf2md.ExternalDatasetIndex",
                "schema_version": 1,
                "generated_at": "2026-05-23T00:00:00Z",
                "datasets": [
                    {
                        "id": "previously-installed",
                        "path": "/no/longer/here",
                        "source_url": "https://example.com",
                        "ref": "main",
                        "resolved_commit": "x",
                        "status": "installed",
                        "compile_status": "not_run",
                    }
                ],
            }
        )
    )
    payload = update_global_index(index_path=index, external_root=tmp_path / "external")
    found = next(d for d in payload["datasets"] if d["id"] == "previously-installed")
    assert found["status"] == MISSING


def test_missing_upstream_raises_clear_error(tmp_path: Path):
    dataset_dir = tmp_path / "tlc3-examples"
    dataset_dir.mkdir()
    with pytest.raises(FileNotFoundError) as exc:
        generate_dataset_manifest(dataset_dir=dataset_dir, name_or_alias="tlc3-examples")
    assert "upstream" in str(exc.value)
