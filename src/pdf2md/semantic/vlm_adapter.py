"""Subprocess adapter for the DeepSeek-VL2 semantic backend.

DeepSeek-VL2 requires PyTorch + transformers + accelerate, which live
only inside the isolated ``pdf2md-deepseek-vl2`` conda env (per
Plan 005_0). The adapter therefore invokes
``backend/semantic/deepseek_vl2/smoke_test.py`` via subprocess and parses
the resulting JSON, mirroring the pattern used by ``pipeline.runner`` for
extraction backends.

The adapter does NOT import ``torch`` or ``transformers`` from the main
``pdf2md`` env, by design.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from pdf2md.models.cross_ref import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefMarker,
    RefType,
)
from pdf2md.semantic.base import SemanticBackend


BACKEND_NAME = "vlm"
BACKEND_VERSION = "0.1.0"
CONDA_ENV_NAME = "pdf2md-deepseek-vl2"


def _backend_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[3] / "backend" / "semantic" / "deepseek_vl2"


def _smoke_test_path() -> Path:
    return _backend_root() / "smoke_test.py"


def _conda_available() -> bool:
    return shutil.which("conda") is not None


def _conda_env_exists(env_name: str) -> bool:
    """Return True iff ``conda env list`` mentions ``env_name``."""
    if not _conda_available():
        return False
    try:
        result = subprocess.run(
            ["conda", "env", "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        token = line.split()[0]
        if token == env_name:
            return True
    return False


def _hash_image(image_path: Path) -> str:
    sha = hashlib.sha256()
    with image_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


def _marker_dict_to_model(
    raw: dict[str, Any],
    source_ref: str,
) -> RefMarker | None:
    """Convert a raw marker dict from the VLM into a :class:`RefMarker`.

    The VLM emits JSON with keys ``marker_type``, ``marker_text``, and
    optionally ``page_no`` / ``char_offset``. Missing offsets fall back
    to ``(0, len(marker_text))``.
    """
    try:
        marker_type = RefType(raw.get("marker_type", ""))
    except ValueError:
        return None
    marker_text = str(raw.get("marker_text") or "").strip()
    if not marker_text:
        return None
    raw_offset = raw.get("char_offset")
    if isinstance(raw_offset, (list, tuple)) and len(raw_offset) == 2:
        offset = (int(raw_offset[0]), int(raw_offset[1]))
    else:
        offset = (0, len(marker_text))
    confidence_raw = raw.get("confidence", 0.8)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.8
    confidence = max(0.0, min(1.0, confidence))
    return RefMarker(
        source_ref=source_ref,
        marker_text=marker_text,
        marker_type=marker_type,
        char_offset=offset,
        confidence=confidence,
        backend=BACKEND_NAME,
    )


class VlmSemanticBackend(SemanticBackend):
    """Subprocess adapter for the DeepSeek-VL2 backend.

    Runs the standalone smoke_test.py via
    ``conda run -n pdf2md-deepseek-vl2 python ...``. The adapter does not
    create or modify the conda env; it only consumes it.
    """

    def __init__(
        self,
        env_name: str = CONDA_ENV_NAME,
        source_ref: str = "#/document",
        timeout_s: int = 600,
    ) -> None:
        """Initialise the adapter.

        Args:
            env_name: Conda environment that owns the VLM runtime.
            source_ref: JSON pointer stamped on every emitted marker.
            timeout_s: Subprocess timeout for one VLM inference call.
                Defaults to ten minutes (model load + one page).
        """
        self._env_name = env_name
        self._source_ref = source_ref
        self._timeout_s = timeout_s

    def name(self) -> str:
        return BACKEND_NAME

    def version(self) -> str:
        return BACKEND_VERSION

    def is_available(self) -> bool:
        if not _smoke_test_path().is_file():
            return False
        return _conda_env_exists(self._env_name)

    def extract(
        self,
        pdf_path: Path | None,
        text: str | None,
        output_dir: Path,
    ) -> CrossReferenceGraph:
        del text
        if pdf_path is None or not pdf_path.is_file():
            raise ValueError(
                "VlmSemanticBackend.extract requires an existing image path "
                "in pdf_path (the VLM consumes a rendered page image, not a raw PDF)"
            )
        if not self.is_available():
            raise RuntimeError(
                f"VLM backend not available: conda env {self._env_name!r} "
                "or backend/semantic/deepseek_vl2/smoke_test.py is missing"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "conda",
            "run",
            "-n",
            self._env_name,
            "--no-capture-output",
            "python",
            str(_smoke_test_path()),
            "--image",
            str(pdf_path),
            "--out-dir",
            str(output_dir),
        ]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"VLM subprocess timed out after {self._timeout_s}s"
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"VLM subprocess exited with {result.returncode}: "
                f"stderr={result.stderr.strip()[:500]}"
            )

        smoke_json = output_dir / "vlm_smoke_result.json"
        if not smoke_json.is_file():
            raise RuntimeError(
                f"VLM subprocess succeeded but did not write {smoke_json}"
            )
        smoke = json.loads(smoke_json.read_text(encoding="utf-8"))

        markers: list[RefMarker] = []
        for raw in smoke.get("markers", []) or []:
            if not isinstance(raw, dict):
                continue
            marker = _marker_dict_to_model(raw, self._source_ref)
            if marker is not None:
                markers.append(marker)

        return CrossReferenceGraph(
            schema_version=CROSS_REF_SCHEMA_VERSION,
            doc_hash=_hash_image(pdf_path),
            markers=markers,
            edges=[],
            entities=[],
            backend_versions={
                BACKEND_NAME: str(smoke.get("backend_version") or BACKEND_VERSION),
            },
        )


__all__ = ["VlmSemanticBackend", "BACKEND_NAME", "BACKEND_VERSION", "CONDA_ENV_NAME"]


if __name__ == "__main__":  # pragma: no cover — diagnostic helper
    backend = VlmSemanticBackend()
    print(
        json.dumps(
            {
                "available": backend.is_available(),
                "env": CONDA_ENV_NAME,
                "smoke_test": str(_smoke_test_path()),
            },
            indent=2,
        )
    )
    sys.exit(0)
