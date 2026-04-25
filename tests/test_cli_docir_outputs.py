"""CLI integration tests for Markdown and DocIR outputs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]


def _make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "CLI deterministic text")
    doc.save(path)
    doc.close()


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "doc2md", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_includes_docir_option() -> None:
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "--emit-docir" in result.stdout


def test_cli_default_still_writes_markdown_only(tmp_path) -> None:
    input_pdf = tmp_path / "sample.pdf"
    output_dir = tmp_path / "out"
    _make_pdf(input_pdf)

    result = _run_cli(str(input_pdf), "-o", str(output_dir), "-vv")
    assert result.returncode == 0, result.stderr

    assert (output_dir / "sample.md").exists()
    assert not (output_dir / "sample.docir.json").exists()


def test_cli_can_emit_docir_json(tmp_path) -> None:
    input_pdf = tmp_path / "sample.pdf"
    output_dir = tmp_path / "out_docir"
    _make_pdf(input_pdf)

    result = _run_cli(str(input_pdf), "-o", str(output_dir), "-vv", "--emit-docir")
    assert result.returncode == 0, result.stderr

    md_file = output_dir / "sample.md"
    docir_file = output_dir / "sample.docir.json"

    assert md_file.exists()
    assert docir_file.exists()

    payload = json.loads(docir_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "0.1"
    assert payload["pages"]


def test_cli_can_emit_chunks_jsonl(tmp_path) -> None:
    input_pdf = tmp_path / "sample.pdf"
    output_dir = tmp_path / "out_chunks"
    _make_pdf(input_pdf)

    result = _run_cli(str(input_pdf), "-o", str(output_dir), "-vv", "--emit-chunks")
    assert result.returncode == 0, result.stderr

    assert (output_dir / "sample.md").exists()
    assert (output_dir / "sample.blocks.jsonl").exists()
