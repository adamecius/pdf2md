"""Tests for backend registry behavior."""

from doc2md.backends.base import ExtractionBackend
from doc2md.backends.deterministic import DeterministicBackend
from doc2md.backends.mineru_backend import MineruBackend
from doc2md.backends.paddleocr_vl_backend import PaddleOcrVlBackend
from doc2md.backends.registry import create_backend, get_backend, list_backends, register_backend


class _ToyBackend(ExtractionBackend):
    name = "toy"

    def available(self) -> bool:
        return True

    def extract(self, input_path, output_dir=None, options=None):
        raise NotImplementedError


def test_registry_has_deterministic_backend() -> None:
    assert "deterministic" in list_backends()
    backend = create_backend("deterministic")
    assert isinstance(backend, DeterministicBackend)


def test_registry_has_mineru_backend_factory() -> None:
    assert "mineru" in list_backends()
    backend = create_backend("mineru")
    assert isinstance(backend, MineruBackend)
def test_registry_has_paddleocr_vl_backend() -> None:
    assert "paddleocr-vl" in list_backends()
    backend = create_backend("paddleocr-vl")
    assert isinstance(backend, PaddleOcrVlBackend)


def test_register_and_lookup_backend() -> None:
    register_backend("toy", _ToyBackend)
    assert get_backend("toy") is _ToyBackend
    assert isinstance(create_backend("toy"), _ToyBackend)


def test_register_backend_rejects_duplicates() -> None:
    register_backend("dupe", _ToyBackend)
    try:
        register_backend("dupe", _ToyBackend)
        assert False, "expected ValueError for duplicate backend registration"
    except ValueError as exc:
        assert "already registered" in str(exc)
