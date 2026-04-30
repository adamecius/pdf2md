#!/usr/bin/env python3
"""
MinerU CLI — Convert PDF → Markdown (pipeline backend only)
Simple, clean and ready to run.
"""

import argparse
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="MinerU CLI: Convert PDF to Markdown using pipeline backend"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to the input PDF file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to the output Markdown file (default: same folder, same name + .md)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists"
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        sys.exit(1)
    if input_path.suffix.lower() != ".pdf":
        print(f"⚠️  Warning: Input is not a .pdf file: {input_path}")

    # Default output: same folder, same name + .md
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.with_suffix(".md")

    if output_path.exists() and not args.force:
        print(f"⚠️  Output file already exists: {output_path}")
        print("   Use --force to overwrite")
        sys.exit(1)

    print(f"🚀 Converting: {input_path.name}")
    print(f"📤 Output will be saved to: {output_path}")

    # Run MinerU pipeline backend
    try:
        cmd = [
            "mineru",
            "-p", str(input_path),
            "-o", str(output_path.parent),
            "-b", "pipeline",
            "--formula-enable",
            "--table-enable"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # MinerU usually saves the .md file with the same base name
        md_file = output_path.parent / f"{input_path.stem}.md"

        if md_file.exists():
            print("✅ Conversion successful!")
            print(f"📄 Markdown saved: {md_file}")
            # Show first 15 lines as preview
            print("\n📝 Preview (first 15 lines):")
            with open(md_file, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if i > 15:
                        break
                    print(line.rstrip())
        else:
            print("⚠️  MinerU finished but .md file was not found.")
            print(result.stdout)

    except subprocess.CalledProcessError as e:
        print("❌ MinerU failed:")
        print(e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("❌ 'mineru' command not found!")
        print("   Make sure you are in the (mineru-backend) environment:")
        print("   conda activate mineru-backend")
        sys.exit(1)

if __name__ == "__main__":
    main()

