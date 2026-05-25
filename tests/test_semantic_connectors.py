"""Tests for the per-backend ``connect()`` functions under
``backend/semantic/<name>/connector.py``.

These mirror the OCR-backend connector tests under
``tests/test_connector_common.py`` + ``tests/test_backend_connectors.py``.

The semantic connectors live in `backend/`, which is intentionally NOT
a Python package — so we load them by file path with `importlib.util`,
the same way :func:`pdf2md.semantic.regex_adapter._load_connector_module`
does at runtime.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from pdf2md.connectors.common import SemanticConnectorResult
from pdf2md.models import CrossReferenceGraph


REPO_ROOT = Path(__file__).resolve().parent.parent
SEMANTIC_ROOT = REPO_ROOT / "backend" / "semantic"
SAMPLE_TEXT = REPO_ROOT / "tests" / "data" / "semantic_fixtures" / "sample_text.txt"


def _load_connector(backend: str) -> ModuleType:
    path = SEMANTIC_ROOT / backend / "connector.py"
    assert path.is_file(), f"missing {path}"
    spec = importlib.util.spec_from_file_location(
        f"_test_connector_{backend}", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# OCR-parallel convention checks (run for every semantic backend)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("backend", ["regex", "grobid", "deepseek_vl2"])
def test_connector_exports_required_constants(backend: str) -> None:
    module = _load_connector(backend)
    assert hasattr(module, "BACKEND"), f"{backend}/connector.py missing BACKEND"
    assert isinstance(module.BACKEND, str)
    assert hasattr(module, "BACKEND_VERSION"), f"{backend}/connector.py missing BACKEND_VERSION"
    assert hasattr(module, "connect"), f"{backend}/connector.py missing connect()"
    assert callable(module.connect)
    assert hasattr(module, "main"), f"{backend}/connector.py missing main()"
    assert callable(module.main)


@pytest.mark.parametrize("backend", ["regex", "grobid", "deepseek_vl2"])
def test_connector_connect_has_canonical_signature(backend: str) -> None:
    """`connect(raw_dir, document_id, out_dir=None, …) -> SemanticConnectorResult`."""
    import inspect

    module = _load_connector(backend)
    sig = inspect.signature(module.connect)
    params = list(sig.parameters.values())
    # The first three positional params must match the OCR convention.
    assert params[0].name == "raw_dir"
    assert params[1].name == "document_id"
    assert params[2].name == "out_dir"
    # Backend-specific kwargs follow (keyword-only after `*`).
    # Just confirm there are some kwargs (positional-only would be wrong).
    assert any(p.kind == inspect.Parameter.KEYWORD_ONLY for p in params)


# ---------------------------------------------------------------------------
# Regex connector — no network / GPU needed
# ---------------------------------------------------------------------------
def test_regex_connector_end_to_end(tmp_path: Path) -> None:
    if not SAMPLE_TEXT.is_file():
        pytest.skip(f"missing fixture: {SAMPLE_TEXT}")
    module = _load_connector("regex")
    text = SAMPLE_TEXT.read_text(encoding="utf-8")
    result = module.connect(
        raw_dir=tmp_path,
        document_id="fixture",
        out_dir=tmp_path / "out",
        text=text,
    )
    assert isinstance(result, SemanticConnectorResult)
    assert isinstance(result.graph, CrossReferenceGraph)
    assert result.warnings == []
    assert len(result.graph.markers) > 0
    # Output file written under <out>/<backend>/cross_references.json.
    written = tmp_path / "out" / "regex" / "cross_references.json"
    assert written.is_file()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    assert "regex" in payload["backend_versions"]


def test_regex_connector_no_text_warns(tmp_path: Path) -> None:
    module = _load_connector("regex")
    result = module.connect(
        raw_dir=tmp_path,
        document_id="empty",
        out_dir=None,
        text=None,
    )
    assert "no_text_found" in result.warnings
    assert result.graph.markers == []


def test_regex_connector_reads_text_from_raw_dir(tmp_path: Path) -> None:
    (tmp_path / "text.txt").write_text("See Figure 7 and [42].", encoding="utf-8")
    module = _load_connector("regex")
    result = module.connect(
        raw_dir=tmp_path,
        document_id="from-raw-dir",
        out_dir=None,
    )
    assert result.graph.markers, "expected the connector to find markers from text.txt"


def test_regex_connector_cli_writes_file(tmp_path: Path) -> None:
    if not SAMPLE_TEXT.is_file():
        pytest.skip(f"missing fixture: {SAMPLE_TEXT}")
    cli = SEMANTIC_ROOT / "regex" / "connector.py"
    out_dir = tmp_path / "out"
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "HOME": str(tmp_path),
    }
    completed = subprocess.run(
        [
            sys.executable, str(cli),
            "--raw-dir", str(tmp_path),
            "--document-id", "smoke",
            "--text", str(SAMPLE_TEXT),
            "--out-dir", str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert "regex connector:" in completed.stdout
    assert (out_dir / "regex" / "cross_references.json").is_file()


# ---------------------------------------------------------------------------
# GROBID connector — env_not_ready path (no daemon needed for the test)
# ---------------------------------------------------------------------------
def test_grobid_connector_env_not_ready_path(tmp_path: Path) -> None:
    # Put a dummy PDF in raw_dir so the lookup succeeds; the connector
    # will reach the is_alive() check and return env_not_ready.
    fake_pdf = tmp_path / "input.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 stub\n%%EOF\n")
    module = _load_connector("grobid")
    result = module.connect(
        raw_dir=tmp_path,
        document_id="stub",
        out_dir=None,
        # Force an unreachable host so the gating path triggers.
        host="127.0.0.1",
        port=1,
    )
    assert isinstance(result, SemanticConnectorResult)
    assert result.graph.markers == []
    assert any(w.startswith("env_not_ready:") for w in result.warnings)


def test_grobid_connector_missing_pdf_raises(tmp_path: Path) -> None:
    module = _load_connector("grobid")
    with pytest.raises(FileNotFoundError):
        module.connect(
            raw_dir=tmp_path,
            document_id="missing",
            out_dir=None,
        )


# ---------------------------------------------------------------------------
# VL2 connector — only tested via its module-level surface here, since
# `connect()` requires the pdf2md-deepseek-vl2 env. The CLI's exit-3
# env_not_ready path is exercised by the existing
# test_build_cross_references_cli.py.
# ---------------------------------------------------------------------------
def test_vlm_connector_module_loads() -> None:
    module = _load_connector("deepseek_vl2")
    assert module.BACKEND == "vlm"
    assert callable(module.connect)
    # `connect` is imported in the test process (main pdf2md env) but
    # never called — the deferred import of `vlm_client` inside the
    # function body keeps the test-environment import clean.
