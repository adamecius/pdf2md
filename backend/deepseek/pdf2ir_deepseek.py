#!/usr/bin/env python3
"""Canonical DeepSeek pdf2ir entrypoint.

Kept as a thin wrapper for backward compatibility with the legacy
`pdf2ir_deeepseek.py` module name.
"""

from __future__ import annotations

from pdf2ir_deeepseek import main


if __name__ == "__main__":
    main()
