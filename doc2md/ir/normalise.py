"""Compatibility wrapper for legacy UK spelling."""

from doc2md.ir.normalize import normalize_text

# Backward-compatible alias
normalise_text = normalize_text

__all__ = ["normalize_text", "normalise_text"]
