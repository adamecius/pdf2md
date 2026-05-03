from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_NAME = "Ashcroft_Mermin_sub.pdf"
EXPECTED_SHA256 = "20f76bdfdf94ad46a49d89f66f92ce0b9c4c37c3974201ee70c0020104691438"
EXPECTED_MD5 = "8670be28770453180c2a14161b4b6209"
EXPECTED_SIZE = 2372656
EXPECTED_PAGE_DIMS = [
    (389.5199890136719, 602.6400146484375),
    (438.239990234375, 584.1599731445312),
    (429.1199951171875, 607.6799926757812),
    (417.8399963378906, 587.280029296875),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def locate_sample_pdf() -> Path | None:
    candidates = [
        REPO_ROOT / PDF_NAME,
        REPO_ROOT / "groundtruth" / PDF_NAME,
        REPO_ROOT / "tests" / "fixtures" / PDF_NAME,
        REPO_ROOT / ".current" / "consensus" / "Ashcroft_Mermin_sub" / PDF_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def ensure_tmp_clean_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_cli(
    module: str,
    *args: str,
    env_overrides: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    if env_overrides:
        for key, value in env_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
    return subprocess.run([sys.executable, "-m", module, *args], cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)


def resolve_test_consensus_config() -> Path | None:
    env_config = os.environ.get("PDF2MD_CONSENSUS_CONFIG")
    if env_config:
        candidate = Path(env_config)
        if candidate.exists():
            return candidate
    repo_candidate = REPO_ROOT / "pdf2md.consensus.example.toml"
    if repo_candidate.exists():
        return repo_candidate
    return None


@pytest.fixture(scope="session")
def sample_pdf_path() -> Path:
    pdf = locate_sample_pdf()
    if not pdf:
        pytest.skip("Sample PDF Ashcroft_Mermin_sub.pdf missing in expected locations")
    return pdf


@pytest.fixture(scope="session")
def backend_ir_root() -> Path:
    stem = "Ashcroft_Mermin_sub"
    roots = [
        REPO_ROOT / "backend" / "mineru" / ".current" / "extraction_ir" / stem,
        REPO_ROOT / "backend" / "paddleocr" / ".current" / "extraction_ir" / stem,
        REPO_ROOT / "backend" / "deepseek" / ".current" / "extraction_ir" / stem,
    ]
    missing = [str(r) for r in roots if not r.exists()]
    if missing:
        pytest.skip(f"Backend IR artefacts missing, cannot run sample pipeline contract tests: {missing}")
    return REPO_ROOT


@pytest.fixture
def built_pipeline_artifacts(tmp_path: Path, sample_pdf_path: Path, backend_ir_root: Path) -> dict:
    config_path = resolve_test_consensus_config()
    if not config_path:
        pytest.skip("No consensus config found for Ashcroft sample pipeline. Set PDF2MD_CONSENSUS_CONFIG or add pdf2md.consensus.example.toml at repo root.")
    out_dir = ensure_tmp_clean_dir(tmp_path / "ashcroft_pipeline")
    consensus_root = ensure_tmp_clean_dir(tmp_path / "consensus")
    tmp_config = tmp_path / "pdf2md.consensus.test.toml"
    cfg_text = config_path.read_text(encoding="utf-8")
    cfg_text = cfg_text.replace(
        'output_root = ".current/consensus"',
        f'output_root = "{consensus_root.as_posix()}"',
        1,
    )
    tmp_config.write_text(cfg_text, encoding="utf-8")

    cons = consensus_root / "Ashcroft_Mermin_sub" / "consensus_report.json"
    sem_links = out_dir / "semantic_links.json"
    media_manifest = out_dir / "media_manifest.json"
    sem_doc = out_dir / "semantic_document.json"

    res = run_cli("pdf2md.utils.consensus_report", str(sample_pdf_path), "--config", str(tmp_config), "--verbose")
    assert res.returncode == 0, res.stderr
    assert cons.exists(), f"Expected consensus output at {cons}"
    res = run_cli("pdf2md.utils.semantic_linker", str(cons), "--output", str(sem_links), "--verbose")
    assert res.returncode == 0, res.stderr
    res = run_cli("pdf2md.utils.media_materializer", str(cons), "--semantic-links", str(sem_links), "--output-root", str(out_dir), "--verbose")
    assert res.returncode == 0, res.stderr
    res = run_cli("pdf2md.utils.semantic_document_builder", str(cons), "--semantic-links", str(sem_links), "--media-manifest", str(media_manifest), "--output", str(sem_doc), "--verbose")
    assert res.returncode == 0, res.stderr

    return {
        "out_dir": out_dir,
        "consensus_report": json.loads(cons.read_text(encoding="utf-8")),
        "semantic_links": json.loads(sem_links.read_text(encoding="utf-8")),
        "media_manifest": json.loads(media_manifest.read_text(encoding="utf-8")),
        "semantic_document": json.loads(sem_doc.read_text(encoding="utf-8")),
        "paths": {
            "consensus_report": cons,
            "semantic_links": sem_links,
            "media_manifest": media_manifest,
            "semantic_document": sem_doc,
            "media_root": out_dir,
        },
    }
