from __future__ import annotations

import hashlib
import json
import platform
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_manifest(*, output_path: Path, payload: dict) -> None:
    payload = dict(payload)
    payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
    payload.setdefault("hostname", socket.gethostname())
    payload.setdefault("python_version", platform.python_version())
    try:
        payload.setdefault("git_sha", subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
    except Exception:
        payload.setdefault("git_sha", None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
