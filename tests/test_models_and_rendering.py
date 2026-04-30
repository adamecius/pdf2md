from pdf2md.models import Block, Document, Page
from pdf2md.renderers.markdown import render_markdown


def _sample_document() -> Document:
    return Document(
        id="doc-1",
        pages=[
            Page(
                number=1,
                blocks=[
                    Block(id="b1", type="heading", text="Title", level=1, page_number=1, order=0),
                    Block(id="b2", type="paragraph", text="Intro paragraph.", page_number=1, order=1),
                    Block(id="b3", type="table", text="|a|b|\n|-|-|\n|1|2|", page_number=1, order=2),
                    Block(id="b4", type="formula", text="E = mc^2", page_number=1, order=3),
                    Block(id="b5", type="image", media_id="img-123", page_number=1, order=4),
                    Block(id="b6", type="caption", text="Figure 1: Example", page_number=1, order=5),
                ],
            )
        ],
    )


def test_document_serialization_roundtrip() -> None:
    doc = _sample_document()
    dumped = doc.model_dump_json()
    loaded = Document.model_validate_json(dumped)
    assert loaded.id == doc.id
    assert len(loaded.pages) == 1
    assert len(loaded.pages[0].blocks) == 6


def test_render_supported_block_types() -> None:
    md = render_markdown(_sample_document())
    assert "# Title" in md
    assert "Intro paragraph." in md
    assert "|a|b|" in md
    assert "$$\nE = mc^2\n$$" in md
    assert "[image:img-123]" in md
    assert "*Figure 1: Example*" in md


def test_preserves_reading_order() -> None:
    doc = Document(
        id="doc-2",
        pages=[
            Page(
                number=1,
                blocks=[
                    Block(id="b2", type="paragraph", text="Second", page_number=1, order=1),
                    Block(id="b1", type="paragraph", text="First", page_number=1, order=0),
                ],
            )
        ],
    )
    md = render_markdown(doc)
    assert md.index("First") < md.index("Second")


def test_image_placeholder_format() -> None:
    doc = Document(
        id="doc-3",
        pages=[Page(number=1, blocks=[Block(id="img-block", type="image", media_id="m-1", page_number=1, order=0)])],
    )
    md = render_markdown(doc)
    assert "[image:m-1]" in md
