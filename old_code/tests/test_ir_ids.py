"""Tests for DocIR stable ID helpers."""

from doc2md.ir.ids import make_block_id, make_document_id, make_media_id, make_page_id


def test_document_id_is_deterministic() -> None:
    path = "groundtruth/test/deterministic/test1_text.pdf"
    assert make_document_id(path) == make_document_id(path)


def test_page_id_is_deterministic() -> None:
    assert make_page_id(7) == "page_0007"


def test_block_id_is_deterministic() -> None:
    a = make_block_id(1, 2, text="hello", bbox=[0.0, 1.0, 2.0, 3.0])
    b = make_block_id(1, 2, text="hello", bbox=[0.0, 1.0, 2.0, 3.0])
    c = make_block_id(1, 2, text="world", bbox=[0.0, 1.0, 2.0, 3.0])
    assert a == b
    assert a != c


def test_media_id_is_deterministic() -> None:
    assert make_media_id(3, "image", 0) == "med_0003_image_0000"
