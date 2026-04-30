#!/usr/bin/env python3
if __name__ != "__main__":
    import pytest
    pytest.skip("integration script; requires external backend dependencies", allow_module_level=True)

"""
Minimal MinerU smoke test.

What it does:
1. Creates a tiny valid PDF containing known text.
2. Runs MinerU on that PDF.
3. Searches the MinerU output directory for Markdown files.
4. Checks that the extracted Markdown contains expected keywords.

Run:

    python smoke_mineru.py

Optional:

    python smoke_mineru.py --keep
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PDF_TEXT = [
    "MinerU smoke test",
    "This document is a minimal extraction test.",
    "The purpose of this file is to verify that MinerU can read a simple PDF and produce Markdown output.",
    "Expected keywords: MinerU, smoke, extract, markdown, pipeline.",
    "If this text appears in the generated Markdown, the basic MinerU text extraction path is working.",
]

EXPECTED_KEYWORDS = [
    "MinerU",
    "smoke",
    "extract",
    "markdown",
    "pipeline",
]


def make_minimal_pdf(path: Path) -> None:
    """
    Write a simple, valid PDF without external dependencies.

    The PDF uses Helvetica and plain text drawing commands.
    This keeps the smoke test independent from reportlab or other packages.
    """

    text_stream_lines = [
        "BT",
        "/F1 16 Tf",
        "72 720 Td",
    ]

    first_line = True
    for line in PDF_TEXT:
        safe_line = (
            line.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

        if first_line:
            text_stream_lines.append(f"({safe_line}) Tj")
            first_line = False
        else:
            text_stream_lines.append("0 -28 Td")
            text_stream_lines.append(f"({safe_line}) Tj")

    text_stream_lines.append("ET")
    text_stream = "\n".join(text_stream_lines).encode("utf-8")

    objects: list[bytes] = []

    objects.append(
        b"<< /Type /Catalog /Pages 2 0 R >>"
    )

    objects.append(
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    )

    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>"
    )

    objects.append(
        b"<< /Length " + str(len(text_stream)).encode("ascii") + b" >>\n"
        b"stream\n" + text_stream + b"\nendstream"
    )

    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")

    offsets = [0]

    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)

    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        b"trailer\n"
        + f"<< /Root 1 0 R /Size {len(objects) + 1} >>\n".encode("ascii")
        + b"startxref\n"
        + f"{xref_offset}\n".encode("ascii")
        + b"%%EOF\n"
    )

    path.write_bytes(pdf)


def run_command(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command))

    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def find_markdown_files(output_dir: Path) -> list[Path]:
    return sorted(output_dir.rglob("*.md"))


def read_all_markdown(markdown_files: list[Path]) -> str:
    chunks = []

    for md_file in markdown_files:
        try:
            chunks.append(f"\n\n--- {md_file} ---\n")
            chunks.append(md_file.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            chunks.append(f"\n\n--- Could not read {md_file}: {exc} ---\n")

    return "\n".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal MinerU smoke test.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the temporary input and output directories after the test.",
    )
    parser.add_argument(
        "--backend",
        default="pipeline",
        help="MinerU backend to use. Default: pipeline.",
    )
    parser.add_argument(
        "--method",
        default="txt",
        help="MinerU parse method to use. Default: txt.",
    )

    args = parser.parse_args()

    mineru_path = shutil.which("mineru")
    if mineru_path is None:
        print("ERROR: MinerU CLI was not found on PATH.")
        print("Try activating the environment where MinerU is installed.")
        return 1

    temp_root_obj = tempfile.TemporaryDirectory(prefix="mineru_smoke_")
    temp_root = Path(temp_root_obj.name)

    input_dir = temp_root / "input"
    output_dir = temp_root / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = input_dir / "mineru_smoke.pdf"
    make_minimal_pdf(pdf_path)

    print(f"Created PDF: {pdf_path}")
    print(f"Output directory: {output_dir}")

    command = [
        mineru_path,
        "-p",
        str(pdf_path),
        "-o",
        str(output_dir),
        "-b",
        args.backend,
        "-m",
        args.method,
    ]

    result = run_command(command)

    print("\n--- MinerU output ---")
    print(result.stdout)

    if result.returncode != 0:
        print(f"ERROR: MinerU failed with exit code {result.returncode}.")
        if args.keep:
            print(f"Temporary files kept at: {temp_root}")
        else:
            temp_root_obj.cleanup()
        return result.returncode

    markdown_files = find_markdown_files(output_dir)

    if not markdown_files:
        print("ERROR: MinerU completed, but no Markdown file was found.")
        print(f"Searched recursively inside: {output_dir}")
        if args.keep:
            print(f"Temporary files kept at: {temp_root}")
        else:
            temp_root_obj.cleanup()
        return 1

    combined_markdown = read_all_markdown(markdown_files)

    missing_keywords = [
        keyword for keyword in EXPECTED_KEYWORDS
        if keyword.lower() not in combined_markdown.lower()
    ]

    print("\n--- Markdown files found ---")
    for md_file in markdown_files:
        print(md_file)

    print("\n--- Extracted Markdown preview ---")
    print(combined_markdown[:2000])

    if missing_keywords:
        print("\nERROR: MinerU produced Markdown, but some expected keywords were missing.")
        print("Missing keywords:")
        for keyword in missing_keywords:
            print(f"- {keyword}")

        if args.keep:
            print(f"Temporary files kept at: {temp_root}")
        else:
            temp_root_obj.cleanup()

        return 1

    print("\nSUCCESS: MinerU smoke test passed.")
    print("The generated Markdown contains the expected keywords.")

    if args.keep:
        print(f"Temporary files kept at: {temp_root}")
    else:
        temp_root_obj.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
