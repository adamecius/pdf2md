#!/usr/bin/env python3
"""
MinerU PDF → Markdown + JSON Converter
Supports single PDF or directory of PDFs.
Outputs: .md (formatted Markdown) + structured JSON files.
"""

import asyncio
import argparse
from pathlib import Path

from mineru.cli import api_client as _api_client
from mineru.cli.common import image_suffixes, office_suffixes, pdf_suffixes
from mineru.utils.guess_suffix_or_lang import guess_suffix_by_path


SUPPORTED_SUFFIXES = set(pdf_suffixes + image_suffixes + office_suffixes)


def collect_files(input_path: str | Path) -> list[Path]:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")

    if path.is_file():
        if guess_suffix_by_path(path) not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file: {path.name}")
        return [path]

    if path.is_dir():
        files = sorted(
            (p.resolve() for p in path.iterdir()
             if p.is_file() and guess_suffix_by_path(p) in SUPPORTED_SUFFIXES),
            key=lambda x: x.name
        )
        if not files:
            raise ValueError(f"No supported files in directory: {path}")
        return files

    raise ValueError(f"Input must be file or directory: {path}")


async def convert_with_mineru(
    input_path: str | Path,
    output_dir: str | Path,
    backend: str = "hybrid-auto-engine",  # Best quality: hybrid-auto-engine, pipeline (CPU), vlm-auto-engine
    language: str = "en",                 # "ch", "en", or auto-detect
    formula: bool = True,
    table: bool = True,
    start_page: int = 0,
    end_page: int | None = None,
    api_url: str | None = None,           # None = start local temporary API
) -> None:
    input_files = collect_files(input_path)
    out_path = Path(output_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    # Build request (return_md + content_list + middle JSON for rich structured output)
    form_data = _api_client.build_parse_request_form_data(
        lang_list=[language],
        backend=backend,
        parse_method="auto",
        formula_enable=formula,
        table_enable=table,
        start_page_id=start_page,
        end_page_id=end_page,
        return_md=True,
        return_content_list=True,   # content_list.json (flat readable blocks)
        return_middle_json=True,    # middle.json (full structured data)
        return_model_output=False,
        return_images=True,
        response_format_zip=True,
        return_original_file=False,
    )

    upload_assets = [
        _api_client.UploadAsset(path=f, upload_name=f.name)
        for f in input_files
    ]

    async with _api_client.get_http_client() as client:
        local_server = None
        try:
            if api_url is None:
                local_server = _api_client.LocalAPIServer()
                base_url = local_server.start()
                await _api_client.wait_for_local_api_ready(client, local_server)
            else:
                base_url = api_url

            print(f"🚀 Processing {len(input_files)} file(s) with backend={backend}")
            submit_resp = await _api_client.submit_parse_task(
                base_url=base_url, upload_assets=upload_assets, form_data=form_data
            )

            await _api_client.wait_for_task_result(
                client=client, submit_response=submit_resp, task_label=f"{len(input_files)} files"
            )

            zip_path = await _api_client.download_result_zip(
                client=client, submit_response=submit_resp
            )

            _api_client.safe_extract_zip(zip_path, out_path)
            zip_path.unlink(missing_ok=True)

            print(f"✅ Conversion complete! Outputs saved to: {out_path}")
            print("   Key files per document:")
            print("   • *.md          → Formatted Markdown (with LaTeX tables/images)")
            print("   • *_content_list.json → Flat structured JSON (easy to use)")
            print("   • *_middle.json → Full hierarchical parsing data")

        finally:
            if local_server:
                local_server.stop()


def main():
    parser = argparse.ArgumentParser(description="MinerU PDF → Markdown + JSON")
    parser.add_argument("-i", "--input", required=True, help="PDF file or directory")
    parser.add_argument("-o", "--output", default="mineru_output", help="Output directory")
    parser.add_argument("-b", "--backend", default="hybrid-auto-engine",
                        choices=["hybrid-auto-engine", "pipeline", "vlm-auto-engine"],
                        help="Parsing backend")
    parser.add_argument("-l", "--lang", default="en", help="Language hint (en/ch)")
    parser.add_argument("--no-formula", action="store_true", help="Disable formula parsing")
    parser.add_argument("--no-table", action="store_true", help="Disable table parsing")
    parser.add_argument("--api-url", default=None, help="Existing MinerU API URL (optional)")

    args = parser.parse_args()

    asyncio.run(convert_with_mineru(
        input_path=args.input,
        output_dir=args.output,
        backend=args.backend,
        language=args.lang,
        formula=not args.no_formula,
        table=not args.no_table,
        api_url=args.api_url,
    ))


if __name__ == "__main__":
    main()