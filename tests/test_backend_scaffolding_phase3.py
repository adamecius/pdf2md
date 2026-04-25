"""Phase 3 backend scaffolding contract tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_backend_catalog_has_phase3_contract_entries() -> None:
    catalog_path = REPO_ROOT / "backend_catalog.yaml"
    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))

    assert payload["canonical_result_artifact"] == "document.docir.json"
    assert payload["run_output_root"] == "runs"

    backends = payload["backends"]
    assert set(backends) >= {"deterministic", "mineru", "paddleocr_vl"}

    assert backends["deterministic"]["registry_name"] == "deterministic"
    assert backends["mineru"]["registry_name"] == "mineru"
    assert backends["paddleocr_vl"]["registry_name"] == "paddleocr_vl"


def test_run_backend_script_produces_canonical_docir_for_deterministic(tmp_path) -> None:
    run_root = tmp_path / "runs"
    input_pdf = REPO_ROOT / "test_image1.pdf"

    proc = subprocess.run(
        ["scripts/run_backend.sh", "deterministic", str(input_pdf), str(run_root)],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHON_BIN": sys.executable},
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout

    output_docir = run_root / "test_image1" / "deterministic" / "document.docir.json"
    assert output_docir.exists()
