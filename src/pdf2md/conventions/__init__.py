"""OCR convention extraction and per-backend block normalisation."""

from .latex_groundtruth import equation_body_key, extract_groundtruth_objects
from .normalizer import normalise_blocks

__all__ = ["equation_body_key", "extract_groundtruth_objects", "normalise_blocks"]
