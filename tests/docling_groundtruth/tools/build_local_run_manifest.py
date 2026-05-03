from __future__ import annotations

import argparse
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_stage_entries(stage_values: list[str]) -> dict:
    out = {}
    for item in stage_values:
        name, rc, log = item.split(":", 2)
        out[name] = {"returncode": int(rc), "log_path": log}
    return out


def git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--document-id", required=True)
    p.add_argument("--batch", required=True)
    p.add_argument("--input-pdf", required=True)
    p.add_argument("--source-tex", required=True)
    p.add_argument("--consensus-config", required=True)
    p.add_argument("--latex-engine", default=None)
    p.add_argument("--backend-command", action="append", default=[])
    p.add_argument("--stage", action="append", default=[])
    p.add_argument("--artifact", action="append", default=[])
    args = p.parse_args()

    artifacts = {}
    for item in args.artifact:
        key, val = item.split("=", 1)
        pth = Path(val)
        artifacts[key] = {"path": str(pth), "sha256": sha256_file(pth)}

    backend_cmds = {}
    for item in args.backend_command:
        k, v = item.split("=", 1)
        backend_cmds[k] = v

    payload = {
        "git_sha": git_sha(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "python_version": platform.python_version(),
        "document_id": args.document_id,
        "batch": args.batch,
        "latex_engine": args.latex_engine,
        "source_tex": {"path": args.source_tex, "sha256": sha256_file(Path(args.source_tex))},
        "input_pdf": {"path": args.input_pdf, "sha256": sha256_file(Path(args.input_pdf))},
        "consensus_config": {"path": args.consensus_config, "sha256": sha256_file(Path(args.consensus_config))},
        "backend_commands": backend_cmds,
        "stage_status": parse_stage_entries(args.stage),
        "artifacts": artifacts,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
