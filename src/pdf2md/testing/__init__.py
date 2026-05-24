"""Test fixtures and mock-backend IR generators used by the test suite."""

from .fixtures import BATCH_002_FIXTURES, generate_batch_002
from .mock_backend_ir import build_label_map, generate_mock_backend_ir, get_detectable_references

__all__=["BATCH_002_FIXTURES", "build_label_map", "generate_batch_002", "generate_mock_backend_ir", "get_detectable_references"]
