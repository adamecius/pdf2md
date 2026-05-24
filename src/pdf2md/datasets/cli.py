"""Typer subcommand group for external dataset workflows (Additional Plan 1, A4).

Wires :mod:`pdf2md.datasets.registry`, :mod:`pdf2md.datasets.downloader`,
and :mod:`pdf2md.datasets.manifest` behind ``pdf2md datasets ...``.

Subcommands:

- ``pdf2md datasets list``
- ``pdf2md datasets install <name>`` (also ``install all``)
- ``pdf2md datasets status``
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pdf2md.datasets.downloader import DownloadResult, download_dataset
from pdf2md.datasets.manifest import (
    INSTALLED,
    generate_dataset_manifest,
    update_global_index,
)
from pdf2md.datasets.registry import DatasetStatus, get_dataset, list_datasets

DATASETS_DEFAULT_OUTPUT = Path("groundtruth/external")
INDEX_DEFAULT_PATH = Path("groundtruth/manifest/external_datasets.json")

NOT_IMPLEMENTED_PLAN_18_MSG = (
    "Not implemented in Additional Plan 1. See Plan 18 for compilation work."
)

datasets_app = typer.Typer(
    name="datasets",
    help="Manage external ground-truth dataset downloads and manifests.",
    no_args_is_help=True,
)


def _status_for(entry) -> str:
    if entry.status is DatasetStatus.NOT_AVAILABLE:
        return "not_available"
    return "available"


def _read_index(index_path: Path) -> dict:
    if not index_path.is_file():
        return {"datasets": []}
    try:
        return dict(json.loads(index_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {"datasets": []}


def _installed_ids(index_path: Path) -> set[str]:
    payload = _read_index(index_path)
    return {
        d["id"]
        for d in payload.get("datasets", [])
        if isinstance(d, dict)
        and d.get("status") == INSTALLED
        and isinstance(d.get("id"), str)
    }


@datasets_app.command("list")
def list_command(
    output: Path = typer.Option(
        DATASETS_DEFAULT_OUTPUT,
        "--output",
        help="Root directory under which dataset directories live.",
    ),
) -> None:
    """Print all registered datasets with id, aliases, licence, and status."""

    index_path = INDEX_DEFAULT_PATH
    installed = _installed_ids(index_path)

    for entry in list_datasets():
        status = _status_for(entry)
        if entry.id in installed:
            status = INSTALLED
        elif (output / entry.id / "upstream").is_dir():
            # Installed on disk but not yet indexed (e.g. fresh manifest-only run).
            status = INSTALLED
        aliases = ", ".join(entry.aliases) if entry.aliases else "(none)"
        typer.echo(
            f"{entry.id}\taliases={aliases}\tlicence={entry.licence or '(unknown)'}\tstatus={status}"
        )


def _run_install_one(
    *,
    name: str,
    output: Path,
    ref: str | None,
    force: bool,
    dry_run: bool,
    manifest_only: bool,
) -> int:
    """Internal: install one dataset. Returns process-style exit code."""

    try:
        entry = get_dataset(name)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        return 1

    if entry.status is DatasetStatus.NOT_AVAILABLE:
        typer.echo(
            f"Dataset {entry.id} is not yet available for download "
            f"({entry.description or 'see registry'}).",
            err=True,
        )
        return 1

    output.mkdir(parents=True, exist_ok=True)
    dataset_dir = output / entry.id

    if dry_run:
        typer.echo(
            f"[dry-run] dataset_id={entry.id} source_url={entry.url} "
            f"ref={ref or entry.default_ref or 'main'} output={dataset_dir} "
            f"keep={list(entry.keep_paths)} exclude={list(entry.exclude_paths)} "
            f"force_required={(dataset_dir.exists() and not force)}"
        )
        return 0

    resolved_commit: str | None = None
    if manifest_only:
        # Skip clone; we just regenerate manifests from existing upstream/.
        if not (dataset_dir / "upstream").is_dir():
            typer.echo(
                f"--manifest-only requested but {dataset_dir / 'upstream'} does not exist.",
                err=True,
            )
            return 1
        try:
            meta = generate_dataset_manifest(
                dataset_dir=dataset_dir,
                name_or_alias=entry.id,
            )
        except Exception as exc:
            typer.echo(f"manifest generation failed: {exc}", err=True)
            return 1
        update_global_index(
            index_path=INDEX_DEFAULT_PATH,
            dataset_meta=meta,
            external_root=output,
        )
        typer.echo(f"manifest-only refresh complete: {entry.id}")
        return 0

    result: DownloadResult = download_dataset(
        entry.id,
        output_root=output,
        ref=ref,
        force=force,
    )
    if not result.success:
        typer.echo(f"install failed for {entry.id}: {result.error_message}", err=True)
        return 1

    resolved_commit = result.resolved_commit
    try:
        meta = generate_dataset_manifest(
            dataset_dir=dataset_dir,
            name_or_alias=entry.id,
            source_url=entry.url,
            ref=result.ref_used,
            resolved_commit=resolved_commit,
        )
    except Exception as exc:
        typer.echo(f"manifest generation failed: {exc}", err=True)
        return 1

    update_global_index(
        index_path=INDEX_DEFAULT_PATH,
        dataset_meta=meta,
        external_root=output,
    )
    typer.echo(
        f"installed {entry.id} at {dataset_dir} "
        f"(ref={result.ref_used}, commit={resolved_commit or 'unknown'})"
    )
    return 0


@datasets_app.command("install")
def install_command(
    name: str = typer.Argument(..., help="Dataset id, alias, or 'all'."),
    output: Path = typer.Option(DATASETS_DEFAULT_OUTPUT, "--output"),
    ref: str | None = typer.Option(None, "--ref", help="Override the default git ref."),
    force: bool = typer.Option(False, "--force", help="Replace an existing dataset directory."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    manifest_only: bool = typer.Option(
        False, "--manifest-only",
        help="Regenerate manifests from an existing local install without re-downloading.",
    ),
    compile_: bool = typer.Option(
        False, "--compile", help="Reserved. Compilation lives in a future plan.",
    ),
    limit: int | None = typer.Option(
        None, "--limit", help="Reserved. Will cap root files compiled in a future plan.",
    ),
    engine: str | None = typer.Option(
        None, "--engine", help="Reserved. Selects LaTeX engine in a future plan.",
    ),
) -> None:
    """Download (or refresh) one or all datasets."""

    if compile_ or limit is not None or engine is not None:
        typer.echo(NOT_IMPLEMENTED_PLAN_18_MSG)
        raise typer.Exit(code=0)

    if name == "all":
        exit_code = 0
        for entry in list_datasets():
            if entry.status is DatasetStatus.NOT_AVAILABLE:
                typer.echo(f"skipping {entry.id}: not_available")
                continue
            rc = _run_install_one(
                name=entry.id,
                output=output,
                ref=ref,
                force=force,
                dry_run=dry_run,
                manifest_only=manifest_only,
            )
            exit_code = exit_code or rc
        raise typer.Exit(code=exit_code)

    rc = _run_install_one(
        name=name,
        output=output,
        ref=ref,
        force=force,
        dry_run=dry_run,
        manifest_only=manifest_only,
    )
    raise typer.Exit(code=rc)


@datasets_app.command("status")
def status_command(
    output: Path = typer.Option(DATASETS_DEFAULT_OUTPUT, "--output"),
) -> None:
    """Report installed, missing, and not-installed datasets."""

    index_path = INDEX_DEFAULT_PATH
    payload = update_global_index(index_path=index_path, external_root=output)
    indexed_ids = {d["id"] for d in payload.get("datasets", []) if isinstance(d, dict)}
    for d in payload.get("datasets", []):
        typer.echo(
            f"{d['id']}\tstatus={d.get('status', '?')}\t"
            f"ref={d.get('ref') or '(unknown)'}\t"
            f"commit={d.get('resolved_commit') or '(unknown)'}\t"
            f"path={d.get('path') or '(unknown)'}"
        )
    for entry in list_datasets():
        if entry.id in indexed_ids:
            continue
        st = "not_available" if entry.status is DatasetStatus.NOT_AVAILABLE else "not_installed"
        typer.echo(f"{entry.id}\tstatus={st}\tref=(unknown)\tcommit=(unknown)\tpath=(unknown)")


__all__ = ["datasets_app"]
