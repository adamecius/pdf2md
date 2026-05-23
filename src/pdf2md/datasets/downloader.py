"""Git-based external dataset downloader (Additional Plan 1, Task A2).

Clones a dataset from its registry-configured URL into a temporary
directory, applies the dataset's ``keep_paths`` / ``exclude_paths``
filtering rules, and atomically renames the result into
``groundtruth/external/<dataset>/upstream/``.

Tests in ``tests/test_dataset_downloader.py`` use local-only git fixtures
created via ``git init`` + ``git commit`` in a temp directory — there are
no network calls.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pdf2md.datasets.registry import DatasetEntry, DatasetStatus, get_dataset


@dataclass(frozen=True)
class DownloadResult:
    """Outcome of a single dataset download."""

    dataset_id: str
    output_path: Path
    resolved_commit: str | None
    ref_used: str | None
    success: bool
    error_message: str | None = None


GitRunner = Callable[[list[str], Path | None], subprocess.CompletedProcess[str]]


def _default_git_runner(cmd: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )


def _require_git(git_runner: GitRunner | None) -> None:
    """Ensure git is on PATH unless an explicit runner is provided.

    Tests supply ``git_runner`` to avoid touching the system git.
    """

    if git_runner is not None:
        return
    if not shutil.which("git"):
        raise RuntimeError(
            "git was not found on PATH. Install git and retry. "
            "This script does not install external dependencies."
        )


def _apply_keep_filter(clone_dir: Path, dataset: DatasetEntry) -> None:
    """Remove anything in ``clone_dir`` that is not in ``keep_paths``.

    ``keep_paths`` containing ``"."`` means "keep everything" — no
    filtering happens. ``exclude_paths`` are then removed regardless of
    whether they would have been kept.
    """

    keep_paths = list(dataset.keep_paths)
    if "." not in keep_paths:
        keep_resolved = {(clone_dir / p).resolve() for p in keep_paths}
        # Always preserve .git so we can read the resolved commit. It's
        # removed at the very end, after manifests are generated, by the
        # caller in the typical workflow; here we just don't strip it.
        keep_resolved.add((clone_dir / ".git").resolve())

        for entry in sorted(clone_dir.iterdir()):
            if entry.resolved() if hasattr(entry, "resolved") else entry.resolve() not in keep_resolved:  # noqa: SIM103
                _remove(entry)

    for path in dataset.exclude_paths:
        target = clone_dir / path
        if target.exists():
            _remove(target)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _resolve_commit(clone_dir: Path, git_runner: GitRunner) -> str | None:
    cp = git_runner(["git", "rev-parse", "HEAD"], clone_dir)
    if cp.returncode != 0:
        return None
    return (cp.stdout or "").strip() or None


def _strip_git_dir(clone_dir: Path) -> None:
    git_dir = clone_dir / ".git"
    if git_dir.exists():
        _remove(git_dir)


def download_dataset(
    name_or_alias: str,
    *,
    output_root: Path,
    ref: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    git_runner: GitRunner | None = None,
    keep_git_dir: bool = False,
) -> DownloadResult:
    """Download one dataset.

    Args:
        name_or_alias: registry id or alias of the dataset.
        output_root: parent directory under which ``<dataset>/upstream/``
            will be created.
        ref: git branch or commit to check out. Defaults to the dataset's
            ``default_ref``.
        force: if true, replace an existing ``<dataset>/`` directory.
        dry_run: if true, return a result describing what would be done
            without touching the filesystem or running git.
        git_runner: subprocess-compatible callable used by the tests to
            inject a local-only git fixture. Defaults to a real git call.
        keep_git_dir: if true, retain the ``.git`` directory inside the
            installed dataset. Default removes it after recording the
            resolved commit.

    Returns:
        :class:`DownloadResult`. On failure, ``success`` is False and
        ``error_message`` is populated; no exception is raised for the
        common cases (missing git binary still raises so the caller can
        differentiate environment issues from per-dataset failures).
    """

    dataset = get_dataset(name_or_alias)

    if dataset.status is DatasetStatus.NOT_AVAILABLE:
        return DownloadResult(
            dataset_id=dataset.id,
            output_path=Path(output_root) / dataset.id,
            resolved_commit=None,
            ref_used=None,
            success=False,
            error_message=(
                f"Dataset {dataset.id!r} is not yet available for download "
                f"({dataset.description or 'see registry'})."
            ),
        )

    effective_ref = ref or dataset.default_ref or "main"
    output_root = Path(output_root)
    dataset_dir = output_root / dataset.id
    upstream_dir = dataset_dir / "upstream"

    if dry_run:
        return DownloadResult(
            dataset_id=dataset.id,
            output_path=dataset_dir,
            resolved_commit=None,
            ref_used=effective_ref,
            success=True,
            error_message=None,
        )

    _require_git(git_runner)
    runner = git_runner or _default_git_runner

    if dataset_dir.exists():
        if not force:
            return DownloadResult(
                dataset_id=dataset.id,
                output_path=dataset_dir,
                resolved_commit=None,
                ref_used=effective_ref,
                success=False,
                error_message=(
                    f"Output directory {dataset_dir} already exists. "
                    f"Pass --force to replace it."
                ),
            )
        _remove(dataset_dir)

    output_root.mkdir(parents=True, exist_ok=True)
    tmp_parent = tempfile.mkdtemp(prefix=f"{dataset.id}_clone_", dir=str(output_root))
    tmp_clone = Path(tmp_parent) / "clone"

    try:
        # For branch-style refs, shallow-clone for speed. For commit-style
        # refs (40-char hex), clone unshallowed then checkout.
        is_commit_ref = len(effective_ref) == 40 and all(
            c in "0123456789abcdefABCDEF" for c in effective_ref
        )
        if is_commit_ref:
            clone_cmd = ["git", "clone", dataset.url, str(tmp_clone)]
        else:
            clone_cmd = [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                effective_ref,
                dataset.url,
                str(tmp_clone),
            ]
        cp = runner(clone_cmd, None)
        if cp.returncode != 0:
            return DownloadResult(
                dataset_id=dataset.id,
                output_path=dataset_dir,
                resolved_commit=None,
                ref_used=effective_ref,
                success=False,
                error_message=(
                    f"git clone failed: {(cp.stderr or cp.stdout or '').strip()[:500]}"
                ),
            )
        if is_commit_ref:
            ck = runner(["git", "checkout", effective_ref], tmp_clone)
            if ck.returncode != 0:
                return DownloadResult(
                    dataset_id=dataset.id,
                    output_path=dataset_dir,
                    resolved_commit=None,
                    ref_used=effective_ref,
                    success=False,
                    error_message=(
                        f"git checkout {effective_ref} failed: "
                        f"{(ck.stderr or ck.stdout or '').strip()[:500]}"
                    ),
                )

        resolved_commit = _resolve_commit(tmp_clone, runner)
        _apply_keep_filter(tmp_clone, dataset)
        if not keep_git_dir:
            _strip_git_dir(tmp_clone)

        # Atomic move into place: rename tmp_clone -> dataset_dir/upstream
        dataset_dir.mkdir(parents=True, exist_ok=True)
        if upstream_dir.exists():
            _remove(upstream_dir)
        os.rename(str(tmp_clone), str(upstream_dir))

        return DownloadResult(
            dataset_id=dataset.id,
            output_path=dataset_dir,
            resolved_commit=resolved_commit,
            ref_used=effective_ref,
            success=True,
            error_message=None,
        )
    finally:
        # Clean up the tmp parent if it still exists (rename emptied it on
        # success; failure paths may leave it behind).
        if Path(tmp_parent).exists():
            shutil.rmtree(tmp_parent, ignore_errors=True)


__all__ = ["DownloadResult", "download_dataset"]
