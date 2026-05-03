from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

EXPECTED_MD5 = "8670be28770453180c2a14161b4b6209"
EXPECTED_SHA256 = "20f76bdfdf94ad46a49d89f66f92ce0b9c4c37c3974201ee70c0020104691438"
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


def ensure_tmp_clean_dir(path: Path) -> Path:
    import shutil
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_cli(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    repo_root = Path(__file__).resolve().parents[2]
    return subprocess.run([sys.executable, "-m", module, *args], cwd=repo_root, env=env, text=True, capture_output=True, check=False)


def test_pdf_checksum_and_page_contract(sample_pdf_path: Path):
    fitz = pytest.importorskip("fitz", reason="PyMuPDF unavailable")
    assert sample_pdf_path.stat().st_size == EXPECTED_SIZE
    assert sha256(sample_pdf_path) == EXPECTED_SHA256
    assert md5(sample_pdf_path) == EXPECTED_MD5

    doc = fitz.open(str(sample_pdf_path))
    assert doc.page_count == 4
    for i, (w, h) in enumerate(EXPECTED_PAGE_DIMS):
        page = doc.load_page(i)
        assert abs(page.rect.width - w) < 1e-3
        assert abs(page.rect.height - h) < 1e-3
        assert len(page.get_text("blocks")) <= 1


def test_backend_ir_presence_only(backend_ir_root: Path):
    stem = "Ashcroft_Mermin_sub"
    for backend in ("mineru", "paddleocr", "deepseek"):
        root = backend_ir_root / "backend" / backend / ".current" / "extraction_ir" / stem
        assert (root / "manifest.json").exists()
        pages = root / "pages"
        assert pages.exists()
        for idx in range(4):
            assert (pages / f"page_{idx:04d}.json").exists()


def test_consensus_semantic_media_semanticdoc_contracts(built_pipeline_artifacts: dict, tmp_path: Path):
    c = built_pipeline_artifacts["consensus_report"]
    s = built_pipeline_artifacts["semantic_links"]
    m = built_pipeline_artifacts["media_manifest"]
    d = built_pipeline_artifacts["semantic_document"]

    assert c["schema_name"] == "pdf2md.consensus_report"
    assert c["document_summary"]["page_count"] == 4
    assert set(c["sources"]) >= {"mineru", "paddleocr", "deepseek", "pymupdf"}
    assert all((p.get("pymupdf_page") or {}).get("native_text_block_count", 0) == 0 for p in c["pages"])
    p2 = c["pages"][2]
    gids = {g["group_id"] for g in p2["candidate_groups"]}
    assert "p0002_g0001" in gids and "p0002_g0013" in gids
    assert p2["conflicts"]

    summary = s["summary"]
    assert summary["equation_anchors"] == 6
    assert summary["figure_anchors"] == 1
    assert summary["table_anchors"] == 1
    assert summary["footnote_anchors"] == 3
    assert summary["references_detected"] == 19
    assert summary["references_resolved"] == 9
    assert summary["references_unresolved"] == 10
    assert summary["equation_numbers_attached"] == 6
    assert summary["equation_numbers_unattached"] == 0
    assert summary["footnote_markers_detected"] == 6
    assert summary["footnote_markers_resolved"] == 0

    fig = next(a for a in s["anchors"] if a["anchor_id"] == "fig:1.2")
    assert fig["target_group_id"] == "p0002_g0013"
    assert fig["page_index"] == 2
    assert fig["selected_geometry_source"] == "paddleocr"
    assert fig["selection_mode"] == "fallback_default_backend"
    assert fig["bbox"] == pytest.approx([132.712, 108.553, 444.703, 185.033], abs=0.02)
    assert any("fallback_default_backend:default_figure_geometry_backend=paddleocr" in w for w in fig.get("warnings", []))

    assert any(a["anchor_id"] == "footnote:8" for a in s["anchors"])
    assert not any(a["anchor_id"] == "footnote:7" for a in s["anchors"])
    unresolved_7 = [r for r in s["references"] if not r.get("resolved") and r.get("reference_type") == "footnote" and r.get("label") == "7"]
    assert unresolved_7

    assert m["policy"]["materialize_orphan_images"] is False
    assets = {a["media_id"]: a for a in m["assets"]}
    assert "media:fig_1_2" in assets
    assert "media:p0002_g0001" not in assets
    fig_asset = assets["media:fig_1_2"]
    assert fig_asset["source_group_id"] == "p0002_g0013"
    assert fig_asset["anchor_id"] == "fig:1.2"
    assert fig_asset["bbox"] == pytest.approx([132.712, 108.553, 444.703, 185.033], abs=0.02)
    assert fig_asset["file_path"] == "media/fig_1_2.png"
    p = built_pipeline_artifacts["paths"]["media_root"] / "media" / "fig_1_2.png"
    assert p.exists() and p.stat().st_size > 0
    assert not (built_pipeline_artifacts["paths"]["media_root"] / "media" / "p0002_g0001.png").exists()
    assert not (built_pipeline_artifacts["paths"]["media_root"] / "media" / "p0002_g0013.png").exists()

    assert d["schema_name"] == "pdf2md.semantic_document"
    assert not any("hash mismatch" in w.lower() for w in d.get("warnings", []))
    b13 = next(b for b in d["blocks"] if b["source_group_id"] == "p0002_g0013")
    assert b13["type"] == "figure"
    assert b13["anchor_id"] == "fig:1.2"
    assert b13["media_id"] == "media:fig_1_2"
    assert b13["media_path"] == "media/fig_1_2.png"
    assert b13["bbox"] == pytest.approx([132.712, 108.553, 444.703, 185.033], abs=0.02)
    b01 = next(b for b in d["blocks"] if b["source_group_id"] == "p0002_g0001")
    assert b01.get("media_id") != "media:p0002_g0001"
    media_dbg_root = ensure_tmp_clean_dir(tmp_path / "media_out_debug")
    res = run_cli("pdf2md.utils.media_materializer", str(built_pipeline_artifacts["paths"]["consensus_report"]), "--semantic-links", str(built_pipeline_artifacts["paths"]["semantic_links"]), "--output-root", str(media_dbg_root), "--materialize-orphan-images", "--json-only")
    assert res.returncode == 0, res.stderr
    dbg = json.loads((media_dbg_root / "media_manifest.json").read_text(encoding="utf-8"))
    assert dbg["policy"]["materialize_orphan_images"] is True
    by_id = {a["media_id"]: a for a in dbg["assets"]}
    assert "media:fig_1_2" in by_id
    if "media:p0002_g0001" in by_id:
        assert by_id["media:p0002_g0001"].get("anchor_id") is None


def test_docling_adapter_on_fresh_canonical_semantic_document(built_pipeline_artifacts: dict, tmp_path: Path):
    try:
        from pdf2md.utils.docling_adapter import DoclingBackend, AdapterError
        DoclingBackend.load()
    except Exception:
        pytest.skip("docling_core unavailable for real adapter integration test")

    out = ensure_tmp_clean_dir(tmp_path / "docling_out")
    sem_path = built_pipeline_artifacts["paths"]["semantic_document"]
    res = run_cli(
        "pdf2md.utils.docling_adapter",
        str(sem_path),
        "--output-root",
        str(out),
        "--mode",
        "inspection",
        "--export-markdown",
        "--verbose",
    )
    assert res.returncode == 0, res.stderr
    dd = out / "docling_document.json"
    dr = out / "docling_relations.json"
    rp = out / "docling_adapter_report.json"
    assert dd.exists() and dr.exists() and rp.exists()
    preview = out / "docling_preview.md"
    rel = json.loads(dr.read_text(encoding="utf-8"))
    rep = json.loads(rp.read_text(encoding="utf-8"))
    assert rep.get("errors") == []
    if rep.get("markdown_exported"):
        assert preview.exists()
    assert "block:p0002_g0013" in rel.get("id_map", {})
    mapped_type = rel["id_map"]["block:p0002_g0013"].get("docling_type")
    if mapped_type not in {"picture", "text"}:
        pytest.fail(f"Unexpected mapping for block:p0002_g0013: {mapped_type}")
    if mapped_type == "text":
        assert any("degraded_block:block:p0002_g0013:figure->text" in w for w in rel.get("warnings", []) + rep.get("warnings", []))
    bad = rel.get("id_map", {}).get("block:p0002_g0001")
    if bad:
        assert bad.get("docling_type") != "picture"


def test_consensus_cli_config_resolution_contract(sample_pdf_path: Path, tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    repo_config = repo_root / "pdf2md.backends.toml"
    if not repo_config.exists():
        pytest.skip("Repo config pdf2md.backends.toml missing; cannot verify implicit consensus config resolution")

    default_out = tmp_path / "consensus_default.json"
    res_default = run_cli(
        "pdf2md.utils.consensus_report",
        str(sample_pdf_path),
        "--output",
        str(default_out),
        "--json-only",
        env_overrides={"PDF2MD_BACKENDS_CONFIG": None},
    )
    assert res_default.returncode == 0, res_default.stderr
    default_report = json.loads(default_out.read_text(encoding="utf-8"))
    assert Path(default_report["config_path"]).resolve() == repo_config.resolve()

    env_out = tmp_path / "consensus_env.json"
    res_env = run_cli(
        "pdf2md.utils.consensus_report",
        str(sample_pdf_path),
        "--output",
        str(env_out),
        "--json-only",
        env_overrides={"PDF2MD_BACKENDS_CONFIG": str(repo_config)},
    )
    assert res_env.returncode == 0, res_env.stderr
    env_report = json.loads(env_out.read_text(encoding="utf-8"))
    assert Path(env_report["config_path"]).resolve() == repo_config.resolve()

    explicit_out = tmp_path / "consensus_explicit.json"
    res_explicit = run_cli(
        "pdf2md.utils.consensus_report",
        str(sample_pdf_path),
        "--config",
        str(repo_config),
        "--output",
        str(explicit_out),
        "--json-only",
    )
    assert res_explicit.returncode == 0, res_explicit.stderr
    explicit_report = json.loads(explicit_out.read_text(encoding="utf-8"))
    assert Path(explicit_report["config_path"]).resolve() == repo_config.resolve()

    missing_out = tmp_path / "consensus_missing.json"
    missing_cfg = tmp_path / "does-not-exist.backends.toml"
    res_missing = run_cli(
        "pdf2md.utils.consensus_report",
        str(sample_pdf_path),
        "--config",
        str(missing_cfg),
        "--output",
        str(missing_out),
        "--json-only",
    )
    assert res_missing.returncode != 0
    assert "Backend config not found at --config path" in (res_missing.stderr + res_missing.stdout)
