#!/usr/bin/env python3
"""Simple GLM OCR CLI wrapper."""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="GLM OCR wrapper")
    parser.add_argument("-i", "--input", required=True, help="Input image path")
    parser.add_argument("-o", "--output", help="Output markdown path")
    args = parser.parse_args()

    cmd = ["python", "run_claude.py", args.input]
    if args.output:
        cmd += ["-o", args.output]

    print("🚀 Running:", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        print("❌ GLM OCR failed")
        sys.exit(rc)
    print("✅ GLM OCR finished")


if __name__ == "__main__":
    main()
