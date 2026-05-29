"""Subprocess adapter for the DeepSeek-VL2 semantic backend.

DeepSeek-VL2 requires PyTorch + transformers + accelerate, which live
only inside the isolated ``pdf2md-deepseek-vl2`` conda env (per
Plan 005_0). The adapter therefore invokes
``backend/semantic/deepseek_vl2/connector.py`` via subprocess —
mirroring the OCR-backend ``connect()`` convention and the
``pipeline.runner`` pattern for extraction backends.

The adapter does NOT import ``torch`` or ``transformers`` from the main
``pdf2md`` env, by design.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from pdf2md.models.cross_ref import CrossReferenceGraph
from pdf2md.semantic.base import SemanticBackend

BACKEND_NAME = "vlm"
BACKEND_VERSION = "0.1.0"
CONDA_ENV_NAME = "pdf2md-deepseek-vl2"


def _backend_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[3] / "backend" / "semantic" / "deepseek_vl2"


def _smoke_test_path() -> Path:
    return _backend_root() / "smoke_test.py"


def _connector_path() -> Path:
    return _backend_root() / "connector.py"


def _conda_available() -> bool:
    return shutil.which("conda") is not None


def _conda_env_exists(env_name: str) -> bool:
    """Return True iff ``conda env list`` mentions ``env_name``."""
    return _conda_env_python(env_name) is not None


def _conda_env_python(env_name: str) -> Path | None:
    """Return the absolute path to ``<env_name>``'s ``bin/python``.

    Used in preference to ``conda run -n`` because the latter is
    unreliable on some hosts — observed on the dev machine where
    ``conda run -n pdf2md-deepseek-vl2 python -c 'import sys;
    print(sys.executable)'`` reports the *outer* shell's Python, not
    the env's. Calling the env's python binary directly avoids the
    ambiguity entirely.
    """
    if not _conda_available():
        return None
    try:
        result = subprocess.run(
            ["conda", "env", "list", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        import json as _json
        envs = _json.loads(result.stdout).get("envs", [])
    except (ValueError, KeyError):
        return None
    for env_path in envs:
        path = Path(env_path)
        if path.name != env_name:
            continue
        py = path / "bin" / "python"
        if py.is_file():
            return py
        # Windows fallback (uncommon on the dev host but keep it cheap).
        py_win = path / "Scripts" / "python.exe"
        if py_win.is_file():
            return py_win
    return None


class VlmSemanticBackend(SemanticBackend):
    """Subprocess adapter for the DeepSeek-VL2 backend.

    Shells out to ``backend/semantic/deepseek_vl2/connector.py`` (the
    Plan-005-2 connector, same convention as the OCR backends) inside
    the ``pdf2md-deepseek-vl2`` conda env. The adapter does not create
    or modify the conda env; it only consumes it.
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
        """Return the canonical backend identifier (``"vlm"``)."""
        return BACKEND_NAME

    def version(self) -> str:
        """Return the pinned backend version string."""
        return BACKEND_VERSION

    def is_available(self) -> bool:
        """Return whether the isolated VL2 conda env + connector exist.

        Cheap: only checks the connector script's presence and that
        ``conda env list`` shows ``pdf2md-deepseek-vl2``. The actual
        model load is deferred to :meth:`extract`.
        """
        if not _connector_path().is_file():
            return False
        return _conda_env_exists(self._env_name)

    def extract(
        self,
        pdf_path: Path | None,
        text: str | None,
        output_dir: Path,
    ) -> CrossReferenceGraph:
        """Run DeepSeek-VL2 on a single page image and return its graph.

        The backend is invoked as a subprocess inside its dedicated
        conda env (``pdf2md-deepseek-vl2``) so torch / transformers
        stay isolated from the main pdf2md env.

        Args:
            pdf_path: Path to a rendered page image (PNG/JPG). The
                parameter is called ``pdf_path`` for compatibility with
                the :class:`SemanticBackend` ABC — the VLM consumes
                images, not raw PDFs.
            text: Ignored.
            output_dir: Directory the connector writes its
                ``cross_references.json`` to.

        Returns:
            The :class:`CrossReferenceGraph` produced by the standalone
            VL2 connector.

        Raises:
            ValueError: When ``pdf_path`` is missing or not a file.
            RuntimeError: When the conda env or connector script is
                missing, when the env's python binary can't be found,
                or when the subprocess exits non-zero.
        """
        del text
        if pdf_path is None or not pdf_path.is_file():
            raise ValueError(
                "VlmSemanticBackend.extract requires an existing image path "
                "in pdf_path (the VLM consumes a rendered page image, not a raw PDF)"
            )
        if not self.is_available():
            raise RuntimeError(
                f"VLM backend not available: conda env {self._env_name!r} "
                "or backend/semantic/deepseek_vl2/connector.py is missing"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        env_python = _conda_env_python(self._env_name)
        if env_python is None:
            raise RuntimeError(
                f"VLM backend not available: conda env {self._env_name!r} "
                "exists but its python binary could not be located",
            )
        # Shell out to the backend's `connector.py` (NOT smoke_test.py).
        # The connector is the single source of truth and matches the
        # OCR-backend convention (`backend/<name>/connector.py`).
        # `connector.py --raw-dir <dir> --document-id <id> --out-dir
        # <out> --image <path>` writes the graph to `<out>/vlm/
        # cross_references.json` and exits 0 on success, 1 on real
        # failure, 2 on bad input, 3 on env_not_ready.
        #
        # The connector requires `pdf2md` on its sys.path so it can
        # import `pdf2md.connectors.common` and `pdf2md.models.cross_ref`.
        # The connector itself prepends `<repo>/src` via a sys.path
        # insert at the top of the file, so no PYTHONPATH wrangling
        # needed here.
        cmd = [
            str(env_python),
            str(_connector_path()),
            "--raw-dir",
            str(pdf_path.parent),
            "--document-id",
            pdf_path.stem,
            "--out-dir",
            str(output_dir),
            "--image",
            str(pdf_path),
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
                f"VLM connector exited with {result.returncode}: "
                f"stderr={result.stderr.strip()[:500]}"
            )

        graph_json = output_dir / BACKEND_NAME / "cross_references.json"
        if not graph_json.is_file():
            raise RuntimeError(
                f"VLM connector succeeded but did not write {graph_json}"
            )
        return CrossReferenceGraph.model_validate_json(
            graph_json.read_text(encoding="utf-8"),
        )


__all__ = ["BACKEND_NAME", "BACKEND_VERSION", "CONDA_ENV_NAME", "VlmSemanticBackend"]


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
