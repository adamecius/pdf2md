"""Tests for the external dataset registry (Additional Plan 1, Task A1)."""

from __future__ import annotations

import pytest

from pdf2md.datasets.registry import (
    DatasetEntry,
    DatasetStatus,
    get_dataset,
    list_datasets,
    resolve_alias,
)


def test_list_datasets_returns_all_registered_entries_in_id_order():
    entries = list_datasets()
    ids = [entry.id for entry in entries]
    assert ids == ["arxiv-curated", "latex-cookbook", "tlc3-examples"]


def test_get_dataset_by_canonical_id():
    entry = get_dataset("tlc3-examples")
    assert isinstance(entry, DatasetEntry)
    assert entry.id == "tlc3-examples"
    assert entry.url.endswith("tlc3-examples.git")


def test_get_dataset_by_alias():
    entry = get_dataset("tlc3")
    assert entry.id == "tlc3-examples"
    entry = get_dataset("cookbook")
    assert entry.id == "latex-cookbook"
    entry = get_dataset("arxiv")
    assert entry.id == "arxiv-curated"


def test_unknown_dataset_raises_with_choices():
    with pytest.raises(ValueError) as exc:
        get_dataset("not-a-real-dataset")
    message = str(exc.value)
    assert "not-a-real-dataset" in message
    assert "tlc3-examples" in message
    assert "latex-cookbook" in message


def test_empty_name_raises_with_choices():
    with pytest.raises(ValueError) as exc:
        get_dataset("")
    message = str(exc.value)
    assert "tlc3-examples" in message


def test_resolve_alias_returns_canonical_id():
    assert resolve_alias("tlc3") == "tlc3-examples"
    assert resolve_alias("cookbook") == "latex-cookbook"
    assert resolve_alias("arxiv-curated") == "arxiv-curated"


def test_arxiv_curated_is_not_available():
    entry = get_dataset("arxiv-curated")
    assert entry.status is DatasetStatus.NOT_AVAILABLE
    assert entry.url == ""


def test_tlc3_has_keep_and_exclude_paths():
    entry = get_dataset("tlc3-examples")
    assert "NORMAL" in entry.keep_paths
    assert "SPECIAL" in entry.keep_paths
    assert "SUPPORT" in entry.keep_paths
    assert "BOOK-PDFS" in entry.exclude_paths
    assert any(g.startswith("NORMAL/") for g in entry.root_globs)


def test_latex_cookbook_uses_root_files_not_globs():
    entry = get_dataset("latex-cookbook")
    assert entry.root_files == ("cookbook.tex",)
    assert entry.root_globs == ()
    assert entry.recommended_engine == "lualatex"
    assert entry.licence == "MIT"


def test_dataset_entry_is_frozen():
    entry = get_dataset("tlc3-examples")
    with pytest.raises(Exception):
        entry.id = "tampered"  # type: ignore[misc]
