"""Plan 16 MVP pipeline CLI tests.

Tests the argparse surface, mode mutual exclusion, and the document-list
file reader. The real stage chain is mocked via the runner module's
``_StageOverrides`` — we don't shell out for these tests.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX_CORPUS = ROOT / "tests" / "data" / "mvp_pipeline_fixtures" / "sample_corpus"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location(
        "run_mvp_pipeline_cli",
        ROOT / "tools" / "run_mvp_pipeline.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_mvp_pipeline_cli"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# A monkeypatchable stub for run_one_document so we never run real stages.
def _stub_one_document(**kwargs):
    from pdf2md.pipeline.runner import (
        DocumentRecord,
        DocumentResult,
        MvpReadiness,
        PipelineManifest,
        StageName,
        StageRecord,
        StageStatus,
    )

    doc = DocumentRecord(
        document_id="stub",
        input_pdf=str(kwargs.get("pdf_path")),
        result=DocumentResult.PASSED,
        eligible_backends=["paddleocr"],
        stages=[StageRecord(name=s, status=StageStatus.SUCCEEDED) for s in StageName],
        final_artefacts={"docling": "/fake/x.docling.json"},
    )
    return PipelineManifest(
        generated_at="2026-05-23T00:00:00Z",
        mode="one_document",
        input_pdf=str(kwargs.get("pdf_path")),
        out_dir=str(kwargs.get("out_dir")),
        work_dir=str(kwargs.get("work_dir") or kwargs.get("out_dir")),
        selected_backends=kwargs.get("backends") or [],
        documents=[doc],
        mvp_readiness=MvpReadiness.MVP_READY,
    )


def _stub_corpus(**kwargs):
    from pdf2md.pipeline.runner import (
        CorpusEvaluation,
        DocumentRecord,
        DocumentResult,
        MvpReadiness,
        PipelineManifest,
        StageName,
        StageRecord,
        StageStatus,
    )

    docs = [
        DocumentRecord(
            document_id=name,
            result=DocumentResult.PASSED,
            stages=[StageRecord(name=s, status=StageStatus.SUCCEEDED) for s in StageName],
            final_artefacts={"docling": f"/fake/{name}.docling.json"},
        )
        for name in ("doc_a", "doc_b")
    ]
    manifest = PipelineManifest(
        generated_at="2026-05-23T00:00:00Z",
        mode="corpus_subset",
        corpus_root=str(kwargs.get("corpus_root")),
        out_dir=str(kwargs.get("out_dir")),
        work_dir=str(kwargs.get("work_dir") or kwargs.get("out_dir")),
        selected_backends=kwargs.get("backends") or [],
        documents=docs,
        mvp_readiness=MvpReadiness.MVP_READY,
    )
    evaluation = CorpusEvaluation(
        generated_at="2026-05-23T00:00:00Z",
        corpus_root=str(kwargs.get("corpus_root")),
        out_dir=str(kwargs.get("out_dir")),
        selected_documents=[d.document_id for d in docs],
        # d.result is already a string due to use_enum_values=True on the model.
        document_results={d.document_id: (d.result if isinstance(d.result, str) else d.result.value) for d in docs},
        mvp_readiness=MvpReadiness.MVP_READY,
    )
    return manifest, evaluation


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestModeSelection:
    def test_pdf_and_corpus_root_are_mutually_exclusive(self, tmp_path: Path, capsys):
        cli = _load_cli_module()
        rc = cli.main(
            [
                "--pdf",
                str(tmp_path / "x.pdf"),
                "--corpus-root",
                str(FIX_CORPUS),
                "--out-dir",
                str(tmp_path / "out"),
            ]
        )
        # argparse prints help + exits 1 via our _ExitCodeOneParser.
        assert rc == 1

    def test_neither_mode_is_an_error(self, tmp_path: Path):
        cli = _load_cli_module()
        rc = cli.main(["--out-dir", str(tmp_path / "out")])
        assert rc == 1


class TestOneDocumentMode:
    def test_one_document_calls_run_one_document(self, tmp_path: Path, monkeypatch):
        cli = _load_cli_module()
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return _stub_one_document(**kwargs)

        monkeypatch.setattr(cli, "run_one_document", fake)
        rc = cli.main(
            [
                "--pdf",
                str(tmp_path / "x.pdf"),
                "--out-dir",
                str(tmp_path / "out"),
                "--backends",
                "paddleocr,mineru",
            ]
        )
        assert rc == 0
        assert captured["backends"] == ["paddleocr", "mineru"]
        assert captured["pdf_path"] == tmp_path / "x.pdf"

    def test_verbose_prints_document_summary(self, tmp_path: Path, monkeypatch, capsys):
        cli = _load_cli_module()
        monkeypatch.setattr(cli, "run_one_document", _stub_one_document)
        rc = cli.main(
            [
                "--pdf",
                str(tmp_path / "x.pdf"),
                "--out-dir",
                str(tmp_path / "out"),
                "--verbose",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "document: stub" in captured.out
        assert "mvp_readiness: MVP_ready" in captured.out


class TestCorpusMode:
    def test_corpus_mode_calls_run_corpus(self, tmp_path: Path, monkeypatch):
        cli = _load_cli_module()
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return _stub_corpus(**kwargs)

        monkeypatch.setattr(cli, "run_corpus", fake)
        rc = cli.main(
            [
                "--corpus-root",
                str(FIX_CORPUS),
                "--out-dir",
                str(tmp_path / "out"),
                "--max-documents",
                "5",
                "--backends",
                "paddleocr",
            ]
        )
        assert rc == 0
        assert captured["corpus_root"] == FIX_CORPUS
        assert captured["max_documents"] == 5
        assert captured["backends"] == ["paddleocr"]

    def test_document_list_file_is_read(self, tmp_path: Path, monkeypatch):
        cli = _load_cli_module()
        listing = tmp_path / "docs.txt"
        listing.write_text("doc_a\n# a comment\n\ndoc_b\n", encoding="utf-8")
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return _stub_corpus(**kwargs)

        monkeypatch.setattr(cli, "run_corpus", fake)
        rc = cli.main(
            [
                "--corpus-root",
                str(FIX_CORPUS),
                "--out-dir",
                str(tmp_path / "out"),
                "--document-list",
                str(listing),
            ]
        )
        assert rc == 0
        assert captured["document_list"] == ["doc_a", "doc_b"]

    def test_missing_document_list_file_is_an_error(self, tmp_path: Path, monkeypatch):
        cli = _load_cli_module()
        monkeypatch.setattr(cli, "run_corpus", _stub_corpus)
        rc = cli.main(
            [
                "--corpus-root",
                str(FIX_CORPUS),
                "--out-dir",
                str(tmp_path / "out"),
                "--document-list",
                str(tmp_path / "missing.txt"),
            ]
        )
        assert rc == 1
