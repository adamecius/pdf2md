"""Plan 18 — tests for the orchestrator-run directory layout (``RunLayout``)."""

from __future__ import annotations

from pathlib import Path

from pdf2md.pipeline.artifacts import (
    ARTEFACT_PIPELINE_MANIFEST,
    ARTEFACT_PIPELINE_SUMMARY,
    RunLayout,
)


def test_run_layout_path_properties(tmp_path: Path) -> None:
    layout = RunLayout(run_dir=tmp_path / "run")
    assert layout.run_dir == tmp_path / "run"
    assert layout.input_dir == tmp_path / "run" / "input"
    assert layout.raw_dir == tmp_path / "run" / "raw"
    assert layout.connector_dir == tmp_path / "run" / "connector"
    assert layout.priors_dir == tmp_path / "run" / "priors"
    assert layout.consensus_dir == tmp_path / "run" / "consensus"
    assert layout.linked_dir == tmp_path / "run" / "linked"
    assert layout.export_dir == tmp_path / "run" / "export"
    assert layout.manifest_path == tmp_path / "run" / ARTEFACT_PIPELINE_MANIFEST
    assert layout.summary_path == tmp_path / "run" / ARTEFACT_PIPELINE_SUMMARY


def test_run_layout_backend_subdirs(tmp_path: Path) -> None:
    layout = RunLayout(run_dir=tmp_path / "run")
    assert layout.raw_backend_dir("mineru") == tmp_path / "run" / "raw" / "mineru"
    assert layout.connector_backend_dir("paddleocr") == tmp_path / "run" / "connector" / "paddleocr"


def test_run_layout_create_dirs_makes_tree(tmp_path: Path) -> None:
    layout = RunLayout(run_dir=tmp_path / "run").create_dirs()
    assert layout.run_dir.is_dir()
    assert layout.input_dir.is_dir()
    assert layout.raw_dir.is_dir()
    assert layout.connector_dir.is_dir()
    assert layout.priors_dir.is_dir()
    assert layout.consensus_dir.is_dir()
    assert layout.linked_dir.is_dir()
    assert layout.export_dir.is_dir()


def test_run_layout_create_dirs_is_idempotent(tmp_path: Path) -> None:
    layout = RunLayout(run_dir=tmp_path / "run").create_dirs()
    # Drop a sentinel; calling again must not erase it.
    sentinel = layout.input_dir / "marker.txt"
    sentinel.write_text("keep me")
    layout.create_dirs()
    assert sentinel.read_text() == "keep me"


def test_run_layout_priors_dir_matches_consensus_io_expectation(tmp_path: Path) -> None:
    """Priors path layout must match what consensus.io.load_consensus_inputs walks.

    ``load_consensus_inputs`` looks for ``<priors_root>/<backend>.json`` —
    asserting the layout API yields a directory under which we can drop
    ``<backend>.json`` files.
    """

    layout = RunLayout(run_dir=tmp_path / "run").create_dirs()
    prior_path = layout.priors_dir / "mineru.json"
    prior_path.write_text("{}")
    assert prior_path.parent == layout.priors_dir
    assert prior_path.exists()


def test_run_layout_connector_dir_matches_consensus_io_expectation(tmp_path: Path) -> None:
    """Connector dir must allow ``<backend>/pages/page_NNNN.json`` siblings."""

    layout = RunLayout(run_dir=tmp_path / "run").create_dirs()
    backend_dir = layout.connector_backend_dir("mineru")
    (backend_dir / "pages").mkdir(parents=True)
    (backend_dir / "entities.json").write_text("{}")
    assert (backend_dir / "pages").is_dir()
    assert (backend_dir / "entities.json").exists()
