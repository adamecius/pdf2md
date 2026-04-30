from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pdf2md.config import get_enabled_backends

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_safe_run_name(name: str) -> str:
    if not name or name in {".", ".."} or len(name) > 120 or not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f'Cannot derive a safe run directory from input filename: "{name}"\n'
            "Allowed characters: letters, numbers, dot, underscore, hyphen.\n"
            "Rename the file or pass --run-name SAFE_NAME."
        )
    return name


def derive_run_name(input_pdf: Path, override: str | None) -> str:
    return validate_safe_run_name(override if override is not None else input_pdf.stem)


def plan_backend_command(repo_root: Path, backend_name: str, backend_cfg: dict, input_pdf_abs: Path, raw_dir: Path) -> list[str]:
    cmd = [
        "conda",
        "run",
        "-n",
        backend_cfg["env_name"],
        "--cwd",
        str(repo_root),
        "--",
        "python",
        backend_cfg["script"],
        "-i",
        str(input_pdf_abs),
        "-o",
        str(raw_dir / "output.md"),
        "--json-out",
        str(raw_dir / "manifest.json"),
        "--out-dir",
        str(raw_dir),
    ]
    args = backend_cfg.get("args", {})
    mapping = {"lang": "--lang", "device": "--device", "model_path": "--model-path", "model_id": "--model-id", "models_dir": "--models-dir"}
    for key, flag in mapping.items():
        if key in args:
            cmd.extend([flag, str(args[key])])
    if args.get("api") is True:
        cmd.append("--api")
    if args.get("allow_download") is True:
        cmd.append("--allow-download")
    cmd.extend(str(x) for x in backend_cfg.get("extra_args", []))
    return cmd


def run_configured_backends(
    *,
    input_pdf: Path,
    config: dict,
    repo_root: Path,
    work_dir_override: Path | None = None,
    run_name_override: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    timeout_override: int | None = None,
    keep_going: bool = False,
) -> int:
    if not input_pdf.exists():
        raise ValueError(f"Input PDF does not exist: {input_pdf}")
    if not input_pdf.is_file():
        raise ValueError(f"Input path is not a file: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input file must have .pdf extension: {input_pdf}")

    settings = config.get("settings", {})
    work_dir = work_dir_override or Path(settings.get("work_dir", ".tmp"))
    timeout = timeout_override or int(settings.get("default_timeout_seconds", 3600))
    stop_on_failure = bool(settings.get("stop_on_failure", True)) and not keep_going

    run_name = derive_run_name(input_pdf=input_pdf, override=run_name_override)
    run_dir = work_dir / run_name

    if run_dir.exists() and not force:
        raise ValueError(f"Run directory already exists: {run_dir}. Pass --force to overwrite.")
    if run_dir.exists() and force:
        shutil.rmtree(run_dir)

    input_dir = run_dir / "input"
    raw_root = run_dir / "raw"
    input_dir.mkdir(parents=True, exist_ok=True)
    raw_root.mkdir(parents=True, exist_ok=True)

    input_copy = input_dir / input_pdf.name
    shutil.copy2(input_pdf, input_copy)
    input_pdf_abs = input_copy.resolve()

    enabled = get_enabled_backends(config)
    run_manifest = {"run_name": run_name, "input_pdf": str(input_pdf_abs), "backends": list(enabled.keys()), "dry_run": dry_run}
    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    any_failures = False
    for backend_name, backend_cfg in enabled.items():
        backend_dir = raw_root / backend_name
        backend_dir.mkdir(parents=True, exist_ok=True)

        command = plan_backend_command(repo_root, backend_name, backend_cfg, input_pdf_abs, backend_dir)
        env = os.environ.copy()
        env.update({k: str(v) for k, v in backend_cfg.get("env", {}).items()})

        command_payload = {
            "backend": backend_name,
            "command": command,
            "env": {k: "***" for k in backend_cfg.get("env", {}).keys()},
        }
        (backend_dir / "command.json").write_text(json.dumps(command_payload, indent=2), encoding="utf-8")

        status_path = backend_dir / "status.json"
        if dry_run:
            print(f"[dry-run] {backend_name}: {' '.join(command)}")
            status_path.write_text(
                json.dumps({"backend": backend_name, "dry_run": True, "success": None}, indent=2), encoding="utf-8"
            )
            continue

        started = datetime.now(UTC)
        result = subprocess.run(
            command,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        finished = datetime.now(UTC)

        (backend_dir / "stdout.log").write_text(result.stdout or "", encoding="utf-8")
        (backend_dir / "stderr.log").write_text(result.stderr or "", encoding="utf-8")

        success = result.returncode == 0
        status = {
            "backend": backend_name,
            "returncode": result.returncode,
            "success": success,
            "output_md": str(backend_dir / "output.md"),
            "manifest_json": str(backend_dir / "manifest.json"),
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": (finished - started).total_seconds(),
        }
        status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

        if not success:
            any_failures = True
            if stop_on_failure:
                break

    return 1 if any_failures else 0
