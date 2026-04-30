from __future__ import annotations

import typer

from pdf2md.pipeline.convert import convert_pdf

app = typer.Typer(help="PDF to Markdown converter.")


@app.command()
def convert(pdf_path: str) -> None:
    """Convert a PDF to Markdown (placeholder)."""
    _ = convert_pdf  # reserved for future wiring
    typer.echo(f"Conversion pipeline not implemented yet for: {pdf_path}")


if __name__ == "__main__":
    app()
