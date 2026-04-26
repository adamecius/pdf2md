"""Tests for markdown export from canonical DocIR."""

from doc2md.exporters.markdown import export_markdown
from doc2md.ir.schema import BlockIR, DocumentIR, PageIR


def _doc_fixture() -> DocumentIR:
    return DocumentIR(
        schema_version="0.1",
        document_id="doc_fixture",
        source_path="fixture.pdf",
        pages=[
            PageIR(page_id="page_0000", page_index=0, width=612, height=792),
            PageIR(page_id="page_0001", page_index=1, width=612, height=792),
        ],
        blocks=[
            BlockIR(
                block_id="blk_table",
                type="table",
                html="<table><tr><td>A</td></tr></table>",
                markdown="|A|\n|-|",
                text="A",
                page_indexes=[0],
                order=0,
            ),
            BlockIR(
                block_id="blk_equation",
                type="equation",
                latex="x^2 + y^2 = z^2",
                text="x2 + y2 = z2",
                page_indexes=[0],
                order=1,
            ),
            BlockIR(
                block_id="blk_paragraph",
                type="paragraph",
                markdown="Body text",
                page_indexes=[1],
                order=0,
            ),
            BlockIR(
                block_id="blk_skip",
                type="paragraph",
                markdown="Should be skipped",
                include_in_rag=False,
                page_indexes=[1],
                order=1,
            ),
        ],
    )


def test_markdown_export_is_deterministic() -> None:
    doc = _doc_fixture()

    first = export_markdown(doc)
    second = export_markdown(doc)

    assert first == second


def test_markdown_export_equations_tables_and_page_markers() -> None:
    output = export_markdown(_doc_fixture())

    assert "<!-- page 1 -->" in output
    assert "<!-- page 2 -->" in output
    assert "<table><tr><td>A</td></tr></table>" in output
    assert "$$ x^2 + y^2 = z^2 $$" in output
    assert "Body text" in output
    assert "Should be skipped" not in output
