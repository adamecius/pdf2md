"""Tests for DocIR JSON exporter wrappers."""

from doc2md.exporters.json_ir import read_docir, write_docir
from doc2md.ir.schema import BlockIR, DocumentIR, PageIR
from doc2md.ir.serialise import to_dict


def _doc_fixture() -> DocumentIR:
    return DocumentIR(
        schema_version="0.1",
        document_id="doc_fixture",
        source_path="fixture.pdf",
        pages=[PageIR(page_id="page_0000", page_index=0, width=612, height=792)],
        blocks=[
            BlockIR(
                block_id="blk_1",
                type="paragraph",
                text="hello",
                markdown="hello",
                page_indexes=[0],
                order=0,
            )
        ],
    )


def test_json_ir_round_trip_file(tmp_path) -> None:
    doc = _doc_fixture()
    out_file = tmp_path / "sample.docir.json"

    write_docir(doc, out_file)
    loaded = read_docir(out_file)

    assert to_dict(loaded) == to_dict(doc)
