"""Tests for the `pdf2md datasets` Typer subcommand (Additional Plan 1, A4).

Downloader calls are mocked so no network access is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pdf2md.cli.main import app
from pdf2md.datasets.downloader import DownloadResult


runner = CliRunner()


def _bin_index_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the global index file into tmp_path."""

    from pdf2md.datasets import cli as datasets_cli_mod

    index_path = tmp_path / "manifest" / "external_datasets.json"
    monkeypatch.setattr(datasets_cli_mod, "INDEX_DEFAULT_PATH", index_path)
    return index_path


def test_list_shows_registry_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _bin_index_path(tmp_path, monkeypatch)
    result = runner.invoke(app, ["datasets", "list", "--output", str(tmp_path / "external")])
    assert result.exit_code == 0, result.stdout
    assert "tlc3-examples" in result.stdout
    assert "latex-cookbook" in result.stdout
    assert "arxiv-curated" in result.stdout
    assert "not_available" in result.stdout
    assert "available" in result.stdout


def test_install_dry_run_produces_output_without_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _bin_index_path(tmp_path, monkeypatch)
    out_dir = tmp_path / "external"
    result = runner.invoke(
        app,
        [
            "datasets",
            "install",
            "tlc3",
            "--output",
            str(out_dir),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "[dry-run]" in result.stdout
    assert "tlc3-examples" in result.stdout
    assert not (out_dir / "tlc3-examples").exists()


def test_install_with_mocked_downloader_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    index_path = _bin_index_path(tmp_path, monkeypatch)
    out_dir = tmp_path / "external"

    from pdf2md.datasets import cli as datasets_cli_mod

    def fake_download(name: str, *, output_root: Path, ref=None, force=False):
        # Simulate the downloader creating the upstream directory with a tex file.
        dataset_dir = Path(output_root) / "latex-cookbook"
        upstream = dataset_dir / "upstream"
        upstream.mkdir(parents=True, exist_ok=True)
        (upstream / "cookbook.tex").write_text(
            "\\documentclass{book}\\begin{document}c\\end{document}\n"
        )
        return DownloadResult(
            dataset_id="latex-cookbook",
            output_path=dataset_dir,
            resolved_commit="cafebabe" * 5,
            ref_used="main",
            success=True,
        )

    monkeypatch.setattr(datasets_cli_mod, "download_dataset", fake_download)

    result = runner.invoke(
        app,
        [
            "datasets",
            "install",
            "latex-cookbook",
            "--output",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "installed latex-cookbook" in result.stdout
    assert (out_dir / "latex-cookbook" / "dataset.json").is_file()
    assert (out_dir / "latex-cookbook" / "manifest.jsonl").is_file()
    index = json.loads(index_path.read_text())
    assert any(d["id"] == "latex-cookbook" for d in index["datasets"])


def test_install_arxiv_curated_prints_not_available_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _bin_index_path(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        ["datasets", "install", "arxiv-curated", "--output", str(tmp_path / "external")],
    )
    assert result.exit_code != 0
    assert "not yet available" in (result.stdout + result.stderr)


def test_install_unknown_dataset_returns_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _bin_index_path(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        ["datasets", "install", "totally-not-a-dataset", "--output", str(tmp_path)],
    )
    assert result.exit_code != 0
    combined = result.stdout + result.stderr
    assert "totally-not-a-dataset" in combined or "Unknown" in combined


def test_install_without_force_on_existing_dataset_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _bin_index_path(tmp_path, monkeypatch)
    out_dir = tmp_path / "external"
    (out_dir / "latex-cookbook" / "upstream").mkdir(parents=True)
    (out_dir / "latex-cookbook" / "upstream" / "cookbook.tex").write_text("stub")

    from pdf2md.datasets import cli as datasets_cli_mod

    def fake_download(name: str, *, output_root: Path, ref=None, force=False):
        if not force:
            return DownloadResult(
                dataset_id="latex-cookbook",
                output_path=Path(output_root) / "latex-cookbook",
                resolved_commit=None,
                ref_used="main",
                success=False,
                error_message="Output directory already exists. Pass --force to replace it.",
            )
        return DownloadResult(
            dataset_id="latex-cookbook",
            output_path=Path(output_root) / "latex-cookbook",
            resolved_commit="x",
            ref_used="main",
            success=True,
        )

    monkeypatch.setattr(datasets_cli_mod, "download_dataset", fake_download)
    result = runner.invoke(
        app,
        ["datasets", "install", "latex-cookbook", "--output", str(out_dir)],
    )
    assert result.exit_code != 0
    combined = result.stdout + result.stderr
    assert "already exists" in combined


def test_status_reads_and_reports_from_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    index_path = _bin_index_path(tmp_path, monkeypatch)
    out_dir = tmp_path / "external"
    (out_dir / "latex-cookbook").mkdir(parents=True)
    (out_dir / "latex-cookbook" / "upstream").mkdir(parents=True)
    (out_dir / "latex-cookbook" / "dataset.json").write_text(
        json.dumps(
            {
                "id": "latex-cookbook",
                "source_url": "https://example.com/c.git",
                "ref": "main",
                "resolved_commit": "abc",
                "compile_status": "not_run",
            }
        )
    )

    result = runner.invoke(app, ["datasets", "status", "--output", str(out_dir)])
    assert result.exit_code == 0, result.stdout
    assert "latex-cookbook" in result.stdout
    assert "installed" in result.stdout
    assert "tlc3-examples" in result.stdout
    assert "not_installed" in result.stdout or "not_available" in result.stdout


def test_compile_flag_prints_not_implemented_and_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _bin_index_path(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "datasets",
            "install",
            "tlc3-examples",
            "--output",
            str(tmp_path),
            "--compile",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Plan 18" in result.stdout


def test_install_all_skips_not_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _bin_index_path(tmp_path, monkeypatch)
    out_dir = tmp_path / "external"

    from pdf2md.datasets import cli as datasets_cli_mod

    def fake_download(name: str, *, output_root: Path, ref=None, force=False):
        dataset_dir = Path(output_root) / name
        upstream = dataset_dir / "upstream"
        upstream.mkdir(parents=True, exist_ok=True)
        (upstream / "x.tex").write_text("\\documentclass{article}\\begin{document}\\end{document}\n")
        return DownloadResult(
            dataset_id=name,
            output_path=dataset_dir,
            resolved_commit="0123" * 10,
            ref_used="main",
            success=True,
        )

    monkeypatch.setattr(datasets_cli_mod, "download_dataset", fake_download)
    result = runner.invoke(
        app,
        ["datasets", "install", "all", "--output", str(out_dir)],
    )
    assert result.exit_code == 0, result.stdout
    assert "skipping arxiv-curated" in result.stdout
    assert "installed tlc3-examples" in result.stdout
    assert "installed latex-cookbook" in result.stdout


def test_manifest_only_refresh_without_clone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _bin_index_path(tmp_path, monkeypatch)
    out_dir = tmp_path / "external"

    # Pre-populate an existing dataset on disk; --manifest-only should
    # regenerate dataset.json + manifest.jsonl without invoking the
    # downloader.
    upstream = out_dir / "latex-cookbook" / "upstream"
    upstream.mkdir(parents=True)
    (upstream / "cookbook.tex").write_text(
        "\\documentclass{book}\\begin{document}cookbook\\end{document}\n"
    )

    from pdf2md.datasets import cli as datasets_cli_mod

    def boom(*_args, **_kwargs):
        raise AssertionError("downloader must NOT be called in --manifest-only mode")

    monkeypatch.setattr(datasets_cli_mod, "download_dataset", boom)

    result = runner.invoke(
        app,
        [
            "datasets",
            "install",
            "latex-cookbook",
            "--output",
            str(out_dir),
            "--manifest-only",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (out_dir / "latex-cookbook" / "dataset.json").is_file()
    assert (out_dir / "latex-cookbook" / "manifest.jsonl").is_file()
