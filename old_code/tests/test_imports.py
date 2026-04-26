"""Basic import smoke tests for package layout."""

from doc2md.cli import main
from doc2md.profiler import profile_document
from doc2md.router import route_document
from doc2md.strategies.deterministic import DeterministicStrategy


def test_imports_smoke() -> None:
    assert callable(main)
    assert callable(profile_document)
    assert callable(route_document)
    assert DeterministicStrategy.__name__ == "DeterministicStrategy"
