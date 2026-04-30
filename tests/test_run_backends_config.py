from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.backends.runner import derive_run_name, run_configured_backends, validate_safe_run_name
from pdf2md.config import get_enabled_backends, load_backend_config


def _load_module_by_path(script: Path, name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_deepseek_module():
    return _load_module_by_path(Path("backend/deepseek/pdf2md_deepseek.py"), "pdf2md_deepseek_local")


def _config_text() -> str:
    return """
[settings]
work_dir = ".tmp"
default_timeout_seconds = 60
stop_on_failure = true

[backends.mineru]
enabled = true
runner = "conda"
env_name = "pdf2md-mineru"
script = "backend/mineru/pdf2md_mineru.py"

[backends.deepseek]
enabled = false
runner = "conda"
env_name = "pdf2md-deepseek"
script = "backend/deepseek/pdf2md_deepseek.py"
""".strip()


def test_safe_run_names() -> None:
    assert validate_safe_run_name("test") == "test"
    assert validate_safe_run_name("book_01") == "book_01"
    assert validate_safe_run_name("chapter-2") == "chapter-2"
    with pytest.raises(ValueError):
        validate_safe_run_name("my book")
    with pytest.raises(ValueError):
        validate_safe_run_name("../book")


def test_config_loading_and_enabled_selection(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    enabled = get_enabled_backends(config)
    assert "mineru" in enabled
    assert "deepseek" not in enabled


def test_dry_run_creates_manifest_and_does_not_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    called = {"run": False}

    def _fake_run(*args, **kwargs):
        called["run"] = True
        raise AssertionError("subprocess.run should not be called in dry-run")

    monkeypatch.setattr("pdf2md.backends.runner.subprocess.run", _fake_run)

    rc = run_configured_backends(
        input_pdf=pdf,
        config=config,
        repo_root=Path.cwd(),
        work_dir_override=tmp_path / ".tmp",
        dry_run=True,
    )
    assert rc == 0
    assert called["run"] is False

    run_dir = tmp_path / ".tmp" / derive_run_name(pdf, None)
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "raw" / "mineru" / "command.json").exists()
    assert (run_dir / "raw" / "mineru" / "status.json").exists()

    status = json.loads((run_dir / "raw" / "mineru" / "status.json").read_text(encoding="utf-8"))
    assert status["dry_run"] is True
    assert status["success"] is None


def test_missing_input_pdf_fails(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    with pytest.raises(ValueError):
        run_configured_backends(
            input_pdf=tmp_path / "missing.pdf",
            config=config,
            repo_root=Path.cwd(),
            work_dir_override=tmp_path / ".tmp",
            dry_run=True,
        )


def test_existing_run_dir_requires_force(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    run_dir = tmp_path / ".tmp" / "test"
    run_dir.mkdir(parents=True)

    with pytest.raises(ValueError):
        run_configured_backends(
            input_pdf=pdf,
            config=config,
            repo_root=Path.cwd(),
            work_dir_override=tmp_path / ".tmp",
            dry_run=True,
        )


def test_force_recreates_only_selected_run_dir(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.toml"
    cfg_file.write_text(_config_text(), encoding="utf-8")
    config = load_backend_config(cfg_file)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    base = tmp_path / ".tmp"
    keep_dir = base / "keep"
    keep_dir.mkdir(parents=True)
    (keep_dir / "marker.txt").write_text("keep", encoding="utf-8")

    target = base / "test"
    target.mkdir(parents=True)
    (target / "old.txt").write_text("old", encoding="utf-8")

    rc = run_configured_backends(
        input_pdf=pdf,
        config=config,
        repo_root=Path.cwd(),
        work_dir_override=base,
        dry_run=True,
        force=True,
    )
    assert rc == 0
    assert (keep_dir / "marker.txt").exists()
    assert not (target / "old.txt").exists()


def test_safe_model_dir_name() -> None:
    ds = _load_deepseek_module()
    assert ds.safe_model_dir_name("deepseek-ai/DeepSeek-OCR-2") == "deepseek-ai__DeepSeek-OCR-2"


def test_missing_model_without_allow_download_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ds = _load_deepseek_module()

    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    import sys

    old = sys.argv
    sys.argv = ["pdf2md_deepseek.py", "-i", str(pdf), "--models-dir", str(tmp_path / "models")]
    try:
        rc = ds.main()
    finally:
        sys.argv = old
    err = capsys.readouterr().err
    assert rc == 1
    assert "Looked in:" in err
    assert "--model-path" in err
    assert "PDF2MD_DEEPSEEK_MODEL" in err
    assert "--allow-download" in err


def test_allow_download_calls_explicit_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ds = _load_deepseek_module()

    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    model_dir = tmp_path / "models" / "deepseek-ai__DeepSeek-OCR-2"

    called = {"download": False, "model_path": None}

    def fake_download(*, model_id: str, models_dir: str) -> Path:
        called["download"] = True
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir

    def fake_run(ip, out_dir, model_path, dev, local_only=True):
        called["model_path"] = model_path
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        md = out_dir / "generated.md"
        md.write_text("ok", encoding="utf-8")
        return md, {}

    monkeypatch.setattr(ds, "explicit_download_model", fake_download)
    import types
    import sys

    fake_module = types.SimpleNamespace(run=fake_run)
    sys.modules["pdf_to_md_json"] = fake_module
    old = sys.argv
    sys.argv = [
        "pdf2md_deepseek.py",
        "-i",
        str(pdf),
        "--allow-download",
        "--models-dir",
        str(tmp_path / "models"),
    ]
    try:
        rc = ds.main()
    finally:
        sys.argv = old
        sys.modules.pop("pdf_to_md_json", None)
    assert rc == 0
    assert called["download"] is True
    assert called["model_path"] == str(model_dir)


def test_runner_maps_model_id_and_models_dir() -> None:
    from pdf2md.backends.runner import plan_backend_command

    cmd = plan_backend_command(
        repo_root=Path('/repo'),
        backend_name='deepseek',
        backend_cfg={
            'env_name': 'pdf2md-deepseek',
            'script': 'backend/deepseek/pdf2md_deepseek.py',
            'args': {'model_id': 'deepseek-ai/DeepSeek-OCR-2', 'models_dir': '.local_models/deepseek'},
        },
        input_pdf_abs=Path('/tmp/in.pdf'),
        raw_dir=Path('/tmp/raw/deepseek'),
    )
    assert '--model-id' in cmd
    assert 'deepseek-ai/DeepSeek-OCR-2' in cmd
    assert '--models-dir' in cmd
    assert '.local_models/deepseek' in cmd


def _load_mineru_wrapper_module():
    return _load_module_by_path(Path("backend/mineru/pdf2md_mineru.py"), "pdf2md_mineru_local")


def test_mineru_wrapper_help() -> None:
    import subprocess, sys

    r = subprocess.run([sys.executable, "backend/mineru/pdf2md_mineru.py", "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--start-page" in r.stdout


def test_mineru_wrapper_missing_pdf_fails() -> None:
    import subprocess, sys

    r = subprocess.run([sys.executable, "backend/mineru/pdf2md_mineru.py", "-i", "missing.pdf"], capture_output=True, text=True)
    assert r.returncode == 1
    assert "existing PDF file" in r.stderr


def test_mineru_parser_accepts_compat_flags() -> None:
    m = _load_mineru_wrapper_module()
    args = m.build_parser().parse_args([
        "-i", "x.pdf", "-o", "x.md", "--json-out", "x.json", "--out-dir", "tmp", "--lang", "en",
        "--device", "cpu", "--model-path", "/m", "--api", "--backend", "pipeline", "--api-url", "http://127.0.0.1:8000",
        "--no-formula", "--no-table", "--start-page", "1", "--end-page", "2",
    ])
    assert args.input == "x.pdf"
    assert args.output == "x.md"
    assert args.start_page == 1
    assert args.end_page == 2


def test_mineru_form_data_compat_supports_optional_server_url() -> None:
    mfd = _load_module_by_path(Path("backend/mineru/mineru_form_data.py"), "mineru_form_data_local")
    build_parse_request_form_data_compat = mfd.build_parse_request_form_data_compat

    class ClientWithServer:
        def build_parse_request_form_data(self, **kwargs):
            return kwargs

    class ClientNoServer:
        def build_parse_request_form_data(self, lang_list, backend, parse_method, formula_enable, table_enable, start_page_id, end_page_id, return_md, return_content_list, return_middle_json, return_model_output, return_images, response_format_zip, return_original_file):
            return locals()

    out1 = build_parse_request_form_data_compat(
        ClientWithServer(), language="en", backend="pipeline", formula=True, table=True, start_page=3, end_page=8, server_url="http://x"
    )
    assert out1["start_page_id"] == 3
    assert out1["end_page_id"] == 8

    out2 = build_parse_request_form_data_compat(
        ClientNoServer(), language="en", backend="pipeline", formula=True, table=True, start_page=0, end_page=None, server_url="http://x"
    )
    assert out2["start_page_id"] == 0
    assert out2["end_page_id"] is None
    assert "server_url" not in out2


def test_no_enabled_backends_fails_early(tmp_path: Path) -> None:
    cfg = {
        "settings": {"work_dir": ".tmp"},
        "backends": {
            "mineru": {"enabled": False, "runner": "conda", "env_name": "x", "script": "backend/mineru/pdf2md_mineru.py"}
        },
    }
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(ValueError, match="No enabled backends found"):
        run_configured_backends(input_pdf=pdf, config=cfg, repo_root=Path.cwd(), work_dir_override=tmp_path / ".tmp", dry_run=True)


def test_deepseek_default_model_path() -> None:
    ds = _load_deepseek_module()
    p = ds.default_model_path("deepseek-ai/DeepSeek-OCR-2", ".local_models/deepseek")
    assert str(p).endswith(".local_models/deepseek/deepseek-ai__DeepSeek-OCR-2")


def test_paddleocr_wrapper_help_and_errors(tmp_path: Path) -> None:
    import subprocess, sys

    h = subprocess.run([sys.executable, "backend/paddleocr/pdf2md_paddleocr.py", "--help"], capture_output=True, text=True)
    assert h.returncode == 0
    m = subprocess.run([sys.executable, "backend/paddleocr/pdf2md_paddleocr.py", "-i", "missing.pdf"], capture_output=True, text=True)
    assert m.returncode == 1

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    a = subprocess.run([sys.executable, "backend/paddleocr/pdf2md_paddleocr.py", "-i", str(pdf), "--api"], capture_output=True, text=True)
    assert a.returncode == 1
    d = subprocess.run([sys.executable, "backend/paddleocr/pdf2md_paddleocr.py", "-i", str(pdf), "--allow-download"], capture_output=True, text=True)
    assert d.returncode == 1


def test_paddleocr_command_mapping_and_json_extraction(tmp_path: Path) -> None:
    pmod = _load_module_by_path(Path("backend/paddleocr/pdf2md_paddleocr.py"), "paddle_local")
    base = pmod.plan_paddleocr_command(Path("/in.pdf"), Path("/out"), "en", "auto")
    assert "--device" not in base
    cpu = pmod.plan_paddleocr_command(Path("/in.pdf"), Path("/out"), "en", "cpu")
    assert cpu[-2:] == ["--device", "cpu"]
    gpu = pmod.plan_paddleocr_command(Path("/in.pdf"), Path("/out"), "en", "cuda")
    assert gpu[-2:] == ["--device", "gpu:0"]

    out = tmp_path / "out"
    out.mkdir()
    (out / "a.json").write_text('{"result": [{"rec_text": "hello"}, {"text": "world"}]}', encoding="utf-8")
    lines = pmod.extract_text_from_json_files(out)
    assert "hello" in lines and "world" in lines


def test_deepseek_allow_download_still_runs_local_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ds = _load_deepseek_module()
    pdf = tmp_path / "t.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    model_dir = tmp_path / "models" / "deepseek-ai__DeepSeek-OCR-2"

    called = {"local_only": None}

    def fake_download(*, model_id: str, models_dir: str) -> Path:
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir

    def fake_run(ip, out_dir, model_path, dev, local_only=True):
        called["local_only"] = local_only
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        md = out_dir / "generated.md"
        md.write_text("ok", encoding="utf-8")
        return md, {}

    monkeypatch.setattr(ds, "explicit_download_model", fake_download)
    import types, sys

    sys.modules["pdf_to_md_json"] = types.SimpleNamespace(run=fake_run)
    old = sys.argv
    sys.argv = ["pdf2md_deepseek.py", "-i", str(pdf), "--allow-download", "--models-dir", str(tmp_path / "models")]
    try:
        rc = ds.main()
    finally:
        sys.argv = old
        sys.modules.pop("pdf_to_md_json", None)
    assert rc == 0
    assert called["local_only"] is True
