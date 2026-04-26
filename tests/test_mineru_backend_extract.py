from __future__ import annotations

import importlib
import importlib.util
import subprocess
from pathlib import Path

import pytest

from doc2md.backends.mineru_backend import MineruBackend


def test_mineru_extract_reads_markdown_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = MineruBackend()
    input_pdf = tmp_path / "sample.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(importlib, "import_module", lambda _name: object())

    def fake_run(cmd, check, capture_output, text):
        out_idx = cmd.index("--output") + 1
        out_dir = Path(cmd[out_idx])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.md").write_text("MinerU markdown output", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    doc = backend.extract(input_pdf, output_dir=tmp_path / "out")

    assert doc.blocks
    assert "MinerU markdown output" in (doc.blocks[0].markdown or "")
    assert doc.backend_runs[0].backend == "mineru"


def test_mineru_extract_falls_back_when_module_entrypoint_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = MineruBackend()
    input_pdf = tmp_path / "sample.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(importlib, "import_module", lambda _name: object())
    monkeypatch.setattr(backend, "_candidate_cli_commands", lambda *_args, **_kwargs: [["py", "-m", "mineru"], ["mineru"]])

    calls: list[list[str]] = []

    def fake_run(cmd, check, capture_output, text):
        calls.append(cmd)
        if cmd == ["py", "-m", "mineru"]:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                stderr="No module named mineru.__main__; 'mineru' is a package and cannot be directly executed.",
            )
        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.md").write_text("fallback output", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    doc = backend.extract(input_pdf, output_dir=tmp_path / "out")

    assert calls == [["py", "-m", "mineru"], ["mineru"]]
    assert "fallback output" in (doc.blocks[0].markdown or "")
