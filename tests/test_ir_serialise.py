"""Tests for DocIR serialization and normalization helpers."""

from doc2md.ir.normalise import normalise_text
from doc2md.ir.schema import BackendRun, BlockIR, DocumentIR, MediaRef, PageIR, Provenance
from doc2md.ir.serialise import from_dict, from_json, to_dict, to_json


def _sample_doc() -> DocumentIR:
    return DocumentIR(
        schema_version="0.1",
        document_id="doc_abc",
        source_path="sample.pdf",
        pages=[
            PageIR(
                page_id="page_0000",
                page_index=0,
                width=612.0,
                height=792.0,
                block_ids=["blk_0000_0000_abc"],
                strategy="deterministic",
            )
        ],
        blocks=[
            BlockIR(
                block_id="blk_0000_0000_abc",
                type="paragraph",
                role="body",
                text="Hello",
                markdown="Hello",
                page_indexes=[0],
                order=0,
                bbox=[10, 20, 100, 200],
                provenance=[
                    Provenance(
                        backend="deterministic",
                        backend_version="1.0",
                        strategy="deterministic",
                        page_index=0,
                    )
                ],
            )
        ],
        media=[
            MediaRef(
                media_id="med_0000_image_0000",
                type="image",
                path="media/p0_i0.png",
                page_index=0,
            )
        ],
        backend_runs=[
            BackendRun(
                run_id="run_1",
                backend="deterministic",
                backend_version="1.0",
                status="ok",
            )
        ],
        metadata={"title": "Sample"},
    )


def test_docir_round_trip_dict() -> None:
    doc = _sample_doc()
    data = to_dict(doc)
    restored = from_dict(data)
    assert to_dict(restored) == data


def test_docir_round_trip_json(tmp_path) -> None:
    doc = _sample_doc()
    out = tmp_path / "sample.docir.json"
    to_json(doc, out)
    loaded = from_json(out)
    assert to_dict(loaded) == to_dict(doc)


def test_normalise_text_is_stable_and_simple() -> None:
    raw = "  A\uFB01\r\nline  \r\n\r\n\r\nB\t\n"
    once = normalise_text(raw)
    twice = normalise_text(once)
    assert once == twice
    assert once == "Afi\nline\n\nB"
