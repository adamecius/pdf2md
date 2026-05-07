# Expected pytest item count: 12 test functions.
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from pdf2md.connectors.common import ConnectorResult

BACKENDS = ["deepseek", "glm", "mineru", "paddleocr"]
FIXTURE_SIMPLE = Path("tests/data/connector_fixtures/simple_markdown")
FIXTURE_SEMANTIC = Path("tests/data/connector_fixtures/semantic_markdown")


def load_connector(backend):
    path = Path("backend") / backend / "connector.py"
    spec = importlib.util.spec_from_file_location(f"{backend}_connector", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestBackendConnectorImports:
    def test_deepseek_connector_imports_without_heavy_dependencies(self): assert load_connector("deepseek")
    def test_glm_connector_imports_without_heavy_dependencies(self): assert load_connector("glm")
    def test_mineru_connector_imports_without_heavy_dependencies(self): assert load_connector("mineru")
    def test_paddleocr_connector_imports_without_heavy_dependencies(self): assert load_connector("paddleocr")


class TestBackendConnectorPublicApi:
    def test_each_connector_exposes_backend_constant(self):
        assert all(isinstance(load_connector(b).BACKEND, str) for b in BACKENDS)
    def test_each_connector_exposes_connect_function(self):
        assert all(callable(load_connector(b).connect) for b in BACKENDS)
    def test_each_connector_connect_returns_connector_result(self):
        assert all(isinstance(load_connector(b).connect(FIXTURE_SIMPLE, "doc"), ConnectorResult) for b in BACKENDS)
    def test_each_connector_uses_expected_backend_name(self):
        assert all(load_connector(b).BACKEND == b for b in BACKENDS)


class TestBackendConnectorCli:
    def test_each_connector_help_exits_zero(self):
        for b in BACKENDS:
            r = subprocess.run([sys.executable, f"backend/{b}/connector.py", "--help"], text=True, capture_output=True)
            assert r.returncode == 0
    def test_each_connector_cli_writes_expected_files_from_simple_fixture(self, tmp_path):
        for b in BACKENDS:
            out = tmp_path / b
            r = subprocess.run([sys.executable, f"backend/{b}/connector.py", "--raw-dir", str(FIXTURE_SIMPLE), "--document-id", "doc", "--out-dir", str(out)], text=True, capture_output=True)
            assert r.returncode == 0, r.stderr
            assert (out / b / "manifest.json").exists()
    def test_each_connector_cli_writes_expected_files_from_semantic_fixture(self, tmp_path):
        for b in BACKENDS:
            out = tmp_path / b
            r = subprocess.run([sys.executable, f"backend/{b}/connector.py", "--raw-dir", str(FIXTURE_SEMANTIC), "--document-id", "doc", "--out-dir", str(out)], text=True, capture_output=True)
            assert r.returncode == 0, r.stderr
            assert (out / b / "entities.json").exists()
    def test_each_connector_cli_missing_raw_dir_exits_nonzero(self):
        for b in BACKENDS:
            r = subprocess.run([sys.executable, f"backend/{b}/connector.py", "--raw-dir", "/no/such/path", "--document-id", "doc"], text=True, capture_output=True)
            assert r.returncode == 1
