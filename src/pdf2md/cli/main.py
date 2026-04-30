from __future__ import annotations

from pathlib import Path

import typer

from pdf2md.backends.runner import run_configured_backends
from pdf2md.config import load_backend_config
from pdf2md.pipeline.convert import convert_pdf

app = typer.Typer(help="PDF to Markdown converter.")


@app.command()
def convert(pdf_path: str) -> None:
    """Convert a PDF to Markdown (placeholder)."""
    _ = convert_pdf
    typer.echo(f"Conversion pipeline not implemented yet for: {pdf_path}")


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
