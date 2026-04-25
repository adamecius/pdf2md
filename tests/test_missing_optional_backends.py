"""Optional backend stubs should fail clearly when unavailable."""

import pytest

from doc2md.backends.docling_backend import DoclingBackend
from doc2md.backends.dots_ocr_backend import DotsOcrBackend
from doc2md.backends.firered_backend import FireRedBackend
from doc2md.backends.glm_ocr_backend import GlmOcrBackend
from doc2md.backends.marker_backend import MarkerBackend
from doc2md.backends.mineru_backend import MineruBackend
from doc2md.backends.olmocr_backend import OlmOcrBackend
from doc2md.backends.paddleocr_vl_backend import PaddleOcrVlBackend


@pytest.mark.parametrize(
    "backend_cls",
    [
        DoclingBackend,
        MineruBackend,
        PaddleOcrVlBackend,
        GlmOcrBackend,
        DotsOcrBackend,
        FireRedBackend,
        MarkerBackend,
        OlmOcrBackend,
    ],
)
def test_optional_backends_raise_clear_runtime_error_when_missing(
    backend_cls,
    tmp_path,
    monkeypatch,
) -> None:
    backend = backend_cls()
    monkeypatch.setattr(backend, "available", lambda: False)

    with pytest.raises(RuntimeError) as exc_info:
        backend.extract(tmp_path / "dummy.pdf", output_dir=tmp_path)

    message = str(exc_info.value).lower()
    assert "optional" in message
    assert "offline/local experimentation" in message
