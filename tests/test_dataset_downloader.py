"""Tests for the external dataset downloader (Additional Plan 1, Task A2).

These tests build a local-only git fixture in a temporary directory
(``git init`` + ``git add`` + ``git commit``) and inject a custom
``git_runner`` so no network access is required.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pdf2md.datasets.downloader import DownloadResult, download_dataset
from pdf2md.datasets.registry import DatasetEntry, DatasetStatus


# ---------------------------------------------------------------------------
# Helpers — build a local "remote" git repo to clone from
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "pdf2md test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "pdf2md test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "PATH": "/usr/bin:/usr/local/bin:/bin",
        },
    )


def _build_local_tlc3_like_repo(tmp_path: Path) -> Path:
    """Create a local git repo that mimics the TLC3 directory layout."""

    repo = tmp_path / "remote-tlc3.git_src"
    repo.mkdir()

    (repo / "NORMAL").mkdir()
    (repo / "NORMAL" / "1-3-1.ltx").write_text("\\documentclass{article}\\begin{document}1.3.1\\end{document}\n")
    (repo / "SPECIAL").mkdir()
    (repo / "SPECIAL" / "10-5-1.ltx").write_text("\\documentclass{article}\\begin{document}10.5.1\\end{document}\n")
    (repo / "SUPPORT").mkdir()
    (repo / "SUPPORT" / "figure.pdf").write_bytes(b"%PDF-fake")
    (repo / "BOOK-PDFS").mkdir()
    (repo / "BOOK-PDFS" / "tlc3.pdf").write_bytes(b"%PDF-bookpdf-DO-NOT-INSTALL")
    (repo / "README.md").write_text("# TLC3 fixture\n")
    (repo / "build.lua").write_text("-- fake build script\n")

    _git(["init", "-b", "main"], repo)
    _git(["add", "."], repo)
    _git(["commit", "-m", "initial"], repo)
    return repo


def _build_local_cookbook_like_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "remote-cookbook.git_src"
    repo.mkdir()
    (repo / "cookbook.tex").write_text("\\documentclass{book}\\begin{document}cookbook\\end{document}\n")
    (repo / "chapters").mkdir()
    (repo / "chapters" / "intro.tex").write_text("intro\n")
    (repo / "LICENSE").write_text("MIT\n")
    _git(["init", "-b", "main"], repo)
    _git(["add", "."], repo)
    _git(["commit", "-m", "initial"], repo)
    return repo


def _patched_entry(monkeypatch: pytest.MonkeyPatch, *, name: str, url: str) -> None:
    """Override the registry URL for a specific dataset id."""

    from pdf2md.datasets import downloader, registry

    original_get = registry.get_dataset

    def patched_get(id_or_alias: str) -> DatasetEntry:
        entry = original_get(id_or_alias)
        if entry.id == name:
            return DatasetEntry(
                id=entry.id,
                aliases=entry.aliases,
                source_type=entry.source_type,
                url=url,
                default_ref=entry.default_ref or "main",
                licence=entry.licence,
                keep_paths=entry.keep_paths,
                exclude_paths=entry.exclude_paths,
                root_globs=entry.root_globs,
                root_files=entry.root_files,
                recommended_engine=entry.recommended_engine,
                description=entry.description,
                status=entry.status,
            )
        return entry

    monkeypatch.setattr(downloader, "get_dataset", patched_get)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_successful_clone_and_positioning_for_tlc3_excludes_book_pdfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    remote = _build_local_tlc3_like_repo(tmp_path)
    _patched_entry(monkeypatch, name="tlc3-examples", url=str(remote))

    out_root = tmp_path / "external"
    result = download_dataset("tlc3-examples", output_root=out_root)

    assert result.success, result.error_message
    upstream = out_root / "tlc3-examples" / "upstream"
    assert (upstream / "NORMAL" / "1-3-1.ltx").is_file()
    assert (upstream / "SPECIAL" / "10-5-1.ltx").is_file()
    assert (upstream / "SUPPORT" / "figure.pdf").is_file()
    assert (upstream / "README.md").is_file()
    assert (upstream / "build.lua").is_file()
    # The keep/exclude rules must drop BOOK-PDFS.
    assert not (upstream / "BOOK-PDFS").exists()
    # .git is stripped by default
    assert not (upstream / ".git").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_keep_paths_dot_keeps_everything_for_cookbook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    remote = _build_local_cookbook_like_repo(tmp_path)
    _patched_entry(monkeypatch, name="latex-cookbook", url=str(remote))

    out_root = tmp_path / "external"
    result = download_dataset("latex-cookbook", output_root=out_root)

    assert result.success, result.error_message
    upstream = out_root / "latex-cookbook" / "upstream"
    assert (upstream / "cookbook.tex").is_file()
    assert (upstream / "chapters" / "intro.tex").is_file()
    assert (upstream / "LICENSE").is_file()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_force_replaces_existing_dataset_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    remote = _build_local_cookbook_like_repo(tmp_path)
    _patched_entry(monkeypatch, name="latex-cookbook", url=str(remote))

    out_root = tmp_path / "external"
    first = download_dataset("latex-cookbook", output_root=out_root)
    assert first.success

    # Sentinel marker that should be wiped by --force
    sentinel = out_root / "latex-cookbook" / "upstream" / "marker.txt"
    sentinel.write_text("stale")

    second = download_dataset("latex-cookbook", output_root=out_root, force=True)
    assert second.success
    assert not sentinel.exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_without_force_existing_dir_returns_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    remote = _build_local_cookbook_like_repo(tmp_path)
    _patched_entry(monkeypatch, name="latex-cookbook", url=str(remote))

    out_root = tmp_path / "external"
    first = download_dataset("latex-cookbook", output_root=out_root)
    assert first.success

    second = download_dataset("latex-cookbook", output_root=out_root, force=False)
    assert not second.success
    assert second.error_message is not None
    assert "already exists" in second.error_message
    assert "--force" in second.error_message


def test_missing_git_binary_raises_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from pdf2md.datasets import downloader

    monkeypatch.setattr(downloader.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError) as exc:
        download_dataset("tlc3-examples", output_root=tmp_path / "external")
    assert "git was not found" in str(exc.value)


def test_not_available_dataset_returns_failure_without_clone(tmp_path: Path):
    result = download_dataset("arxiv-curated", output_root=tmp_path / "external")
    assert not result.success
    assert "not yet available" in (result.error_message or "")
    # No files written
    assert not (tmp_path / "external" / "arxiv-curated").exists()


def test_dry_run_does_not_create_anything(tmp_path: Path):
    result = download_dataset(
        "tlc3-examples", output_root=tmp_path / "external", dry_run=True
    )
    assert result.success
    assert result.ref_used == "main"
    assert not (tmp_path / "external" / "tlc3-examples").exists()
