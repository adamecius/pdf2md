from __future__ import annotations

from pathlib import Path

import typer

from pdf2md.backends.runner import run_configured_backends
from pdf2md.config import load_backend_config
from pdf2md.datasets.cli import datasets_app
from pdf2md.pipeline.orchestrator import PipelineSettings, run_pipeline

app = typer.Typer(help="PDF to Markdown converter.")
app.add_typer(datasets_app, name="datasets")


@app.command()
def convert(
    pdf_path: Path = typer.Argument(..., help="Input PDF path."),
    config: Path = typer.Option(Path("pdf2md.backends.toml"), "--config", help="Backend TOML config file path."),
    out_dir: Path = typer.Option(None, "--out-dir", help="Output directory. Default: .tmp/<pdf-stem>/"),
    priors_dir: Path = typer.Option(None, "--priors-dir", help="Pre-computed calibration priors directory."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing output directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan the run; do not execute or write files."),
    timeout: int = typer.Option(None, "--timeout", help="Per-backend timeout override (seconds)."),
    keep_going: bool = typer.Option(True, "--keep-going/--no-keep-going", help="Continue past backend failures."),
    skip_export: bool = typer.Option(False, "--skip-export", help="Stop after consensus."),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging."),
) -> None:
    """Convert a PDF to consensus-derived Docling JSON, Markdown, and RAG chunks.

    Runs all enabled backends in ``--config``, joins their outputs through
    consensus and linked-structure stages, and emits final exports under
    ``--out-dir``.
    """

    resolved_out_dir = out_dir if out_dir is not None else Path(".tmp") / pdf_path.stem

    try:
        cfg = load_backend_config(config)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    settings = PipelineSettings(
        config=cfg,
        priors_dir=priors_dir,
        force=force,
        dry_run=dry_run,
        timeout=timeout,
        keep_going=keep_going,
        skip_calibration=False,
        skip_export=skip_export,
        verbose=verbose,
    )

    try:
        result = run_pipeline(pdf_path, resolved_out_dir, settings)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    if not dry_run and result.manifest_path.exists():
        try:
            typer.echo(result.manifest_path.with_name("pipeline_summary.txt").read_text(encoding="utf-8"))
        except OSError:
            typer.echo(f"manifest: {result.manifest_path}")

    if result.overall_status in ("success", "not_started"):
        raise typer.Exit(code=0)
    if result.overall_status == "partial":
        raise typer.Exit(code=2)
    raise typer.Exit(code=1)


@app.command("run-backends", help="Run configured backend wrappers into a .tmp/<run-name>/ folder.")
def run_backends(
    input_pdf: Path = typer.Argument(..., help="Input PDF path."),
    config: Path = typer.Option(Path("pdf2md.backends.toml"), "--config", help="Config file path."),
    work_dir: Path | None = typer.Option(None, "--work-dir", help="Override settings.work_dir."),
    run_name: str | None = typer.Option(None, "--run-name", help="Override safe run directory name."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing run directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan commands only; do not execute subprocesses."),
    timeout: int | None = typer.Option(None, "--timeout", help="Per-backend timeout override (seconds)."),
    keep_going: bool = typer.Option(False, "--keep-going", help="Continue if one backend fails."),
) -> None:
    """Run only configured and enabled backends from TOML config.

    No backend runs unless it appears in config and has enabled=true.
    """
    try:
        cfg = load_backend_config(config)
        rc = run_configured_backends(
            input_pdf=input_pdf,
            config=cfg,
            repo_root=Path.cwd(),
            work_dir_override=work_dir,
            run_name_override=run_name,
            force=force,
            dry_run=dry_run,
            timeout_override=timeout,
            keep_going=keep_going,
        )
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    raise typer.Exit(code=rc)


if __name__ == "__main__":
    app()
